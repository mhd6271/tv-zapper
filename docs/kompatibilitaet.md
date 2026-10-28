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
