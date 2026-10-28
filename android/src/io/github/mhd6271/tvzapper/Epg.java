package io.github.mhd6271.tvzapper;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.media.tv.TvContract;
import android.provider.Settings;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Sender und laufende Sendungen aus der Android-TV-Datenbank (TvContract), gefuellt vom Tuner des Fernsehers.
 *  Geprueft auf einem TCL Google TV; Eingang und Fernseh-App werden erkannt, nicht fest vorgegeben. */
final class Epg {
    private static String input, tvApp;
    private static boolean tvAppResolved;

    /** Tuner-Eingang: Einstellung "tv_eingang", sonst der Tuner-Eingang (TYPE_TUNER) mit den meisten Sendern,
     *  sonst der Eingang mit den meisten Sendern ueberhaupt. Am TCL: com.tcl.tvinput/.TunerInputService/HW2. */
    // KOMPAT: Ein Eingang wird genommen: Geraete mit getrennten Tuner-Eingaengen (DVB-C/S/T) oder Sendern bei
    //   Nicht-Tuner-Eingaengen (IPTV, Zattoo, waipu) sehen nur einen Teil – Einstellung tv_eingang setzen.
    static synchronized String tunerInput(Context c) {
        String cfg = Config.load(c).tvInput;
        if (!cfg.isEmpty()) return cfg;
        if (input != null) return input;
        java.util.Map<String, Integer> count = new java.util.HashMap<>();
        try (Cursor cur = c.getContentResolver().query(TvContract.Channels.CONTENT_URI,
                new String[]{TvContract.Channels.COLUMN_INPUT_ID}, null, null, null)) {
            while (cur != null && cur.moveToNext()) count.merge(nz(cur.getString(0)), 1, Integer::sum);
        } catch (Exception ignored) {
        }
        java.util.Set<String> tuners = new java.util.HashSet<>();
        try {
            for (android.media.tv.TvInputInfo info : c.getSystemService(android.media.tv.TvInputManager.class).getTvInputList())
                if (info.getType() == android.media.tv.TvInputInfo.TYPE_TUNER) tuners.add(info.getId());
        } catch (Exception ignored) {
        }
        String best = null;
        int bestN = 0;
        for (int pass = 0; pass < 2 && best == null; pass++)
            for (java.util.Map.Entry<String, Integer> e : count.entrySet())
                if ((pass == 1 || tuners.contains(e.getKey())) && !e.getKey().isEmpty() && e.getValue() > bestN) {
                    best = e.getKey();
                    bestN = e.getValue();
                }
        if (best != null) input = best;
        return best == null ? "" : best;
    }

    /** App, die einen Sender abspielt (ACTION_VIEW auf eine Sender-Adresse): Einstellung "tv_app", sonst vom
     *  System erfragt. Am TCL: com.tcl.tv. null, wenn unbekannt. */
    // KOMPAT: Ist keine Fernseh-App Standard, liefert resolveActivity die Auswahl ("android") -> null; dann gilt das
    //   Fernsehbild nie als vorn und der Zapper schaltet nie. Andere TV-Apps (z. B. Live Channels) nehmen ACTION_VIEW evtl. nicht an.
    static synchronized String tvPackage(Context c) {
        String cfg = Config.load(c).tvApp;
        if (!cfg.isEmpty()) return cfg;
        if (tvAppResolved) return tvApp;
        List<Channel> chs = channels(c);
        if (chs.isEmpty()) return null;
        android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_VIEW,
                TvContract.buildChannelUri(chs.get(0).id));
        android.content.pm.ResolveInfo ri = c.getPackageManager().resolveActivity(i, 0);
        if (ri != null && ri.activityInfo != null && !"android".equals(ri.activityInfo.packageName))
            tvApp = ri.activityInfo.packageName;
        tvAppResolved = true;
        return tvApp;
    }

    static final class Channel {
        long id;
        String number = "", name = "";
        boolean browsable;
        /** Vorgabe "an". TCL markiert die Sender seiner Favoritenliste (dort "Favorit1") mit
         *  internal_provider_flag2 = 1 (am Geraet 27.10.2026: 37 Sender, alle frei; verschluesselte wie Sky 0).
         *  Markiert der Fernseher keinen Sender so, gelten alle sichtbaren (browsable) Sender als Vorgabe. */
        boolean favorite;
    }

    static final class Program {
        String title = "", episode = "", desc = "", genre = "";
        long start, end;

        String text() {
            return String.join(" ", title, episode, genre, desc);
        }
    }

    /** Alle Sender des Tuner-Eingangs, nach Nummer sortiert. */
    static List<Channel> channels(Context c) {
        List<Channel> list = new ArrayList<>();
        String[] proj = {TvContract.Channels._ID, TvContract.Channels.COLUMN_DISPLAY_NUMBER,
                TvContract.Channels.COLUMN_DISPLAY_NAME, TvContract.Channels.COLUMN_BROWSABLE,
                TvContract.Channels.COLUMN_INTERNAL_PROVIDER_FLAG2};
        try (Cursor cur = c.getContentResolver().query(TvContract.buildChannelsUriForInput(tunerInput(c)), proj,
                null, null, null)) {
            if (cur == null) return list;
            while (cur.moveToNext()) {
                Channel ch = new Channel();
                ch.id = cur.getLong(0);
                ch.number = nz(cur.getString(1));
                ch.name = nz(cur.getString(2));
                ch.browsable = cur.getInt(3) != 0;
                // KOMPAT: internal_provider_flag2 = Favorit ist TCL-eigen; andere Hersteller nutzen das Feld anders
                //   (oder gar nicht) – dann stimmen die Vorgaben an/aus nicht.
                ch.favorite = !cur.isNull(4) && cur.getInt(4) == 1;
                list.add(ch);
            }
        }
        boolean anyFav = false;
        for (Channel ch : list) anyFav |= ch.favorite;
        if (!anyFav) for (Channel ch : list) ch.favorite = ch.browsable;
        list.sort(Comparator.comparingLong(ch -> num(ch.number)));
        return list;
    }

    /** Die gerade laufende Sendung eines Senders oder null. */
    static Program current(Context c, long channelId) {
        long now = System.currentTimeMillis();
        String[] proj = {TvContract.Programs.COLUMN_TITLE, TvContract.Programs.COLUMN_EPISODE_TITLE,
                TvContract.Programs.COLUMN_SHORT_DESCRIPTION, TvContract.Programs.COLUMN_CANONICAL_GENRE,
                TvContract.Programs.COLUMN_BROADCAST_GENRE, TvContract.Programs.COLUMN_START_TIME_UTC_MILLIS,
                TvContract.Programs.COLUMN_END_TIME_UTC_MILLIS};
        ContentResolver cr = c.getContentResolver();
        // KOMPAT: Sendungen gibt es nur, wenn der Tuner das EPG in TvContract schreibt; manche Hersteller halten es intern
        //   (dann ueberall leer, kaum Punkte).
        try (Cursor cur = cr.query(TvContract.buildProgramsUriForChannel(channelId, now, now), proj,
                null, null, null)) {
            if (cur == null) return null;
            while (cur.moveToNext()) {
                if (cur.getLong(5) > now || cur.getLong(6) <= now) continue;
                Program p = new Program();
                p.title = nz(cur.getString(0));
                p.episode = nz(cur.getString(1));
                p.desc = nz(cur.getString(2));
                // KOMPAT: Genre: TCL liefert DVB-Codes als Zahl ("32"), andere Geraete Texte ("MOVIES") oder nichts; Beschreibungen
                //   fehlen bei manchen Tunern ganz – Kategorie-Woerter treffen dann anders.
                p.genre = (nz(cur.getString(3)) + " " + nz(cur.getString(4))).trim();
                p.start = cur.getLong(5);
                p.end = cur.getLong(6);
                return p;
            }
        }
        return null;
    }

    /** Zuletzt von der App umgeschalteter Sender – Rueckfall, wo der Fernseher den laufenden Sender nicht meldet. */
    static volatile long lastTuned = -1;

    /** Gerade laufender Sender (TvContract-_id). TCL meldet ihn in Settings.Global "recent_play_channel_id"
     *  (-1, solange das Fernsehbild nicht vorn ist); andere Fernseher nicht oeffentlich – dann der zuletzt von
     *  der App gewaehlte Sender (selbst Umschalten bemerkt die App dort nicht). */
    static long currentChannelId(Context c) {
        String v = null;
        try {
            // KOMPAT: TCL-eigener Schluessel. Anderswo null -> lastTuned: selbst Umschalten bemerkt die App nicht, der
            //   Werbe-Sensor beobachtet dann den falschen Sender, und tuneTo() meldet jedes Umschalten als bestaetigt.
            v = Settings.Global.getString(c.getContentResolver(), "recent_play_channel_id");
        } catch (Exception ignored) {
        }
        if (v == null) return lastTuned;
        try {
            return Long.parseLong(v.trim());
        } catch (Exception e) {
            return lastTuned;
        }
    }

    /** Fuer "Einmal pruefen": was die Datenbank ueber die Sender weiss (Spalten, Anzahl), und ob der aktuelle
     *  Sender lesbar ist. */
    static void diagnose(Context c) {
        try {
            Log.add(c, "recent_play_channel_id = " + Settings.Global.getString(c.getContentResolver(), "recent_play_channel_id"));
        } catch (Exception e) {
            Log.add(c, "recent_play_channel_id nicht lesbar: " + e);
        }
        try (Cursor cur = c.getContentResolver().query(TvContract.Channels.CONTENT_URI, null, null, null, null)) {
            if (cur == null) return;
            Log.add(c, "TvContract: " + cur.getCount() + " Sender, Spalten " + String.join(",", cur.getColumnNames()));
            java.util.Map<String, Integer> byInput = new java.util.TreeMap<>();
            int n = 0;
            while (cur.moveToNext()) {
                String in = cur.getString(cur.getColumnIndex("input_id")) + " browsable=" + cur.getString(cur.getColumnIndex("browsable"));
                byInput.merge(in, 1, Integer::sum);
                if (n++ < 400) {
                    StringBuilder b = new StringBuilder("  ");
                    for (String col : new String[]{"_id", "display_number", "display_name", "browsable", "searchable",
                            "locked", "type", "service_type", "internal_provider_flag1", "internal_provider_flag2",
                            "internal_provider_flag3", "internal_provider_flag4", "internal_provider_id"}) {
                        int i = cur.getColumnIndex(col);
                        if (i >= 0) b.append(col).append('=').append(cur.getString(i)).append(' ');
                    }
                    int ipd = cur.getColumnIndex("internal_provider_data");
                    if (ipd >= 0 && cur.getType(ipd) == Cursor.FIELD_TYPE_BLOB && cur.getBlob(ipd) != null) {
                        byte[] blob = cur.getBlob(ipd);
                        b.append("ipd=").append(new String(blob, 0, Math.min(blob.length, 200),
                                java.nio.charset.StandardCharsets.ISO_8859_1).replaceAll("[^\\x20-\\x7e]", "."));
                    }
                    android.util.Log.i("TVZapperDiag", b.toString());
                }
            }
            Log.add(c, "nach Eingang: " + byInput);
        } catch (Exception e) {
            Log.add(c, "Diagnose fehlgeschlagen: " + e);
        }
    }

    static long num(String s) {
        try {
            // KOMPAT: Nummern wie "1-2"/"1.1" (ATSC, Unterkanaele) zaehlen nur mit dem ersten Teil – Reihenfolge dann ungenau.
            return Long.parseLong(s.replaceAll("[^0-9].*", ""));
        } catch (Exception e) {
            return Long.MAX_VALUE;
        }
    }

    private static String nz(String s) {
        return s == null ? "" : s.trim();
    }
}
