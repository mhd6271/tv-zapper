package io.github.mhd6271.tvzapper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Senderliste der FRITZ!Box Cable (DVB-C ueber SAT>IP). Die Box dient nur als zweiter Empfaenger fuer die
 *  Werbeerkennung; geguckt wird weiter ueber den Tuner des Fernsehers. */
final class FritzTv {
    /** normalisierter Name -> rtsp-Adressen; SD zuerst eingelesen (SD-Logos sind gelernt), dann HD. Mehrere Eintraege
     *  gibt es nach einem Sendersuchlauf, wenn die Box alte Frequenzen behaelt – dann der Reihe nach probieren. */
    final Map<String, List<String>> urls = new LinkedHashMap<>();
    final Map<String, List<String>> names = new LinkedHashMap<>();
    private final Map<String, Integer> pick = new HashMap<>();

    static FritzTv load(String host) throws Exception {
        FritzTv f = new FritzTv();
        for (String list : new String[]{"tvsd", "tvhd"}) {
            // KOMPAT: Diese Listen gibt es nur bei FRITZ!Box-Modellen mit DVB-C-Empfang (Cable); DSL-/Glasfaser-Boxen liefern
            //   nichts -> keine Werbeerkennung. Verschluesselte Sender (CI-Karte) liefert die Box nicht. Geprueft nur an der 6660.
            HttpURLConnection c = (HttpURLConnection) new URL("http://" + host + "/dvb/m3u/" + list + ".m3u").openConnection();
            c.setConnectTimeout(4000);
            c.setReadTimeout(6000);
            try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8))) {
                String name = null, line;
                long read = 0;
                while ((line = r.readLine()) != null) {
                    // fremde Daten begrenzen: die echte Liste hat ~20 kB, ueberlange Zeilen sind kein Sender
                    if ((read += line.length()) > 2_000_000 || f.urls.size() > 5000) break;
                    if (line.length() > 2000) continue;
                    if (line.startsWith("#EXTINF:")) name = line.substring(line.indexOf(',') + 1).trim();
                    else if (line.startsWith("rtsp://") && name != null) {
                        String key = norm(name);
                        if (!f.urls.containsKey(key)) {
                            f.urls.put(key, new ArrayList<>());
                            f.names.put(key, new ArrayList<>());
                        }
                        if (!f.urls.get(key).contains(line.trim())) {
                            f.urls.get(key).add(line.trim());
                            f.names.get(key).add(name);
                        }
                        name = null;
                    }
                }
            }
        }
        return f;
    }

    /** Fernseh-Sendername (z. B. "ProSieben MAXX HD") -> Schluessel der Fritz-Liste. */
    static String norm(String s) {
        s = s.toLowerCase(Locale.GERMAN).trim();
        s = s.replaceAll("(^|\\s)(hd|uhd|sd)(?=\\s|$)", " ").trim();   // auch mittendrin: "WDR HD Köln" = "WDR Köln"
        // KOMPAT: Angleichungen fuer TCL-Namen gegen Vodafone-Kabel-Namen (BW). Andere Fernseher, Netze oder Satellit
        //   schreiben Namen anders -> "gibt es nicht bei der FRITZ!Box".
        if (s.equals("nitro")) s = "rtlnitro";
        if (s.equals("swr bw")) s = "swr fernsehen bw";
        if (s.equals("swr rp")) s = "swr fernsehen rp";
        if (s.equals("sonlife broadcasting network")) s = "sonlife";
        s = s.replace("prosieben maxx", "pro7 maxx").replace("rtl television", "rtl").replace("eurosport 1 deutschland", "eurosport 1")
                .replace("n-tv", "ntv").replace("rtl2", "rtlzwei");
        return s.replaceAll("[^a-z0-9äöüß]", "");
    }

    String urlFor(String tvName) {
        List<String> l = urls.get(norm(tvName));
        return l == null ? null : l.get(index(tvName));
    }

    String fritzName(String tvName) {
        List<String> l = names.get(norm(tvName));
        if (l == null) return null;
        java.util.regex.Matcher fm = java.util.regex.Pattern.compile("freq=(\\d+)").matcher(String.valueOf(urlFor(tvName)));
        String m = fm.find() ? fm.group(1) : null;
        return l.get(index(tvName)) + (m == null ? "" : ", " + m + " MHz") + (l.size() > 1 ? ", Eintrag " + (index(tvName) + 1) + "/" + l.size() : "");
    }

    private int index(String tvName) {
        Integer i = pick.get(norm(tvName));
        return i == null ? 0 : i;
    }

    /** Wieder beim ersten Eintrag anfangen (nach der Wartezeit, wenn keiner ging). */
    void reset(String tvName) {
        pick.remove(norm(tvName));
    }

    /** Naechsten Eintrag fuer diesen Sender nehmen; false, wenn keiner mehr uebrig ist. */
    boolean next(String tvName) {
        List<String> l = urls.get(norm(tvName));
        int i = index(tvName) + 1;
        if (l == null || i >= l.size()) return false;
        pick.put(norm(tvName), i);
        return true;
    }
}
