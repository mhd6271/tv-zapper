package io.github.mhd6271.tvzapper;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Iterator;
import java.util.Map;
import java.util.TreeMap;

/** Gemessene Werbepausen je Sender in werbepausen.json – fuer die Zeitgrenze und die Anzeige.
 *  Je Sender: "pausen" = [{"ende": ms, "s": Sekunden}] (seit 0.3.2), dazu aeltere Sammelwerte "anzahl"/"summe_s"
 *  aus 0.2.x/0.3.0 ohne Einzelwerte. Oeffentliche Zahlen je Sender gibt es nicht; gesetzlich sind 20 % je
 *  Zeitfenster erlaubt (§ 70 MStV). */
final class PauseStats {
    private static final int MAX_PER_CHANNEL = 200;

    private static File file(Context c) {
        return new File(c.getFilesDir(), "werbepausen.json");
    }

    static synchronized JSONObject read(Context c) {
        try {
            return new JSONObject(new String(Files.readAllBytes(file(c).toPath()), StandardCharsets.UTF_8));
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    private static void write(Context c, JSONObject o) throws Exception {
        Files.write(file(c).toPath(), o.toString(2).getBytes(StandardCharsets.UTF_8));
    }

    /** Nur Pausen zwischen 30 s und 15 min zaehlen (kuerzer = Trailer/Fehlalarm, laenger = Logo falsch). */
    static synchronized void add(Context c, String channel, long secs) {
        if (secs < 30 || secs > 900) return;
        try {
            JSONObject o = read(c);
            JSONObject e = o.optJSONObject(channel);
            if (e == null) e = new JSONObject();
            JSONArray list = e.optJSONArray("pausen");
            if (list == null) list = new JSONArray();
            list.put(new JSONObject().put("ende", System.currentTimeMillis()).put("s", secs));
            if (list.length() > MAX_PER_CHANNEL) {   // nur die neuesten behalten, die Datei soll nicht unbegrenzt wachsen
                JSONArray keep = new JSONArray();
                for (int i = list.length() - MAX_PER_CHANNEL; i < list.length(); i++) keep.put(list.get(i));
                list = keep;
            }
            e.put("pausen", list);
            o.put(channel, e);
            write(c, o);
        } catch (Exception ignored) {
        }
    }

    /** {anzahl, summe_s} aus Einzelwerten und alten Sammelwerten. */
    private static long[] totals(JSONObject e) {
        if (e == null) return new long[]{0, 0};
        long n = e.optInt("anzahl"), sum = e.optLong("summe_s");
        JSONArray list = e.optJSONArray("pausen");
        for (int i = 0; list != null && i < list.length(); i++) {
            JSONObject p = list.optJSONObject(i);
            if (p == null) continue;
            n++;
            sum += p.optLong("s");
        }
        return new long[]{n, sum};
    }

    /** Durchschnitt in s, 0 wenn noch keine Messung. */
    static long averageSec(Context c, String channel) {
        JSONObject e = read(c).optJSONObject(channel);
        if (e == null) return 0;
        long[] t = totals(e);
        return t[0] == 0 ? 0 : t[1] / t[0];
    }

    static Map<String, String> summary(Context c) {
        Map<String, String> m = new TreeMap<>();
        JSONObject o = read(c);
        for (Iterator<String> it = o.keys(); it.hasNext(); ) {
            String k = it.next();
            long[] t = totals(o.optJSONObject(k));
            if (t[0] > 0) m.put(k, String.format(java.util.Locale.GERMANY, "Ø %d:%02d min (%d gemessen)",
                    t[1] / t[0] / 60, t[1] / t[0] % 60, t[0]));
        }
        return m;
    }

    /** Fuer die Schnittstelle: je Sender anzahl, durchschnitt_s, alte Sammelwerte und Einzelpausen. */
    static JSONObject toJson(Context c) throws Exception {
        JSONObject out = new JSONObject();
        JSONObject o = read(c);
        for (Iterator<String> it = o.keys(); it.hasNext(); ) {
            String k = it.next();
            JSONObject e = o.optJSONObject(k);
            if (e == null) continue;
            long[] t = totals(e);
            JSONObject r = new JSONObject();
            r.put("anzahl", t[0]);
            r.put("durchschnitt_s", t[0] == 0 ? 0 : t[1] / t[0]);
            r.put("alt_anzahl", e.optInt("anzahl"));
            r.put("alt_summe_s", e.optLong("summe_s"));
            r.put("pausen", e.optJSONArray("pausen") == null ? new JSONArray() : e.optJSONArray("pausen"));
            out.put(k, r);
        }
        return out;
    }

    /** Pausen eines Senders loeschen: mit von/bis (ms, Ende der Pause) nur Einzelwerte in diesem Zeitraum,
     *  mit alt=true die alten Sammelwerte, ohne beides alles. Gibt die Zahl der entfernten Pausen zurueck. */
    static synchronized int delete(Context c, String channel, long from, long to, boolean old) throws Exception {
        JSONObject o = read(c);
        JSONObject e = o.optJSONObject(channel);
        if (e == null) return 0;
        int removed = 0;
        boolean all = from <= 0 && to <= 0 && !old;
        if (all || old) {
            removed += e.optInt("anzahl");
            e.remove("anzahl");
            e.remove("summe_s");
        }
        JSONArray list = e.optJSONArray("pausen"), keep = new JSONArray();
        for (int i = 0; list != null && i < list.length(); i++) {
            JSONObject p = list.optJSONObject(i);
            if (p == null) continue;
            long end = p.optLong("ende");
            boolean hit = all || (from > 0 || to > 0) && (from <= 0 || end >= from) && (to <= 0 || end <= to);
            if (hit) removed++;
            else keep.put(p);
        }
        e.put("pausen", keep);
        o.put(channel, e);
        write(c, o);
        return removed;
    }
}
