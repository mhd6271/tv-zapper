package io.github.mhd6271.tvzapper;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;

/** Kleiner Comic-Fernseher, der nach dem Start unten rechts ins Bild huepft, winkt, gruesst und dann verblassend
 *  nach rechts hinausrennt (Overlay-Fenster wie die Einblendung, braucht "Ueber anderen Apps einblenden").
 *  Alles gezeichnet, keine Grafikdateien.
 *
 *  Ablauf (Sekunden): 0–0,4 hereinfallen, 0,4–2,6 drei Huepfer mit Strecken/Stauchen, ab 0,6 winken und
 *  Sprechblase, 3,8–6,2 wegrennen mit Speedlines und Staubwoelkchen, dabei verblassen.
 *
 *  Kleine Fassung ({@link #flitzen}, beim Senderwechsel): ein Viertel so gross, rennt in Hoehe der Senderlogos
 *  am oberen Bildrand von rechts nach links quer durchs Bild und verschwindet oben links. */
final class Maskottchen extends View {
    static final long DAUER_MS = 6200;
    static final float RENNEN_AB = 3.8f;
    static final long FLITZ_MS = 4000;
    private static final float KLEIN = 0.25f;
    private static long busyUntil;   // nie zwei Maskottchen gleichzeitig

    // Farben
    private static final int GEH_HELL = 0xFFFFC857, GEH_DUNKEL = 0xFFE89A1E, RAND = 0xFF8A4B08, NAVY = 0xFF1B2A49,
            BILD_OBEN = 0xFF2E4A7A, BILD_UNTEN = 0xFF14203A, PINK = 0xFFE83F6F, TUERKIS = 0xFF3FC8E8,
            WEISS = 0xFFFFFFFF, SCHUH = 0xFFE83F6F;

    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final long t0 = SystemClock.uptimeMillis();
    private final float d;
    private final boolean klein, rechts;
    /** Klein nach rechts: Figur spiegeln (R2) oder nicht (R1) – Max hat am 29.10.2026 in der Browser-Vorschau R2 gewaehlt. */
    private static final boolean FIGUR_SPIEGELN_NACH_RECHTS = true;
    private Bitmap frame;   // nur klein: Einzelbild der gespiegelten Figur

    private Maskottchen(Context c, boolean klein, boolean rechts) {
        super(c);
        this.klein = klein;
        this.rechts = rechts;
        d = c.getResources().getDisplayMetrics().density;
        setLayerType(LAYER_TYPE_HARDWARE, null);
    }

    static void show(Context ctx) {
        show(ctx, false, false);
    }

    /** Kleine Fassung, die einmal oben quer durchs Bild flitzt (beim Senderwechsel): vorwaerts geschaltet nach links,
     *  zurueck nach rechts. */
    static void flitzen(Context ctx, boolean nachRechts) {
        show(ctx, true, nachRechts);
    }

    private static void show(Context ctx, boolean klein, boolean rechts) {
        Context c = ctx.getApplicationContext();
        if (!Settings.canDrawOverlays(c)) return;
        Handler main = new Handler(Looper.getMainLooper());
        main.post(() -> {
            long now = SystemClock.uptimeMillis();
            if (now < busyUntil) return;
            long ms = klein ? FLITZ_MS : DAUER_MS;
            WindowManager wm = c.getSystemService(WindowManager.class);
            Maskottchen v = new Maskottchen(c, klein, rechts);
            float d = v.d;
            // KOMPAT: Wie Banner: Overlay ueber dem Fernsehbild, nur am TCL gesehen.
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                    klein ? WindowManager.LayoutParams.MATCH_PARENT : (int) (360 * d), (int) (300 * d * (klein ? KLEIN : 1)),
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                    PixelFormat.TRANSLUCENT);
            if (klein) {
                lp.gravity = Gravity.TOP | Gravity.START;   // oberer Rand, etwa in Hoehe der Senderlogos
                lp.y = 0;   // ganz oben; Max wollte es zweimal je 10 dp hoeher als die ersten 18 (Rest in onDraw)
            } else {
                lp.gravity = Gravity.BOTTOM | Gravity.END;
                lp.x = 0;   // am rechten Bildrand, damit er hinausrennen kann
                lp.y = (int) (16 * d);
            }
            try {
                wm.addView(v, lp);
                busyUntil = now + ms;
                main.postDelayed(() -> {
                    try {
                        wm.removeView(v);
                    } catch (Exception ignored) {
                    }
                }, ms);
            } catch (Exception e) {
                Log.add(c, "Maskottchen nicht einblendbar: " + e.getMessage());
            }
        });
    }

    private static int a(int color, float alpha) {
        return (color & 0x00FFFFFF) | ((int) (Color.alpha(color) * Math.max(0, Math.min(1, alpha))) << 24);
    }

    private static float ease(float x) {   // weich ein/aus
        x = Math.max(0, Math.min(1, x));
        return x * x * (3 - 2 * x);
    }

    @Override
    protected void onDraw(Canvas cv) {
        float tt = (SystemClock.uptimeMillis() - t0) / 1000f;
        if (!klein) {
            drawFigure(cv, tt, getWidth(), getHeight(), tt);
        } else {
            // Verkleinert in eine eigene Bitmap zeichnen, die quer durchs Bild wandert; die Figur steckt dabei
            // dauerhaft mitten im Rennen (ohne Gruss, ohne Sprechblase). Nach links wird nur der Schweif gespiegelt
            // (in drawFigure), die Figur selbst nicht: Max hat am 29.10.2026 aus vier Varianten diese als richtig
            // herum gewaehlt; ganz gespiegelt (0.4.8/0.4.9) lief sie fuer ihn falsch herum. Der Schweif liegt immer hinten.
            float S = KLEIN, bw = 360 * d * S, bh = 300 * d * S;
            if (frame == null) frame = Bitmap.createBitmap((int) Math.ceil(bw), (int) Math.ceil(bh), Bitmap.Config.ARGB_8888);
            frame.eraseColor(Color.TRANSPARENT);
            Canvas bc = new Canvas(frame);
            bc.scale(S, S);
            if (!rechts) bc.translate(-70 * d, 0);   // links ist ohne Schweif Platz frei, rechts braucht ihn der gespiegelte Schweif
            drawFigure(bc, tt + RENNEN_AB + 1, 360 * d, 300 * d, tt);
            float f = tt / (FLITZ_MS / 1000f);
            float x = rechts ? -bw + f * (getWidth() + bw) : getWidth() - f * (getWidth() + bw);
            cv.drawBitmap(frame, x, -2 * d, null);   // 2 dp hoeher als der Fensterrand (ueber den Antennen ist ~20 dp Luft)
        }
        if (tt * 1000 < (klein ? FLITZ_MS : DAUER_MS)) postInvalidateOnAnimation();
    }

    /** Die Figur zur Zeit t (Sekunden des grossen Ablaufs) in ein W x H grosses Feld; tt = echte Laufzeit. */
    private void drawFigure(Canvas cv, float t, float W, float H, float tt) {
        float run = Math.max(0f, t - RENNEN_AB), runTotal = DAUER_MS / 1000f - RENNEN_AB;
        float alpha = klein ? Math.min(1f, tt / 0.3f) * Math.min(1f, (FLITZ_MS / 1000f - tt) / 0.6f)
                : Math.min(1f, t / 0.25f) * Math.max(0f, 1f - (float) Math.pow(run / runTotal, 1.4));

        // --- Bewegung ---
        float drop = t < 0.4f ? (1 - ease(t / 0.4f)) * -120 * d : 0;              // faellt von oben herein
        float hopPhase = t >= 0.4f && t < 2.6f ? (t - 0.4f) / 0.733f : -1;          // drei Huepfer
        float hop = 0, stretch = 1;
        if (hopPhase >= 0) {
            float f = hopPhase % 1f;
            hop = (float) Math.sin(f * Math.PI) * 42 * d * (1 - hopPhase / 4);
            stretch = f < 0.12f || f > 0.88f ? 0.9f : 1.06f;                        // stauchen beim Aufkommen
        }
        if (run > 0) hop = Math.abs((float) Math.sin(run * Math.PI * 6)) * 8 * d;   // Huepfen beim Rennen
        float dx = klein ? 0 : run * run * 300 * d;
        float lean = run > 0 ? Math.min(14, run * 40) : 0;
        float wave = t > 0.6f && run == 0 ? (float) Math.sin((t - 0.6f) * Math.PI * 3.2) : 0;
        float swing = run > 0 ? (float) Math.sin(run * Math.PI * 6) : 0;            // Arme/Beine beim Rennen
        float antenna = (float) Math.sin(t * 9) * (hopPhase >= 0 || run > 0 ? 9 : 3);

        float cx = W * 0.6f, ground = H - 14 * d;
        float bw = 150 * d, bh = 112 * d * stretch, legLen = 26 * d;
        float bottom = ground - legLen - hop + drop;
        float bwS = bw / stretch;   // gestaucht = breiter
        RectF body = new RectF(cx - bwS / 2, bottom - bh, cx + bwS / 2, bottom);

        // Staubwoelkchen und Speedlines beim Rennen (nicht mit dem Koerper geneigt); klein: gespiegelt, also rechts
        // hinter der nach links laufenden Figur
        if (run > 0) {
            cv.save();
            if (klein && !rechts) cv.scale(-1, 1, cx, 0);
            for (int i = 0; i < 4; i++) {
                float age = (run * 6 + i * 0.25f) % 1f;
                float px = cx + dx - 70 * d - age * 90 * d, py = ground - 6 * d - age * 14 * d;
                p.setColor(a(0xFFD9D2C5, alpha * (1 - age) * 0.8f));
                cv.drawCircle(px, py, (6 + age * 10) * d, p);
            }
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeWidth(4 * d);
            for (int i = 0; i < 3; i++) {
                float y = body.top + (30 + i * 28) * d;
                float len = (40 + 20 * i) * d * Math.min(1, run * 3);
                p.setColor(a(WEISS, alpha * 0.55f));
                cv.drawLine(body.left + dx - 20 * d - len, y, body.left + dx - 20 * d, y, p);
            }
            cv.restore();
        }

        // Schatten (schrumpft beim Huepfen)
        float sh = 1 - Math.min(0.6f, (hop - drop) / (90 * d));
        p.setShader(new RadialGradient(cx + dx, ground, 70 * d * sh, a(0x66000000, alpha), 0x00000000,
                Shader.TileMode.CLAMP));
        cv.drawOval(new RectF(cx + dx - 70 * d * sh, ground - 9 * d, cx + dx + 70 * d * sh, ground + 9 * d), p);
        p.setShader(null);

        cv.save();
        if (klein && rechts && FIGUR_SPIEGELN_NACH_RECHTS) cv.scale(-1, 1, cx, 0);
        cv.translate(dx, 0);
        cv.rotate(lean, cx, ground);

        // --- Beine mit Schuhen ---
        p.setStrokeCap(Paint.Cap.ROUND);
        for (int side = -1; side <= 1; side += 2) {
            float hipX = cx + side * 34 * d, hipY = bottom - 4 * d;
            float kick = run > 0 ? swing * side * 18 * d : 0;
            float footX = hipX + kick, footY = hipY + legLen - Math.max(0, swing * side) * 10 * d;
            p.setColor(a(NAVY, alpha));
            p.setStrokeWidth(10 * d);
            cv.drawLine(hipX, hipY, footX, footY, p);
            p.setColor(a(SCHUH, alpha));
            cv.drawRoundRect(new RectF(footX - 13 * d, footY - 6 * d, footX + 17 * d, footY + 8 * d), 8 * d, 8 * d, p);
            p.setColor(a(WEISS, alpha));
            cv.drawRoundRect(new RectF(footX - 13 * d, footY + 3 * d, footX + 17 * d, footY + 8 * d), 4 * d, 4 * d, p);
        }

        // --- Antennen (federn) ---
        float topX = cx, topY = body.top + 4 * d;
        p.setStrokeWidth(5 * d);
        p.setColor(a(NAVY, alpha));
        float l1x = topX - 36 * d + antenna * d, l1y = topY - 46 * d;
        float r1x = topX + 40 * d - antenna * d * 0.7f, r1y = topY - 50 * d;
        cv.drawLine(topX - 8 * d, topY, l1x, l1y, p);
        cv.drawLine(topX + 8 * d, topY, r1x, r1y, p);
        drawBall(cv, l1x, l1y, 8 * d, PINK, alpha);
        drawBall(cv, r1x, r1y, 8 * d, TUERKIS, alpha);
        p.setColor(a(RAND, alpha));
        cv.drawRoundRect(new RectF(topX - 16 * d, topY - 8 * d, topX + 16 * d, topY + 4 * d), 6 * d, 6 * d, p);

        // --- Rechter Arm (hinter dem Koerper): Hand in die Hüfte, beim Rennen schwingend ---
        float rsx = body.right - 8 * d, rsy = body.top + 52 * d;
        drawArm(cv, rsx, rsy, run > 0 ? 30 + swing * 45 : 55, 40 * d, alpha, false);

        // --- Koerper: Gehaeuse mit Verlauf, Rand, Glanzkante ---
        p.setShader(new LinearGradient(0, body.top, 0, body.bottom, a(GEH_HELL, alpha), a(GEH_DUNKEL, alpha),
                Shader.TileMode.CLAMP));
        cv.drawRoundRect(body, 26 * d, 26 * d, p);
        p.setShader(null);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(4 * d);
        p.setColor(a(RAND, alpha));
        cv.drawRoundRect(body, 26 * d, 26 * d, p);
        p.setStrokeWidth(3 * d);
        p.setColor(a(0xFFFFE6A8, alpha * 0.9f));
        cv.drawArc(new RectF(body.left + 8 * d, body.top + 6 * d, body.right - 8 * d, body.bottom - 6 * d), 200, 60,
                false, p);
        p.setStyle(Paint.Style.FILL);

        // Bildschirm mit innerem Rahmen, Verlauf, Glanz
        RectF bez = new RectF(body.left + 12 * d, body.top + 12 * d, body.right - 42 * d, body.bottom - 12 * d);
        p.setColor(a(RAND, alpha));
        cv.drawRoundRect(bez, 20 * d, 20 * d, p);
        RectF scr = new RectF(bez.left + 5 * d, bez.top + 5 * d, bez.right - 5 * d, bez.bottom - 5 * d);
        p.setShader(new LinearGradient(0, scr.top, 0, scr.bottom, a(BILD_OBEN, alpha), a(BILD_UNTEN, alpha),
                Shader.TileMode.CLAMP));
        cv.drawRoundRect(scr, 16 * d, 16 * d, p);
        p.setShader(null);
        Path gloss = new Path();
        gloss.moveTo(scr.left + 10 * d, scr.top + 8 * d);
        gloss.lineTo(scr.left + 46 * d, scr.top + 8 * d);
        gloss.lineTo(scr.left + 18 * d, scr.bottom - 26 * d);
        gloss.lineTo(scr.left + 8 * d, scr.bottom - 34 * d);
        gloss.close();
        p.setColor(a(WEISS, alpha * 0.12f));
        cv.drawPath(gloss, p);

        // Bedienleiste: zwei Drehknoepfe, Lautsprecher-Rillen
        float kx = body.right - 22 * d;
        drawKnob(cv, kx, body.top + 30 * d, 9 * d, PINK, t * 90, alpha);
        drawKnob(cv, kx, body.top + 56 * d, 9 * d, TUERKIS, -t * 70, alpha);
        p.setColor(a(RAND, alpha * 0.8f));
        p.setStrokeWidth(2.5f * d);
        for (int i = 0; i < 3; i++) {
            float y = body.top + (76 + i * 8) * d;
            if (y < body.bottom - 10 * d) cv.drawLine(kx - 9 * d, y, kx + 9 * d, y, p);
        }

        // --- Gesicht ---
        float ex = scr.centerX(), ey = scr.centerY() - 6 * d;
        float blinkT = (t % 2.2f);
        boolean blink = blinkT > 1.6f && blinkT < 1.72f && run == 0;
        float brow = t > 0.6f && run == 0 ? 3 * d * (float) Math.abs(Math.sin(t * 4)) : 0;
        p.setColor(a(WEISS, alpha));
        p.setStrokeWidth(3.5f * d);
        cv.drawLine(ex - 30 * d, ey - 18 * d - brow, ex - 12 * d, ey - 21 * d - brow, p);   // Augenbrauen
        cv.drawLine(ex + 12 * d, ey - 21 * d - brow, ex + 30 * d, ey - 18 * d - brow, p);
        for (int side = -1; side <= 1; side += 2) {
            float x = ex + side * 20 * d;
            if (blink) {
                p.setStrokeWidth(4 * d);
                cv.drawLine(x - 9 * d, ey, x + 9 * d, ey, p);
            } else {
                p.setColor(a(WEISS, alpha));
                cv.drawOval(new RectF(x - 10 * d, ey - 12 * d, x + 10 * d, ey + 12 * d), p);
                p.setColor(a(NAVY, alpha));
                float look = run > 0 ? 4 * d : 0;
                cv.drawCircle(x + 2 * d + look, ey + 2 * d, 6 * d, p);
                p.setColor(a(WEISS, alpha));
                cv.drawCircle(x + 4 * d + look, ey - 1 * d, 2.2f * d, p);
            }
            p.setColor(a(PINK, alpha * 0.55f));
            cv.drawOval(new RectF(x + side * 14 * d - 7 * d, ey + 12 * d, x + side * 14 * d + 7 * d, ey + 18 * d), p);
        }
        // Mund: offen lachend beim Gruessen, sonst Laecheln
        boolean talk = t > 0.6f && t < 3.4f;
        if (talk) {
            // grosser offener Mund (D-Form), oeffnet und schliesst sich beim "Sprechen", mit Zunge und Zaehnen
            float open = 9 * d + 7 * d * (float) Math.abs(Math.sin(t * 9));
            RectF mr = new RectF(ex - 18 * d, ey + 10 * d, ex + 18 * d, ey + 10 * d + open * 2);
            cv.save();
            Path clip = new Path();
            clip.addArc(mr, 0, 180);
            clip.lineTo(mr.left, mr.centerY());
            clip.close();
            p.setColor(a(0xFF5A1530, alpha));
            cv.drawPath(clip, p);
            cv.clipPath(clip);
            p.setColor(a(PINK, alpha));
            cv.drawOval(new RectF(ex - 11 * d, mr.bottom - 10 * d, ex + 11 * d, mr.bottom + 6 * d), p);
            p.setColor(a(WEISS, alpha));
            cv.drawRect(new RectF(mr.left, mr.centerY(), mr.right, mr.centerY() + 4 * d), p);
            cv.restore();
        } else {
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(4 * d);
            p.setColor(a(GEH_HELL, alpha));
            cv.drawArc(new RectF(ex - 16 * d, ey + 4 * d, ex + 16 * d, ey + 26 * d), 20, 140, false, p);
            p.setStyle(Paint.Style.FILL);
        }

        // --- Linker Arm (vorne): winkt, beim Rennen schwingend ---
        float lsx = body.left + 8 * d, lsy = body.top + 50 * d;
        drawArm(cv, lsx, lsy, run > 0 ? 200 - swing * 45 : 215 + wave * 30, 46 * d, alpha, true);

        cv.restore();

        // --- Funkelsterne beim Gruessen ---
        if (!klein && t > 0.6f && t < 3.6f) {
            for (int i = 0; i < 3; i++) {
                float ph = (t * 1.6f + i * 0.33f) % 1f;
                float sx = body.left - 26 * d + i * 30 * d, sy = body.top - 30 * d - ph * 26 * d;
                drawStar(cv, sx, sy, (5 + 4 * (float) Math.sin(ph * Math.PI)) * d,
                        i == 1 ? TUERKIS : GEH_HELL, alpha * (float) Math.sin(ph * Math.PI));
            }
        }

        // --- Sprechblase (ploppt auf, verschwindet vor dem Rennen) ---
        if (!klein && t > 0.6f && run < 0.3f) {
            float pop = t < 0.9f ? ease((t - 0.6f) / 0.3f) : 1f;
            float sc = pop < 1 ? 0.6f + 0.55f * pop - 0.15f * pop * pop : 1f;   // leichtes Ueberschwingen
            float ba = pop * alpha * (1f - run / 0.3f);
            String s1 = "Hallo!", s2 = "TV-Zapper läuft";
            p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
            p.setTextSize(20 * d);
            float w1 = p.measureText(s1);
            p.setTypeface(Typeface.DEFAULT);
            p.setTextSize(15 * d);
            float tw = Math.max(w1, p.measureText(s2));
            RectF b = new RectF(10 * d, 10 * d, 10 * d + tw + 32 * d, 10 * d + 64 * d);
            cv.save();
            cv.scale(sc, sc, b.right - 20 * d, b.bottom + 18 * d);
            Path tail = new Path();
            tail.moveTo(b.right - 52 * d, b.bottom - 4 * d);
            tail.lineTo(b.right - 6 * d, b.bottom + 26 * d);
            tail.lineTo(b.right - 28 * d, b.bottom - 4 * d);
            tail.close();
            p.setColor(a(0x33000000, ba));
            cv.drawRoundRect(new RectF(b.left + 3 * d, b.top + 4 * d, b.right + 3 * d, b.bottom + 4 * d), 18 * d, 18 * d, p);
            p.setColor(a(WEISS, ba));
            cv.drawRoundRect(b, 18 * d, 18 * d, p);
            cv.drawPath(tail, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(3 * d);
            p.setColor(a(NAVY, ba));
            cv.drawRoundRect(b, 18 * d, 18 * d, p);
            p.setStyle(Paint.Style.FILL);
            p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
            p.setTextSize(20 * d);
            p.setColor(a(PINK, ba));
            cv.drawText(s1, b.left + 16 * d, b.top + 28 * d, p);
            p.setTypeface(Typeface.DEFAULT);
            p.setTextSize(15 * d);
            p.setColor(a(NAVY, ba));
            cv.drawText(s2, b.left + 16 * d, b.top + 50 * d, p);
            cv.restore();
        }

    }

    /** Arm von der Schulter aus, Winkel in Grad (0 = nach rechts), mit Handschuh-Hand. */
    private void drawArm(Canvas cv, float sx, float sy, float deg, float len, float alpha, boolean front) {
        double r = Math.toRadians(deg);
        float ex = sx + (float) Math.cos(r) * len, ey = sy + (float) Math.sin(r) * len;
        float mx = sx + (float) Math.cos(r) * len * 0.5f, my = sy + (float) Math.sin(r) * len * 0.5f + 4 * d;
        Path arm = new Path();
        arm.moveTo(sx, sy);
        arm.quadTo(mx, my, ex, ey);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeCap(Paint.Cap.ROUND);
        p.setStrokeWidth(10 * d);
        p.setColor(a(RAND, alpha));
        cv.drawPath(arm, p);
        p.setStrokeWidth(6 * d);
        p.setColor(a(GEH_DUNKEL, alpha));
        cv.drawPath(arm, p);
        p.setStyle(Paint.Style.FILL);
        // Handschuh mit Daumen
        p.setColor(a(RAND, alpha));
        cv.drawCircle(ex, ey, 13 * d, p);
        p.setColor(a(WEISS, alpha));
        cv.drawCircle(ex, ey, 11 * d, p);
        cv.drawCircle(ex + (float) Math.cos(r + 1.6) * 10 * d, ey + (float) Math.sin(r + 1.6) * 10 * d, 5 * d, p);
        p.setColor(a(0xFFD8D8D8, alpha));
        p.setStrokeWidth(1.5f * d);
        for (int i = -1; i <= 1; i++) {
            double fr = r + i * 0.35;
            cv.drawLine(ex + (float) Math.cos(fr) * 3 * d, ey + (float) Math.sin(fr) * 3 * d,
                    ex + (float) Math.cos(fr) * 9 * d, ey + (float) Math.sin(fr) * 9 * d, p);
        }
    }

    private void drawBall(Canvas cv, float x, float y, float r, int color, float alpha) {
        p.setShader(new RadialGradient(x - r * 0.35f, y - r * 0.35f, r * 1.2f, a(WEISS, alpha), a(color, alpha),
                Shader.TileMode.CLAMP));
        cv.drawCircle(x, y, r, p);
        p.setShader(null);
    }

    private void drawKnob(Canvas cv, float x, float y, float r, int color, float rot, float alpha) {
        p.setColor(a(RAND, alpha));
        cv.drawCircle(x, y, r + 2 * d, p);
        drawBall(cv, x, y, r, color, alpha);
        cv.save();
        cv.rotate(rot, x, y);
        p.setColor(a(NAVY, alpha));
        p.setStrokeWidth(2.5f * d);
        cv.drawLine(x, y, x, y - r + 2 * d, p);
        cv.restore();
    }

    private void drawStar(Canvas cv, float x, float y, float r, int color, float alpha) {
        Path s = new Path();
        for (int i = 0; i < 8; i++) {
            double ang = Math.PI / 4 * i - Math.PI / 2;
            float rr = i % 2 == 0 ? r : r * 0.4f;
            float px = x + (float) Math.cos(ang) * rr, py = y + (float) Math.sin(ang) * rr;
            if (i == 0) s.moveTo(px, py);
            else s.lineTo(px, py);
        }
        s.close();
        p.setColor(a(color, alpha));
        cv.drawPath(s, p);
    }
}
