package io.github.mhd6271.tvzapper;

import android.content.Context;

import org.json.JSONObject;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Iterator;
import java.util.Map;
import java.util.TreeMap;

/** Gemessene Werbepausen je Sender (Anzahl, Summe in s) in werbepausen.json – fuer die Zeitgrenze und die Anzeige.
 *  Oeffentliche Zahlen je Sender gibt es nicht; gesetzlich sind 20 % je Zeitfenster erlaubt (§ 70 MStV). */
final class PauseStats {
    private static File file(Context c) {
        return new File(c.getFilesDir(), "werbepausen.json");
    }

    private static synchronized JSONObject read(Context c) {
        try {
            return new JSONObject(new String(Files.readAllBytes(file(c).toPath()), StandardCharsets.UTF_8));
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    /** Nur Pausen zwischen 30 s und 15 min zaehlen (kuerzer = Trailer/Fehlalarm, laenger = Logo falsch). */
    static synchronized void add(Context c, String channel, long secs) {
        if (secs < 30 || secs > 900) return;
        try {
            JSONObject o = read(c);
            JSONObject e = o.optJSONObject(channel);
            if (e == null) e = new JSONObject();
            e.put("anzahl", e.optInt("anzahl") + 1);
            e.put("summe_s", e.optLong("summe_s") + secs);
            o.put(channel, e);
            Files.write(file(c).toPath(), o.toString(2).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    /** Durchschnitt in s, 0 wenn noch keine Messung. */
    static long averageSec(Context c, String channel) {
        JSONObject e = read(c).optJSONObject(channel);
        return e == null || e.optInt("anzahl") == 0 ? 0 : e.optLong("summe_s") / e.optInt("anzahl");
    }

    static Map<String, String> summary(Context c) {
        Map<String, String> m = new TreeMap<>();
        JSONObject o = read(c);
        for (Iterator<String> it = o.keys(); it.hasNext(); ) {
            String k = it.next();
            JSONObject e = o.optJSONObject(k);
            int n = e.optInt("anzahl");
            if (n > 0) m.put(k, String.format(java.util.Locale.GERMANY, "Ø %d:%02d min (%d gemessen)",
                    e.optLong("summe_s") / n / 60, e.optLong("summe_s") / n % 60, n));
        }
        return m;
    }
}
