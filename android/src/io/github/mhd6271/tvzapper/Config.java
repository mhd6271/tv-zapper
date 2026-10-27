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
    String fritz = "fritz.box";
    /** Leer = automatisch erkennen. */
    String tvInput = "", tvApp = "";
    /** Spaetestens nach so vielen Minuten zurueck zum Hauptsender, auch wenn der Sensor nichts meldet
     *  (gemessene Durchschnittsdauer des Senders + 1 min, wenn bekannt). */
    int pauseMaxMin = 6;
    /** Werbefreie Ausweichsender, bei gleicher Punktzahl gilt die Reihenfolge. */
    List<String> adFree = new ArrayList<>(java.util.Arrays.asList("ZDFinfo HD", "zdf_neo HD", "arte HD",
            "tagesschau24 HD", "3sat HD", "phoenix HD", "WDR HD Köln", "hr-fernsehen HD"));

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
                    json = new String(in.readAllBytes(), StandardCharsets.UTF_8);
                }
            }
            return parse(new JSONObject(json));
        } catch (Exception e) {
            Log.add(c, "Einstellungen nicht lesbar: " + e.getMessage());
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
        cfg.fritz = o.optString("fritzbox", "fritz.box");
        cfg.tvInput = o.optString("tv_eingang", "");
        cfg.tvApp = o.optString("tv_app", "");
        cfg.pauseMaxMin = o.optInt("werbepause_max_min", 6);
        if (o.has("werbefrei")) cfg.adFree = strings(o.optJSONArray("werbefrei"));
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
        return cfg;
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
        o.put("fritzbox", fritz);
        o.put("tv_eingang", tvInput);
        o.put("tv_app", tvApp);
        o.put("werbepause_max_min", pauseMaxMin);
        o.put("werbefrei", new JSONArray(adFree));
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
