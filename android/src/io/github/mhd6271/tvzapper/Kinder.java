package io.github.mhd6271.tvzapper;

import android.content.Context;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/** Kinder-Modus: nur erlaubte Sender (eigens erlaubt oder, wenn die uebrigen erlaubt sind, nicht eigens gesperrt),
 *  keine Sendung mit einem Sperrbegriff (Titel, Folge, Genre, Beschreibung; Abgleich wie bei Scorer, * am Ende = Wortanfang). Der Dienst prueft alle 2,5 s und schaltet weg. */
final class Kinder {
    private static final Random RND = new Random();

    /** null = darf laufen, sonst der Grund fuers Wegschalten (fuer Protokoll und Einblendung). */
    static String verbot(Context c, Config cfg, Epg.Channel ch) {
        if (ch == null) return "unbekannter Sender";
        if (!allowed(cfg, ch.name)) return ch.name + " ist nicht erlaubt";
        Epg.Program p = Epg.current(c, ch.id);
        String w = sperrwort(cfg, p);
        return w == null ? null : "auf " + ch.name + " läuft „" + p.title + "“ (Sperrbegriff „" + w + "“)";
    }

    /** Sender selbst erlaubt (ohne Blick aufs Programm)? */
    static boolean allowed(Config cfg, String name) {
        return cfg.kidsChannels.contains(name) || cfg.kidsRestAllowed && !cfg.kidsDenied.contains(name);
    }

    static boolean ok(Context c, Config cfg, Epg.Channel ch) {
        return !cfg.kids || verbot(c, cfg, ch) == null;
    }

    /** Erster Sperrbegriff, der auf die Sendung passt, sonst null. Ist ein Begriff der Name einer
     *  Interessen-Kategorie, sperren auch deren Woerter (z. B. "Krimi"). */
    static String sperrwort(Config cfg, Epg.Program p) {
        if (p == null || cfg.kidsBlock.isEmpty()) return null;
        String text = p.text().toLowerCase(Locale.GERMAN);
        for (String w : cfg.kidsBlock) {
            if (Scorer.any(Collections.singletonList(w), text)) return w;
            for (Config.Cat cat : cfg.cats)
                if (cat.name.trim().equalsIgnoreCase(w.trim()) && Scorer.any(cat.words, text)) return w;
        }
        return null;
    }

    /** Zufaelliger erlaubter Sender ohne Sperrbegriff (nicht der laufende), moeglichst ohne Werbung; null = keiner. */
    static Epg.Channel ersatz(Context c, Config cfg, long except) {
        List<Epg.Channel> ok = new ArrayList<>(), noAd = new ArrayList<>();
        for (Epg.Channel ch : Epg.channels(c)) {
            if (ch.id == except || verbot(c, cfg, ch) != null) continue;
            ok.add(ch);
            if (!WerbeWaechter.inAd(ch.name)) noAd.add(ch);
        }
        List<Epg.Channel> from = noAd.isEmpty() ? ok : noAd;
        return from.isEmpty() ? null : from.get(RND.nextInt(from.size()));
    }
}
