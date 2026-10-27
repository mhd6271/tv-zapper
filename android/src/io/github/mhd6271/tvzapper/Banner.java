package io.github.mhd6271.tvzapper;

import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.WindowManager;
import android.widget.TextView;

/** Kurze Einblendung im Fernsehbild nach dem Umschalten (Overlay-Fenster, braucht "Ueber anderen Apps einblenden"). */
final class Banner {
    private static final Handler main = new Handler(Looper.getMainLooper());

    static void show(Context ctx, String text, long ms) {
        Context c = ctx.getApplicationContext();   // Fenster soll die Activity ueberleben
        if (!Settings.canDrawOverlays(c)) {
            Log.add(c, "Einblendung nicht möglich – „Über anderen Apps“ ist nicht erlaubt");
            return;
        }
        main.post(() -> {
            WindowManager wm = c.getSystemService(WindowManager.class);
            TextView v = new TextView(c);
            float d = c.getResources().getDisplayMetrics().density;
            v.setText(text);
            v.setTextSize(22);
            v.setTextColor(Color.WHITE);
            v.setPadding((int) (24 * d), (int) (14 * d), (int) (24 * d), (int) (14 * d));
            GradientDrawable bg = new GradientDrawable();
            bg.setColor(Color.argb(220, 0x1B, 0x2A, 0x49));
            bg.setStroke((int) (2 * d), Color.rgb(0xF2, 0xB1, 0x34));
            bg.setCornerRadius(12 * d);
            v.setBackground(bg);
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                    WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                    PixelFormat.TRANSLUCENT);
            lp.gravity = Gravity.TOP | Gravity.START;
            lp.x = (int) (40 * d);
            lp.y = (int) (30 * d);
            try {
                wm.addView(v, lp);
                main.postDelayed(() -> {
                    try {
                        wm.removeView(v);
                    } catch (Exception ignored) {
                    }
                }, ms);
            } catch (Exception e) {
                Log.add(c, "Einblendung fehlgeschlagen: " + e.getMessage());
            }
        });
    }
}
