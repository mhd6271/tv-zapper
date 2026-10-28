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
    // KOMPAT: Ecke und Maske sind fuer SD in halber Aufloesung (360x288) bemessen. Bei HD-Strom (960x540) ist das
    //   Fenster kleiner als das Logo; UHD ebenso.
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

    /** Weitere Logo-Varianten desselben Senders (z. B. bei 4:3-Sendungen mit schwarzen Raendern sitzt das Logo
     *  woanders – am 27.10.2026 bei ProSieben MAXX/Futurama so gesehen). Wert = bester Treffer aller Varianten. */
    final java.util.List<int[]> variantCorner = new java.util.ArrayList<>();
    final java.util.List<boolean[]> variantMask = new java.util.ArrayList<>();
    /** Variante lernen: Bilder, in denen 2 min lang an derselben Stelle oben ein festes Zeichen steht. */
    static final int VARIANT_FRAMES = 400;
    static final int MAX_VARIANTS = 10;
    private int[][] vCounts;
    private int vLearned;

    boolean ready() {
        return mask != null;
    }

    int learnPercent() {
        return learned * 100 / LEARN_FRAMES;
    }

    /** Ein Bild verarbeiten; gibt den Logo-Wert 0..1 zurueck, oder -1 solange gelernt wird. */
    float feed(byte[] top, byte[] bottom, int w) {
        if (mask != null) {
            float best = score(top, bottom, w, corner, mask, points);
            for (int k = 0; k < variantMask.size(); k++)
                best = Math.max(best, score(top, bottom, w, variantCorner.get(k)[0], variantMask.get(k),
                        variantCorner.get(k)[1]));
            return best;
        }
        for (int c = 0; c < 4; c++) {
            boolean[] e = edges(crop(top, bottom, w, c));
            for (int i = 0; i < e.length; i++) if (e[i]) counts[c][i]++;
        }
        if (++learned >= LEARN_FRAMES) finishLearning();
        return -1;
    }

    private static float score(byte[] top, byte[] bottom, int w, int corner, boolean[] m, int pts) {
        boolean[] e = edges(crop(top, bottom, w, corner));
        int hit = 0;
        for (int i = 0; i < e.length; i++) if (m[i] && e[i]) hit++;
        return hit / (float) pts;
    }

    /** Waehrend vermeintlicher Werbung aufrufen. Liefert true, sobald eine neue Variante gelernt ist
     *  (dann war es keine Werbung). */
    boolean learnVariant(byte[] top, byte[] bottom, int w) {
        if (vCounts == null) vCounts = new int[2][CW * CH];
        for (int c = 0; c < 2; c++) {
            boolean[] e = edges(crop(top, bottom, w, c));
            for (int i = 0; i < e.length; i++) if (e[i]) vCounts[c][i]++;
        }
        if (++vLearned < VARIANT_FRAMES) return false;
        boolean found = false;
        for (int c = 0; c < 2 && !found; c++) {
            boolean[] m = new boolean[CW * CH];
            for (int i = 0; i < m.length; i++) m[i] = vCounts[c][i] > 0.9 * vLearned;
            clean(m);
            int n = 0;
            for (boolean b : m) if (b) n++;
            if (n >= 40) {
                if (variantMask.size() >= MAX_VARIANTS) {   // aelteste Variante verwerfen, Datei und Rechenzeit begrenzen
                    variantCorner.remove(0);
                    variantMask.remove(0);
                }
                variantCorner.add(new int[]{c, n});
                variantMask.add(m);
                found = true;
            }
        }
        resetVariant();
        return found;
    }

    void resetVariant() {
        vCounts = null;
        vLearned = 0;
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
        // KOMPAT: Rechte Ecke ab 70 % der Breite: bei 360 genau bis zum Rand, bei HD (960) nur 672 bis 780 – Logos ganz
        //   rechts liegen dann ausserhalb. Betrifft auch das eigene Setup, sobald ein HD-Eintrag der FRITZ!Box genommen wird.
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
        StringBuilder b = new StringBuilder();
        block(b, corner, mask);
        for (int k = 0; k < variantMask.size(); k++) block(b, variantCorner.get(k)[0], variantMask.get(k));
        try {
            Files.write(file(c, key).toPath(), b.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            Log.add(c, "Logo nicht gespeichert: " + e.getMessage());
        }
    }

    private static void block(StringBuilder b, int corner, boolean[] m) {
        b.append(corner).append('\n');
        for (int y = 0; y < CH; y++) {
            for (int x = 0; x < CW; x++) b.append(m[y * CW + x] ? '1' : '0');
            b.append('\n');
        }
    }

    /** Gibt es fuer den Sender schon ein Logo (gelernt oder mitgeliefert)? */
    static boolean known(Context c, String key) {
        if (file(c, key).exists()) return true;
        try (InputStream in = c.getAssets().open("logos/" + key + ".txt")) {
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** Gespeichertes Logo laden, sonst das mitgelieferte (assets/logos), sonst leer (wird gelernt). */
    static Logo load(Context c, String key) {
        Logo l = new Logo();
        String txt = null;
        try {
            File f = file(c, key);
            if (f.exists()) txt = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
            // KOMPAT: Mitgelieferte Logos stammen aus SD-Aufnahmen aus Vodafone-Kabel (Okt. 2026); bei anderer Aufloesung oder
            //   Logoform passen sie nicht (Fehlalarm, nach 12 min neu lernen).
            //   readAllBytes() gibt es erst ab Android 13 – darunter NoSuchMethodError (wird von catch (Exception) nicht gefangen).
            else try (InputStream in = c.getAssets().open("logos/" + key + ".txt")) {
                txt = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {
        }
        if (txt != null) {
            String[] lines = txt.split("\n");
            for (int at = 0; at + CH < lines.length + 1 && at < lines.length && !lines[at].trim().isEmpty(); at += CH + 1) {
                int corner;
                try {
                    corner = Integer.parseInt(lines[at].trim());
                } catch (NumberFormatException e) {
                    break;   // kaputte Datei: Rest ignorieren, Logo wird notfalls neu gelernt
                }
                if (corner < 0 || corner > 1) break;
                boolean[] m = new boolean[CW * CH];
                int n = 0;
                for (int y = 0; y < CH && at + 1 + y < lines.length; y++)
                    for (int x = 0; x < CW && x < lines[at + 1 + y].length(); x++)
                        if (lines[at + 1 + y].charAt(x) == '1') {
                            m[y * CW + x] = true;
                            n++;
                        }
                if (n < 30) continue;
                if (l.mask == null) {
                    l.corner = corner;
                    l.mask = m;
                    l.points = n;
                } else if (l.variantMask.size() < MAX_VARIANTS) {
                    l.variantCorner.add(new int[]{corner, n});
                    l.variantMask.add(m);
                }
            }
        }
        return l;
    }
}
