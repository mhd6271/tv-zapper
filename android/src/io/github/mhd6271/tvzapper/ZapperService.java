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
    /** Maskottchen nach dem Start zeigen – nur beim Start aus der App, nicht bei STARTEN von aussen (z. B. nach Updates) */
    static final String EXTRA_GREET = "gruessen";
    private static final String CHANNEL = "lauf";
    private static final String RUN_PREFS = "lauf";

    /** Ende des laufenden Durchgangs (ms) fuer die Anzeige, 0 = steht. */
    static volatile long endAt = 0;
    static volatile long nextAt = 0;

    private HandlerThread thread;
    private Handler handler;
    private PowerManager.WakeLock wake;
    private boolean once, readOnly;
    /** Maskottchen als Erinnerung nach je einer Stunde Fernsehen (gezaehlt nur, solange das Fernsehbild vorn ist) */
    private static final long ERINNERUNG_MS = 60 * 60_000L;
    private long watchedMs, lastWatchTick;
    /** Zuletzt gesehener Sender: bei jedem Wechsel flitzt das kleine Maskottchen einmal oben durchs Bild */
    private long lastChannel;
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
        // intent == null: Android startet den Dienst neu, nachdem es ihn beendet hat (z. B. Speichermangel)
        long savedEnd = getSharedPreferences(RUN_PREFS, MODE_PRIVATE).getLong("ende", 0);
        boolean resume = intent == null && savedEnd > System.currentTimeMillis();
        String action = resume ? ACTION_START
                : intent != null && intent.getAction() != null ? intent.getAction() : ACTION_STOP;
        if (ACTION_STOP.equals(action)) {
            if (intent != null) Log.add(this, "Gestoppt");
            saveRun(0, false);
            stopSelf();
            return START_NOT_STICKY;
        }
        // KOMPAT: startForeground mit Typ gibt es erst ab API 29 (Android 8/9: NoSuchMethodError, Dienst stuerzt);
        //   der Typ SPECIAL_USE erst ab 34 – auf 29 bis 33 ungeprueft.
        startForeground(1, notification("Läuft"), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        handler.removeCallbacksAndMessages(null);
        once = ACTION_ONCE.equals(action);
        if (!once && waechter == null) startWaechter();
        readOnly = resume ? getSharedPreferences(RUN_PREFS, MODE_PRIVATE).getBoolean("nurLesen", false)
                : intent.getBooleanExtra(EXTRA_READ_ONLY, false);
        Config cfg = Config.load(this);
        endAt = resume ? savedEnd : once ? System.currentTimeMillis()
                : cfg.runMin <= 0 ? Long.MAX_VALUE : System.currentTimeMillis() + cfg.runMin * 60_000L;
        saveRun(once ? 0 : endAt, readOnly);
        if (!once) {
            if (resume) Log.add(this, "Von Android beendet und neu gestartet – Zapper läuft weiter");
            else Log.add(this, "Start: " + (cfg.runMin <= 0 ? "ohne Ende" : cfg.runMin + " min Laufzeit") + ", alle " + cfg.dwellMin + " min prüfen; Fernseher: Eingang "
                    + Epg.tunerInput(this) + ", App " + Epg.tvPackage(this));
            PowerManager pm = getSystemService(PowerManager.class);
            if (wake != null && wake.isHeld()) wake.release();
            wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tvzapper:lauf");
            wake.acquire(endAt == Long.MAX_VALUE ? 24 * 3600_000L : endAt - System.currentTimeMillis() + 60_000L);
        }
        if (!once && !resume && intent.getBooleanExtra(EXTRA_GREET, false)) greet(0);
        // Beim Start aus der App heraus ist sie selbst noch vorn – kurz warten, bis das Fernsehbild zurueck ist
        handler.postDelayed(this::tick, once ? 0 : 5000);
        // Laufender Zapper: nach einem Beenden durch Android von selbst wieder anlaufen
        return once ? START_NOT_STICKY : START_STICKY;
    }

    /** Laufendes Ende merken, damit ein Neustart durch Android weitermachen kann; 0 = laeuft nicht. */
    private void saveRun(long end, boolean ro) {
        getSharedPreferences(RUN_PREFS, MODE_PRIVATE).edit().putLong("ende", end).putBoolean("nurLesen", ro).commit();
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
                remind();
                onSwitch();
                adHandler.postDelayed(this, 2500);
            }
        });
    }

    private void remind() {
        long now = System.currentTimeMillis();
        long step = lastWatchTick == 0 ? 0 : Math.min(now - lastWatchTick, 10_000);   // Pausen des Threads nicht mitzaehlen
        lastWatchTick = now;
        String tv = Epg.tvPackage(this);
        if (!getSystemService(PowerManager.class).isInteractive() || tv == null || !tv.equals(foregroundApp(this))) return;
        watchedMs += step;
        if (watchedMs >= ERINNERUNG_MS) {
            watchedMs = 0;
            Maskottchen.show(this);
        }
    }

    /** Senderwechsel bemerken (auch von Hand mit der Fernbedienung) und das kleine Maskottchen flitzen lassen.
     *  Nur alle 2,5 s geprueft: Wer schnell durchzappt, sieht es nur auf dem Sender, auf dem er kurz bleibt. */
    private void onSwitch() {
        long cur = Epg.currentChannelId(this);
        if (cur <= 0) {   // Fernsehbild nicht vorn: alten Sender merken, Rueckkehr zum selben Sender zaehlt nicht
            guardKidsInput();
            return;
        }
        kidsNoChannel = 0;
        if (guardKids(cur)) return;
        if (lastChannel > 0 && cur != lastChannel && getSystemService(PowerManager.class).isInteractive()) {
            boolean back = isBack(lastChannel, cur);
            android.util.Log.i("TVZapper", "Senderwechsel " + lastChannel + " -> " + cur + ": Maskottchen nach "
                    + (back ? "rechts" : "links"));   // nur logcat, nicht ins App-Log (sonst jeder Wechsel)
            Maskottchen.flitzen(this, back);
        }
        lastChannel = cur;
    }

    private long kidsNoneLogged;
    private int kidsNoChannel;

    /** Kinder-Modus: Fernseh-App vorn, aber kein Sender (TCL meldet -1) = anderer Eingang wie HDMI, z. B. nach
     *  "Programm runter" auf dem ersten Sender (am Geraet 29.10.2026: Sender 1 -> HDMI 4). Erst beim zweiten Mal in
     *  Folge (5 s) wegschalten, damit kurze Luecken beim Umschalten nicht zaehlen. */
    private void guardKidsInput() {
        String tv = Epg.tvPackage(this);
        if (!Config.load(this).kids || tv == null || !tv.equals(foregroundApp(this))
                || !getSystemService(PowerManager.class).isInteractive()) {
            kidsNoChannel = 0;
            return;
        }
        if (++kidsNoChannel < 2) return;
        kidsNoChannel = 0;
        guardKids(-1);
    }

    /** Kinder-Modus: laeuft ein nicht erlaubter Sender oder eine Sendung mit Sperrbegriff, sofort auf einen zufaelligen
     *  erlaubten Sender schalten – auch in "nur lesen" und nach Umschalten von Hand. true = weggeschaltet. */
    private boolean guardKids(long cur) {
        Config cfg = Config.load(this);
        if (!cfg.kids || !getSystemService(PowerManager.class).isInteractive()) return false;
        Epg.Channel ch = Umschaltungen.channel(this, cur);
        String why = cur <= 0 ? "anderer Eingang statt Fernsehsender" : Kinder.verbot(this, cfg, ch);
        if (why == null) return false;
        Epg.Channel to = Kinder.ersatz(this, cfg, cur);
        if (to == null) {
            if (System.currentTimeMillis() - kidsNoneLogged > 60_000) {
                kidsNoneLogged = System.currentTimeMillis();
                Log.add(this, "Kinder-Modus: " + why + ", aber kein erlaubter Sender ohne Sperrbegriff da – bleibe");
                Banner.show(this, "Kinder-Modus: keine erlaubten Sender eingestellt", 6000);
            }
            return false;
        }
        Log.add(this, "Kinder-Modus: " + why + " – schalte weg auf " + to.number + " " + to.name);
        Epg.Program p = Epg.current(this, to.id);
        if (tuneTo(to, "Kinder-Modus: " + why + " – jetzt " + to.name + (p == null ? "" : ": " + p.title),
                Umschaltungen.KINDER)) lastChannel = to.id;
        return true;
    }

    /** Zurueckgeschaltet? Nach der Stelle in der Senderliste (wie die Programm-Tasten der Fernbedienung); ein Sprung
     *  ueber mehr als die halbe Liste gilt als Ueberlauf (vom letzten auf den ersten Sender = vorwaerts). */
    private boolean isBack(long from, long to) {
        List<Long> ids = new ArrayList<>();
        List<Epg.Channel> all = new ArrayList<>(Epg.channels(this));
        all.sort((a, b) -> Long.compare(Epg.num(a.number), Epg.num(b.number)));
        for (Epg.Channel ch : all) if (ch.browsable || ch.id == from || ch.id == to) ids.add(ch.id);
        int i = ids.indexOf(from), j = ids.indexOf(to), n = ids.size();
        if (i < 0 || j < 0) return false;
        int step = j - i;
        if (step > n / 2) step -= n;
        else if (step < -n / 2) step += n;
        return step < 0;
    }

    /** Maskottchen gruessen lassen, sobald das Fernsehbild vorn ist (hoechstens 15 s warten). */
    private void greet(int tries) {
        new Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
            String tv = Epg.tvPackage(this);
            if (tv != null && tv.equals(foregroundApp(this))) Maskottchen.show(this);
            else if (tries < 5) greet(tries + 1);
        }, 3000);
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
            saveRun(0, false);
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
        String tvApp = Epg.tvPackage(this);
        // KOMPAT: Ohne Nutzungszugriff (fg null) oder ohne erkannte TV-App schaltet der Zapper nie. Ob isInteractive()
        //   bei TVs mit "Bildschirm aus, Ton an" false liefert, ist herstellerabhaengig.
        if (!readOnly && (!screenOn || tvApp == null || !tvApp.equals(fg))) {
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
        if (cfg.kids) {   // Kinder-Modus: nur erlaubte Sender ohne Sperrbegriff, egal ob an/aus
            for (Epg.Channel ch : all) if (Config.BEVORZUGT.equals(cfg.state(ch)) && Kinder.ok(this, cfg, ch)) order.add(ch);
            for (Epg.Channel ch : all) if (!Config.BEVORZUGT.equals(cfg.state(ch)) && Kinder.ok(this, cfg, ch)) order.add(ch);
        } else {
            for (Epg.Channel ch : all) if (Config.BEVORZUGT.equals(cfg.state(ch))) order.add(ch);
            for (Epg.Channel ch : all) if (Config.AN.equals(cfg.state(ch))) order.add(ch);
        }
        List<Scored> scored = new ArrayList<>();
        Scored cur = null, best = null;
        int withProg = 0;
        List<String> skippedAd = new ArrayList<>();
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
            if (ch.id != curId && WerbeWaechter.inAd(ch.name)) {
                skippedAd.add(ch.name);
                continue;   // dort laeuft gerade Werbung – nicht hineinschalten
            }
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
        if (!skippedAd.isEmpty()) Log.add(this, "Gerade Werbung, deshalb gemieden: " + String.join(", ", skippedAd));
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
        if (tuneTo(s.ch, s.ch.name + (s.prog == null ? "" : " – " + s.prog.title) + "  (" + what + s.points
                + (s.points == 1 ? " Punkt)" : " Punkte)"), Umschaltungen.INTERESSE))
            updateNotification(s.ch.number + " " + s.ch.name + (s.prog == null ? "" : ": " + s.prog.title));
    }

    /** Auf einen Sender schalten, pruefen, ob der Fernseher ihn meldet, Einblendung zeigen. */
    synchronized boolean tuneTo(Epg.Channel ch, String banner, String reason) {
        Config kc = Config.load(this);
        String no = kc.kids ? Kinder.verbot(this, kc, ch) : null;
        if (no != null) {   // letzte Sperre fuer Zapper-Runde, Werbe-Sensor und Rueckkehr nach der Werbung
            Log.add(this, "Kinder-Modus: nicht umgeschaltet (" + reason + "), " + no);
            return false;
        }
        Epg.Channel from = Umschaltungen.channel(this, Epg.currentChannelId(this));
        Intent i = new Intent(Intent.ACTION_VIEW, TvContract.buildChannelUri(ch.id));
        String tvApp = Epg.tvPackage(this);
        if (tvApp != null) i.setPackage(tvApp);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            // KOMPAT: Aktivitaet aus dem Hintergrund starten geht seit Android 10 nur dank SYSTEM_ALERT_WINDOW; ob kuenftige
            //   Versionen (15+) oder Hersteller das weiter einschraenken, ist ungeprueft.
            startActivity(i);
        } catch (Exception e) {
            Log.add(this, "Umschalten fehlgeschlagen: " + e.getMessage());
            return false;
        }
        Epg.lastTuned = ch.id;
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
        org.json.JSONObject e = Umschaltungen.add(this, reason, from, ch, banner, ok);
        if (ok) {
            if (Config.load(this).showReason) Banner.show(this, Umschaltungen.explain(e), 12000);
            else Banner.show(this, banner, 6000);
        }
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
            // KOMPAT: ACTIVITY_RESUMED (API 29) hat denselben Wert 1 wie das alte MOVE_TO_FOREGROUND und wird eingebaut – geht
            //   auch darunter. Zeigt die TV-App das Bild ueber ein anderes Paket (Bild-in-Bild, Eingangsdienst), passt der Vergleich nicht.
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
