package io.github.mhd6271.tvzapper;

import android.content.Context;
import android.os.PowerManager;

import java.util.ArrayDeque;
import java.util.List;

/** Werbung umgehen: beobachtet den eigentlich gewaehlten Sender ("Hauptsender") ueber die FRITZ!Box.
 *  Verschwindet sein Logo (Werbung), schaltet der Fernseher auf den besten werbefreien Ausweichsender;
 *  ist das Logo wieder da, zurueck. Schaltet jemand selbst um, wird der neue Sender der Hauptsender. */
final class WerbeWaechter implements Sensor.Frames {
    /** Entscheidung wie am Mac gemessen: Werbung, wenn in 10 s >= 80 % ohne Logo (Wert < 0,35);
     *  Sendung wieder, wenn in 30 s >= 80 % mit Logo (Wert > 0,7). */
    static final int WIN_IN = 10, WIN_OUT = 30;
    static final float LO = .35f, HI = .7f;
    /** Laenger als so lange "Werbung" = eher falsches Logo: neu lernen und Hauptsender aufgeben. */
    static final long MAX_PAUSE_MS = 12 * 60_000L;

    private final ZapperService svc;
    private final Context c;
    private FritzTv fritz;
    private long fritzLoaded, retryAt;

    // Zustand (nur im Waechter-Thread bzw. synchronisiert)
    private Epg.Channel home;          // beobachteter Sender
    private String homeKey;
    private Sensor sensor;
    private Logo logo;
    private boolean pause;             // Hauptsender zeigt gerade Werbung
    private boolean away;              // wir haben auf einen Ausweichsender geschaltet
    private long awayChannel = -1, pauseSince;
    private final ArrayDeque<Float> seconds = new ArrayDeque<>();
    private float secSum;
    private int secN;
    private long secStart;
    private int learnShown = -1;
    private long lastFrame, lastReport, watchStart;
    private boolean gotFrame;
    /** Sender, die die FRITZ!Box gerade nicht liefert (z. B. 562 MHz: MTV, Comedy Central) -> bis wann ignorieren. */
    private final java.util.Map<String, Long> noSignal = new java.util.HashMap<>();
    private int framesSinceReport;

    WerbeWaechter(ZapperService svc) {
        this.svc = svc;
        this.c = svc;
    }

    boolean isAway() {
        return away;
    }

    String status() {
        if (home == null) return "Werbe-Sensor: wartet";
        if (sensor == null) return "Werbe-Sensor: " + home.name + " wird nicht beobachtet";
        if (logo == null || !logo.ready())
            return "Werbe-Sensor: lernt Logo von " + home.name + " (" + (logo == null ? 0 : logo.learnPercent()) + " %)";
        return "Werbe-Sensor: " + home.name + (pause ? " – WERBUNG" : " – Sendung") + (away ? ", ausgewichen" : "");
    }

    /** Alle 2 s aus dem Dienst-Thread. */
    synchronized void tick() {
        PowerManager pm = c.getSystemService(PowerManager.class);
        String fg = ZapperService.foregroundApp(c);
        if (!pm.isInteractive() || !ZapperService.TV_PKG.equals(fg)) {
            stopSensor();
            return;
        }
        long cur = Epg.currentChannelId(c);
        if (cur < 0) return;
        if (away && cur != awayChannel) {
            Log.add(c, "Werbung: selbst umgeschaltet – folge dem neuen Sender");
            away = false;
        }
        if (!away && (home == null || home.id != cur) && System.currentTimeMillis() >= retryAt) watch(cur);
        if (sensor != null && System.currentTimeMillis() - lastFrame > 20_000) {
            if (!gotFrame) {
                Log.add(c, "Werbe-Sensor: FRITZ!Box liefert für " + home.name + " kein Bild – keine Werbeerkennung, "
                        + "neuer Versuch in 30 min");
                noSignal.put(homeKey, System.currentTimeMillis() + 30 * 60_000L);
                stopSensor();
            } else {
                Log.add(c, "Werbe-Sensor: keine Bilder mehr – starte neu");
                watch(cur);
            }
        }
        if (away && pause && System.currentTimeMillis() - pauseSince > MAX_PAUSE_MS) {
            Log.add(c, "Werbung auf " + home.name + " dauert über 12 min – Logo wird neu gelernt, bleibe hier");
            if (logo != null) logo.relearn();
            away = false;
            pause = false;
        }
    }

    private void watch(long channelId) {
        stopSensor();
        home = null;
        pause = false;
        seconds.clear();
        secStart = 0;
        secSum = 0;
        secN = 0;
        for (Epg.Channel ch : Epg.channels(c)) if (ch.id == channelId) home = ch;
        if (home == null) return;
        if (Config.load(c).adFree.contains(home.name)) {
            Log.add(c, "Werbe-Sensor: " + home.name + " ist werbefrei – nichts zu beobachten");
            return;
        }
        try {
            if (fritz == null || System.currentTimeMillis() - fritzLoaded > 6 * 3600_000L) {
                fritz = FritzTv.load(Config.load(c).fritz);
                fritzLoaded = System.currentTimeMillis();
            }
        } catch (Exception e) {
            Log.add(c, "FRITZ!Box-Senderliste nicht lesbar: " + e.getMessage());
            retryAt = System.currentTimeMillis() + 60_000;
            return;
        }
        String url = fritz.urlFor(home.name);
        if (url == null) {
            Log.add(c, "Werbe-Sensor: " + home.name + " gibt es nicht bei der FRITZ!Box");
            retryAt = System.currentTimeMillis() + 60_000;
            return;
        }
        homeKey = FritzTv.norm(home.name);
        Long ns = noSignal.get(homeKey);
        if (ns != null && ns > System.currentTimeMillis()) return;
        logo = Logo.load(c, homeKey);
        learnShown = -1;
        lastFrame = lastReport = watchStart = System.currentTimeMillis();
        gotFrame = false;
        Log.add(c, "Werbe-Sensor beobachtet " + home.name + " (FRITZ!Box: " + fritz.fritzName(home.name) + ")"
                + (logo.ready() ? "" : " – Logo wird gelernt, etwa 5 min"));
        sensor = new Sensor(url, this);
        sensor.start();
    }

    private void stopSensor() {
        if (sensor != null) sensor.stop();
        sensor = null;
    }

    synchronized void shutdown() {
        stopSensor();
        home = null;
    }

    // --- Bilder vom Sensor (Sensor-Thread) ---

    @Override
    public synchronized void frame(byte[] top, byte[] bottom, int w, int h) {
        if (logo == null || home == null) return;
        lastFrame = System.currentTimeMillis();
        gotFrame = true;
        framesSinceReport++;
        boolean wasReady = logo.ready();
        float v = logo.feed(top, bottom, w);
        if (v < 0) {
            int pct = logo.learnPercent() / 25 * 25;
            if (pct != learnShown) {
                learnShown = pct;
                if (pct > 0) Log.add(c, "Logo von " + home.name + ": " + pct + " % gelernt");
            }
            return;
        }
        if (!wasReady) {
            logo.save(c, homeKey);
            Log.add(c, "Logo von " + home.name + " gelernt (" + logo.points + " Punkte) – Werbeerkennung aktiv");
        }
        long now = System.currentTimeMillis();
        if (secStart == 0) secStart = now;
        secSum += v;
        secN++;
        if (now - secStart < 1000) return;
        seconds.addLast(secSum / secN);
        if (now - lastReport > 30_000) {
            Log.add(c, String.format(java.util.Locale.GERMANY, "Werbe-Sensor %s: Logo-Wert %.2f, %d Bilder in %d s%s",
                    home.name, secSum / secN, framesSinceReport, (now - lastReport) / 1000, pause ? ", Werbung" : ""));
            lastReport = now;
            framesSinceReport = 0;
        }
        secSum = 0;
        secN = 0;
        secStart = now;
        while (seconds.size() > WIN_OUT) seconds.removeFirst();
        decide();
    }

    // --- Kontrollbilder: die letzten 60 s und 30 s nach jeder Entscheidung, als PGM unter
    //     /sdcard/Android/data/io.github.mhd6271.tvzapper/files/kontrolle/<Zeit>_<Ereignis>/ (adb pull) ---
    private final ArrayDeque<Object[]> thumbs = new ArrayDeque<>();
    private long dumpUntil;
    private java.io.File dumpDir;

    @Override
    public synchronized void thumb(byte[] g, int w, int h) {
        long now = System.currentTimeMillis();
        thumbs.addLast(new Object[]{now, g, w, h});
        while (thumbs.size() > 30) thumbs.removeFirst();
        if (dumpDir != null && now <= dumpUntil) writeThumb(dumpDir, now, g, w, h);
    }

    private void dump(String what) {
        java.io.File base = c.getExternalFilesDir("kontrolle");
        if (base == null) return;
        String stamp = new java.text.SimpleDateFormat("MMdd-HHmmss", java.util.Locale.GERMANY).format(new java.util.Date());
        dumpDir = new java.io.File(base, stamp + "_" + what);
        dumpDir.mkdirs();
        for (Object[] t : thumbs) writeThumb(dumpDir, (Long) t[0], (byte[]) t[1], (Integer) t[2], (Integer) t[3]);
        dumpUntil = System.currentTimeMillis() + 30_000;
        java.io.File[] old = base.listFiles();
        if (old != null && old.length > 40) {
            java.util.Arrays.sort(old);
            for (int i = 0; i < old.length - 40; i++) {
                java.io.File[] fs = old[i].listFiles();
                if (fs != null) for (java.io.File f : fs) f.delete();
                old[i].delete();
            }
        }
    }

    private static void writeThumb(java.io.File dir, long t, byte[] g, int w, int h) {
        String name = new java.text.SimpleDateFormat("HHmmss", java.util.Locale.GERMANY).format(new java.util.Date(t)) + ".pgm";
        try (java.io.FileOutputStream o = new java.io.FileOutputStream(new java.io.File(dir, name))) {
            o.write(("P5\n" + w + " " + h + "\n255\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));
            o.write(g);
        } catch (Exception ignored) {
        }
    }

    @Override
    public void error(String msg) {
        Log.add(c, "Werbe-Sensor: " + msg);
    }

    private void decide() {
        if (!pause && share(WIN_IN, false) >= .8f) {
            pause = true;
            pauseSince = System.currentTimeMillis();
            Log.add(c, "WERBUNG auf " + home.name);
            dump("werbung_" + homeKey);
            if (Config.load(c).avoidAds) dodge();
        } else if (pause && share(WIN_OUT, true) >= .8f) {
            pause = false;
            Log.add(c, "Werbung auf " + home.name + " vorbei (" + (System.currentTimeMillis() - pauseSince) / 1000 + " s)");
            dump("vorbei_" + homeKey);
            if (away) {
                away = false;
                if (svc.tuneTo(home, "Werbung vorbei – zurück zu " + home.name)) awayChannel = -1;
            }
        }
    }

    /** Anteil der letzten n Sekunden mit (logo=true) bzw. ohne Logo. */
    private float share(int n, boolean withLogo) {
        if (seconds.size() < n) return 0;
        int k = 0, i = 0;
        for (java.util.Iterator<Float> it = seconds.descendingIterator(); it.hasNext() && i < n; i++) {
            float v = it.next();
            if (withLogo ? v > HI : v < LO) k++;
        }
        return k / (float) n;
    }

    /** Auf den besten werbefreien Ausweichsender schalten. */
    private void dodge() {
        Config cfg = Config.load(c);
        List<Epg.Channel> all = Epg.channels(c);
        Epg.Channel best = null;
        int bestPts = Integer.MIN_VALUE, bestRank = Integer.MAX_VALUE;
        for (Epg.Channel ch : all) {
            int rank = cfg.adFree.indexOf(ch.name);
            if (rank < 0 || ch.id == home.id) continue;
            Epg.Program p = Epg.current(c, ch.id);
            int pts = Scorer.score(ch.name + " " + (p == null ? "" : p.text()), cfg).points;
            if (pts < 0) continue;
            if (pts > bestPts || pts == bestPts && rank < bestRank) {
                best = ch;
                bestPts = pts;
                bestRank = rank;
            }
        }
        if (best == null) {
            Log.add(c, "Kein Ausweichsender verfügbar");
            return;
        }
        Epg.Program p = Epg.current(c, best.id);
        if (svc.tuneTo(best, "Werbung auf " + home.name + " – solange " + best.name + (p == null ? "" : ": " + p.title))) {
            away = true;
            awayChannel = best.id;
        }
    }
}
