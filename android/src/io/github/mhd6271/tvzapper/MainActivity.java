package io.github.mhd6271.tvzapper;

import android.app.Activity;
import android.app.AppOpsManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Einstellungen und Bedienung, alles mit der Fernbedienung erreichbar. Oberflaeche im Code gebaut. */
public class MainActivity extends Activity {
    private static final String PERM_LISTINGS = "android.permission.READ_TV_LISTINGS";

    private Config cfg;
    private LinearLayout root, catBox, chanBox;
    private final List<View[]> catRows = new ArrayList<>();   // {name, gewicht, woerter}
    private EditText never, runH, runM, dwell, bonus, adFree, fritz;
    private Button adToggle;
    private TextView status, perms, log;
    private boolean showAllChannels;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Runnable refresher = new Runnable() {
        @Override
        public void run() {
            refreshStatus();
            ui.postDelayed(this, 3000);
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        cfg = Config.load(this);
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(48), dp(24), dp(48), dp(24));
        scroll.addView(root);
        setContentView(scroll);
        build();
        if (checkSelfPermission(PERM_LISTINGS) != PackageManager.PERMISSION_GRANTED
                || checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{PERM_LISTINGS, "android.permission.POST_NOTIFICATIONS"}, 1);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        ui.post(refresher);
    }

    @Override
    protected void onPause() {
        super.onPause();
        ui.removeCallbacks(refresher);
        readForm();
        cfg.save(this);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] p, int[] r) {
        fillChannels();
        refreshStatus();
    }

    private void build() {
        root.addView(text("TV-Zapper", 28, true));
        root.addView(text("Prüft im Hintergrund, was auf den eingeschalteten Sendern läuft, bewertet es nach deinen "
                + "Interessen und schaltet auf den besten Treffer. Läuft nur, wenn das Fernsehprogramm vorn ist.", 15, false));

        status = text("", 17, true);
        status.setPadding(0, dp(12), 0, dp(4));
        root.addView(status);
        LinearLayout ctl = row();
        ctl.addView(button("Start", v -> start(ZapperService.ACTION_START, false)));
        ctl.addView(button("Stopp", v -> startService(new Intent(this, ZapperService.class)
                .setAction(ZapperService.ACTION_STOP))));
        ctl.addView(button("Einmal prüfen (nur lesen)", v -> start(ZapperService.ACTION_ONCE, true)));
        ctl.addView(button("Einblendung testen", v -> Banner.show(this, "TV-Zapper – so sieht die Einblendung aus", 6000)));
        root.addView(ctl);

        perms = text("", 14, false);
        root.addView(perms);
        LinearLayout pr = row();
        pr.addView(button("Fernsehprogramm lesen erlauben", v ->
                requestPermissions(new String[]{PERM_LISTINGS, "android.permission.POST_NOTIFICATIONS"}, 1)));
        pr.addView(button("Nutzungszugriff", v -> openSettings(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))));
        pr.addView(button("Über anderen Apps", v -> openSettings(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName())))));
        root.addView(pr);

        section("Zeit");
        LinearLayout t = row();
        t.addView(text("Laufzeit", 16, false));
        runH = number(String.valueOf(cfg.runMin / 60));
        t.addView(runH);
        t.addView(text("Std.", 16, false));
        runM = number(String.valueOf(cfg.runMin % 60));
        t.addView(runM);
        t.addView(text("Min.   Verweilen je Sender", 16, false));
        dwell = number(String.valueOf(cfg.dwellMin));
        t.addView(dwell);
        t.addView(text("Min.", 16, false));
        root.addView(t);

        section("Interessen");
        root.addView(text("Wörter mit Komma trennen. * am Ende = Wortanfang (doku* passt auf Dokumentation). "
                + "Je Kategorie zählt das Gewicht einmal, die Summe entscheidet.", 14, false));
        catBox = new LinearLayout(this);
        catBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(catBox);
        for (Config.Cat c : cfg.cats) addCat(c);
        LinearLayout ca = row();
        ca.addView(button("Kategorie hinzufügen", v -> addCat(new Config.Cat())));
        ca.addView(button("Grundeinstellung laden (interessen.json beim Bau)", v -> {
            Config.file(this).delete();
            Log.add(this, "Grundeinstellung geladen");
            cfg = Config.load(this);
            catRows.clear();
            root.removeAllViews();
            build();
            refreshStatus();
        }));
        root.addView(ca);

        section("Nie");
        root.addView(text("Sendungen mit diesen Wörtern nie nehmen:", 14, false));
        never = edit(String.join(", ", cfg.never), true);
        root.addView(never);

        section("Sender");
        LinearLayout b = row();
        b.addView(text("Bonus für neu bevorzugte Sender (nur bei Treffern):", 16, false));
        bonus = number(String.valueOf(cfg.bonus));
        b.addView(bonus);
        b.addView(text("P.", 16, false));
        root.addView(b);
        root.addView(text("Vorgabe: die Sender der Liste Favorit1 des Fernsehers. OK auf einem Sender wechselt: an → bevorzugt ★ → aus. Bevorzugte werden zuerst geprüft.", 14, false));
        root.addView(button("Alle Sender zeigen / nur eingeschaltete", v -> {
            showAllChannels = !showAllChannels;
            fillChannels();
        }));
        chanBox = new LinearLayout(this);
        chanBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(chanBox);
        fillChannels();

        section("Werbung umgehen");
        root.addView(text("Die FRITZ!Box empfängt den laufenden Sender nebenher mit. Verschwindet sein Senderlogo "
                + "(Werbung), schaltet der Fernseher auf den besten werbefreien Sender unten und nach der Pause zurück. "
                + "Neue Sender: Logo wird beim ersten Mal etwa 5 min gelernt.", 14, false));
        adToggle = button("", v -> {
            cfg.avoidAds = !cfg.avoidAds;
            adToggle.setText("Werbung umgehen: " + (cfg.avoidAds ? "an" : "aus"));
            cfg.save(this);
        });
        adToggle.setText("Werbung umgehen: " + (cfg.avoidAds ? "an" : "aus"));
        root.addView(adToggle);
        root.addView(text("Werbefreie Ausweichsender (Namen wie in der Senderliste, Reihenfolge = Vorrang):", 14, false));
        adFree = edit(String.join(", ", cfg.adFree), true);
        root.addView(adFree);
        LinearLayout fr = row();
        fr.addView(text("FRITZ!Box-Adresse:", 16, false));
        fritz = edit(cfg.fritz, false);
        fritz.setMinWidth(dp(220));
        fr.addView(fritz);
        root.addView(fr);

        section("Protokoll");
        log = text("", 13, false);
        log.setTypeface(android.graphics.Typeface.MONOSPACE);
        log.setFocusable(true);
        root.addView(log);
    }

    private void addCat(Config.Cat c) {
        LinearLayout r = row();
        EditText name = edit(c.name, false);
        name.setHint("Name");
        name.setLayoutParams(new LinearLayout.LayoutParams(dp(180), LinearLayout.LayoutParams.WRAP_CONTENT));
        EditText weight = number(String.valueOf(c.weight));
        EditText words = edit(String.join(", ", c.words), true);
        words.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        View[] cells = {name, weight, words};
        Button del = button("✕", v -> {
            catBox.removeView(r);
            catRows.remove(cells);
        });
        r.addView(name);
        r.addView(weight);
        r.addView(words);
        r.addView(del);
        catBox.addView(r);
        catRows.add(cells);
    }

    private void fillChannels() {
        chanBox.removeAllViews();
        List<Epg.Channel> list;
        try {
            list = Epg.channels(this);
        } catch (Exception e) {
            list = new ArrayList<>();
        }
        if (list.isEmpty()) {
            chanBox.addView(text("Keine Sender lesbar (Berechtigung „Fernsehprogramm lesen“ fehlt oder der "
                    + "Fernseher liefert keine).", 15, false));
            return;
        }
        int shown = 0;
        for (Epg.Channel ch : list) {
            if (!showAllChannels && Config.AUS.equals(cfg.state(ch))) continue;
            Button bt = button("", null);
            bt.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            label(bt, ch);
            bt.setOnClickListener(v -> {
                String s = cfg.state(ch);
                cfg.channels.put(ch.name, Config.AN.equals(s) ? Config.BEVORZUGT
                        : Config.BEVORZUGT.equals(s) ? Config.AUS : Config.AN);
                label(bt, ch);
                cfg.save(this);
            });
            chanBox.addView(bt);
            shown++;
        }
        chanBox.addView(text(shown + " von " + list.size() + " Sendern angezeigt", 14, false));
    }

    private void label(Button bt, Epg.Channel ch) {
        String s = cfg.state(ch);
        bt.setText(ch.number + "   " + ch.name + "   —   " + (Config.BEVORZUGT.equals(s) ? "bevorzugt ★" : s)
                + (ch.favorite ? "" : "   (nicht in Favorit1)"));
        bt.setAlpha(Config.AUS.equals(s) ? 0.5f : 1f);
    }

    private void readForm() {
        cfg.cats.clear();
        for (View[] c : catRows) {
            Config.Cat cat = new Config.Cat();
            cat.name = ((EditText) c[0]).getText().toString().trim();
            cat.weight = parse(((EditText) c[1]).getText().toString(), 1);
            cat.words = Config.splitList(((EditText) c[2]).getText().toString());
            if (!cat.name.isEmpty() || !cat.words.isEmpty()) cfg.cats.add(cat);
        }
        cfg.never = Config.splitList(never.getText().toString());
        cfg.runMin = Math.max(1, parse(runH.getText().toString(), 0) * 60 + parse(runM.getText().toString(), 0));
        cfg.dwellMin = Math.max(1, parse(dwell.getText().toString(), 5));
        cfg.bonus = parse(bonus.getText().toString(), 0);
        cfg.adFree = Config.splitList(adFree.getText().toString());
        String f = fritz.getText().toString().trim();
        cfg.fritz = f.isEmpty() ? "fritz.box" : f;
    }

    private void start(String action, boolean readOnly) {
        readForm();
        cfg.save(this);
        startForegroundService(new Intent(this, ZapperService.class).setAction(action)
                .putExtra(ZapperService.EXTRA_READ_ONLY, readOnly));
        if (!readOnly) moveTaskToBack(true);   // zurueck zum Fernsehbild
    }

    private void refreshStatus() {
        SimpleDateFormat hm = new SimpleDateFormat("HH:mm", Locale.GERMANY);
        long end = ZapperService.endAt, next = ZapperService.nextAt;
        status.setText(end > System.currentTimeMillis()
                ? "Läuft bis " + hm.format(new Date(end)) + (next > 0 ? ", nächste Prüfung " + hm.format(new Date(next)) : "")
                : "Steht.");
        WerbeWaechter w = ZapperService.waechter;
        if (w != null) status.append("   " + w.status());
        boolean listings = checkSelfPermission(PERM_LISTINGS) == PackageManager.PERMISSION_GRANTED;
        boolean usage = usageAccess();
        boolean overlay = Settings.canDrawOverlays(this);
        perms.setText("Berechtigungen:  Fernsehprogramm lesen " + mark(listings) + "   Nutzungszugriff (was läuft vorn) "
                + mark(usage) + "   Über anderen Apps (Umschalten aus dem Hintergrund) " + mark(overlay));
        List<String> lines = Log.read(this);
        StringBuilder b = new StringBuilder();
        for (int i = lines.size() - 1; i >= Math.max(0, lines.size() - 60); i--) b.append(lines.get(i)).append('\n');
        log.setText(b.length() == 0 ? "(noch leer)" : b.toString());
    }

    private boolean usageAccess() {
        AppOpsManager ao = getSystemService(AppOpsManager.class);
        return ao.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), getPackageName())
                == AppOpsManager.MODE_ALLOWED;
    }

    private void openSettings(Intent i) {
        try {
            startActivity(i);
        } catch (Exception e) {
            Log.add(this, "Diese Einstellungsseite gibt es auf dem Gerät nicht: " + i.getAction());
            refreshStatus();
        }
    }

    // --- kleine Bausteine ---

    private static String mark(boolean ok) {
        return ok ? "✓" : "✗";
    }

    private static int parse(String s, int def) {
        try {
            return Integer.parseInt(s.trim());
        } catch (Exception e) {
            return def;
        }
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void section(String title) {
        TextView t = text(title, 20, true);
        t.setPadding(0, dp(20), 0, dp(4));
        t.setTextColor(Color.rgb(0xF2, 0xB1, 0x34));
        root.addView(t);
    }

    private LinearLayout row() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        return r;
    }

    private TextView text(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        t.setPadding(dp(4), dp(2), dp(8), dp(2));
        return t;
    }

    private Button button(String s, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(15);
        if (l != null) b.setOnClickListener(l);
        return b;
    }

    private EditText edit(String s, boolean multi) {
        EditText e = new EditText(this);
        e.setText(s);
        e.setTextSize(15);
        e.setInputType(InputType.TYPE_CLASS_TEXT | (multi ? InputType.TYPE_TEXT_FLAG_MULTI_LINE : 0));
        return e;
    }

    private EditText number(String s) {
        EditText e = new EditText(this);
        e.setText(s);
        e.setTextSize(15);
        e.setInputType(InputType.TYPE_CLASS_NUMBER);
        e.setMinWidth(dp(64));
        e.setGravity(Gravity.CENTER);
        return e;
    }
}
