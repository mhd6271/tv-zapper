package io.github.mhd6271.tvzapper;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/** Bewertung wie zapper.py: Woerter mit * am Ende passen als Wortanfang, je Kategorie zaehlt das Gewicht einmal,
 *  ein Wort aus "nie" macht die Sendung unbrauchbar (-1). */
final class Scorer {
    static final class Result {
        int points;
        List<String> hits = new ArrayList<>();
    }

    static Pattern wordRx(String w) {
        w = w.toLowerCase(Locale.GERMAN).trim();
        boolean prefix = w.endsWith("*");
        while (w.endsWith("*")) w = w.substring(0, w.length() - 1);
        String tail = prefix ? "" : "(?![a-zäöüß])";
        return Pattern.compile("(?<![a-zäöüß])" + Pattern.quote(w) + tail);
    }

    static boolean any(List<String> words, String text) {
        for (String w : words) {
            if (!w.trim().isEmpty() && wordRx(w).matcher(text).find()) return true;
        }
        return false;
    }

    static Result score(String text, Config cfg) {
        text = text.toLowerCase(Locale.GERMAN);
        Result r = new Result();
        if (any(cfg.never, text)) {
            r.points = -1;
            return r;
        }
        for (Config.Cat cat : cfg.cats) {
            if (any(cat.words, text)) {
                r.points += cat.weight;
                r.hits.add(cat.name);
            }
        }
        return r;
    }
}
