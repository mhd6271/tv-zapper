package io.github.mhd6271.tvzapper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.media.tv.TvContract;
import android.os.PowerManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Schnittstelle fuer Home Assistant & Co. per adb – liest aus der Programmdatenbank, ohne Tasten:
 *
 *  am broadcast -a io.github.mhd6271.tvzapper.ABFRAGEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger
 *     [--es was jetzt|liste|pausen|sender|logos]
 *  am broadcast -a io.github.mhd6271.tvzapper.UMSCHALTEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger
 *     --es nr 167 | --es sender "ProSieben MAXX HD"  [--es text "Einblendung"]  [--es grund "Zeile 1 | Zeile 2"]
 *
 *  Antwort als JSON in den Ergebnisdaten (Ausgabe von am broadcast: data="{...}").
 *  Nur fuer Absender mit DUMP-Recht (adb-Shell, System). */
public class AbfrageEmpfaenger extends BroadcastReceiver {
    static final String ABFRAGEN = "io.github.mhd6271.tvzapper.ABFRAGEN";
    static final String UMSCHALTEN = "io.github.mhd6271.tvzapper.UMSCHALTEN";
    /** --es sender "ProSieben MAXX HD" [--el von <ms>] [--el bis <ms>] [--ez alt true] – siehe PauseStats.delete */
    /** --es ausweichen_bevorzugt true|false  [--es werbung_umgehen true|false] [--es umschaltgrund_einblenden true|false] */
    static final String EINSTELLEN = "io.github.mhd6271.tvzapper.EINSTELLEN";
    static final String PAUSEN_LOESCHEN = "io.github.mhd6271.tvzapper.PAUSEN_LOESCHEN";
    /** [--ez nur_lesen true] – Zapper-Dienst starten wie mit „Start“ in der App, z. B. nach einem Update */
    static final String STARTEN = "io.github.mhd6271.tvzapper.STARTEN";

    @Override
    public void onReceive(Context c, Intent i) {
        JSONObject out = new JSONObject();
        try {
            if (UMSCHALTEN.equals(i.getAction())) umschalten(c, i, out);
            else if (STARTEN.equals(i.getAction())) {
                boolean ro = i.getBooleanExtra("nur_lesen", false);
                c.startForegroundService(new Intent(c, ZapperService.class).setAction(ZapperService.ACTION_START)
                        .putExtra(ZapperService.EXTRA_READ_ONLY, ro));
                Log.add(c, "Zapper von außen gestartet" + (ro ? " (nur lesen)" : ""));
                out.put("ok", true);
                out.put("nur_lesen", ro);
            }
            else if (EINSTELLEN.equals(i.getAction())) {
                Config cfg = Config.load(c);
                String ab = i.getStringExtra("ausweichen_bevorzugt"), wu = i.getStringExtra("werbung_umgehen"),
                        ug = i.getStringExtra("umschaltgrund_einblenden");
                if (ab == null && wu == null && ug == null) throw new IllegalArgumentException("nichts zu setzen");
                if (ab != null) cfg.dodgePreferred = parseBool(ab);
                if (wu != null) cfg.avoidAds = parseBool(wu);
                if (ug != null) cfg.showReason = parseBool(ug);
                cfg.save(c);
                out.put("ok", true);
                out.put("ausweichen_bevorzugt", cfg.dodgePreferred);
                out.put("werbung_umgehen", cfg.avoidAds);
                out.put("umschaltgrund_einblenden", cfg.showReason);
                Log.add(c, "Einstellung von außen: ausweichen_bevorzugt=" + cfg.dodgePreferred + ", werbung_umgehen=" + cfg.avoidAds
                        + ", umschaltgrund_einblenden=" + cfg.showReason);
            } else if (PAUSEN_LOESCHEN.equals(i.getAction())) {
                String ch = i.getStringExtra("sender");
                if (ch == null) throw new IllegalArgumentException("sender fehlt");
                JSONObject before = PauseStats.toJson(c).optJSONObject(ch);
                out.put("vorher", before == null ? JSONObject.NULL : before);
                out.put("entfernt", PauseStats.delete(c, ch, i.getLongExtra("von", 0), i.getLongExtra("bis", 0),
                        i.getBooleanExtra("alt", false)));
                JSONObject after = PauseStats.toJson(c).optJSONObject(ch);
                out.put("nachher", after == null ? JSONObject.NULL : after);
                Log.add(c, "Pausenstatistik " + ch + ": " + out.getInt("entfernt") + " Einträge entfernt (von außen)");
            } else abfragen(c, i, out);
        } catch (Exception e) {
            put(out, "fehler", e.toString());
        }
        setResultCode(out.has("fehler") ? 1 : 0);
        setResultData(out.toString());
    }

    private static void abfragen(Context c, Intent i, JSONObject out) throws Exception {
        String was = i.getStringExtra("was");
        Config cfg = Config.load(c);
        String fg = ZapperService.foregroundApp(c);
        String tvApp = Epg.tvPackage(c);
        boolean on = c.getSystemService(PowerManager.class).isInteractive();
        out.put("zeit", iso(System.currentTimeMillis()));
        out.put("bildschirm_an", on);
        out.put("vorn", fg == null ? JSONObject.NULL : fg);
        out.put("fernsehbild_vorn", on && fg != null && fg.equals(tvApp));
        out.put("zapper_laeuft", ZapperService.endAt > System.currentTimeMillis());
        out.put("werbung_umgehen", cfg.avoidAds);
        out.put("ausweichen_bevorzugt", cfg.dodgePreferred);
        out.put("umschaltgrund_einblenden", cfg.showReason);
        WerbeWaechter w = ZapperService.waechter;
        out.put("werbe_sensor", w == null ? JSONObject.NULL : w.status());
        out.put("werbung", w == null || !w.knowsPause() ? JSONObject.NULL : w.isPause());
        out.put("logos", WerbeWaechter.logoCount(c));
        long cur = Epg.currentChannelId(c);
        JSONObject jetzt = null;
        JSONArray liste = new JSONArray();
        boolean all = "liste".equals(was);
        for (Epg.Channel ch : Epg.channels(c)) {
            boolean isCur = ch.id == cur;
            String state = cfg.state(ch);
            if (!isCur && (!all || Config.AUS.equals(state))) continue;
            JSONObject o = channelJson(c, cfg, ch, state);
            if (isCur) jetzt = o;
            if (all && !Config.AUS.equals(state)) liste.put(o);
        }
        out.put("jetzt", jetzt == null ? JSONObject.NULL : jetzt);
        if (all) out.put("liste", liste);
        if ("pausen".equals(was)) out.put("pausen", PauseStats.toJson(c));
        if ("sender".equals(was)) {   // alle Sender des Tuners, auch ausgeschaltete, ohne Programm
            JSONArray alle = new JSONArray();
            for (Epg.Channel ch : Epg.channels(c)) {
                alle.put(new JSONObject().put("nr", ch.number).put("sender", ch.name).put("id", ch.id)
                        .put("zustand", cfg.state(ch)).put("sichtbar", ch.browsable).put("favorit", ch.favorite));
            }
            out.put("sender", alle);
        }
        if ("logos".equals(was)) out.put("logo_dateien", Logo.export(c));   // fuer logos_sichern.sh (Repo-Sicherung)
        out.put("umschaltungen", Umschaltungen.read(c));
    }

    private static JSONObject channelJson(Context c, Config cfg, Epg.Channel ch, String state) throws Exception {
        JSONObject o = new JSONObject();
        o.put("nr", ch.number);
        o.put("sender", ch.name);
        o.put("id", ch.id);
        o.put("zustand", state);
        Epg.Program p = Epg.current(c, ch.id);
        if (p != null) {
            o.put("sendung", p.title);
            o.put("folge", p.episode);
            o.put("genre", p.genre);
            o.put("beschreibung", p.desc);
            o.put("start", iso(p.start));
            o.put("ende", iso(p.end));
        }
        Scorer.Result r = Scorer.score(ch.name + " " + (p == null ? "" : p.text()), cfg);
        int pts = r.points + (Config.BEVORZUGT.equals(state) && r.points > 0 ? cfg.bonusFor(ch.name) : 0);
        o.put("punkte", pts);
        o.put("treffer", new JSONArray(r.hits));
        return o;
    }

    private static void umschalten(Context c, Intent i, JSONObject out) throws Exception {
        String nr = i.getStringExtra("nr"), name = i.getStringExtra("sender");
        Epg.Channel target = null;
        for (Epg.Channel ch : Epg.channels(c)) {
            if (nr != null && nr.trim().equals(ch.number) || name != null && name.trim().equalsIgnoreCase(ch.name)) {
                target = ch;
                break;
            }
        }
        if (target == null) {
            out.put("fehler", "Sender nicht gefunden: " + (nr != null ? nr : name));
            return;
        }
        Epg.Channel from = Umschaltungen.channel(c, Epg.currentChannelId(c));
        Intent v = new Intent(Intent.ACTION_VIEW, TvContract.buildChannelUri(target.id));
        String pkg = Epg.tvPackage(c);
        if (pkg != null) v.setPackage(pkg);
        v.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        c.startActivity(v);
        Epg.lastTuned = target.id;
        boolean ok = false;
        for (int k = 0; k < 8 && !ok; k++) {
            Thread.sleep(500);
            ok = Epg.currentChannelId(c) == target.id;
        }
        String text = i.getStringExtra("text");
        JSONObject e = Umschaltungen.add(c, Umschaltungen.VON_AUSSEN, from, target, text == null || text.trim().isEmpty()
                ? "Von außen umgeschaltet auf " + target.name : text.trim(), i.getStringExtra("grund"), ok);
        if (ok && Config.load(c).showReason) Banner.show(c, Umschaltungen.explain(e), 12000);
        else if (ok && text != null && !text.trim().isEmpty()) Banner.show(c, text.trim(), 6000);
        Log.add(c, "Von außen umgeschaltet auf " + target.number + " " + target.name + (ok ? "" : " (nicht bestätigt)"));
        out.put("ok", ok);
        out.put("nr", target.number);
        out.put("sender", target.name);
    }

    private static boolean parseBool(String v) {
        v = v.trim().toLowerCase(Locale.ROOT);
        if (v.equals("true") || v.equals("1") || v.equals("an") || v.equals("ja")) return true;
        if (v.equals("false") || v.equals("0") || v.equals("aus") || v.equals("nein")) return false;
        throw new IllegalArgumentException("ungültiger Wert: " + v);
    }

    private static void put(JSONObject o, String k, Object v) {
        try {
            o.put(k, v);
        } catch (Exception ignored) {
        }
    }

    private static String iso(long t) {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.ROOT).format(new Date(t));
    }
}
