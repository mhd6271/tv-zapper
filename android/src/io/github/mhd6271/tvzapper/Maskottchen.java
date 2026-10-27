package io.github.mhd6271.tvzapper;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;

/** Kleiner Comic-Fernseher, der nach dem Start unten rechts ins Bild huepft, winkt und gruesst
 *  (Overlay-Fenster wie die Einblendung, braucht "Ueber anderen Apps einblenden"). Gezeichnet, keine Grafikdateien. */
final class Maskottchen extends View {
    static final long DAUER_MS = 6000;
    /** Ab hier rennt er nach rechts aus dem Bild und verblasst. */
    static final float RENNEN_AB = 3.6f;
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final long t0 = SystemClock.uptimeMillis();
    private final float d;

    private Maskottchen(Context c) {
        super(c);
        d = c.getResources().getDisplayMetrics().density;
    }

    static void show(Context ctx) {
        Context c = ctx.getApplicationContext();
        if (!Settings.canDrawOverlays(c)) return;
        Handler main = new Handler(Looper.getMainLooper());
        main.post(() -> {
            WindowManager wm = c.getSystemService(WindowManager.class);
            Maskottchen v = new Maskottchen(c);
            float d = v.d;
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams((int) (300 * d), (int) (260 * d),
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                    PixelFormat.TRANSLUCENT);
            lp.gravity = Gravity.BOTTOM | Gravity.END;
            lp.x = 0;   // am rechten Bildrand, damit er hinausrennen kann
            lp.y = (int) (20 * d);
            try {
                wm.addView(v, lp);
                main.postDelayed(() -> {
                    try {
                        wm.removeView(v);
                    } catch (Exception ignored) {
                    }
                }, DAUER_MS);
            } catch (Exception e) {
                Log.add(c, "Maskottchen nicht einblendbar: " + e.getMessage());
            }
        });
    }

    @Override
    protected void onDraw(Canvas cv) {
        float t = (SystemClock.uptimeMillis() - t0) / 1000f;   // Sekunden seit dem Erscheinen
        float W = getWidth(), H = getHeight();
        // Einblenden; beim Wegrennen langsam verblassen
        float run = Math.max(0f, t - RENNEN_AB);                       // Sekunden seit Rennbeginn
        float total = DAUER_MS / 1000f - RENNEN_AB;
        float alpha = Math.min(1f, t / 0.3f) * Math.max(0f, 1f - run / total);
        float dx = run * run * 260 * d;                                  // beschleunigt nach rechts
        float step = run > 0 ? (float) Math.sin(run * Math.PI * 7) : 0;  // Trippeln
        cv.save();
        cv.translate(dx, 0);
        if (run > 0) cv.rotate(8, W * 0.62f, H - 16 * d);                // nach vorn gelehnt
        // Huepfen: drei Spruenge, dann stehen
        float hop = t < 2.4f ? (float) Math.abs(Math.sin(t * Math.PI / 0.8)) * 34 * d : 0;
        // Stauchen beim Aufkommen
        float squash = t < 2.4f ? 1f - 0.08f * (float) Math.max(0, Math.cos(t * Math.PI / 0.4)) : 1f;
        // Winken ab 0,6 s
        float wave = t > 0.6f && run == 0 ? (float) Math.sin((t - 0.6f) * Math.PI * 3) * 28 : (run > 0 ? 40 : 0);

        int a = (int) (255 * alpha);
        float cx = W * 0.62f, base = H - 16 * d - hop;
        float bw = 130 * d, bh = 100 * d * squash;
        RectF body = new RectF(cx - bw / 2, base - bh - 18 * d, cx + bw / 2, base - 18 * d);

        // Schatten
        p.setColor(Color.argb((int) (90 * alpha * (1 - hop / (60 * d))), 0, 0, 0));
        cv.drawOval(new RectF(cx - 55 * d, H - 22 * d, cx + 55 * d, H - 10 * d), p);
        // Fuesse
        p.setColor(Color.argb(a, 0x1B, 0x2A, 0x49));
        float lift = 10 * d;
        cv.drawRoundRect(new RectF(cx - 40 * d, base - 20 * d - Math.max(0, step) * lift, cx - 18 * d,
                base - Math.max(0, step) * lift), 6 * d, 6 * d, p);
        cv.drawRoundRect(new RectF(cx + 18 * d, base - 20 * d - Math.max(0, -step) * lift, cx + 40 * d,
                base - Math.max(0, -step) * lift), 6 * d, 6 * d, p);
        // Antennen
        p.setStrokeWidth(5 * d);
        p.setStrokeCap(Paint.Cap.ROUND);
        cv.drawLine(cx - 10 * d, body.top, cx - 38 * d, body.top - 34 * d, p);
        cv.drawLine(cx + 10 * d, body.top, cx + 34 * d, body.top - 38 * d, p);
        p.setColor(Color.argb(a, 0xE8, 0x3F, 0x6F));
        cv.drawCircle(cx - 38 * d, body.top - 34 * d, 7 * d, p);
        p.setColor(Color.argb(a, 0x3F, 0xC8, 0xE8));
        cv.drawCircle(cx + 34 * d, body.top - 38 * d, 7 * d, p);
        // Winkender Arm (links vom Koerper, dreht um die Schulter)
        cv.save();
        float sx = body.left + 6 * d, sy = body.top + 34 * d;
        cv.rotate(-35 + wave, sx, sy);
        p.setColor(Color.argb(a, 0xF2, 0x8C, 0x28));
        p.setStrokeWidth(12 * d);
        cv.drawLine(sx, sy, sx - 44 * d, sy - 6 * d, p);
        p.setColor(Color.argb(a, 0xFF, 0xFF, 0xFF));
        cv.drawCircle(sx - 50 * d, sy - 7 * d, 11 * d, p);
        cv.restore();
        // Koerper
        p.setColor(Color.argb(a, 0xF2, 0xB1, 0x34));
        cv.drawRoundRect(body, 20 * d, 20 * d, p);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(4 * d);
        p.setColor(Color.argb(a, 0xC9, 0x7E, 0x10));
        cv.drawRoundRect(body, 20 * d, 20 * d, p);
        p.setStyle(Paint.Style.FILL);
        // Bildschirm
        RectF scr = new RectF(body.left + 14 * d, body.top + 12 * d, body.right - 30 * d, body.bottom - 12 * d);
        p.setColor(Color.argb(a, 0x1B, 0x2A, 0x49));
        cv.drawRoundRect(scr, 12 * d, 12 * d, p);
        // Knoepfe rechts
        p.setColor(Color.argb(a, 0xE8, 0x3F, 0x6F));
        cv.drawCircle(body.right - 15 * d, body.top + 30 * d, 5 * d, p);
        p.setColor(Color.argb(a, 0x3F, 0xC8, 0xE8));
        cv.drawCircle(body.right - 15 * d, body.top + 48 * d, 5 * d, p);
        // Gesicht: Augen (blinzeln bei 1,8 s und 3,6 s), Wangen, Laecheln
        boolean blink = Math.abs(t - 1.8f) < 0.08f || Math.abs(t - 3.6f) < 0.08f;
        float ex = scr.centerX(), ey = scr.centerY() - 8 * d;
        p.setColor(Color.argb(a, 0xFF, 0xFF, 0xFF));
        if (blink) {
            p.setStrokeWidth(4 * d);
            cv.drawLine(ex - 26 * d, ey, ex - 12 * d, ey, p);
            cv.drawLine(ex + 12 * d, ey, ex + 26 * d, ey, p);
        } else {
            cv.drawCircle(ex - 19 * d, ey, 9 * d, p);
            cv.drawCircle(ex + 19 * d, ey, 9 * d, p);
            p.setColor(Color.argb(a, 0x1B, 0x2A, 0x49));
            cv.drawCircle(ex - 17 * d, ey + 2 * d, 4 * d, p);
            cv.drawCircle(ex + 21 * d, ey + 2 * d, 4 * d, p);
        }
        p.setColor(Color.argb((int) (a * 0.7f), 0xE8, 0x3F, 0x6F));
        cv.drawCircle(ex - 32 * d, ey + 14 * d, 6 * d, p);
        cv.drawCircle(ex + 32 * d, ey + 14 * d, 6 * d, p);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(4 * d);
        p.setColor(Color.argb(a, 0xF2, 0xB1, 0x34));
        cv.drawArc(new RectF(ex - 16 * d, ey + 2 * d, ex + 16 * d, ey + 24 * d), 20, 140, false, p);
        p.setStyle(Paint.Style.FILL);
        cv.restore();
        // Sprechblase oben links, ab 0,5 s, verschwindet beim Wegrennen
        if (t > 0.5f && run < 0.4f) {
            float ba = Math.min(1f, (t - 0.5f) / 0.3f) * alpha * (1f - run / 0.4f);
            String s1 = "Hallo!", s2 = "TV-Zapper läuft";
            p.setTextSize(17 * d);
            p.setFakeBoldText(true);
            float tw = Math.max(p.measureText(s1), p.measureText(s2));
            RectF b = new RectF(8 * d, 8 * d, 8 * d + tw + 28 * d, 8 * d + 58 * d);
            p.setColor(Color.argb((int) (240 * ba), 0xFF, 0xFF, 0xFF));
            cv.drawRoundRect(b, 16 * d, 16 * d, p);
            Path tail = new Path();
            tail.moveTo(b.right - 40 * d, b.bottom - 2);
            tail.lineTo(b.right - 10 * d, b.bottom + 20 * d);
            tail.lineTo(b.right - 22 * d, b.bottom - 2);
            tail.close();
            cv.drawPath(tail, p);
            p.setColor(Color.argb((int) (255 * ba), 0x1B, 0x2A, 0x49));
            cv.drawText(s1, b.left + 14 * d, b.top + 24 * d, p);
            p.setFakeBoldText(false);
            p.setTextSize(15 * d);
            cv.drawText(s2, b.left + 14 * d, b.top + 46 * d, p);
        }
        if (t * 1000 < DAUER_MS) postInvalidateOnAnimation();
    }
}
