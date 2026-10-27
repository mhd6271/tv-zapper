# TV-Zapper

Schaltet am TCL-Google-TV (192.168.20.61) selbstständig auf Sendungen, die mich interessieren.

## Was mich interessiert

Steht in [`interessen.json`](interessen.json) – Kategorien mit Gewicht und Suchwörtern:

| Kategorie | Gewicht |
|---|---|
| Hip-Hop/Rap | 5 |
| Musik | 3 |
| Dokumentation | 2 |
| Lifestyle | 2 |

Nie: Teleshopping, Dauerwerbesendung. Wörter mit `*` passen als Wortanfang (`doku*`).
Neue Interessen einfach dort eintragen.

## Wie es arbeitet

1. Programmzeitschrift des Fernsehers öffnen (Taste GUIDE), Liste **Favorit1** wählen
   (dort liegen alle freien HD-Sender, die funktionieren).
2. Die Liste von oben nach unten durchgehen und je Sender die laufende Sendung lesen,
   für die markierte Zeile auch Genre und Beschreibung (uiautomator, Text).
   Bildschirmfotos vom Fernsehbild gehen nicht – das Bild ist geschützt und bleibt schwarz.
3. Jede Sendung gegen `interessen.json` bewerten.
4. Ist der beste Treffer besser als das, was läuft: Programmzeitschrift schließen,
   Sendernummer Ziffer für Ziffer (0,8 s Pause, sonst verschluckt der Fernseher die erste)
   und OK.
5. 5 Minuten warten (`verweilen_min`), dann wieder ab 1.

Zeigt der Fernseher etwas anderes als das Fernsehprogramm (App, AirPlay, aus),
lässt das Skript ihn in Ruhe.

## Aufruf

```bash
python3 zapper.py                  # 60 Minuten
python3 zapper.py --minuten 30
python3 zapper.py --einmal --nur-lesen   # nur auslesen und bewerten
```

Jeder Durchgang landet in `protokoll.jsonl` (was lief, Treffer, ob umgeschaltet wurde).

## Voraussetzungen

- `adb` verbunden mit dem Fernseher (`adb connect 192.168.20.61:5555`;
  bei Hängern `python3 ~/Projekte/flimmer/tools/tvk.py connect`).
- Fernseher an und auf dem Tuner-Eingang. Wiedereinschalten aus dem Ruhezustand
  geht nur per Wake-on-LAN (MAC 14:ea:63:bc:62:e8), nicht über Home Assistant allein.

## Sendernummern (Favorit1, Stand 27.10.2026)

23 ProSieben HD · 24 sixx HD · 25 RTL HD · 26 SAT.1 HD · 27 SPORT 1 HD · 28 VOX HD ·
29 Kabel Eins HD · 86 DMAX HD · 111 HGTV · 141 N24 DOKU · 167 ProSieben MAXX HD ·
236 tagesschau24 HD · 244 TLC HD · 260 VOXup HD · 265 WDR HD Köln · 268 WELT HD ·
270 zdf_neo HD · 271 ZDFinfo HD
