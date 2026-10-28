package io.github.mhd6271.tvzapper;

import android.content.Context;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Protokoll: logcat (Tag TVZapper) und die letzten Zeilen in protokoll.txt fuer die Anzeige in der App. */
final class Log {
    private static final int KEEP = 300;

    static synchronized void add(Context c, String msg) {
        if (msg.length() > 500) msg = msg.substring(0, 500) + " …";   // fremde Texte (Fehler, Sendernamen) begrenzen
        android.util.Log.i("TVZapper", msg);
        String line = new SimpleDateFormat("dd.MM. HH:mm:ss", Locale.GERMANY).format(new Date()) + "  " + msg;
        List<String> lines = read(c);
        lines.add(line);
        if (lines.size() > KEEP) lines = lines.subList(lines.size() - KEEP, lines.size());
        try (FileOutputStream out = new FileOutputStream(file(c))) {
            out.write((String.join("\n", lines) + "\n").getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    static synchronized List<String> read(Context c) {
        try {
            return new ArrayList<>(Files.readAllLines(file(c).toPath(), StandardCharsets.UTF_8));
        } catch (Exception e) {
            return new ArrayList<>();
        }
    }

    private static File file(Context c) {
        return new File(c.getFilesDir(), "protokoll.txt");
    }
}
