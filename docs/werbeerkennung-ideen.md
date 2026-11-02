# Werbeerkennung verbessern – Ideen aus anderen Programmen

Recherche vom 02.11.2026 (Review-Runde 3). Nichts davon ist umgesetzt. Grundlage ist der Quellcode von drei
Programmen, die Werbung am Senderlogo erkennen:

- **markad** für VDR (https://github.com/kfb77/vdr-plugin-markad), auf deutsche Sender abgestimmt;
- **MythTV mythcommflag** (https://github.com/MythTV/mythtv, `mythtv/programs/mythcommflag`);
- **Comskip** (https://github.com/erikkaashoek/Comskip).

„Im Code nachgesehen“ heißt: Die Stelle wurde in der heruntergeladenen Quelle gelesen. Was nur aus Zusammenfassungen
oder dem Gedächtnis stammt, ist als Vermutung markiert.

## Was markad über unsere Problemsender weiß

Im Code nachgesehen (`criteria.cpp`):
- `LogoTransparent()` enthält **NITRO**. Das passt zu unserem Befund, dass der Logo-Wert dort bei 0,50 hängt.
- `IsAdInFrameWithLogoChannel()` enthält ProSieben, ProSieben MAXX, RTL, RTLZWEI, SAT.1, sixx, VOX, VOXup, kabel eins
  und WELT. Diese Sender zeigen Werbung auch im Rahmen, während das Logo zu sehen ist. Solche Werbung findet keine
  Logo-Erkennung, unsere auch nicht.
- `IsLogoRotating()`: SAT.1. `LogoColorChange()`: RTL, kabel eins, DMAX, TELE 5, Disney Channel.
  `LogoInNewsTicker()`: ntv, WELT.

## Die fünf vielversprechendsten Ideen

1. **Dritter Zustand „unklar“ bei hellem Hintergrund** (gegen ProSieben-Fehlalarme, teils NITRO). markad misst
   Helligkeit und Kontrast der Logo-Ecke und entscheidet bei hellem Bild nicht auf „kein Logo“. Comskip lässt
   Maskenpunkte mit Helligkeit ab 200 aus der Rechnung. Unklare Sekunden zählen weder für „Werbung“ noch für
   „vorbei“. Aufwand klein (`Logo.feed`/`score`, Fensterzählung in `WerbeWaechter`). Risiko: Werbung mit lange
   heller Ecke wird später erkannt; deshalb eine Obergrenze für unklare Sekunden.
2. **Schwellen je Sender aus der Verteilung der Logo-Werte** (gegen NITRO 0,50, HGTV-Schwanken). MythTV legt die
   Schwelle in die Senke zwischen den zwei Häufungen (`TemplateMatcher.cpp`, `pick_mintmpledges`). Aufwand klein bis
   mittel, Rückfall auf die festen 0,35/0,7.
3. **Kanten außerhalb der Maske mitzählen.** Viele Kanten neben dem Logo heißen eher unruhiges Bild als Logo. MythTV
   verlangt wenige „schlechte“ Kanten, markad zieht ihren Anteil vom Wert ab. Macht Idee 2 sicherer. Aufwand klein.
4. **Kantenrichtung statt nur Kantenstärke.** Comskip und MythTV speichern je Maskenpunkt waagrecht/senkrecht; ein
   helles Logo hebt den Hintergrund immer an, das Vorzeichen bleibt gleich. Dazu ±1 Punkt Verschiebung zulassen.
   Aufwand mittel: neues Maskenformat, alle 27 Logos neu lernen.
5. **DOKUSAT, MTV, NITRO gezielt neu lernen und die Maske ansehen.** Vermutung, nicht geprüft: Bei animierten oder
   durchsichtigen Logos bleibt in der 70-%-Maske nur ein Rest. Für Logos mit wechselnder Farbe hilft eine Kantensuche
   auf den Farbebenen (heute liest `Sensor.grab` nur die Helligkeit).

## Schwächere Zusatzsignale

- **Schnittrate:** Werbung schneidet öfter. Nur als Entscheidungshilfe im Zustand „unklar“.
- **Schwarzbilder zwischen Spots:** Comskip nimmt Mittel ≤ 19 und Maximum ≤ 60. Bei etwa 3,4 Bildern/s gehen kurze
  Schwarzbilder oft verloren. Dass deutsche Privatsender sie einsetzen, ist eine Vermutung.
- **Stille zwischen Spots:** bräuchte eine Tonspur-Auswertung. Die eigene Messung zeigt nur gleiche Lautstärke in
  Werbung und Sendung, über kurze Pausen sagt sie nichts.
- **EIT-Laufstatus „pausing“ (Wert 3, EN 300 468):** markad liest ihn. Ein Kommentar dort sagt aber, dass private
  Sender nur den Beginn der nächsten Sendung melden. Wahrscheinlich wertlos.
- **HbbTV-Werbeaustausch (RTL/smartclip):** könnte Werbung genau markieren. Ob das im Strom der FRITZ!Box ankommt,
  ist völlig ungeprüft. Ein billiger Test wäre, die PMT des RTSP-Stroms mit ffprobe nach AIT- und DSM-CC-Strömen
  abzusuchen.
