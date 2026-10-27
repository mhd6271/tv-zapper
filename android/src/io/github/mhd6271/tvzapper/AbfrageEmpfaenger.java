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
 *     [--es was jetzt|liste]
 *  am broadcast -a io.github.mhd6271.tvzapper.UMSCHALTEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger
 *     --es nr 167 | --es sender "ProSieben MAXX HD"  [--es text "Einblendung"]
 *
 *  Antwort als JSON in den Ergebnisdaten (Ausgabe von am broadcast: data="{...}").
 *  Nur fuer Absender mit DUMP-Recht (adb-Shell, System). */
public class AbfrageEmpfaenger extends BroadcastReceiver {
    static final String ABFRAGEN = "io.github.mhd6271.tvzapper.ABFRAGEN";
    static final String UMSCHALTEN = "io.github.mhd6271.tvzapper.UMSCHALTEN";

    @Override
    public void onReceive(Context c, Intent i) {
        JSONObject out = new JSONObject();
        try {
            if (UMSCHALTEN.equals(i.getAction())) umschalten(c, i, out);
            else abfragen(c, i, out);
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
        WerbeWaechter w = ZapperService.waechter;
        out.put("werbe_sensor", w == null ? JSONObject.NULL : w.status());
        out.put("werbung", w == null || !w.knowsPause() ? JSONObject.NULL : w.isPause());
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
        if (ok && text != null && !text.trim().isEmpty()) Banner.show(c, text.trim(), 6000);
        Log.add(c, "Von außen umgeschaltet auf " + target.number + " " + target.name + (ok ? "" : " (nicht bestätigt)"));
        out.put("ok", ok);
        out.put("nr", target.number);
        out.put("sender", target.name);
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
