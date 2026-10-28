# TV-Zapper

Schaltet am TCL-Google-TV selbstständig auf Sendungen, die mich interessieren.

`<TV-IP>` steht unten für die Adresse des Fernsehers im eigenen Netz.

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

- Ein TCL-Fernseher mit Google TV (getestet: TCL Smart TV Pro; die Paketnamen `com.tcl.tv` und die
  Programmzeitschrift sind TCL-spezifisch), ADB über Netzwerk in den Entwickleroptionen eingeschaltet.
- `adb` verbunden mit dem Fernseher (`adb connect <TV-IP>:5555`; bei Hängern `adb kill-server` und neu verbinden).
- Adresse des Fernsehers für `zapper.py`: Umgebungsvariable `TVZ_TV=<TV-IP>:5555` oder eine Zeile
  `<TV-IP>:5555` in der Datei `.tvz_tv` neben dem Skript (steht in `.gitignore`, kommt nicht ins Repo).
- Senderliste: Vorgabe ist die Liste „Favorit1“ der TV-Programmzeitschrift, eine andere über `TVZ_FAV=Favorit2`.
- Eigene Interessen: `interessen.json` anpassen (die mitgelieferte ist ein Beispiel).
- Fernseher an und auf dem Tuner-Eingang. Wiedereinschalten aus dem Ruhezustand
  geht nur per Wake-on-LAN (MAC des Fernsehers), nicht über Home Assistant allein.

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
Die Grundeinstellung sind meine Interessen – nach dem Einrichten unter „Konfigurieren“ an die eigenen anpassen.

**Was man braucht** (alles Weitere stellt man in HA ein, im Code steht keine Adresse):

- einen **TCL-Fernseher mit Google TV** und eingebautem Tuner. Erprobt nur an einem Gerät mit Android 14;
  die Integration bedient die TCL-eigene Programmzeitschrift (`com.tcl.tv`), andere Hersteller gehen nicht.
- Fernseher-Sprache **Deutsch**: Die Programmzeitschrift wird an deutschen Texten erkannt
  („Programmzeitschrift“, „Drücken Sie …“).
- In der Programmzeitschrift eine **eigene Senderliste** (Reiter) mit den Sendern, die in Frage kommen;
  ihr Name wird beim Einrichten eingetragen (bei mir `Favorit1`).
- Der Fernseher muss **ADB über das Netzwerk auf Port 5555** annehmen. Nach
  [Googles Anleitung](https://developers.google.com/cast/docs/android_tv_receiver/debugging):
  Entwickleroptionen freischalten (in den Einstellungen unter Info die Build-Nummer mehrmals mit OK anklicken,
  der Menüweg ist je Hersteller anders), dort **USB-Debugging** an. Viele Geräte lauschen danach noch nicht auf
  5555; dann einmal von einem Rechner aus `adb tcpip 5555` (per USB-Kabel). Prüfen: `adb connect <TV-IP>:5555`
  muss `connected` melden. Wie mein TCL damals freigeschaltet wurde, ist nicht festgehalten; bei ihm ist Port 5555
  offen (Stand 27.10.2026).
  Die Adresse des Fernsehers steht unter Einstellungen → Netzwerk; am besten im Router fest vergeben.
- Home Assistant mit Zugriff auf den Ordner `config` (z. B. Add-on „Samba share“).

**Wie sie den Fernseher erreicht:** Die eingebauten Integrationen reichen nicht. „Android TV Remote“
(`androidtv_remote`) kann nur Tasten
schicken, aber nichts vom Bildschirm lesen. Deshalb spricht die Integration selbst ADB über das Netzwerk
(Bibliothek `adb-shell`, dieselbe wie in der eingebauten Integration „Android Debug Bridge“) und liest die
Programmzeitschrift wie `zapper.py` mit `uiautomator dump`. HA bekommt dafür einen **eigenen ADB-Schlüssel**
(`/config/.storage/tv_zapper_adbkey`); beim ersten Verbinden fragt der Fernseher deshalb einmal
„USB-Debugging zulassen?“ – mit der Fernbedienung **Immer zulassen** wählen.

**Mit der TV-App (ab 0.3.0) geht es ohne Programmzeitschrift:** Ist die App aus `android/` installiert, fragt HA
sie über ihre Schnittstelle (`ABFRAGEN` mit `was=liste`, siehe „Schnittstelle für Home Assistant“ unten) nach allen
Sendern mit der laufenden Sendung, bewertet sie mit den Interessen aus HA (Sender, Sendung, Folge, Beschreibung;
`genre` ist beim TCL nur ein Zahlencode und zählt nicht) und schaltet per `UMSCHALTEN` – keine Tastendrücke,
ein Durchgang dauert Sekunden statt Minuten. Als Senderliste gilt dann die der TV-App (alle nicht ausgeschalteten
Sender), nicht der Reiter aus den Einstellungen. Läuft gerade der Zapper der TV-App, überspringt HA den Durchgang,
damit nicht beide gegeneinander schalten. Ohne App liest HA wie bisher die Programmzeitschrift.

**Einstellungen** (beim Einrichten bzw. über „Konfigurieren“ an der Integration):

| Einstellung | Bedeutung |
|---|---|
| Adresse / Port | IP-Adresse des Fernsehers / ADB-Port 5555 – beim Einrichten, später an der Integration über ⋮ → **Neu konfigurieren** (Einstellungen bleiben) |
| Senderliste | Name des Reiters in der Programmzeitschrift, Standard `Favorit1` |
| Interessen | eine Zeile je Kategorie: `Name \| Gewicht \| wort, wort*, …` |
| Nie nehmen | Wörter, mit Komma getrennt (Teleshopping …) |
| Sender nie nehmen | Sendernamen wie in der Programmzeitschrift, mit Komma getrennt |
| Bevorzugte Sender | eine Zeile je Sender: `N24 DOKU \| 1` – Bonuspunkte, zählen nur, wenn die Sendung auch passt |
| Laufzeit | wie lange der Zapper nach dem Einschalten läuft (Minuten) |
| Verweilzeit | Minuten zwischen zwei Prüfungen |
| Nur lesen | nie umschalten, nur bewerten (zum Ausprobieren) |
| Einblendung am Fernseher | Meldung im Bild beim Einschalten, Umschalten und Ende (siehe unten) |
| TV-Protokoll | regelmäßig nachsehen, was läuft (Sensor „Läuft jetzt“), auch wenn der Zapper aus ist; Standard an |
| Abfragetakt | wie oft das TV-Protokoll nachfragt, 5–600 Sekunden; Standard 15 |
| Speicher-Takt | alle wie viele Minuten der Arbeitsspeicher von Fernseher und TV-App gelesen wird, 0 = aus; Standard 5 |
| MAC-Adresse | optional: Fernseher beim Einschalten des Zappers per Wake-on-LAN wecken (siehe unten) |

Mehr muss man nicht kennen: Alles oben steht in HA (Einrichten, „Konfigurieren“, „Neu konfigurieren“), nichts in
Dateien. Die TV-App braucht **keine eigene Adresse und keinen Port** – HA erreicht sie über dieselbe ADB-Verbindung
(`am broadcast`, ihre Empfänger nehmen nur Aufträge aus der adb-Shell an). ADB und die IP des Fernsehers sind also
immer nötig, mit und ohne App. Den ADB-Schlüssel legt HA selbst an (`/config/.storage/tv_zapper_adbkey`).
Fest im Code und nicht einstellbar: die TCL-Programme (`com.tcl.tv`), die Namen der App-Schnittstelle,
Wake-on-LAN an Port 9 (Broadcast und direkt an den Fernseher), 90 Sekunden Warten nach dem Wecken.
Was die TV-App selbst einstellt (ihre Interessen, Senderauswahl, Werbe-Sensor), stellt man in der App ein;
HA bewertet mit seinen eigenen Interessen.

**Entitäten** (Gerät „TV-Zapper“):

- `switch.tv_zapper_zapper` – an: zappt für die Laufzeit, geht danach (oder nach drei Fehlern hintereinander)
  von selbst aus. Attribut `laeuft_bis`.
- `sensor.tv_zapper_aktueller_treffer` – z. B. `23 ProSieben HD: …`; Attribute Sender, Nummer, Sendung, Punkte,
  Kategorien, Aktion (bleibt/umgeschaltet/uebersprungen/fehler), bester und weitere Treffer.
- `sensor.tv_zapper_lauft_jetzt` – **TV-Protokoll**: im Abfragetakt (Standard 15 s), was gerade läuft (`167 ProSieben MAXX HD: Futurama`),
  „Fernseher aus“ oder „Andere App: …“; Attribute Sendung, Folge, Beschreibung, Start, Ende, Punkte, Kategorien,
  Werbung, dazu die Einstellungen der TV-App `werbung_umgehen` und `ausweichen_bevorzugt` (nur Anzeige; Werbung
  umgeht nur die App, HA nicht). Der Verlauf des Sensors in HA (Verlauf, Logbuch) zeigt, was wann lief. Sender und Sendung kennt HA nur
  über die TV-App; ohne sie zeigt der Sensor bloß „Fernsehbild“ bzw. die App im Vordergrund. Liest nicht, solange
  ein Durchgang den Fernseher bedient.
- **Arbeitsspeicher** (Diagnose, im Speicher-Takt, Standard alle 5 min; Verlauf und Statistik in HA zeigen den Trend):
  - `sensor.tv_zapper_arbeitsspeicher_verfugbar` – verfügbarer Arbeitsspeicher des Fernsehers in MB (`MemAvailable`);
    Attribute Gesamt, Swap gesamt und belegt. Der TCL hat 2,4 GB und ist oft knapp: Android beendet dann Apps.
  - `sensor.tv_zapper_speicher_tv_app` – Speicher der TV-App in MB (PSS); unbekannt, wenn sie nicht läuft.
    Wächst er über Tage stetig, deutet das auf ein Leck.
  - `sensor.tv_zapper_tv_app_vom_system_beendet` – wann Android die TV-App zuletzt **wegen Speichermangel** beendet hat,
    während sie etwas tat (Wichtigkeit bis 200: Zapper oder Werbe-Sensor liefen); Attribute Speicher beim Beenden,
    das zuletzt überhaupt gemeldete Ende mit Grund und die Zahl der Speicher-Beendigungen in Androids Liste
    (`dumpsys activity exit-info`, reicht nur einige Einträge zurück).
- `number.tv_zapper_laufzeit`, `number.tv_zapper_verweilzeit` – lassen sich auch im Dashboard oder per
  Automation ändern und wirken sofort, auch auf einen laufenden Zapper.
- `switch.tv_zapper_bei_werbung_zuerst_bevorzugte_sender` – setzt die Einstellung `ausweichen_bevorzugt` der
  **TV-App** (bei Werbung zuerst auf einen bevorzugten Sender ausweichen, sonst wie bisher auf einen werbefreien).
  HA weicht selbst nicht vor Werbung aus. Setzen per `EINSTELLEN` über die App-Schnittstelle, Zustand aus
  `ABFRAGEN`; „nicht verfügbar“, solange die App die Einstellung nicht meldet (ältere App, App oder Fernseher nicht
  erreichbar, TV-Protokoll aus).
  Ist gerade die Einstellungsseite der TV-App offen, speichert sie beim Schließen ihren eigenen Stand und
  überschreibt einen in der Zeit aus HA gesetzten Wert (laut App-Sitzung, 27.10.2026).
- `switch.tv_zapper_umschaltgrund_einblenden` – setzt die Einstellung `umschaltgrund_einblenden` der **TV-App**
  (ab 0.4.0), Standard aus; zum Nachvollziehen. Ist sie an, blendet die App bei jeder Umschaltung 12 s lang den Grund
  mit Punkten ein – bei ihren eigenen und bei denen des HA-Zappers: der schickt dafür beim `UMSCHALTEN` Zeilen mit
  (`--es grund "Zapper-Runde (HA) | Hip-Hop +5 („hip hop“ im Titel) | ★ bevorzugter Sender +1 | = 6 Punkte"`) und
  blendet dann selbst nichts ein. Verfügbar wie der Schalter darüber, sobald die App die Einstellung meldet.
- `button.tv_zapper_jetzt_prufen_nur_lesen` – ein Durchgang ohne Umschalten.
- Ereignis `tv_zapper_durchgang` nach jedem Durchgang (mit allen Treffern) für eigene Automationen.
- **Einblendung am Fernseher** (Option, Standard an): beim Einschalten („TV-Zapper an – läuft bis …“), nach jedem
  Umschalten („Sender – Sendung (Kategorien, Punkte)“) und am Ende. HA kann selbst nichts ins Bild zeichnen:
  Ist die TV-App aus `android/` mit dem Empfänger `EinblendungEmpfaenger` installiert, blendet sie den Text ein
  (`am broadcast -a io.github.mhd6271.tvzapper.EINBLENDEN … --es text …`), sonst schickt HA eine normale
  Android-Benachrichtigung – ob Google TV die sichtbar zeigt, ist noch nicht getestet. Weg über die App
  am 27.10.2026 16:11 mit dem Code der Integration geprüft: Einblendung erschien (Empfänger verlangt das Recht
  DUMP, das nur die adb-Shell hat).
- **Symbol:** `brand/icon.png` (256 px) und `icon@2x.png` (512 px), gezeichnet wie das Symbol der TV-App
  (`android/res/drawable/icon.xml`). HA 2026.10 liest den Ordner `brand/` einer eigenen Integration erst nach
  einem Neustart; bis dahin zeigt HA „icon not available“.

**Logbuch:** Jede Umschaltung durch einen TV-Zapper steht mit Grund im HA-Logbuch, Punkte ausgeschrieben, z. B.
„TV-Zapper (HA) hat auf 141 N24 DOKU („Hip Hop“) umgeschaltet, vorher 23 ProSieben HD („Navy CIS“) mit 0 Punkten.
Grund: Hip-Hop: 5 Punkte, „hip hop“ im Titel; Doku: 2 Punkte, „doku*“ im Titel; bevorzugter Sender: 1 Punkt extra.
Zusammen 8 Punkte.“ Umschaltungen des Zappers der **TV-App** (Werbung ausgewichen, zurück nach der Werbung, Interesse)
erscheinen als „TV-Zapper (TV-App) …“, sobald die App sie über `ABFRAGEN` im Feld `umschaltungen` meldet; HA liest
das im Abfragetakt mit und trägt jede Umschaltung einmal ein (nach einem HA-Neustart nur neue, nichts nachgetragen).
Ältere App-Versionen ohne dieses Feld liefern keine Einträge. Das Ereignis heißt `tv_zapper_umgeschaltet` und taugt
auch für Automationen (Felder `wer`, `nr`, `sender`, `sendung`, `punkte`, `text`, bei der App `grund`).
Senderwechsel mit der Fernbedienung zeigt weiterhin nur der Verlauf von „Läuft jetzt“.

**Wecken:** Beim Einschalten des Zappers prüft die Integration zuerst den Fernseher. Antwortet ADB, aber das Bild
ist aus (`mWakefulness` nicht `Awake`), drückt sie die Taste WAKEUP. Antwortet ADB nicht und ist unter „Konfigurieren“
eine MAC-Adresse eingetragen, schickt sie Wake-on-LAN (Broadcast, Port 9) und wartet bis zu 90 Sekunden auf ADB.
Am Fernseher muss dafür Wake-on-LAN eingeschaltet sein. Ist danach eine andere App vorn (Startbildschirm, Netflix …),
startet die Integration das Fernsehbild (`am start -n com.tcl.tv/com.tcl.player.TVActivity`) – wer den Zapper
einschaltet, will fernsehen. Das passiert nur beim Einschalten: Wechselt man danach selbst in eine andere App, wird
nicht gezappt, bis wieder das Fernsehbild vorn ist.

Wie `zapper.py` lässt die Integration den Fernseher in Ruhe, wenn er gerade etwas anderes als das
Fernsehprogramm zeigt. Nicht gleichzeitig mit `zapper.py` laufen lassen – beide drücken sonst Tasten
durcheinander.

### Installieren

1. Den Ordner `config` von Home Assistant öffnen, z. B. über das Add-on „Samba share“: am Mac im Finder
   **⌘K** `smb://homeassistant.local/config`, unter Windows `\\homeassistant.local\config`; Benutzer und
   Passwort stehen in der Konfiguration des Add-ons. Klappt es über den Namen nicht, die IP-Adresse von
   Home Assistant nehmen (bei mir zeigte `homeassistant.local` am 27.10.2026 auch auf eine alte Adresse).
2. Den Ordner `homeassistant/custom_components/tv_zapper` nach `config/custom_components/` kopieren –
   mit Finder oder `cp`, nicht mit `rsync` (dessen Hilfsdateien `._…` sperrt das Samba-Add-on).
3. Home Assistant neu starten (Einstellungen → System → Neu starten).
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **TV-Zapper**, Adresse eintragen,
   am Fernseher „Immer zulassen“ bestätigen (60 Sekunden Zeit). Zu spät bestätigt? Einfach noch einmal
   „Absenden“ – die Freigabe ist dann schon gespeichert.
5. Danach unter „Konfigurieren“ Interessen, Sender und Zeiten anpassen; zum Ausprobieren zuerst **Nur lesen** an.
6. Wer einen fertigen Dashboard-Abschnitt will (Schalter, Treffer, Laufzeit, Verweilzeit, Prüfknopf):
   [`homeassistant/dashboard-beispiel.yaml`](homeassistant/dashboard-beispiel.yaml), Anleitung steht in der Datei.

Eingerichtet und einmal „nur lesen“ geprüft am 27.10.2026 (HA 2026.10.4): 37 Sender gelesen,
laufender Sender richtig erkannt, nicht umgeschaltet. Umschalten über die Programmzeitschrift am 27.10.2026
19:21–19:26 am Fernseher geprüft: 37 Sender gelesen, auf 167 ProSieben MAXX HD (Futurama, 4 Punkte) umgeschaltet,
nachgelesen passt. Das Blättern in der Programmzeitschrift schaltet nicht um: `recent_play_channel_id` blieb die
fünf Minuten im Programmführer gleich und wechselte erst beim Umschalten.
Über die TV-App (0.3.0) am 27.10.2026 19:53 geprüft: von 1 Das Erste aus 36 Sender gelesen, per `UMSCHALTEN` auf
75 Comedy Central HD (Bob's Burgers) geschaltet, Nachfrage passt – ganzer Durchgang etwa 4 Sekunden, ohne Tastendruck.
Der Sensor „Läuft jetzt“ läuft seit dem HA-Neustart um 19:39 mit Daten der TV-App.
Am 28.10.2026 um 02:40 geprüft: Der Fernseher war über Nacht ganz aus (kein Ping, ADB-Port zu). Das Wake-on-LAN-Paket
der Integration (`sende_wol`, vom Mac aus geschickt) weckte ihn: nach 2 Sekunden Ping und ADB-Port offen,
`mWakefulness=Awake`, Fernsehbild vorn. Der Schalter „Bei Werbung zuerst bevorzugte Sender“ setzte in HA
`ausweichen_bevorzugt` der TV-App auf `false` und wieder auf `true`, jeweils nach `ABFRAGEN` bestätigt. Nicht geprüft ist das
Wecken aus HA heraus beim Einschalten des Zappers.

### Ohne Home Assistant ausprobieren

`homeassistant/probe_tv.py` führt den Fernseher-Teil der Integration (`tv.py`) direkt vom Rechner aus:

```bash
python3 homeassistant/probe_tv.py --host <TV-IP> --nur-verbinden                          # neuer Schlüssel wie in HA
python3 homeassistant/probe_tv.py --host <TV-IP> --schluessel ~/.android/adbkey --einmal  # ein Durchgang, nur lesen
```

Braucht `pip install "adb-shell[async]==0.4.4"`.

Tests (Fernseher nachgebaut, laufen in einem echten Home Assistant 2026.10.4):

```bash
cd homeassistant && pip install homeassistant==2026.10.4 pytest-homeassistant-custom-component "adb-shell[async]==0.4.4" && python -m pytest tests
```

## TV-App (läuft direkt auf dem Fernseher)

In [`android/`](android/) liegt die Google-TV-App **TV-Zapper** (`io.github.mhd6271.tvzapper`). Sie macht dasselbe
wie `zapper.py`, braucht aber keinen Mac und keine Tasten: Sie liest Sender und laufende Sendungen direkt aus der
Programmdatenbank von Android TV (`TvContract`, gefüllt vom TCL-Tuner) – auf dem Bildschirm passiert dabei nichts, es
wird also auch nicht beim Lesen umgeschaltet. Umgeschaltet wird nur einmal, auf den besten Treffer, per
`ACTION_VIEW` auf den Sender (die TCL-App `com.tcl.tv` nimmt das an). Danach blendet sie 6 Sekunden lang oben links
ein, worauf sie umgeschaltet hat und warum.

**In der App einstellbar** (alles mit der Fernbedienung): Interessen-Kategorien mit Gewicht und Wörtern, Liste
„Nie“, Laufzeit (Std./Min.), Verweilzeit je Sender, je Sender *an* / *bevorzugt ★* / *aus* (OK wechselt),
Bonus für bevorzugte Sender. Bevorzugte werden zuerst geprüft und bekommen den Bonus, aber nur bei einem Treffer.
Die Grundeinstellung ist `interessen.json` zum Zeitpunkt des Baus (gleiches Format inkl. `sender_nie`,
`sender_bevorzugt`, dazu `sender_an`); „Grundeinstellung laden“ setzt darauf zurück. Welche Sender
mitmachen, kommt ab Werk vom Fernseher: TCL markiert in der Datenbank 37 Sender mit `internal_provider_flag2 = 1` –
genau die freien HD-Sender (alle 18 aus der Liste unten, dazu u. a. 1 Das Erste HD, 75 Comedy Central HD,
81 Deluxe Music HD, 125 kabel eins Doku, 139 MTV HD); verschlüsselte wie Sky haben 0. Dass das genau Favorit1 ist,
ist abgeleitet, nicht von TCL dokumentiert. In der App zeigt „Alle Sender zeigen“ auch die übrigen.

**Bedienung:** „Start“ läuft im Hintergrund (Vordergrund-Dienst mit Benachrichtigung) bis die Laufzeit um ist,
„Stopp“ beendet, „Einmal prüfen (nur lesen)“ bewertet nur und schreibt das Ergebnis ins Protokoll unten auf der Seite.
Zeigt der Fernseher etwas anderes als das Fernsehprogramm oder ist er aus, lässt die App ihn in Ruhe.
Beendet Android den Dienst (z. B. bei Speichermangel – der TCL hat nur 2,4 GB RAM), startet er sich von selbst neu
und läuft bis zum gemerkten Ende weiter (ab 0.3.3; Protokoll: „Von Android beendet und neu gestartet“).

**Berechtigungen** (Zeile „Berechtigungen“ in der App zeigt ✓/✗):
- *Fernsehprogramm lesen* (`READ_TV_LISTINGS`) – Abfrage beim ersten Start.
- *Nutzungszugriff* – damit die App weiß, ob gerade das Fernsehprogramm vorn ist. Ohne schaltet sie nie um.
- *Über anderen Apps einblenden* – Android erlaubt einer App im Hintergrund sonst nicht, das Fernsehbild zu öffnen;
  auch für die Einblendung nötig.

**Fertige App:** [neueste Version herunterladen](https://github.com/mhd6271/tv-zapper/releases/latest/download/tv-zapper.apk)
(Releases auf GitHub, Prüfsumme jeweils in der Release-Notiz). Signiert mit dem Release-Schlüssel des Projekts
(Zertifikat SHA-256 `8c371cfa…3f06ee`); eigene Builds mit anderem Schlüssel lassen sich nicht darüber installieren.
Neue Versionen: `versionCode`/`versionName` in `android/AndroidManifest.xml` erhöhen, `android/build.sh`, dann ein
GitHub-Release als „latest“ (kein Pre-Release) mit der Datei genau unter dem Namen `tv-zapper.apk` – muehlbronner.de
holt sich alle 15 min das neueste Release und zeigt Version und Prüfsumme an.

**Bauen und installieren** (kein Gradle, nur Java 17 und das Android-SDK mit build-tools 36 und platform 35;
Pfade über `JAVA_HOME`, `ANDROID_HOME`, eigener Schlüssel über `TVZ_KEYSTORE`):

```bash
android/build.sh
```

```bash
adb -s <TV-IP>:5555 install -r android/build/tv-zapper.apk
```

`build.sh` signiert mit dem Schlüssel aus `~/.tvzapper/keystore.properties` (`storeFile`, `alias`, `password`;
nie ins Repo, Sicherungskopie aufbewahren – ohne ihn keine Updates über installierte Apps), sonst mit dem
Debug-Schlüssel `~/.android/debug.keystore`. Protokoll: `adb logcat -s TVZapper`.

**Maskottchen:** Etwa 3 s nach „Start“ hüpft unten rechts ein kleiner Comic-Fernseher ins Bild, winkt, sagt
„Hallo! TV-Zapper läuft“ und rennt dann verblassend nach rechts hinaus (gezeichnet, keine Grafikdateien; Knopf
„Maskottchen“ zum Ausprobieren). Einzelbilder: `docs/screenshots/7-maskottchen-gruesst.jpg`, `8-…-rennt-weg.jpg`.

**Alle Einstellungen der TV-App im Überblick** (alles in der App, nichts fest im Code, nichts nur per adb):

| Wert | Wo in der App | Vorgabe |
|---|---|---|
| Berechtigungen (Fernsehprogramm lesen, Nutzungszugriff, Über anderen Apps) | Knopf „Einrichten“ (startet beim ersten Öffnen von selbst); Zeile „Berechtigungen“ zeigt ✓/✗ | – |
| Start/Stopp | Knöpfe oben; „Start“ öffnet das Fernsehbild | – |
| Laufzeit, Verweilen je Sender | „Zeit“ | ohne Ende (0), 5 min |
| Interessen (Name, Gewicht, Wörter), „Nie“ | „Interessen“, „Nie“; „Grundeinstellung laden“ | aus `interessen.json` |
| Sender an / bevorzugt / aus, Bonus | „Sender“ | Favoritenliste des Fernsehers, sonst alle sichtbaren |
| Werbung umgehen an/aus, werbefreie Ausweichsender, Zeitgrenze | „Werbung umgehen“ | an; ZDFinfo, zdf_neo, arte …; 6 min |
| Bei Werbung zuerst auf bevorzugte Sender ★ ausweichen (`ausweichen_bevorzugt`): bester bevorzugter Sender, der nicht gerade selbst Werbung hat, sonst ein werbefreier | „Werbung umgehen“ | aus |
| FRITZ!Box-Adresse | „Werbung umgehen“ | `fritz.box` |
| Umschaltgrund einblenden (`umschaltgrund_einblenden`, Fehlersuche): bei jeder Umschaltung 12 s Sender, Grund und Punkte einzeln mit Summe | „Fehlersuche“ | aus |
| Tuner-Eingang, Fernseh-App | „Fernseher“ (leer = automatisch, Erkanntes steht dabei) | automatisch |
| Für Home Assistant: IP des Fernsehers, adb an/aus, adb-Port, Befehle | „Schnittstelle für Home Assistant“ (nur Anzeige) | – |

Die Schnittstelle hat keinen eigenen Port: Home Assistant spricht den Fernseher über adb an (IP des Fernsehers,
Port 5555). Dafür muss am Fernseher USB-Debugging an sein und adb übers Netz lauschen – die App zeigt, ob das so
ist, und wie man es einschaltet (einmal per USB `adb tcpip 5555`; Menüwege je Hersteller verschieden).

**Auf einem anderen Fernseher:** Die App braucht nur Android TV / Google TV mit eingebautem Tuner, der seine
Sender in die Android-TV-Datenbank schreibt. Tuner-Eingang und Fernseh-App erkennt sie selbst (Eingang vom Typ
Tuner mit den meisten Sendern; App, die einen Sender öffnet) und zeigt das Ergebnis unter „Fernseher“, wo man
beides auch von Hand eintragen kann. TCL-Besonderheiten mit Rückfall: Die Favoritenliste erkennt sie an
`internal_provider_flag2`, ohne diese Markierung gelten alle sichtbaren Sender als Vorgabe. Den laufenden Sender
meldet TCL in `recent_play_channel_id`; andere Fernseher tun das nicht öffentlich, dann merkt sich die App den
zuletzt von ihr gewählten Sender (Umschalten von Hand bemerkt sie dort nicht). Werbung umgehen braucht einen
SAT>IP-Empfänger im Netz mit M3U-Listen wie die FRITZ!Box Cable (Adresse in der App, Vorgabe `fritz.box`); die
werbefreien Ausweichsender sind deutsche Vorgaben und in der App änderbar. Geprüft ist das alles nur am TCL.

**Am Fernseher geprüft (27.10.2026, 15:05–15:11):** 377 Tuner-Sender in der Datenbank, 36 eingeschaltet
(37 Favoriten ohne Disney Channel HD aus `sender_nie`), alle 36 mit laufender Sendung. „Start“ auf Comedy Central
(4 P., Bob's Burgers) → nach 10 s umgeschaltet auf 139 MTV HD (7 P., Love & Hip Hop Atlanta), bestätigt über
`settings get global recent_play_channel_id` (1126 → 1190); Android meldet „Background activity start … allowed
because SYSTEM_ALERT_WINDOW permission is granted“. Einblendung: in der App per Bildschirmfoto gesehen, über dem
Fernsehbild meldet Android das Fenster als sichtbar – mit eigenen Augen am Fernseher noch nicht bestätigt
(Bildschirmfotos vom Tunerbild sind leer). Danach im Hintergrund weitergelaufen: 15:15 MTV (inzwischen 2 P.) →
kabel eins Doku (6 P., Ancient Aliens), 15:20 „bleibt“; der Vordergrund-Dienst lief noch, TCL hat ihn nicht beendet.
Auffällig: Shopping Queen, Barbara Salesch u. Ä. bekommen die Dokumentation-Punkte – die App bewertet auch die
Beschreibung jeder Sendung; vermutlich steht dort „Doku-Soap“ o. Ä. (nicht nachgesehen).

### Werbung umgehen (TV-App, seit 27.10.2026)

Der Fernseher selbst gibt einer App weder Bild noch Ton des Tuners: Bildschirmfotos sind leer, und der
Ton-Mitschnitt (`android/tonprobe/`, `AudioPlaybackCapture` mit Freigabe) liefert nur Stille (Wert 0); das Mikrofon
hört nur Rauschen. Deshalb nimmt die **FRITZ!Box 6660 Cable** den laufenden Sender nebenher als zweiter Empfänger
auf (DVB-C über SAT>IP, Senderlisten unter `http://fritz.box/dvb/m3u/tvsd.m3u` bzw. `tvhd.m3u`). Geguckt wird
weiter über den Tuner des Fernsehers.

**Wie es erkennt:** Private Sender blenden in der Werbung ihr Senderlogo aus. Die App (`Sensor.java`) holt den
Stream per RTSP/RTP, decodiert ihn mit dem Hardware-Decoder des TCL (`c2.mtk.mpeg2.decoder`, läuft parallel zum
Fernsehbild), nimmt ~3,4 Bilder/s in halber Auflösung und prüft in der Logo-Ecke, ob die gelernten Logo-Kanten da
sind (`Logo.java`). Werbung = in 10 s mindestens 80 % ohne Logo, vorbei = in 30 s mindestens 80 % mit Logo.
Dann schaltet sie auf den besten **werbefreien Ausweichsender** (Vorgabe ZDFinfo, zdf_neo, arte, tagesschau24,
3sat, phoenix, WDR, hr – in der App änderbar, Punkte nach Interessen) und danach zurück, jeweils mit Einblendung.
Schaltet man selbst um, wird der neue Sender beobachtet. Wer mitten in eine Pause hineinschaltet (selbst oder durch den Zapper), wartet nicht
10 s: In den ersten 30 s nach dem Hineinschalten genügen 4 von 5 Sekunden ohne Logo – nur bei Sendern mit fertiger
Logo-Maske, ohne Maske wird gelernt statt geraten (nicht jede Szene ohne Logo ist Werbung). Sender mit gerade
erkannter Werbung meidet der Zapper bis zum erwarteten Pausenende (gemessener Durchschnitt, sonst 6 min); nach dem
Zurückschalten weicht die App frühestens nach 3 min wieder aus (kein Hin und Her). Spätestens nach einer Zeitgrenze geht es auf jeden Fall
zurück (Vorgabe 6 min, einstellbar; sobald für den Sender Pausen gemessen sind: deren Durchschnitt + 1 min). Die
gemessenen Pausen je Sender zeigt die App an (`werbepausen.json`). Öffentliche Zahlen zur Blocklänge je Sender gibt
es nicht; erlaubt sind 20 % Werbung je Zeitfenster (§ 70 MStV), Spielfilme einmal je 30 min unterbrechen (§ 9). Logos von ProSieben, SAT.1, Kabel Eins, Pro7 MAXX,
kabel eins Doku und sixx liegen fertig bei (`android/assets/logos/`), andere lernt die App beim ersten Mal in etwa
5 min und speichert sie.

**Am Mac geprüft** (20 min Aufnahme von 6 Sendern, 15:56–16:16 Uhr, Bilder angesehen): In allen Lücken ohne Logo
liefen echte Spots (Kaufland, Lidl, Milkana, ERGO …, bei sixx der „WERBUNG“-Trenner), mit Logo lief die Sendung.
Logo-Wert in der Sendung meist 0,97–1,0, in der Werbung meist 0,05–0,2. Erkennung des Pausenbeginns nach 7–19 s,
keine Fehlalarme in der Sendung. Lautstärke taugt nicht als Merkmal (Werbung und Sendung gleich laut, 62–64 dB).

**Am Fernseher geprüft:** Sensor auf kabel eins Doku 16:28–17:20 stabil (Logo-Wert 0,93–1,0); 17:05:16 „Werbung“
erkannt → phoenix HD, 17:06:31 zurück auf kabel eins Doku (beide Wechsel vom Fernseher bestätigt). Ob das eine
echte Werbepause war (nur 74 s), ist nicht belegt – deshalb legt die App seitdem bei jeder Entscheidung
Kontrollbilder ab: `adb pull /sdcard/Android/data/io.github.mhd6271.tvzapper/files/kontrolle`. Erste so belegte Pause:
ProSieben 18:14:56 erkannt (2 s vor dem „WERBUNG“-Trenner, Simpsons-Abspann ohne Logo), Wechsel zu ZDFinfo,
18:20:58 zurück über die 6-min-Grenze, Logo kam fast gleichzeitig zurück (Pause 410 s).
Logos werden nur in den oberen Ecken gesucht, solange dort eines ist: Unten lernte das Verfahren am Mac sonst
Sendungslogos (SAT.1 „Auf Streife“), Spielstände (RTL Fußball) oder Laufbänder (n-tv). Der Sensor ruht, solange
etwas anderes als das Fernsehbild vorn ist, und läuft danach für denselben Sender weiter.

**Grenzen:**
- Die FRITZ!Box liefert die Frequenz 562 MHz nicht (MTV, Comedy Central) – dort keine Werbeerkennung.
- Ein Stream je Gerät: Ein zweites Gerät (z. B. der Mac) daneben lief bei uns nur ~3 min.
- Sender ohne Logo-Ausblendung in der Werbung werden nicht erkannt; Senderwerbung/Trailer ohne Logo gelten als
  Werbung.

**Schnittstelle für Home Assistant & Co.** (per adb, nur mit DUMP-Recht, also adb-Shell oder System; Antwort als
JSON in `data="…"` der Ausgabe von `am broadcast`):

```bash
adb shell am broadcast -a io.github.mhd6271.tvzapper.ABFRAGEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger
adb shell am broadcast -a io.github.mhd6271.tvzapper.ABFRAGEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger --es was liste
adb shell am broadcast -a io.github.mhd6271.tvzapper.UMSCHALTEN -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger --es nr 167 --es text "'Hinweis im Bild'"
```

`ABFRAGEN` liefert `zeit`, `bildschirm_an`, `vorn` (App im Vordergrund), `fernsehbild_vorn`, `zapper_laeuft`,
`werbe_sensor` (Text), `werbung` (true/false, null wenn unbekannt), `werbung_umgehen`, `ausweichen_bevorzugt`, `umschaltgrund_einblenden`, `umschaltungen` (ab 0.4.0) und `jetzt` = laufender Sender mit `nr`, `sender`,
`id` (TvContract), `zustand` (an/bevorzugt/aus), `sendung`, `folge`, `genre` (wie vom Sender geliefert, bei TCL ein
DVB-Zahlencode), `beschreibung`, `start`, `ende` (ISO 8601), `punkte`, `treffer`. Mit `was=liste` zusätzlich `liste`:
alle nicht ausgeschalteten Sender in derselben Form. `umschaltungen` sind die letzten 20 Umschaltungen, neueste
zuletzt: `id` (ms, steigt streng, auch über Neustarts), `zeit`, `grund` (`interesse` = Zapper-Runde, `werbung` = Werbung
umgangen, `zurueck` = Werbung vorbei, `zurueck_zeitgrenze`, `zurueck_fehlalarm` = doch keine Werbung, `von_aussen` =
`UMSCHALTEN`), `von` (`nr`, `sender`, `punkte`; null wenn unbekannt), `nr`, `sender`, `sendung`, `punkte` (null bei einem
„Nie“-Wort), `kategorien` (`name`, `punkte`), `bevorzugt`, `bevorzugt_bonus`, `bestaetigt`, `text` (Einblendung),
`erklaerung` (nur mit `grund` von außen). `UMSCHALTEN` (`nr` oder `sender`, optional `text` für die
Einblendung, `grund` mit Zeilen „a | b | c“ für die Einblendung bei „Umschaltgrund einblenden“) antwortet `{"ok", "nr", "sender"}`; `ok` = der Fernseher meldet den neuen Sender. Am TCL geprüft:
Abfrage 0,3 s, Liste 36 Sender, Umschalten 0,8 s. Mit `--es was pausen` liefert `ABFRAGEN` die gemessenen Werbepausen je Sender
(`anzahl`, `durchschnitt_s`, Einzelwerte `pausen` mit `ende` in ms und `s`); `PAUSEN_LOESCHEN` (`--es sender …`,
optional `--el von <ms> --el bis <ms>` für einen Zeitraum, `--ez alt true` für die Sammelwerte aus 0.2.x/0.3.0)
entfernt Fehlmessungen und antwortet mit `vorher`, `entfernt`, `nachher`. `EINSTELLEN` setzt `--es ausweichen_bevorzugt true|false`,
`--es werbung_umgehen true|false` und/oder `--es umschaltgrund_einblenden true|false` und antwortet mit `ok` und allen drei Werten (ungültiger Wert:
`result=1` mit `fehler`). Ist dabei die Einstellungsseite der App offen, speichert sie beim Schließen ihren eigenen
Stand – dann den Schalter in der App benutzen.

Starten auch ohne Fernbedienung: `adb shell am start -n io.github.mhd6271.tvzapper/.MainActivity --ez start true`.
