package io.github.mhd6271.tvzapper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Programminfo beim Umschalten: bei jedem Senderwechsel (auch von Hand, auch ohne laufenden Zapper) unten links
 *  Sender, laufende Sendung, Uhrzeit und Restzeit einblenden. Hintergrund: die Info-Leiste des Fernsehers zeigt
 *  die Sendung nicht immer aktuell an (Wunsch Max, 18.11.2026).
 *  Eigener kleiner Dienst, damit er unabhaengig vom Zapper laeuft; gestartet aus der App und bei jeder Abfrage von
 *  Home Assistant (ABFRAGEN alle 15 s), falls Android ihn beendet hat. */
public class SenderInfo extends Service {
    private static final String CHANNEL = "programminfo";
    private static final long TAKT_MS = 1000, ANZEIGE_MS = 7000;
    static volatile boolean laeuft;

    private HandlerThread thread;
    private Handler handler;
    private long lastChannel;
    private static final Handler main = new Handler(Looper.getMainLooper());
    private static View sichtbar;

    /** Dienst starten, wenn eingeschaltet und noch nicht da; ausschalten, wenn die Einstellung aus ist. */
    static void sicherstellen(Context c) {
        try {
            boolean an = Config.load(c).programInfo;
            if (an && !laeuft) c.startForegroundService(new Intent(c, SenderInfo.class));
            else if (!an && laeuft) c.stopService(new Intent(c, SenderInfo.class));
        } catch (Exception e) {
            Log.add(c, "Programminfo: Dienst nicht startbar: " + e);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        laeuft = true;
        thread = new HandlerThread("programminfo");
        thread.start();
        handler = new Handler(thread.getLooper());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // KOMPAT: wie ZapperService: Typ SPECIAL_USE erst ab API 34; am TCL verweigert TclAppBoot den Vordergrund-Status
        //   beim Start von aussen (Broadcast), der Dienst laeuft dann ungeschuetzt weiter (beim Zapper so beobachtet).
        if (android.os.Build.VERSION.SDK_INT >= 34)
            startForeground(2, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(2, notification());
        handler.removeCallbacksAndMessages(null);
        handler.post(this::tick);
        return START_STICKY;
    }

    private void tick() {
        try {
            pruefen();
        } catch (Exception e) {
            android.util.Log.w("TVZapper", "Programminfo: " + e);
        }
        handler.postDelayed(this::tick, TAKT_MS);
    }

    /** Wie das Maskottchen in ZapperService.onSwitch: nur echte Wechsel; Rueckkehr aus einer anderen App zum selben
     *  Sender zaehlt nicht (TCL meldet -1, solange das Fernsehbild nicht vorn ist). */
    private void pruefen() {
        long cur = Epg.currentChannelId(this);
        if (cur <= 0) return;
        if (lastChannel > 0 && cur != lastChannel && getSystemService(PowerManager.class).isInteractive()
                && Config.load(this).programInfo)
            zeigen(this, text(this, cur));
        lastChannel = cur;
    }

    static String text(Context c, long channelId) {
        Epg.Channel ch = Umschaltungen.channel(c, channelId);
        String kopf = ch == null ? "Sender " + channelId : (ch.number + " " + ch.name).trim();
        Epg.Program p = Epg.current(c, channelId);
        if (p == null || p.title.isEmpty()) return kopf + "\nkeine Programmdaten";
        SimpleDateFormat hm = new SimpleDateFormat("HH:mm", Locale.GERMANY);
        long rest = Math.max(0, (p.end - System.currentTimeMillis() + 59_999) / 60_000);
        return kopf + "\n" + p.title + (p.episode.isEmpty() ? "" : " – " + p.episode)
                + "\n" + hm.format(new Date(p.start)) + "–" + hm.format(new Date(p.end)) + ", noch " + rest + " min";
    }

    /** Eine Einblendung unten links; ein neuer Wechsel ersetzt die alte (schnelles Durchzappen stapelt nicht). */
    static void zeigen(Context ctx, String text) {
        Context c = ctx.getApplicationContext();
        if (!Settings.canDrawOverlays(c)) return;   // Hinweis darauf schreibt schon Banner ins Protokoll
        main.post(() -> {
            WindowManager wm = c.getSystemService(WindowManager.class);
            if (sichtbar != null) {
                try {
                    wm.removeView(sichtbar);
                } catch (Exception ignored) {
                }
                sichtbar = null;
            }
            float d = c.getResources().getDisplayMetrics().density;
            TextView v = new TextView(c);
            v.setText(text);
            v.setTextSize(20);
            v.setMaxWidth((int) (c.getResources().getDisplayMetrics().widthPixels * 0.55));
            v.setTextColor(Color.WHITE);
            v.setPadding((int) (22 * d), (int) (12 * d), (int) (22 * d), (int) (12 * d));
            GradientDrawable bg = new GradientDrawable();   // Farben wie Banner
            bg.setColor(Color.argb(220, 0x1B, 0x2A, 0x49));
            bg.setStroke((int) (2 * d), Color.rgb(0xF2, 0xB1, 0x34));
            bg.setCornerRadius(12 * d);
            v.setBackground(bg);
            // KOMPAT: Overlay ueber dem Tuner-Bild wie Banner (am TCL sichtbar); unten statt oben, damit es nicht mit
            //   Banner-Meldungen (Umschaltgrund, Home Assistant) zusammenfaellt.
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                    WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                    PixelFormat.TRANSLUCENT);
            lp.gravity = Gravity.BOTTOM | Gravity.START;
            lp.x = (int) (40 * d);
            lp.y = (int) (40 * d);
            try {
                wm.addView(v, lp);
                sichtbar = v;
                main.postDelayed(() -> {
                    if (sichtbar != v) return;
                    try {
                        wm.removeView(v);
                    } catch (Exception ignored) {
                    }
                    sichtbar = null;
                }, ANZEIGE_MS);
            } catch (Exception e) {
                Log.add(c, "Programminfo fehlgeschlagen: " + e.getMessage());
            }
        });
    }

    private Notification notification() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Programminfo beim Umschalten",
                NotificationManager.IMPORTANCE_MIN));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.icon)
                .setContentTitle("TV-Zapper")
                .setContentText("Programminfo beim Umschalten")
                .setContentIntent(open)
                .setOngoing(true)
                .build();
    }

    @Override
    public void onDestroy() {
        laeuft = false;
        handler.removeCallbacksAndMessages(null);
        thread.quitSafely();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
