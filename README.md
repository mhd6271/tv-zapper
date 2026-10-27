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

## Home-Assistant-Fassung

Im Ordner [`homeassistant/custom_components/tv_zapper`](homeassistant/custom_components/tv_zapper) liegt
dieselbe Logik als Integration für Home Assistant (Stand von `zapper.py` am 27.10.2026, Commit 4d6133c: Sender nie/bevorzugt,
pro Durchgang nur einmal umschalten und danach nachlesen, BACK nur bei offener Programmzeitschrift). Alles wird in HA eingestellt, `interessen.json` ist nur
die Vorlage für die Grundeinstellung: Sie liegt als Kopie `tv_zapper/vorlage.json` in der Integration. Nach einer
Änderung an `interessen.json` neu kopieren (`cp interessen.json homeassistant/custom_components/tv_zapper/vorlage.json`),
ein Test meldet sonst den Unterschied. Eine schon eingerichtete Integration behält ihre Einstellungen.

**Wie sie den Fernseher erreicht:** Die eingebauten Integrationen reichen nicht. „Android TV Remote“
(`androidtv_remote`, so ist der Fernseher heute als `media_player.smart_tv_pro` eingebunden) kann nur Tasten
schicken, aber nichts vom Bildschirm lesen. Deshalb spricht die Integration selbst ADB über das Netzwerk
(Bibliothek `adb-shell`, dieselbe wie in der eingebauten Integration „Android Debug Bridge“) und liest die
Programmzeitschrift wie `zapper.py` mit `uiautomator dump`. HA bekommt dafür einen **eigenen ADB-Schlüssel**
(`/config/.storage/tv_zapper_adbkey`); beim ersten Verbinden fragt der Fernseher deshalb einmal
„USB-Debugging zulassen?“ – mit der Fernbedienung **Immer zulassen** wählen.

**Einstellungen** (beim Einrichten bzw. über „Konfigurieren“ an der Integration):

| Einstellung | Bedeutung |
|---|---|
| Adresse / Port | 192.168.20.61 / 5555 |
| Senderliste | Name des Reiters in der Programmzeitschrift, Standard `Favorit1` |
| Interessen | eine Zeile je Kategorie: `Name \| Gewicht \| wort, wort*, …` |
| Nie nehmen | Wörter, mit Komma getrennt (Teleshopping …) |
| Sender nie nehmen | Sendernamen wie in der Programmzeitschrift, mit Komma getrennt |
| Bevorzugte Sender | eine Zeile je Sender: `N24 DOKU \| 1` – Bonuspunkte, zählen nur, wenn die Sendung auch passt |
| Laufzeit | wie lange der Zapper nach dem Einschalten läuft (Minuten) |
| Verweilzeit | Minuten zwischen zwei Prüfungen |
| Nur lesen | nie umschalten, nur bewerten (zum Ausprobieren) |

**Entitäten** (Gerät „TV-Zapper“):

- `switch.tv_zapper_zapper` – an: zappt für die Laufzeit, geht danach (oder nach drei Fehlern hintereinander)
  von selbst aus. Attribut `laeuft_bis`.
- `sensor.tv_zapper_aktueller_treffer` – z. B. `23 ProSieben HD: …`; Attribute Sender, Nummer, Sendung, Punkte,
  Kategorien, Aktion (bleibt/umgeschaltet/uebersprungen/fehler), bester und weitere Treffer.
- `number.tv_zapper_laufzeit`, `number.tv_zapper_verweilzeit` – lassen sich auch im Dashboard oder per
  Automation ändern und wirken sofort, auch auf einen laufenden Zapper.
- `button.tv_zapper_jetzt_prufen_nur_lesen` – ein Durchgang ohne Umschalten.
- Ereignis `tv_zapper_durchgang` nach jedem Durchgang (mit allen Treffern) für eigene Automationen.

Wie `zapper.py` lässt die Integration den Fernseher in Ruhe, wenn er gerade etwas anderes als das
Fernsehprogramm zeigt. Nicht gleichzeitig mit `zapper.py` laufen lassen – beide drücken sonst Tasten
durcheinander.

### Installieren

1. Im Finder **⌘K** („Mit Server verbinden“) `smb://192.168.20.70/config`, „Registrierter Benutzer“,
   Name `homeassistant`, Passwort aus Einstellungen → Add-ons → Samba share → Konfiguration.
   Über `homeassistant.local` klappt es nicht zuverlässig: Der Name zeigt auch auf 192.168.20.49,
   wo nichts antwortet (Stand 27.10.2026).
2. Den Ordner `homeassistant/custom_components/tv_zapper` nach `config/custom_components/` kopieren –
   mit Finder oder `cp`, nicht mit `rsync` (dessen Hilfsdateien `._…` sperrt das Samba-Add-on).
3. Home Assistant neu starten (Einstellungen → System → Neu starten).
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **TV-Zapper**, Adresse eintragen,
   am Fernseher „Immer zulassen“ bestätigen (60 Sekunden Zeit). Zu spät bestätigt? Einfach noch einmal
   „Absenden“ – die Freigabe ist dann schon gespeichert.

Eingerichtet und einmal „nur lesen“ geprüft am 27.10.2026 (HA 2026.10.4): 37 Sender gelesen,
laufender Sender richtig erkannt, nicht umgeschaltet. Noch nicht geklärt: ob schon das Blättern in der
Programmzeitschrift den Sender umschaltet (Beobachtung von Max beim Lauf von `zapper.py`).

### Ohne Home Assistant ausprobieren

`homeassistant/probe_tv.py` führt den Fernseher-Teil der Integration (`tv.py`) direkt vom Mac aus:

```bash
python3 homeassistant/probe_tv.py --nur-verbinden                         # neuer Schlüssel wie in HA
python3 homeassistant/probe_tv.py --schluessel ~/.android/adbkey --einmal  # ein Durchgang, nur lesen
```

Braucht `pip install "adb-shell[async]==0.4.4"`.

Tests (Fernseher nachgebaut, laufen in einem echten Home Assistant 2026.10.4):

```bash
cd homeassistant && pip install homeassistant==2026.10.4 pytest-homeassistant-custom-component "adb-shell[async]==0.4.4" && python -m pytest tests
```
