# Kompatibilität mit anderen Geräten

Diese Liste zeigt, wo der TV-Zapper vom TCL-Fernseher, von Android 14/Google TV, von der deutschen Oberfläche oder von
Max' Home-Assistant-Aufbau abhängt. Jede Stelle steht auch im Quellcode, dort als Kommentar `KOMPAT:` (in Kotlin/Java
`// KOMPAT:`). Geändert ist bisher nichts, das hier ist nur die Bestandsaufnahme.

Suchen: `grep -rn "KOMPAT:" .`

## Home-Assistant-Integration und zapper.py

Stand 28.10.2026, HA-Sitzung. Durchgesehen wurden alle Dateien in `homeassistant/custom_components/tv_zapper/`
sowie `homeassistant/probe_tv.py` und `zapper.py`. Geprüft ist alles nur mit dem TCL (Android 14, Google TV,
deutsche Oberfläche) und mit HA 2026.10.4 auf einem HA Green. Was mit „vermutlich“ oder „nicht nachgeschaut“
markiert ist, ist nicht belegt.

Es gibt zwei Wege. Mit der TV-App aus `android/` liest die Integration Sender und Sendungen über deren Schnittstelle
(ABFRAGEN/UMSCHALTEN). Ohne die App liest sie die Programmzeitschrift per `uiautomator` und schaltet per Tasten um.
Der zweite Weg ist fast vollständig an den TCL gebunden.

### Fernseher und Hersteller (TCL)

| Stelle | Abhängigkeit | Folge auf anderen Geräten |
|---|---|---|
| `tv.py` `TV_APP`, `GUIDE_APP`; `zapper.py` dieselben | Activities `com.tcl.tv/com.tcl.player.TVActivity` und `…epg.EpgProActivity` | Ohne TV-App gilt das Fernsehbild nie als „vorn“, jeder Durchgang wird übersprungen; `fernsehbild_holen()` startet eine Activity, die es nicht gibt |
| `tv.py` `close_guide` | BACK springt beim TCL im Fernsehbild auf den vorigen Sender | Anderswo kann BACK etwas anderes tun; die Schutzprüfung bleibt nötig |
| `tv.py` `open_guide` | `KEYCODE_GUIDE` öffnet die Programmzeitschrift | Andere Live-TV-Apps reagieren nicht oder anders |
| `tv.py` `ensure_fav_tab` | Reiter links, mit LINKS erreichbar, Erkennung per `content-desc` | Reiter wird nicht gefunden, der Durchgang bricht ab |
| `tv.py` `collect`; `zapper.py` `collect` | 6×20 Schritte nach oben, höchstens 200 Schritte, 0,35 s je Schritt | Favoritenlisten über etwa 120 Sender werden nicht ab oben gelesen; langsame Geräte brauchen mehr Zeit |
| `tv.py` `tune`; `zapper.py` `tune` | Ziffern einzeln mit 0,8 s Abstand, dann OK | Andere Fernseher schalten ohne OK um, oder OK öffnet eine Info- bzw. Senderliste |
| `tv.py` `app_sendung` | TvContract-Felder, wie TCL sie füllt (Genre als DVB-Code) | Fehlende Beschreibungen ergeben weniger Treffer |
| `tv.py` `wecken`, `fernsehbild_holen` | 8 s bzw. 5 s Wartezeit, am TCL gemessen | Langsamere Geräte brauchen eventuell länger |
| `entity.py` | Gerätemodell heißt „TCL-Fernseher …“ | Nur eine Beschriftung, ohne Auswirkung |

### Android-Version und Google TV

| Stelle | Abhängigkeit | Folge |
|---|---|---|
| `tv.py` `focus_app`; `zapper.py` `focus_app` | Format `mCurrentFocus=Window{… paket/activity}` aus `dumpsys window` (Android 14) | Anderes Format: Ergebnis ist leer, alles gilt als „nicht vorn“. Das ist sicher, aber der Zapper tut dann nichts |
| `tv.py` `wach` | `mWakefulness=Awake` aus `dumpsys power` (AOSP) | Heißt das Feld anders, wird bei jedem Start WAKEUP gesendet, meist harmlos |
| `tv.py` `wecken` | `KEYCODE_WAKEUP` (ab Android 5) | Manche Geräte schalten damit nur den Bildschirm ein, nicht den Tuner |
| `tv.py` `key`; `zapper.py` | Mehrere Tasten in einem `input keyevent` | Ältere Android-Fassungen drücken vermutlich nur die erste Taste, das Blättern wird dann sehr langsam (nicht geprüft) |
| `tv.py` `dump`; `zapper.py` `dump` | `uiautomator dump` nach `/sdcard` | Braucht ein beschreibbares `/sdcard`; scheitert manchmal bei Video und Animation; auf schwachen Geräten langsam |
| `tv.py` `speicher_lesen` | `dumpsys meminfo -s`, `dumpsys activity exit-info` (ab Android 11) | Passt das Format nicht, bleiben die Speicher-Sensoren leer, es gibt keinen Fehler |
| `tv.py` `einblenden` | `cmd package query-receivers`, `cmd notification post` | Seit welcher Android-Fassung es sie gibt, ist nicht nachgeschaut. Google TV zeigt Benachrichtigungen meist nicht im Bild, ohne TV-App gibt es also oft keine sichtbare Einblendung |

### Sprache der Oberfläche (Deutsch) und deutsche Sender

| Stelle | Abhängigkeit | Folge |
|---|---|---|
| `logik.py` `parse_guide`; `zapper.py` `parse_guide` | Texte „Programmzeitschrift“, „Drücken Sie …“, „drücken Sie OK“; Genre-Trenner „·“; Merkmale „Keine/Stereo/FHD/TTX/Dolby Audio“ | Bei anderer Systemsprache werden keine Sender und kein Kopf gefunden |
| `logik.py` `TABS` | Reiternamen „Alle, Streamen, Digital, Radio, Kostenlos, Daten/Andere“ | Kein Reiter wird erkannt, Abbruch. Gewollt: nie in „Alle“ blättern |
| `const.py`, `config_flow.py`, `logik.py`, `zapper.py` | Vorgabe der Favoritenliste „Favorit1“ | Lässt sich in den Optionen bzw. mit `TVZ_FAV` ändern. Der englische Name ist nicht nachgeschaut |
| `logik.py` `word_rx`; `zapper.py` | Wortgrenzen nur für a–z und äöüß | In anderen Sprachen zählt ein Akzentbuchstabe als Grenze, das ergibt ungenaue Treffer |
| `logik.py` `sender_schluessel`, `_SENDER_ALIAS` | Gleichsetzungen für deutsche Sender; nur a–z, 0–9 und äöüß bleiben übrig | Namen in anderer Schrift werden leer (passen nie) oder fallen zusammen. Muss gleich bleiben mit `FritzTv.norm` der App |
| `const.py` `_VORLAGE` (`vorlage.json`) | Interessen und Sendernamen auf Deutsch | Trifft in anderen Ländern kaum etwas, muss angepasst werden |
| `translations/` | Nur `de.json` und `en.json` | In anderen Sprachen zeigt HA den englischen Text |
| `dashboard-beispiel.yaml` | Entitäts-IDs aus den deutschen Namen, z. B. `sensor.tv_zapper_lauft_jetzt` | Stimmen nur, wenn nichts umbenannt wurde. Bei mehreren Fernsehern bekommen die IDs Zusätze |

### Netzwerk, ADB und Wake-on-LAN

| Stelle | Abhängigkeit | Folge |
|---|---|---|
| `tv.py` `verbinden`; `config_flow.py` (Port 5555) | Klassisches ADB über TCP, in den Entwickleroptionen eingeschaltet | Manche Geräte vergessen das nach Neustart oder Update. Bietet ein Gerät nur „Kabelloses Debugging“ (Android 11+, Koppeln, wechselnder Port), kann die Integration es vermutlich nicht erreichen (adb-shell und Kopplung sind nicht geprüft) |
| `tv.py` `verbinden` | Abfrage „USB-Debugging zulassen?“ mit „Immer zulassen“ | Bei manchen Herstellern sieht sie anders aus oder fehlt |
| `const.py` `SCHLUESSEL_DATEI` | Schlüssel in `/config/.storage` | Nach einer Neuinstallation ohne `.storage` kommt die Abfrage am Fernseher erneut |
| `tv.py` `magic_packet`, `sende_wol` | Wake-on-LAN an Broadcast 255.255.255.255:9 und an die IP | Geht nur im selben Netz. Ein Docker-Netz ohne host-Modus, ein anderes VLAN oder ein WLAN, das Broadcasts filtert, blockiert es. Viele Fernseher wecken nur über LAN oder mit einer Option wie „Netzwerk-Standby“ |
| `config_flow.py` `_adresse_ok` | Nur `A–Z a–z 0–9 . : - [ ]` | IPv6 mit Zone (`fe80::1%eth0`) und Namen mit Unterstrich werden abgelehnt |
| `zapper.py` `adb` | Programm `adb` im PATH und ein laufender adb-Server | Nur auf einem Rechner mit Android Platform Tools |

### Home Assistant, Python und Bibliotheken

| Stelle | Abhängigkeit | Folge |
|---|---|---|
| `manifest.json` (JSON, kein Kommentar möglich) | `adb-shell[async]==0.4.4` fest gepinnt, wie `androidtv` in HA 2026.10 | Pinnt HA core später eine andere Fassung, kann die Installation scheitern. adb-shell ist reines Python (rsa/pyasn1), läuft also auf ARM und x86 |
| `manifest.json` / Repo | Keine `hacs.json` mit Mindestversion von HA | HACS warnt bei zu alter HA-Fassung nicht |
| `__init__.py` | `type X = …` (Python 3.12), `Task.cancelling()` (3.11) | HA 2026.10 verlangt Python 3.14.2, alte HA-Fassungen laden die Integration nicht |
| `__init__.py` `_umgeschaltet_melden` | `async_get_device_by_identifier` (in 2026.10.4 vorhanden, seit wann nicht nachgeschaut) | Ältere HA: AttributeError, das Logbuch-Ereignis scheitert. Das alte `async_get_device` fällt laut HA mit 2027.8 weg |
| `config_flow.py` | `_get_reconfigure_entry`, `async_update_reload_and_abort(data_updates=)`, OptionsFlow ohne `config_entry` | Erst in neueren HA-Fassungen, aus dem Gedächtnis etwa ab 2024.11/12 (nicht nachgeschaut) |

### Zeitzonen

| Stelle | Abhängigkeit | Folge |
|---|---|---|
| `sensor.py` `_ortszeit` | exit-info liefert Ortszeit des Fernsehers ohne Zone, sie wird als HA-Zeitzone gelesen | Hat der Fernseher eine andere Zeitzone, ist der Sensor um den Unterschied verschoben |
| `__init__.py` `starten` | Die Einblendung „läuft bis HH:MM“ steht in HA-Zeit | Passt dann nicht zur Uhr am Fernseher |
| `zapper.py` `now` | Ortszeit des Rechners | Nur für Protokoll und Ausgabe |

Gefährdet ist in Max' Aufbau nichts davon (TCL, Deutsch, HA 2026.10.4, gleiches Netz, gleiche Zeitzone).

## TV-App (`android/`)

Stand 28.10.2026, App-Sitzung, Version 0.4.5. Durchgesehen wurden alle Dateien in `android/src/`, dazu
`AndroidManifest.xml` und `build.sh`. Die Hilfs-App `android/tonprobe/` ist ein Test und wird nicht ausgeliefert.
Geprüft ist alles nur am TCL (Android 14, API 34, Google TV, MediaTek) mit der FRITZ!Box 6660 Cable und Vodafone-Kabel.

**Belegt** sind die API-Stufen (aus `api-versions.xml` des SDK, platform 35) und die direkten Aufrufe im fertigen dex
(mit `dexdump` nachgesehen). Die Berechtigungsstufen hat `dumpsys package` am TCL gezeigt. Alles, was „ungeprüft“
oder „vermutlich“ heißt, ist nicht belegt. Zeilen beziehen sich auf den `KOMPAT:`-Kommentar.

Risiko: **hoch** = geht dort sicher oder sehr wahrscheinlich nicht, **mittel** = geht auf einem Teil der Geräte nicht,
**niedrig** = kleine Abweichung.

### Android-Version (minSdk 26, geprüft nur 34)

| Datei:Zeile | Abhängigkeit | Risiko | Folge auf anderen Geräten | Möglicher Weg später |
|---|---|---|---|---|
| `AndroidManifest.xml:7` | `minSdk 26` zugesagt, der Code braucht aber API 29 bzw. 33 | hoch | Android 8 bis 12 stürzen ab (Zeilen unten) | minSdk ehrlich auf 33 setzen oder die drei Stellen unten ersetzen |
| `Config.java:83` | `InputStream.readAllBytes()` (API 33), direkt im dex | hoch | Android 8 bis 12: Absturz beim ersten Start (noch keine Einstellungsdatei); `NoSuchMethodError` fängt `catch (Exception)` nicht | Eigene Leseschleife mit `ByteArrayOutputStream` |
| `Logo.java:245` | dasselbe für die mitgelieferten Logos | hoch | Android 8 bis 12: Werbe-Thread stürzt ab, sobald ein Sender mit mitgeliefertem Logo beobachtet wird | wie oben |
| `ZapperService.java:63` | `startForeground(id, n, typ)` (API 29), Typ `SPECIAL_USE` (API 34) | hoch (8/9), mittel (10 bis 13) | Android 8/9: Dienst stürzt beim Start ab. 10 bis 13: unbekannter Typ, Verhalten ungeprüft | Nach `Build.VERSION.SDK_INT` verzweigen: unter 29 ohne Typ, unter 34 Typ 0 oder dataSync |
| `MainActivity.java:506` | `unsafeCheckOpNoThrow` (API 29) | hoch | Android 8/9: Oberfläche stürzt beim Anzeigen ab | Unter 29 `checkOpNoThrow` |
| `AndroidManifest.xml:87` | Dienst-Typ `specialUse` | mittel | Google Play verlangt eine Begründung. Ältere Android-Versionen kennen den Typ nicht (ungeprüft) | Bei Store-Einreichung begründen |
| `ZapperService.java:244` | Start einer Aktivität aus dem Hintergrund nur dank `SYSTEM_ALERT_WINDOW` (Sperre seit Android 10) | mittel | Künftige Android-Versionen (15+) oder Hersteller schränken das evtl. weiter ein (ungeprüft) | Bei neuer Android-Version am Gerät testen |
| `ZapperService.java:292` | `ACTIVITY_RESUMED` (API 29) | niedrig | Wert 1 = altes `MOVE_TO_FOREGROUND`, wird eingebaut, geht also auch darunter. Zeigt die TV-App das Bild über ein anderes Paket, passt der Vergleich nicht | – |
| `MainActivity.java:107` | `POST_NOTIFICATIONS` erst ab Android 13 eine Laufzeit-Berechtigung | niedrig | Darunter still übergangen, unschädlich | – |
| `MainActivity.java:482` | versteckte API `SystemProperties` (Spiegelung) | niedrig | Kann gesperrt sein, dann zeigt die App den adb-Port als „nicht freigegeben“, nur eine Anzeige | – |
| `build.sh:35` | d8 ohne core library desugaring | niedrig (nur Bauen) | Ersetzt keine fehlenden Bibliotheksmethoden, deshalb bleibt die API-33-Stelle | Mit `--desugared-lib` bauen oder die Stellen ersetzen |
| `build.sh:8` | macOS/Homebrew-Pfade, build-tools 36.0.0, platform 35 fest | niedrig (nur Bauen) | Auf Linux/Windows Pfade per `JAVA_HOME`/`ANDROID_HOME` setzen | – |

### Fernseher, Hersteller und Live-TV (TvContract)

| Datei:Zeile | Abhängigkeit | Risiko | Folge auf anderen Geräten | Möglicher Weg später |
|---|---|---|---|---|
| `Epg.java:156` | `Settings.Global "recent_play_channel_id"`, gibt es nur bei TCL | hoch | Die App kennt den laufenden Sender nicht (nur den zuletzt selbst gewählten). Selbst Umschalten bemerkt sie nicht, der Werbe-Sensor beobachtet dann den falschen Sender, und jedes Umschalten gilt als bestätigt | Andere Herstellerquellen suchen, sonst laufenden Sender per `dumpsys`/TvInputManager oder vom Nutzer |
| `Epg.java:53` | Fernseh-App über `ACTION_VIEW` auf einen Sender gefunden | hoch | Ist keine App Standard (Auswahl „android“), bleibt sie unbekannt. Dann gilt das Fernsehbild nie als vorn, und der Zapper schaltet nie. Manche TV-Apps nehmen den Intent nicht an | Einstellung `tv_app` (gibt es schon); Liste bekannter Pakete (Sony, Philips, Live Channels) |
| `AndroidManifest.xml:16` | `READ_TV_LISTINGS` vom TvProvider (am TCL „dangerous“, zur Laufzeit erteilt), nicht im öffentlichen SDK | mittel | Ob andere Hersteller oder ältere Android-Versionen fremde Sender und Sendungen an Dritt-Apps herausgeben, ist ungeprüft. Wenn nicht: „Keine Sender lesbar“ | An einem zweiten Gerät testen |
| `Epg.java:136` | EPG muss in TvContract stehen | mittel | Manche Hersteller halten das EPG intern, dann sind alle Sendungen leer und es gibt kaum Punkte | Nur Sendernamen bewerten; HA-Weg über die Programmzeitschrift |
| `Epg.java:104` | `internal_provider_flag2 = 1` als Favorit, TCL-eigen | mittel | Andere nutzen das Feld anders, dann stimmen die Vorgaben an/aus nicht. Gesetzt ist es nur, wenn überhaupt ein Sender so markiert ist | Je Hersteller erkennen, sonst „sichtbar“ (`browsable`) als Vorgabe |
| `Epg.java:21` | ein Tuner-Eingang (`TYPE_TUNER` mit den meisten Sendern) | mittel | Getrennte Eingänge für DVB-C/S/T oder Sender bei IPTV/Zattoo/waipu: nur ein Teil wird gesehen | Mehrere Eingänge zulassen; Einstellung `tv_eingang` gibt es schon |
| `Epg.java:125` | Genre als DVB-Code (TCL: „32“) | niedrig | Andere liefern Text oder nichts, Beschreibungen fehlen manchmal, die Kategorie-Wörter treffen dann anders | Genre-Codes in Wörter übersetzen |
| `Epg.java:210` | Sendernummer = erste Zahl | niedrig | „1-2“/„1.1“ (ATSC, Unterkanäle) werden ungenau sortiert | – |
| `ZapperService.java:163` | Nutzungszugriff und `isInteractive()` | mittel | Ohne Nutzungszugriff schaltet der Zapper nie. „Bildschirm aus, Ton an“ meldet jeder Hersteller anders | – |
| `AndroidManifest.xml:29`, `:33`, `MainActivity.java:114` | Einstellungsseiten „Über anderen Apps“ und „Nutzungszugriff“ | mittel | Fehlen auf manchen TV-Firmwares, dann nur per adb `appops set … allow` | In der App die adb-Befehle anzeigen |
| `Banner.java:41`, `Maskottchen.java:55` | Overlay über dem Tuner-Bild | mittel | Am TCL sichtbar. Ob andere Geräte Overlays über geschütztem Video oder eigener Video-Ebene zeigen, ist ungeprüft | Am zweiten Gerät testen |

### Video-Decoder und Werbeerkennung

| Datei:Zeile | Abhängigkeit | Risiko | Folge auf anderen Geräten | Möglicher Weg später |
|---|---|---|---|---|
| `Sensor.java:127` | zweiter Hardware-Decoder neben dem Fernsehbild, feste Größe 720x576 | mittel bis hoch | Am TCL (MediaTek) mit MPEG-2 geprüft. Am 28.10. per `dumpsys media.resource_manager` gesehen: der Tuner (`com.tcl.tvinput`) nutzt `c2.mtk.avc.decoder`, die App gleichzeitig `c2.mtk.mpeg2.decoder` (Hardware); `media_codecs-mt5896.xml` erlaubt je Decoder 16 Instanzen. Amlogic/Realtek erlauben oft nur wenige Decoder gleichzeitig, dann Fehler oder ruckelndes Fernsehbild. HEVC/UHD braucht mehr. Feste Größe bei HD ungeprüft | Decoder-Fähigkeiten abfragen (`MediaCodecList`, `getMaxSupportedInstances`), SD-Eintrag bevorzugen, Software-Decoder als Rückfall |
| `Logo.java:186` | rechte Logo-Ecke ab 70 % der Bildbreite, für 360 Punkte bemessen | hoch bei HD | Bei HD (960 Punkte) nur 672 bis 780, Logos ganz rechts liegen außerhalb. **Betrifft auch Max' Aufbau**, sobald die FRITZ!Box einen HD-Eintrag liefert (die alten SD-Einträge sind teils tot) | Ecke relativ zur Breite schneiden oder das Bild vorher auf 360 Breite verkleinern |
| `Logo.java:15` | Ecke 108x72 und Maske für SD in halber Auflösung | mittel | Bei HD/UHD ist das Fenster relativ kleiner als das Logo | wie oben |
| `Logo.java:245` | mitgelieferte Logos aus SD-Aufnahmen (Vodafone-Kabel, Okt. 2026) | mittel | Bei anderer Auflösung oder Logoform passen sie nicht: Fehlalarm, nach 12 min wird neu gelernt | Mitgelieferte Logos nur bei passender Auflösung nehmen |
| `Sensor.java:191` | 8-Bit-Y, `getCropRect()` nicht beachtet | niedrig bis mittel | Bei 1088 statt 1080 Zeilen ist die Unterkante leicht verschoben; 10-Bit-Video (HEVC Main10, HDR) ergibt Unsinn | Crop-Rechteck und Bittiefe beachten |
| `Sensor.java:152` | Decoder liefert `Image` | niedrig | Manche Decoder (nur getunnelt) liefern null, dann kommen nie Bilder | Ausgabe auf eine Surface/ImageReader |
| `Sensor.java:258` | nur MPEG-2/H.264/HEVC, nur das erste Programm mit Video | niedrig | Andere Codecs werden nicht erkannt | – |
| `WerbeWaechter.java:15` | Schwellen am Mac an 6 Sendern gemessen | mittel | Durchsichtige, wechselnde oder animierte Logos und Sport mit Eckeinblendungen verhalten sich evtl. anders. Heute bei SPORT 1 HD scheiterten zwei Lernrunden, vermutlich wegen Werbung während des Lernens | Lernen nur in Abschnitten mit stabilem Bild; Schwellen je Sender |

### FRITZ!Box und Kabelnetz

| Datei:Zeile | Abhängigkeit | Risiko | Folge auf anderen Geräten | Möglicher Weg später |
|---|---|---|---|---|
| `FritzTv.java:27` | `/dvb/m3u/tvsd.m3u` und `tvhd.m3u` gibt es nur bei FRITZ!Box-Modellen mit DVB-C | hoch ohne Cable-Box | DSL-/Glasfaser-Boxen: keine Werbeerkennung (die App läuft sonst weiter). Verschlüsselte Sender (CI-Karte) liefert die Box nicht. Geprüft nur an der 6660 | Andere SAT>IP-Quellen per eigener M3U-Adresse zulassen |
| `Sensor.java:97` | SAT>IP wie bei der FRITZ!Box: RTSP über TCP, RTP/UDP-Unicast | mittel | Digibit, minisatip und tvheadend arbeiten teils mit RTP über TCP, Multicast oder anderen URL-Parametern (ungetestet) | Übertragungsart aus der SETUP-Antwort lesen |
| `Sensor.java:118` | RTP-Kopf vorausgesetzt | mittel | Reiner TS über UDP würde verschoben gelesen | Am Sync-Byte 0x47 ausrichten |
| `FritzTv.java:62` | Namensangleichung TCL ↔ Vodafone-Kabel BW | mittel | Andere Fernseher, Netze oder Satellit schreiben Namen anders, dann „gibt es nicht bei der FRITZ!Box“ | Zuordnung in den Einstellungen; muss gleich bleiben mit `sender_schluessel` der HA-Integration |
| `Config.java:48` | Vorgabe `fritz.box` | niedrig | Löst nur auf, wenn die FRITZ!Box der DNS-Server ist, sonst die IP eintragen | – |

### Sprache, Zeit und Speicher (nur hier, ohne eigenen Kommentar)

- **Deutsch:** Alle Texte der App sind fest auf Deutsch, auch die Interessen (`interessen.json`), die Wortgrenzen
  (a–z, äöüß in `Scorer.java`) und die Sendernamen. In anderen Ländern trifft wenig, und die Oberfläche ist deutsch.
- **Zeit:** Die Zeiten folgen der Zeitzone des Fernsehers. Die ABFRAGEN-Zeiten tragen den Versatz (ISO mit `+01:00`)
  und stimmen deshalb auch in HA.
- **Speicher:** Puffer bis 2 MB (UDP), 4 MB (PES) und 5000 FRITZ!Box-Einträge sind auch für Geräte mit 1 GB RAM klein.
  Ein zweiter Decoder kostet aber Video-Speicher; auf schwachen Geräten ungeprüft.
- **Bedienung:** Die Oberfläche ist für die Fernbedienung (D-Pad) gebaut und geht auch mit Touch. Auf Handys und
  Tablets gibt es aber keinen Tuner und damit keine Sender.

Gefährdet ist in Max' Aufbau (TCL, Android 14, FRITZ!Box 6660, Vodafone-Kabel) nur ein Punkt: die rechte Logo-Ecke
bei HD-Einträgen (`Logo.java:186`). Ob sie dort schon zu falschen Ergebnissen führt, ist nicht geprüft. SPORT 1 HD läuft
am Werbe-Sensor über einen SD-Eintrag (MPEG-2, siehe Recherche), ist also kein Beleg dafür.

### Recherche zu anderen Geräten (28.10.2026, App-Sitzung)

Gesucht im Netz und an Quelltexten; dazu Lesezugriffe am TCL (nichts installiert, keine Tasten). Art: **belegt** =
am Gerät oder im Quelltext nachgesehen, **Doku** = offizielle Dokumentation, **Forum** = Bericht von Nutzern,
**Vermutung** = eigene Folgerung. Zu Sony, Philips, Hisense, Xiaomi, Sharp und Panasonic habe ich **keine** Quelle
gefunden, die sagt, ob ihre Fernseh-App `ACTION_VIEW` von fremden Apps annimmt oder ob ihre Sender im TvProvider stehen.
Das bleibt offen und geht nur mit einem Testgerät.

| Zu Stelle | Erkenntnis | Art | Quelle |
|---|---|---|---|
| `AndroidManifest.xml:16` | Der TvProvider erklärt `READ_TV_LISTINGS` als `dangerous` („read … all the TV listings“), `READ_EPG_DATA` als `normal`, `ACCESS_ALL_EPG_DATA` als `signature\|privileged`. Eine normale App kann es also bekommen, wenn der Hersteller den AOSP-TvProvider nutzt. Am TCL genauso (`dumpsys package`) | belegt (Quelltext, Gerät) | [TvProvider AndroidManifest.xml](https://android.googlesource.com/platform/packages/providers/TvProvider/+/refs/heads/main/AndroidManifest.xml) |
| `Epg.java:53` | Googles eigene Live-TV-App (`com.android.tv.MainActivity`) nimmt `ACTION_VIEW` mit `vnd.android.cursor.item/channel` an. Geräte mit dieser App (oder einer Ableitung) sollten das Umschalten also können | belegt (Quelltext); für andere Geräte Vermutung | [packages/apps/TV AndroidManifest.xml](https://android.googlesource.com/platform/packages/apps/TV/+/android-live-tv/AndroidManifest.xml) |
| `Epg.java:136`, `Epg.java:21` | Ein Eingang kann „pass-through“ sein und hat dann gar keine Sender im TvProvider (z. B. HDMI) | Doku | [TvInputInfo](https://developer.android.com/reference/kotlin/android/media/tv/TvInputInfo) |
| `Epg.java:136` | Ein Nutzer berichtet, Sony setze das TV Input Framework nicht voll um und nutze ein eigenes EPG. Dann fehlen Sendungen in TvContract | Forum | [Sony Community](https://community.sony.bg/t5/android-tv/live-channels-app-no-programme-information-on-guide/td-p/2437164) |
| `Epg.java:156` | Eine öffentliche Schnittstelle für „gerade laufender Sender“ gibt es nicht; nur die Eingangs-App selbst kennt ihn (`onTune`). `recent_play_channel_id` taucht in keiner Doku auf | Doku; Rest Vermutung | [Amazon Fire TV: Playback](https://developer.amazon.com/docs/fire-tv/playback-in-fire-tv-ui.html), [TvContract](https://developer.android.com/reference/android/media/tv/TvContract) |
| `AndroidManifest.xml:29`, `:33`, `MainActivity.java:114` | Auf Android TV/NVIDIA Shield/Fire TV fehlt oft die Seite „Über anderen Apps“; die Einstellung geht dann per `adb shell appops set <paket> SYSTEM_ALERT_WINDOW allow`, wirkt ohne Neustart. Bei verwalteten Geräten (MDM) kann der Befehl wirkungslos sein. Für `GET_USAGE_STATS` gilt derselbe Weg (AppOp), am Gerät nicht geprüft | Forum; Usage Stats Vermutung | [Floating Apps: Shield/Android TV](https://blog.floatingapps.net/2018/02/using-floating-apps-on-nvidia-shield-and-android-tv/), [Google Issue 37121932](https://issuetracker.google.com/issues/37121932), [Play Signage Fire TV](https://playsignage.com/setup/amazon-firetv-launch-on-startup/), [SOTI](https://pulse.soti.net/community/thread/cbd25a20-593c-4c39-9018-807350940059) |
| `Sensor.java:127` | Wie viele Decoder gleichzeitig gehen, legt der Hersteller in `media_codecs.xml` fest (`concurrent-instances`), abfragbar mit `getMaxSupportedInstances()`. Der Wert ist eine Angabe des Herstellers, nicht unbedingt, was neben dem Tuner wirklich geht. Am TCL: 16 je MTK-Decoder; die `c2.android.*`-Software-Decoder gibt es zusätzlich | Doku; TCL belegt | [AOSP: OEM-Abhängigkeiten Media Resource Manager](https://source.android.com/docs/core/media/oem), [Media3 MediaCodecInfo](https://developer.android.com/reference/androidx/media3/exoplayer/mediacodec/MediaCodecInfo) |
| `Sensor.java:127` | Für Amlogic/Realtek habe ich keinen Bericht gefunden, ob ein zweiter Decoder neben dem Live-TV geht | offen | – |
| `FritzTv.java:27` | Die Listen `/dvb/m3u/` (HD, SD, Radio) erzeugt der Dienst `cableinfo` nach dem Suchlauf. Es gibt ihn ab den 6490-Cable-Modellen und beim FRITZ!WLAN Repeater DVB-C. Die Listen enthalten nur unverschlüsselte Sender | Doku (Wiki) | [BoxMatrix: cableinfo](https://boxmatrix.info/wiki/Property:cableinfo_(avmcmd)) |
| `FritzTv.java:27` | AVM: Manche Kabelanbieter unterstützen die Funktion nicht, dann fehlt das Menü DVB-C ganz. Verschlüsselte Sender gehen nur mit CI-Modul am Fernseher. Ob Vodafone das bei Mietboxen sperrt, habe ich nicht gefunden | Doku; Vodafone offen | [AVM 6591: DVB-C einrichten](https://uk.fritz.com/service/knowledge-base/dok/FRITZ-Box-6591-Cable/1528_Configuring-the-FRITZ-Box-for-TV-reception-over-DVB-C/), [TECHBOOK](https://www.techbook.de/connectivity/internet-dsl-kabel/tv-signal-verteilen-kabellos-via-fritzbox) |
| `FritzTv.java:27` | Fehlt das Menü, hilft laut Bericht oft eine neue Firmware oder die „Erweiterte Ansicht“; danach „Live-TV aktivieren“ und Suchlauf | Forum/Ratgeber | [GIGA](https://www.giga.de/tech/fernsehen-ohne-extra-hardware-so-nutzt-ihr-eure-fritzbox-als-tv-receiver--01M3BQFQ51PD8CXKR39GKHBAHB) |
| `Sensor.java:97`, `Sensor.java:118` | minisatip und tvheadend können RTP auch über TCP („interleaved“, `RTP/AVP/TCP;interleaved=0-1`). tvheadend nutzt als Client standardmäßig UDP. Ein Server, der nur TCP anbietet, ginge mit der App nicht | Doku (Projekt-Tracker) | [tvheadend #3092](https://old.tvheadend.org/issues/3092), [tvheadend #4505](https://old.tvheadend.org/issues/4505), [tvheadend RemoteTuner](https://old.tvheadend.org/projects/tvheadend/wiki/RemoteTuner) |
| `WerbeWaechter.java:15` | Auch Comskip/MythTV erkennen Werbung u. a. am verschwundenen Senderlogo. Bekannte Fehler: Werbung mit logoähnlicher Grafik (Eigenwerbung mit Sendelogo), Sendeteile ohne Logo, Logo, das in der Pause an eine andere Stelle wandert. Vorschläge dort: Logo nur in einem Bildviertel suchen, je Sender abschalten | Forum, Wiki | [MythTV Commflagging](https://wiki.mythtv.org/wiki/Commflagging), [Channels: Logo in Quadrants](https://community.getchannels.com/t/can-comskip-be-tweaked-to-look-for-logo-in-quadrants/35759), [Channels: Erfahrungen](https://community.getchannels.com/t/commercial-detection-experiences/13311) |
| `Logo.java:186` | SPORT 1 HD bekommt der Werbe-Sensor über einen SD-Eintrag: Die App hielt am 28.10. `c2.mtk.mpeg2.decoder`. Die HD-Logo-Ecke ist damit weiter ungeprüft | belegt (Gerät) | `dumpsys media.resource_manager` |
