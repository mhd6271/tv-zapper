package io.github.mhd6271.tvzapper;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.media.tv.TvContract;
import android.provider.Settings;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Sender und laufende Sendungen aus der Android-TV-Datenbank (TvContract), gefuellt vom TCL-Tuner. */
final class Epg {
    static final String TUNER = "com.tcl.tvinput/.TunerInputService/HW2";

    static final class Channel {
        long id;
        String number = "", name = "";
        boolean browsable;
        /** TCL markiert die Sender der Liste Favorit1 mit internal_provider_flag2 = 1 (am Geraet 27.10.2026:
         *  37 Sender, alle frei; verschluesselte wie Sky haben 0). */
        boolean favorite;
    }

    static final class Program {
        String title = "", episode = "", desc = "", genre = "";

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
        try (Cursor cur = c.getContentResolver().query(TvContract.buildChannelsUriForInput(TUNER), proj,
                null, null, null)) {
            if (cur == null) return list;
            while (cur.moveToNext()) {
                Channel ch = new Channel();
                ch.id = cur.getLong(0);
                ch.number = nz(cur.getString(1));
                ch.name = nz(cur.getString(2));
                ch.browsable = cur.getInt(3) != 0;
                ch.favorite = !cur.isNull(4) && cur.getInt(4) == 1;
                list.add(ch);
            }
        }
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
        try (Cursor cur = cr.query(TvContract.buildProgramsUriForChannel(channelId, now, now), proj,
                null, null, null)) {
            if (cur == null) return null;
            while (cur.moveToNext()) {
                if (cur.getLong(5) > now || cur.getLong(6) <= now) continue;
                Program p = new Program();
                p.title = nz(cur.getString(0));
                p.episode = nz(cur.getString(1));
                p.desc = nz(cur.getString(2));
                p.genre = (nz(cur.getString(3)) + " " + nz(cur.getString(4))).trim();
                return p;
            }
        }
        return null;
    }

    /** Zuletzt vom TCL-Fernsehen gespielter Sender (TvContract-_id), -1 wenn unbekannt. */
    static long currentChannelId(Context c) {
        try {
            return Long.parseLong(Settings.Global.getString(c.getContentResolver(), "recent_play_channel_id"));
        } catch (Exception e) {
            return -1;
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
            return Long.parseLong(s.replaceAll("[^0-9].*", ""));
        } catch (Exception e) {
            return Long.MAX_VALUE;
        }
    }

    private static String nz(String s) {
        return s == null ? "" : s.trim();
    }
}
