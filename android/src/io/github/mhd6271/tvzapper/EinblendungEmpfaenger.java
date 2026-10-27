package io.github.mhd6271.tvzapper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Einblendung von aussen, z. B. aus Home Assistant per adb:
 *  am broadcast -a io.github.mhd6271.tvzapper.EINBLENDEN -n io.github.mhd6271.tvzapper/.EinblendungEmpfaenger
 *     --es text '<Text>' --ei ms 6000
 *  Nur fuer Absender mit DUMP-Recht (adb-Shell, System), damit andere Apps keine Einblendungen ausloesen. */
public class EinblendungEmpfaenger extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String text = i.getStringExtra("text");
        if (text == null || text.trim().isEmpty()) return;
        Banner.show(c, text.trim(), i.getIntExtra("ms", 6000));
    }
}
