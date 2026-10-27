package io.github.mhd6271.tvzapper;

import android.content.Context;

import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Senderlogo als Kantenmaske in einer Bildecke (Bild 360x288, Ecke 108x72) – Verfahren am Mac an 20 min
 *  Aufnahme von 6 Sendern geprueft (scratchpad werbung/auswertung.py): Kanten (Sobel > 60), die in > 70 % der
 *  Bilder an derselben Stelle sind, ohne Bildrand und lange Linien, nur der dichteste 70x50-Bereich.
 *  Wert je Bild = Anteil der Maskenpunkte, die gerade eine Kante haben (Sendung ~1,0, Werbung ~0,1). */
final class Logo {
    static final int CW = 108, CH = 72;
    /** Lernzeit fuer unbekannte Sender: 5 min bei 4 Bildern/s. */
    static final int LEARN_FRAMES = 1200;

    int corner = -1;          // 0 oben links, 1 oben rechts, 2 unten links, 3 unten rechts
    boolean[] mask;
    int points;
    private int[][] counts = new int[4][CW * CH];
    private int learned;
    /** Lernrunden ohne brauchbares Logo (z. B. weil viel Werbung lief). */
    int failedRounds;

    boolean ready() {
        return mask != null;
    }

    int learnPercent() {
        return learned * 100 / LEARN_FRAMES;
    }

    /** Ein Bild verarbeiten; gibt den Logo-Wert 0..1 zurueck, oder -1 solange gelernt wird. */
    float feed(byte[] top, byte[] bottom, int w) {
        if (mask != null) {
            boolean[] e = edges(crop(top, bottom, w, corner));
            int hit = 0;
            for (int i = 0; i < e.length; i++) if (mask[i] && e[i]) hit++;
            return hit / (float) points;
        }
        for (int c = 0; c < 4; c++) {
            boolean[] e = edges(crop(top, bottom, w, c));
            for (int i = 0; i < e.length; i++) if (e[i]) counts[c][i]++;
        }
        if (++learned >= LEARN_FRAMES) finishLearning();
        return -1;
    }

    void relearn() {
        mask = null;
        corner = -1;
        counts = new int[4][CW * CH];
        learned = 0;
    }

    private void finishLearning() {
        int bestPts = 0;
        // Senderlogos sitzen oben; untere Ecken nur, wenn oben nichts ist (dort sind oft Sendungslogos,
        // Spielstaende oder Laufbaender – am Mac bei SAT.1, RTL und n-tv so passiert)
        for (int c = 0; c < 4; c++) {
            if (c == 2 && bestPts >= 30) break;
            boolean[] m = new boolean[CW * CH];
            for (int i = 0; i < m.length; i++) m[i] = counts[c][i] > 0.7 * learned;
            clean(m);
            int n = 0;
            for (boolean b : m) if (b) n++;
            if (n > bestPts) {
                bestPts = n;
                mask = m;
                corner = c;
            }
        }
        points = bestPts;
        if (points < 30) {   // kein Logo gefunden – weiter lernen
            mask = null;
            failedRounds++;
        }
        counts = new int[4][CW * CH];
        learned = 0;
    }

    /** Rand weg, lange Linien weg, Einzelpunkte weg, nur dichtesten 70x50-Bereich behalten. */
    static void clean(boolean[] m) {
        for (int y = 0; y < CH; y++)
            for (int x = 0; x < CW; x++)
                if (y < 8 || y >= CH - 8 || x < 8 || x >= CW - 8) m[y * CW + x] = false;
        for (int y = 0; y < CH; y++) clearRuns(m, y * CW, 1, CW);
        for (int x = 0; x < CW; x++) clearRuns(m, x, CW, CH);
        boolean[] c = m.clone();
        for (int y = 1; y < CH - 1; y++)
            for (int x = 1; x < CW - 1; x++) {
                if (!c[y * CW + x]) continue;
                int nb = 0;
                for (int dy = -1; dy <= 1; dy++)
                    for (int dx = -1; dx <= 1; dx++) if ((dy != 0 || dx != 0) && c[(y + dy) * CW + x + dx]) nb++;
                if (nb == 0) m[y * CW + x] = false;
            }
        int best = -1, by = 0, bx = 0;
        for (int y = 0; y < CH; y++)
            for (int x = 0; x < CW; x++) {
                int n = 0;
                for (int yy = Math.max(0, y - 25); yy < Math.min(CH, y + 25); yy++)
                    for (int xx = Math.max(0, x - 35); xx < Math.min(CW, x + 35); xx++) if (m[yy * CW + xx]) n++;
                if (n > best) {
                    best = n;
                    by = y;
                    bx = x;
                }
            }
        for (int y = 0; y < CH; y++)
            for (int x = 0; x < CW; x++)
                if (y < by - 25 || y >= by + 25 || x < bx - 35 || x >= bx + 35) m[y * CW + x] = false;
    }

    private static void clearRuns(boolean[] m, int start, int step, int len) {
        int run = 0;
        for (int i = 0; i <= len; i++) {
            boolean on = i < len && m[start + i * step];
            if (on) run++;
            else {
                if (run > 60) for (int k = i - run; k < i; k++) m[start + k * step] = false;
                run = 0;
            }
        }
    }

    static byte[] crop(byte[] top, byte[] bottom, int w, int c) {
        byte[] src = c < 2 ? top : bottom;
        int x0 = (c % 2 == 0) ? 0 : (int) (w * .7);
        byte[] r = new byte[CW * CH];
        for (int y = 0; y < CH; y++)
            for (int x = 0; x < CW && x0 + x < w; x++) r[y * CW + x] = src[y * w + x0 + x];
        return r;
    }

    static boolean[] edges(byte[] g) {
        boolean[] e = new boolean[CW * CH];
        for (int y = 1; y < CH - 1; y++)
            for (int x = 1; x < CW - 1; x++) {
                int i = y * CW + x;
                int a = g[i - CW - 1] & 0xff, b = g[i - CW] & 0xff, c = g[i - CW + 1] & 0xff;
                int d = g[i - 1] & 0xff, f = g[i + 1] & 0xff;
                int h = g[i + CW - 1] & 0xff, k = g[i + CW] & 0xff, l = g[i + CW + 1] & 0xff;
                int gx = (c + 2 * f + l) - (a + 2 * d + h);
                int gy = (h + 2 * k + l) - (a + 2 * b + c);
                e[i] = gx * gx + gy * gy > 3600;
            }
        return e;
    }

    // --- Speichern: Ecke, dann CH Zeilen aus 0/1 ---

    private static File file(Context c, String key) {
        File d = new File(c.getFilesDir(), "logos");
        d.mkdirs();
        return new File(d, key + "_v2.txt");   // v2: nur noch obere Ecken bevorzugt; aeltere Dateien neu lernen
    }

    void save(Context c, String key) {
        if (mask == null) return;
        StringBuilder b = new StringBuilder().append(corner).append('\n');
        for (int y = 0; y < CH; y++) {
            for (int x = 0; x < CW; x++) b.append(mask[y * CW + x] ? '1' : '0');
            b.append('\n');
        }
        try {
            Files.write(file(c, key).toPath(), b.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            Log.add(c, "Logo nicht gespeichert: " + e.getMessage());
        }
    }

    /** Gespeichertes Logo laden, sonst das mitgelieferte (assets/logos), sonst leer (wird gelernt). */
    static Logo load(Context c, String key) {
        Logo l = new Logo();
        String txt = null;
        try {
            File f = file(c, key);
            if (f.exists()) txt = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
            else try (InputStream in = c.getAssets().open("logos/" + key + ".txt")) {
                txt = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {
        }
        if (txt != null) {
            String[] lines = txt.split("\n");
            l.corner = Integer.parseInt(lines[0].trim());
            l.mask = new boolean[CW * CH];
            for (int y = 0; y < CH && y + 1 < lines.length; y++)
                for (int x = 0; x < CW && x < lines[y + 1].length(); x++)
                    if (lines[y + 1].charAt(x) == '1') {
                        l.mask[y * CW + x] = true;
                        l.points++;
                    }
            if (l.points < 30) l.mask = null;
        }
        return l;
    }
}
