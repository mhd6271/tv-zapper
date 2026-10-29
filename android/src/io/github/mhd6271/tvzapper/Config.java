package io.github.mhd6271.tvzapper;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Einstellungen der App. Liegt als einstellungen.json im App-Ordner; erste Fassung aus assets/interessen.json
 *  (Kopie von ../interessen.json, gleiches Format wie beim Mac-Skript plus Felder der App). */
final class Config {
    static final String AN = "an", BEVORZUGT = "bevorzugt", AUS = "aus";

    static final class Cat {
        String name = "";
        int weight = 1;
        List<String> words = new ArrayList<>();
    }

    List<Cat> cats = new ArrayList<>();
    List<String> never = new ArrayList<>();
    int dwellMin = 5;
    /** Laufzeit in Minuten, 0 = ohne Ende (bis Stopp). */
    int runMin = 0;
    int bonus = 2;
    /** Sendername -> an / bevorzugt / aus, nur wo vom Fernseher abweichend eingestellt.
     *  Gespeichert wie in interessen.json: sender_nie (Liste), sender_bevorzugt (Name -> Bonus), dazu sender_an. */
    Map<String, String> channels = new LinkedHashMap<>();
    Map<String, Integer> prefBonus = new LinkedHashMap<>();
    String newChannels = AUS;
    /** Werbung umgehen ueber die FRITZ!Box als zweiten Empfaenger. */
    boolean avoidAds = true;
    /** Bei Werbung zuerst auf den besten bevorzugten Sender (★) ausweichen, erst dann auf werbefreie. */
    boolean dodgePreferred = false;
    /** Debug: bei jeder Umschaltung Grund und Punkte einblenden. */
    boolean showReason = false;
    // KOMPAT: "fritz.box" loest nur auf, wenn die FRITZ!Box der DNS-Server ist; sonst IP in den Einstellungen eintragen.
    String fritz = "fritz.box";
    /** Leer = automatisch erkennen. */
    String tvInput = "", tvApp = "";
    /** Spaetestens nach so vielen Minuten zurueck zum Hauptsender, auch wenn der Sensor nichts meldet
     *  (gemessene Durchschnittsdauer des Senders + 1 min, wenn bekannt). */
    int pauseMaxMin = 6;
    /** Werbefreie Ausweichsender, bei gleicher Punktzahl gilt die Reihenfolge. */
    List<String> adFree = new ArrayList<>(java.util.Arrays.asList("ZDFinfo HD", "zdf_neo HD", "arte HD",
            "tagesschau24 HD", "3sat HD", "phoenix HD", "WDR HD Köln", "hr-fernsehen HD"));
    /** Kinder-Modus: erlaubte (kidsChannels) und gesperrte Sender (kidsDenied); alle uebrigen nach kidsRestAllowed.
     *  Keine Sendung mit einem Wort aus kidsBlock (siehe Kinder). */
    boolean kids = false;
    List<String> kidsChannels = new ArrayList<>(), kidsDenied = new ArrayList<>();
    boolean kidsRestAllowed = false;
    /** Sperrbegriffe; ein Name einer Interessen-Kategorie sperrt auch alle Woerter dieser Kategorie. */
    List<String> kidsBlock = new ArrayList<>();

    /** Eigene Einstellung des Senders, sonst die Markierung des Fernsehers (Favorit1 = an), sonst newChannels. */
    String state(Epg.Channel ch) {
        String s = channels.get(ch.name);
        if (s != null) return s;
        return ch.favorite ? AN : newChannels;
    }

    int bonusFor(String name) {
        Integer b = prefBonus.get(name);
        return b != null ? b : bonus;
    }

    static File file(Context c) {
        return new File(c.getFilesDir(), "einstellungen.json");
    }

    static Config load(Context c) {
        try {
            File f = file(c);
            String json;
            if (f.exists()) {
                json = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
            } else {
                try (InputStream in = c.getAssets().open("interessen.json")) {
                    // KOMPAT: readAllBytes() erst ab Android 13: beim ersten Start (noch keine Einstellungsdatei) stuerzt die App auf
                    //   Android 8 bis 12 ab – NoSuchMethodError faengt catch (Exception) nicht.
                    json = new String(in.readAllBytes(), StandardCharsets.UTF_8);
                }
            }
            return parse(new JSONObject(json));
        } catch (Exception e) {
            Log.add(c, "Einstellungen nicht lesbar: " + e.getMessage());
            // kaputte Datei aufheben, bevor sie beim naechsten Speichern mit der Grundeinstellung ueberschrieben wird
            File f = file(c), bak = new File(c.getFilesDir(), "einstellungen.kaputt.json");
            if (f.exists() && !bak.exists()) f.renameTo(bak);
            return new Config();
        }
    }

    static Config parse(JSONObject o) throws JSONException {
        Config cfg = new Config();
        JSONArray cats = o.optJSONArray("interessen");
        if (cats != null) {
            for (int i = 0; i < cats.length(); i++) {
                JSONObject co = cats.getJSONObject(i);
                Cat cat = new Cat();
                cat.name = co.optString("name");
                cat.weight = co.optInt("gewicht", 1);
                cat.words = strings(co.optJSONArray("woerter"));
                cfg.cats.add(cat);
            }
        }
        cfg.never = strings(o.optJSONArray("aus"));
        cfg.dwellMin = o.optInt("verweilen_min", 5);
        cfg.runMin = o.optInt("laufzeit_min", 0);
        cfg.bonus = o.optInt("bonus_bevorzugt", 2);
        cfg.newChannels = o.optString("neue_sender", AUS);
        cfg.avoidAds = o.optBoolean("werbung_umgehen", true);
        cfg.dodgePreferred = o.optBoolean("ausweichen_bevorzugt", false);
        cfg.showReason = o.optBoolean("umschaltgrund_einblenden", false);
        cfg.fritz = o.optString("fritzbox", "fritz.box");
        cfg.tvInput = o.optString("tv_eingang", "");
        cfg.tvApp = o.optString("tv_app", "");
        cfg.pauseMaxMin = o.optInt("werbepause_max_min", 6);
        if (o.has("werbefrei")) cfg.adFree = strings(o.optJSONArray("werbefrei"));
        cfg.kids = o.optBoolean("kinder_modus", false);
        cfg.kidsChannels = strings(o.optJSONArray("kinder_sender"));
        cfg.kidsDenied = strings(o.optJSONArray("kinder_sender_gesperrt"));
        cfg.kidsRestAllowed = o.optBoolean("kinder_uebrige_erlaubt", false);
        cfg.kidsBlock = strings(o.optJSONArray("kinder_sperrbegriffe"));
        for (String n : strings(o.optJSONArray("sender_an"))) cfg.channels.put(n, AN);
        JSONObject pref = o.optJSONObject("sender_bevorzugt");
        if (pref != null) {
            for (Iterator<String> it = pref.keys(); it.hasNext(); ) {
                String k = it.next();
                cfg.channels.put(k, BEVORZUGT);
                cfg.prefBonus.put(k, pref.getInt(k));
            }
        }
        for (String n : strings(o.optJSONArray("sender_nie"))) cfg.channels.put(n, AUS);
        cfg.sanitize();
        return cfg;
    }

    // Grenzen fuer alle Eingaben (Oberflaeche, Datei, Schnittstelle): schuetzen den Fernseher mit wenig Speicher
    static final int MAX_CATS = 50, MAX_WORDS = 100, MAX_NEVER = 200, MAX_TEXT = 60, MAX_CHANNELS = 2000, MAX_ADFREE = 100;

    /** Werte auf sinnvolle Bereiche begrenzen, ueberlange Listen kuerzen, unbrauchbare Woerter entfernen. */
    void sanitize() {
        List<Cat> keep = new ArrayList<>();
        for (Cat cat : cats) {
            if (keep.size() >= MAX_CATS) break;
            cat.name = cut(cat.name, MAX_TEXT);
            cat.weight = clamp(cat.weight, -100, 100);
            cat.words = words(cat.words, MAX_WORDS);
            keep.add(cat);
        }
        cats = keep;
        never = words(never, MAX_NEVER);
        dwellMin = clamp(dwellMin, 1, 24 * 60);
        runMin = clamp(runMin, 0, 30 * 24 * 60);
        bonus = clamp(bonus, -100, 100);
        pauseMaxMin = clamp(pauseMaxMin, 1, 60);
        if (!AN.equals(newChannels) && !AUS.equals(newChannels) && !BEVORZUGT.equals(newChannels)) newChannels = AUS;
        List<String> af = new ArrayList<>();
        for (String n : adFree) if (af.size() < MAX_ADFREE && !n.trim().isEmpty()) af.add(cut(n.trim(), 100));
        adFree = af;
        kidsChannels = names(kidsChannels);
        kidsDenied = names(kidsDenied);
        kidsDenied.removeAll(kidsChannels);   // ein Sender ist entweder erlaubt oder gesperrt
        kidsBlock = words(kidsBlock, MAX_NEVER);
        Map<String, String> ch = new LinkedHashMap<>();
        for (Map.Entry<String, String> e : channels.entrySet()) {
            if (ch.size() >= MAX_CHANNELS) break;
            String v = e.getValue();
            if (e.getKey().length() <= 100 && (AN.equals(v) || AUS.equals(v) || BEVORZUGT.equals(v))) ch.put(e.getKey(), v);
        }
        channels = ch;
        prefBonus.keySet().retainAll(channels.keySet());
        prefBonus.replaceAll((k, v) -> clamp(v, -100, 100));
        // nur ein Rechnername / eine IP (auch [IPv6]) mit optionalem Port – kein Pfad, keine Zugangsdaten
        if (fritz == null || !fritz.matches("[A-Za-z0-9.\\-]{1,253}(:\\d{1,5})?|\\[[0-9A-Fa-f:.]{2,45}\\](:\\d{1,5})?"))
            fritz = "fritz.box";
        tvInput = cut(tvInput == null ? "" : tvInput.trim(), 200);
        if (tvApp == null || !tvApp.trim().matches("([A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+)?")) tvApp = "";
        tvApp = tvApp.trim();
    }

    private static List<String> names(List<String> in) {
        List<String> out = new ArrayList<>();
        for (String n : in) {
            n = n == null ? "" : n.trim();
            if (out.size() < MAX_CHANNELS && !n.isEmpty() && n.length() <= 100 && !out.contains(n)) out.add(n);
        }
        return out;
    }

    private static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static String cut(String s, int n) {
        return s == null ? "" : s.length() > n ? s.substring(0, n) : s;
    }

    /** Woerter kuerzen; leere und reine "*"-Woerter (passen sonst auf jede Sendung) weglassen. */
    private static List<String> words(List<String> in, int max) {
        List<String> out = new ArrayList<>();
        for (String w : in) {
            if (out.size() >= max) break;
            w = cut(w == null ? "" : w.trim(), MAX_TEXT);
            if (!w.replace("*", "").trim().isEmpty()) out.add(w);
        }
        return out;
    }

    JSONObject toJson() throws JSONException {
        JSONObject o = new JSONObject();
        JSONArray cats = new JSONArray();
        for (Cat cat : this.cats) {
            JSONObject co = new JSONObject();
            co.put("name", cat.name);
            co.put("gewicht", cat.weight);
            co.put("woerter", new JSONArray(cat.words));
            cats.put(co);
        }
        o.put("interessen", cats);
        o.put("aus", new JSONArray(never));
        o.put("verweilen_min", dwellMin);
        o.put("laufzeit_min", runMin);
        o.put("bonus_bevorzugt", bonus);
        o.put("neue_sender", newChannels);
        o.put("werbung_umgehen", avoidAds);
        o.put("ausweichen_bevorzugt", dodgePreferred);
        o.put("umschaltgrund_einblenden", showReason);
        o.put("fritzbox", fritz);
        o.put("tv_eingang", tvInput);
        o.put("tv_app", tvApp);
        o.put("werbepause_max_min", pauseMaxMin);
        o.put("werbefrei", new JSONArray(adFree));
        o.put("kinder_modus", kids);
        o.put("kinder_sender", new JSONArray(kidsChannels));
        o.put("kinder_sender_gesperrt", new JSONArray(kidsDenied));
        o.put("kinder_uebrige_erlaubt", kidsRestAllowed);
        o.put("kinder_sperrbegriffe", new JSONArray(kidsBlock));
        JSONArray on = new JSONArray(), nie = new JSONArray();
        JSONObject pref = new JSONObject();
        for (Map.Entry<String, String> e : channels.entrySet()) {
            if (AN.equals(e.getValue())) on.put(e.getKey());
            else if (AUS.equals(e.getValue())) nie.put(e.getKey());
            else pref.put(e.getKey(), bonusFor(e.getKey()));
        }
        o.put("sender_an", on);
        o.put("sender_bevorzugt", pref);
        o.put("sender_nie", nie);
        return o;
    }

    void save(Context c) {
        sanitize();
        try (FileOutputStream out = new FileOutputStream(file(c))) {
            out.write(toJson().toString(2).getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            Log.add(c, "Speichern fehlgeschlagen: " + e.getMessage());
        }
    }

    private static List<String> strings(JSONArray a) {
        List<String> l = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) l.add(a.optString(i));
        return l;
    }

    /** "a, b ,c" -> [a, b, c] */
    static List<String> splitList(String s) {
        List<String> l = new ArrayList<>();
        for (String p : s.split(",")) {
            p = p.trim();
            if (!p.isEmpty()) l.add(p);
        }
        return l;
    }
}
