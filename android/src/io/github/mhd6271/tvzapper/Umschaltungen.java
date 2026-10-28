package io.github.mhd6271.tvzapper;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Die letzten Umschaltungen der App mit Grund in umschaltungen.json – fuer ABFRAGEN (Logbuch in Home Assistant).
 *  Gruende: interesse, werbung, zurueck, zurueck_zeitgrenze, zurueck_fehlalarm, von_aussen. */
final class Umschaltungen {
    static final String INTERESSE = "interesse", WERBUNG = "werbung", ZURUECK = "zurueck",
            ZURUECK_ZEITGRENZE = "zurueck_zeitgrenze", ZURUECK_FEHLALARM = "zurueck_fehlalarm", VON_AUSSEN = "von_aussen";
    private static final int MAX = 20;
    private static long lastId;

    private static File file(Context c) {
        return new File(c.getFilesDir(), "umschaltungen.json");
    }

    static synchronized JSONArray read(Context c) {
        try {
            return new JSONArray(new String(Files.readAllBytes(file(c).toPath()), StandardCharsets.UTF_8));
        } catch (Exception e) {
            return new JSONArray();
        }
    }

    /** Eine Umschaltung merken; Punkte und Kategorien aus der laufenden Sendung des Zielsenders. */
    static synchronized JSONObject add(Context c, String reason, Epg.Channel from, Epg.Channel to, String text, boolean ok) {
        return add(c, reason, from, to, text, null, ok);
    }

    /** extra: Erklaerung von aussen (Home Assistant), Zeilen mit " | " getrennt. */
    static synchronized JSONObject add(Context c, String reason, Epg.Channel from, Epg.Channel to, String text,
                                       String extra, boolean ok) {
        JSONObject o = new JSONObject();
        try {
            JSONArray all = read(c);
            long now = System.currentTimeMillis();
            if (lastId == 0 && all.length() > 0) lastId = all.getJSONObject(all.length() - 1).optLong("id");
            long id = Math.max(now, lastId + 1);   // eindeutig, auch ueber Neustarts der App
            lastId = id;
            Config cfg = Config.load(c);
            Epg.Program p = Epg.current(c, to.id);
            Scorer.Result r = Scorer.score(to.name + " " + (p == null ? "" : p.text()), cfg);
            boolean pref = Config.BEVORZUGT.equals(cfg.state(to));
            Integer bonus = pref && r.points > 0 ? cfg.bonusFor(to.name) : null;
            JSONArray cats = new JSONArray();
            for (Config.Cat cat : cfg.cats) {
                if (r.hits.contains(cat.name)) cats.put(new JSONObject().put("name", cat.name).put("punkte", cat.weight));
            }
            o.put("id", id);
            o.put("zeit", new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.ROOT).format(new Date(now)));
            o.put("grund", reason);
            JSONObject vo = null;
            if (from != null) {
                Epg.Program fp = Epg.current(c, from.id);
                Scorer.Result fr = Scorer.score(from.name + " " + (fp == null ? "" : fp.text()), cfg);
                int fb = Config.BEVORZUGT.equals(cfg.state(from)) && fr.points > 0 ? cfg.bonusFor(from.name) : 0;
                vo = new JSONObject().put("nr", from.number).put("sender", from.name)
                        .put("punkte", fr.points < 0 ? JSONObject.NULL : fr.points + fb);
            }
            o.put("von", vo == null ? JSONObject.NULL : vo);
            o.put("nr", to.number);
            o.put("sender", to.name);
            o.put("sendung", p == null ? JSONObject.NULL : p.title);
            o.put("punkte", r.points < 0 ? JSONObject.NULL : r.points + (bonus == null ? 0 : bonus));
            o.put("kategorien", cats);
            o.put("bevorzugt", pref);
            o.put("bevorzugt_bonus", bonus == null ? JSONObject.NULL : bonus);
            o.put("bestaetigt", ok);
            o.put("text", text);
            if (extra != null && !extra.trim().isEmpty()) o.put("erklaerung", extra.trim());
            all.put(o);
            JSONArray keep = new JSONArray();
            for (int i = Math.max(0, all.length() - MAX); i < all.length(); i++) keep.put(all.get(i));
            Files.write(file(c).toPath(), keep.toString(2).getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            Log.add(c, "Umschaltung nicht gespeichert: " + e);
        }
        return o;
    }

    /** Debug-Einblendung: Sender, Grund und Punkte einzeln mit Summe. */
    static String explain(JSONObject e) {
        StringBuilder b = new StringBuilder();
        b.append("→ ").append(e.optString("nr")).append(' ').append(e.optString("sender"));
        if (!e.isNull("sendung")) b.append(": ").append(e.optString("sendung"));
        JSONObject von = e.optJSONObject("von");
        String from = von == null ? "dem vorigen Sender" : von.optString("sender");
        String r = e.optString("grund");
        b.append("\nGrund: ");
        if (INTERESSE.equals(r)) b.append("Zapper-Runde – passt am besten");
        else if (WERBUNG.equals(r)) b.append("Werbung auf ").append(from).append(" umgangen – ")
                .append(e.optBoolean("bevorzugt") ? "bevorzugter Sender ★" : "werbefreier Ausweichsender");
        else if (ZURUECK.equals(r)) b.append("Werbung vorbei – zurück");
        else if (ZURUECK_ZEITGRENZE.equals(r)) b.append("Werbepause dauert zu lange (Zeitgrenze) – zurück");
        else if (ZURUECK_FEHLALARM.equals(r)) b.append("doch keine Werbung (neue Logo-Variante) – zurück");
        else if (VON_AUSSEN.equals(r)) b.append("Home Assistant");
        else b.append(r);
        if (e.has("erklaerung")) {
            for (String line : e.optString("erklaerung").split("\\s*\\|\\s*")) b.append("\n• ").append(line);
            return b.toString();
        }
        JSONArray cats = e.optJSONArray("kategorien");
        if (cats != null) for (int i = 0; i < cats.length(); i++) {
            JSONObject k = cats.optJSONObject(i);
            b.append("\n• ").append(k.optString("name")).append(" +").append(k.optInt("punkte"));
        }
        if (!e.isNull("bevorzugt_bonus")) b.append("\n• ★ bevorzugter Sender +").append(e.optInt("bevorzugt_bonus"));
        if (e.isNull("punkte")) b.append("\n= ausgeschlossen (Wort aus „Nie“)");
        else b.append("\n= ").append(points(e.optInt("punkte")));
        if (von != null) b.append("\nvorher: ").append(von.optString("nr")).append(' ').append(von.optString("sender"))
                .append(von.isNull("punkte") ? " (ausgeschlossen)" : " (" + points(von.optInt("punkte")) + ")");
        return b.toString();
    }

    private static String points(int n) {
        return n + (n == 1 ? " Punkt" : " Punkte");
    }

    static Epg.Channel channel(Context c, long id) {
        for (Epg.Channel ch : Epg.channels(c)) if (ch.id == id) return ch;
        return null;
    }
}
