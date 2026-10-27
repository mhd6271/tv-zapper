package io.github.mhd6271.tvzapper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/** Senderliste der FRITZ!Box Cable (DVB-C ueber SAT>IP). Die Box dient nur als zweiter Empfaenger fuer die
 *  Werbeerkennung; geguckt wird weiter ueber den Tuner des Fernsehers. */
final class FritzTv {
    /** normalisierter Name -> rtsp-Adresse; SD zuerst eingelesen, HD ueberschreibt nicht (SD-Logos sind gelernt). */
    final Map<String, String> urls = new LinkedHashMap<>();
    final Map<String, String> names = new LinkedHashMap<>();

    static FritzTv load(String host) throws Exception {
        FritzTv f = new FritzTv();
        for (String list : new String[]{"tvsd", "tvhd"}) {
            HttpURLConnection c = (HttpURLConnection) new URL("http://" + host + "/dvb/m3u/" + list + ".m3u").openConnection();
            c.setConnectTimeout(4000);
            c.setReadTimeout(6000);
            try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8))) {
                String name = null, line;
                while ((line = r.readLine()) != null) {
                    if (line.startsWith("#EXTINF:")) name = line.substring(line.indexOf(',') + 1).trim();
                    else if (line.startsWith("rtsp://") && name != null) {
                        String key = norm(name);
                        if (!f.urls.containsKey(key)) {
                            f.urls.put(key, line.trim());
                            f.names.put(key, name);
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
        s = s.replaceAll("\\s+(hd|uhd|sd)$", "");
        s = s.replace("prosieben maxx", "pro7 maxx").replace("rtl television", "rtl").replace("eurosport 1 deutschland", "eurosport 1")
                .replace("n-tv", "ntv").replace("das erste", "das erste");
        return s.replaceAll("[^a-z0-9äöüß]", "");
    }

    String urlFor(String tvName) {
        return urls.get(norm(tvName));
    }

    String fritzName(String tvName) {
        return names.get(norm(tvName));
    }
}
