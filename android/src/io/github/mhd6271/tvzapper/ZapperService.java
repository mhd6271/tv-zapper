package io.github.mhd6271.tvzapper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.tv.TvContract;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;

import java.util.ArrayList;
import java.util.List;

/** Dauerlauf: alle verweilen_min Minuten die laufenden Sendungen bewerten und auf den besten Treffer umschalten,
 *  bis die Laufzeit um ist. Laeuft als Vordergrund-Dienst, damit Android ihn nicht beendet. */
public class ZapperService extends Service {
    static final String ACTION_START = "start", ACTION_ONCE = "once", ACTION_STOP = "stop";
    static final String EXTRA_READ_ONLY = "nurLesen";
    static final String TV_PKG = "com.tcl.tv";
    private static final String CHANNEL = "lauf";

    /** Ende des laufenden Durchgangs (ms) fuer die Anzeige, 0 = steht. */
    static volatile long endAt = 0;
    static volatile long nextAt = 0;

    private HandlerThread thread;
    private Handler handler;
    private PowerManager.WakeLock wake;
    private boolean once, readOnly;
    private HandlerThread adThread;
    private Handler adHandler;
    static volatile WerbeWaechter waechter;

    @Override
    public void onCreate() {
        super.onCreate();
        thread = new HandlerThread("zapper");
        thread.start();
        handler = new Handler(thread.getLooper());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null && intent.getAction() != null ? intent.getAction() : ACTION_STOP;
        if (ACTION_STOP.equals(action)) {
            Log.add(this, "Gestoppt");
            stopSelf();
            return START_NOT_STICKY;
        }
        startForeground(1, notification("Läuft"), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        handler.removeCallbacksAndMessages(null);
        once = ACTION_ONCE.equals(action);
        if (!once && waechter == null) startWaechter();
        readOnly = intent.getBooleanExtra(EXTRA_READ_ONLY, false);
        Config cfg = Config.load(this);
        endAt = once ? System.currentTimeMillis() : System.currentTimeMillis() + cfg.runMin * 60_000L;
        if (!once) {
            Log.add(this, "Start: " + cfg.runMin + " min Laufzeit, alle " + cfg.dwellMin + " min prüfen");
            PowerManager pm = getSystemService(PowerManager.class);
            wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tvzapper:lauf");
            wake.acquire(cfg.runMin * 60_000L + 60_000L);
        }
        // Beim Start aus der App heraus ist sie selbst noch vorn – kurz warten, bis das Fernsehbild zurueck ist
        handler.postDelayed(this::tick, once ? 0 : 5000);
        return START_NOT_STICKY;
    }

    private void startWaechter() {
        waechter = new WerbeWaechter(this);
        adThread = new HandlerThread("werbung");
        adThread.start();
        adHandler = new Handler(adThread.getLooper());
        adHandler.post(new Runnable() {
            @Override
            public void run() {
                WerbeWaechter w = waechter;
                if (w == null) return;
                try {
                    if (Config.load(ZapperService.this).avoidAds) w.tick();
                    else w.shutdown();
                } catch (Exception e) {
                    Log.add(ZapperService.this, "Werbe-Sensor Fehler: " + e);
                }
                adHandler.postDelayed(this, 2500);
            }
        });
    }

    private void tick() {
        try {
            if (once) Epg.diagnose(this);
            cycle(readOnly);
        } catch (Exception e) {
            Log.add(this, "Fehler: " + e);
        }
        Config cfg = Config.load(this);
        long next = System.currentTimeMillis() + Math.max(1, cfg.dwellMin) * 60_000L;
        if (once || next > endAt) {
            if (!once) Log.add(this, "Laufzeit um – Ende");
            stopSelf();
            return;
        }
        nextAt = next;
        handler.postDelayed(this::tick, next - System.currentTimeMillis());
    }

    static final class Scored {
        Epg.Channel ch;
        Epg.Program prog;
        Scorer.Result res;
        int points;
        boolean preferred;
    }

    void cycle(boolean readOnly) {
        Config cfg = Config.load(this);
        WerbeWaechter w = waechter;
        if (!readOnly && w != null && w.isAway()) {
            Log.add(this, "Werbepause läuft – Zapper wartet");
            return;
        }
        String fg = foregroundApp(this);
        boolean screenOn = getSystemService(PowerManager.class).isInteractive();
        if (!readOnly && (!screenOn || !TV_PKG.equals(fg))) {
            Log.add(this, "Fernseher zeigt gerade etwas anderes (" + (screenOn ? (fg == null ? "unbekannt – Nutzungszugriff erlaubt?" : fg)
                    : "Bildschirm aus") + ") – lasse ihn in Ruhe");
            return;
        }
        List<Epg.Channel> all = Epg.channels(this);
        if (all.isEmpty()) {
            Log.add(this, "Keine Sender lesbar – fehlt die Berechtigung „Fernsehprogramm lesen“?");
            return;
        }
        long curId = Epg.currentChannelId(this);
        // Bevorzugte Sender zuerst, dann die uebrigen eingeschalteten
        List<Epg.Channel> order = new ArrayList<>();
        for (Epg.Channel ch : all) if (Config.BEVORZUGT.equals(cfg.state(ch))) order.add(ch);
        for (Epg.Channel ch : all) if (Config.AN.equals(cfg.state(ch))) order.add(ch);
        List<Scored> scored = new ArrayList<>();
        Scored cur = null, best = null;
        int withProg = 0;
        for (Epg.Channel ch : order) {
            Scored s = new Scored();
            s.ch = ch;
            s.prog = Epg.current(this, ch.id);
            if (s.prog != null) withProg++;
            s.res = Scorer.score(ch.name + " " + (s.prog == null ? "" : s.prog.text()), cfg);
            s.preferred = Config.BEVORZUGT.equals(cfg.state(ch));
            s.points = s.res.points + (s.preferred && s.res.points > 0 ? cfg.bonusFor(ch.name) : 0);
            scored.add(s);
            if (ch.id == curId) cur = s;
            if (best == null || s.points > best.points) best = s;
        }
        if (cur == null) {
            for (Epg.Channel ch : all) {
                if (ch.id != curId) continue;
                cur = new Scored();
                cur.ch = ch;
                cur.prog = Epg.current(this, ch.id);
                cur.res = Scorer.score(ch.name + " " + (cur.prog == null ? "" : cur.prog.text()), cfg);
                cur.points = cur.res.points;
            }
        }
        int curPoints = cur == null ? 0 : cur.points;
        Log.add(this, order.size() + " Sender geprüft (" + withProg + " mit Sendung), läuft: "
                + (cur == null ? "unbekannt (" + curId + ")" : describe(cur)));
        scored.sort((a, b) -> b.points - a.points);
        for (int i = 0; i < Math.min(5, scored.size()); i++) {
            if (scored.get(i).points > 0) Log.add(this, "   " + describe(scored.get(i)));
        }
        if (best != null && best.points > 0 && best.points > curPoints && (cur == null || best.ch.id != cur.ch.id)) {
            if (readOnly) {
                Log.add(this, "→ würde umschalten auf " + best.ch.number + " " + best.ch.name);
            } else {
                tune(best);
            }
        } else {
            Log.add(this, "→ bleibt" + (best != null && best.points > 0 ? "" : " (nichts Passendes gefunden)"));
        }
    }

    private void tune(Scored s) {
        String what = s.res.hits.isEmpty() ? "" : String.join(", ", s.res.hits) + ", ";
        if (tuneTo(s.ch, s.ch.name + (s.prog == null ? "" : " – " + s.prog.title) + "  (" + what + s.points + " P.)"))
            updateNotification(s.ch.number + " " + s.ch.name + (s.prog == null ? "" : ": " + s.prog.title));
    }

    /** Auf einen Sender schalten, pruefen, ob der Fernseher ihn meldet, Einblendung zeigen. */
    synchronized boolean tuneTo(Epg.Channel ch, String banner) {
        Intent i = new Intent(Intent.ACTION_VIEW, TvContract.buildChannelUri(ch.id));
        i.setPackage(TV_PKG);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(i);
        } catch (Exception e) {
            Log.add(this, "Umschalten fehlgeschlagen: " + e.getMessage());
            return false;
        }
        boolean ok = false;
        for (int k = 0; k < 8 && !ok; k++) {
            try {
                Thread.sleep(500);
            } catch (InterruptedException ignored) {
            }
            ok = Epg.currentChannelId(this) == ch.id;
        }
        Log.add(this, (ok ? "→ umgeschaltet auf " : "→ Umschalten auf ") + ch.number + " " + ch.name
                + (ok ? "" : " nicht bestätigt (Fernseher meldet " + Epg.currentChannelId(this) + ")"));
        if (ok) Banner.show(this, banner, 6000);
        return ok;
    }

    static String describe(Scored s) {
        StringBuilder b = new StringBuilder();
        b.append(s.points).append(" P. ").append(s.ch.number).append(' ').append(s.ch.name);
        if (s.prog != null) b.append(": ").append(s.prog.title);
        if (s.res != null && !s.res.hits.isEmpty()) b.append("  [").append(String.join(", ", s.res.hits)).append(']');
        if (s.preferred) b.append(" ★");
        return b.toString();
    }

    private static long fgQueried;
    private static String fgLast;

    /** Paket der zuletzt nach vorn gekommenen App (Nutzungszugriff noetig), null wenn unbekannt.
     *  Liest nur die Ereignisse seit der letzten Abfrage (wird alle paar Sekunden gefragt). */
    static synchronized String foregroundApp(Context c) {
        UsageStatsManager um = c.getSystemService(UsageStatsManager.class);
        long now = System.currentTimeMillis();
        long from = fgQueried == 0 ? now - 7 * 24 * 3600_000L : fgQueried - 2000;
        UsageEvents ev = um.queryEvents(from, now);
        UsageEvents.Event e = new UsageEvents.Event();
        while (ev != null && ev.hasNextEvent()) {
            ev.getNextEvent(e);
            if (e.getEventType() == UsageEvents.Event.ACTIVITY_RESUMED) fgLast = e.getPackageName();
        }
        fgQueried = now;
        return fgLast;
    }

    private Notification notification(String text) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "TV-Zapper läuft",
                NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.icon)
                .setContentTitle("TV-Zapper")
                .setContentText(text)
                .setContentIntent(open)
                .setOngoing(true)
                .build();
    }

    private void updateNotification(String text) {
        getSystemService(NotificationManager.class).notify(1, notification(text));
    }

    @Override
    public void onDestroy() {
        WerbeWaechter w = waechter;
        waechter = null;
        if (w != null) w.shutdown();
        if (adThread != null) adThread.quitSafely();
        endAt = 0;
        nextAt = 0;
        handler.removeCallbacksAndMessages(null);
        thread.quitSafely();
        if (wake != null && wake.isHeld()) wake.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
