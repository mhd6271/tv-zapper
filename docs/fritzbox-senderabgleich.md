# Abgleich Fernsehsender ↔ FRITZ!Box (28.10.2026)

Stand nach dem DVB-C-Sendersuchlauf der FRITZ!Box 6660 Cable. Zuordnung mit der echten Logik der App (`FritzTv.norm`, ab 0.4.4),
jeder FRITZ!Box-Eintrag einzeln vom Mac abgerufen (RTSP, 3 s; unklare Fälle 5 s aufgenommen und Videobilder mit ffmpeg dekodiert,
Gegenprobe ProSieben: 101 Bilder). „Bild“ heißt: unverschlüsseltes Video kommt an. Werbeerkennung ist dann möglich, sobald das
Logo gelernt ist; HD-Einträge (H.264) hat die App am Fernseher bisher nicht ausprobiert, geprüft ist sie mit SD (MPEG-2).
Radiosender (ab 3001) sind weggelassen. Zustand = Einstellung in der App (an/bevorzugt/aus).

Ergebnis: 127 von 271 Fernsehsendern haben einen FRITZ!Box-Eintrag mit Bild, 10 haben nur Einträge ohne Bild, 134 gibt es bei der FRITZ!Box nicht (meist Pay-TV wie Sky/DAZN, ausländische Sender und verschlüsselte Privatsender in HD).

| Nr | Fernsehsender | Zustand | FRITZ!Box-Einträge (Frequenz MHz: Bild) | Werbeerkennung möglich |
|---|---|---|---|---|
| 1 | Das Erste HD | an | Das Erste @522: nein; Das Erste HD @314: ja | ja |
| 2 | ZDF HD | an | ZDF @514: nein; ZDF HD @410: nein; ZDF HD @322: ja | ja |
| 3 | RTL Television | aus | RTL Television @426: ja | ja |
| 4 | Sat.1 | aus | Sat.1 @442: ja | ja |
| 5 | ProSieben | aus | ProSieben @442: ja | ja |
| 6 | RTL2 | aus | RTLZWEI @426: ja | ja |
| 7 | VOX | aus | VOX @426: ja | ja |
| 8 | kabel eins | aus | Kabel Eins @442: ja | ja |
| 9 | DMAX | aus | DMAX @450: ja | ja |
| 10 | sixx | aus | sixx @442: ja | ja |
| 11 | TELE 5 | aus | TELE 5 @450: ja | ja |
| 12 | SUPER RTL | aus | SUPER RTL @426: ja | ja |
| 13 | KiKA | aus | KiKA @514: nein; KiKA HD @330: ja | ja |
| 14 | n-tv | aus | ntv @426: ja | ja |
| 15 | SPORT1 | aus | SPORT1 @450: ja | ja |
| 16 | DELUXE MUSIC | aus | DELUXE MUSIC @434: ja | ja |
| 17 | arte HD | an | arte HD @314: ja | ja |
| 18 | ZDFinfo | aus | ZDFinfo @514: nein; ZDFinfo HD @330: ja | ja |
| 19 | zdf_neo | aus | zdf_neo @514: nein; zdf_neo HD @410: nein; zdf_neo HD @330: ja | ja |
| 20 | 3sat | aus | 3sat @514: nein; 3sat HD @330: ja | ja |
| 21 | Bibel TV | aus | Bibel TV @562: nein; Bibel TV @418: ja; Bibel TV HD @570: nein; Bibel TV HD @466: ja | ja |
| 22 | Bloomberg Europe TV | aus | Bloomberg Europe TV @570: nein; Bloomberg Europe TV @466: ja | ja |
| 23 | ProSieben HD | an | ProSieben @442: ja | ja |
| 24 | sixx HD | an | sixx @442: ja | ja |
| 25 | RTL HD | an | RTL Television @426: ja | ja |
| 26 | SAT.1 HD | an | Sat.1 @442: ja | ja |
| 27 | SPORT 1 HD | an | SPORT1 @450: ja | ja |
| 28 | VOX HD | an | VOX @426: ja | ja |
| 29 | Kabel Eins HD | an | Kabel Eins @442: ja | ja |
| 30 | 1-2-3.tv | aus | 1-2-3.tv @434: nein; 1-2-3.tv HD @554: nein; 1-2-3.tv HD @410: ja | ja |
| 31 | sonnenklar.TV HD | aus | sonnenklar.TV @450: ja; sonnenklar.TV HD @450: ja | ja |
| 32 | Sonnenklar TV | aus | sonnenklar.TV @450: ja; sonnenklar.TV HD @450: ja | ja |
| 33 | QVC | aus | QVC @434: ja; QVC HD @458: ja | ja |
| 34 | QVC HD | aus | QVC @434: ja; QVC HD @458: ja | ja |
| 35 | Sky Krimi | aus | – | nein |
| 36 | Sky Sport News | aus | – | nein |
| 37 | Sky Sport 1 | aus | – | nein |
| 38 | 1-2-3.tv HD | aus | 1-2-3.tv @434: nein; 1-2-3.tv HD @554: nein; 1-2-3.tv HD @410: ja | ja |
| 39 | 13th Street | aus | – | nein |
| 40 | 13th Street HD | aus | – | nein |
| 41 | 3sat HD | aus | 3sat @514: nein; 3sat HD @330: ja | ja |
| 42 | 8Sport | aus | 8Sport @474: ja; 8Sport @578: nein; 8Sport HD @506: ja | ja |
| 43 | Al Arabia HD | aus | – | nein |
| 44 | Al Jazeera HD | aus | Al Jazeera HD @586: nein | nein |
| 45 | Al Sharjah HD | aus | – | nein |
| 46 | ALEX BERLIN HD | aus | ALEX BERLIN HD @578: nein; ALEX BERLIN HD @474: ja | ja |
| 47 | ANIXE+ | aus | ANIXE+ @434: ja | ja |
| 48 | ARD alpha HD | aus | ARD alpha HD @306: ja | ja |
| 49 | ARD-Test-1 | aus | ARD-TEST-1 @530: nein; ARD-Test-1 @306: ja | ja |
| 50 | ARD-Test-R | aus | ARD-Test-R @306: ja | ja |
| 51 | Arirang TV HD | aus | – | nein |
| 52 | ATV Avrupa | aus | – | nein |
| 53 | auto motor und sport channel | aus | – | nein |
| 54 | AXN Black | aus | – | nein |
| 55 | AXN White | aus | – | nein |
| 56 | Balkanika | aus | – | nein |
| 57 | BBC News | aus | BBC News @378: ja | ja |
| 58 | Beate Uhse | aus | – | nein |
| 59 | Bibel TV HD | aus | Bibel TV @562: nein; Bibel TV @418: ja; Bibel TV HD @570: nein; Bibel TV HD @466: ja | ja |
| 60 | BN 2 | aus | – | nein |
| 61 | BN Music | aus | – | nein |
| 62 | BNT 4 | aus | – | nein |
| 63 | BR Fernsehen Süd HD | aus | BR Fernsehen Süd @522: nein; BR Fernsehen Süd HD @322: ja | ja |
| 64 | BVN TV | aus | – | nein |
| 65 | CANAL 24 HORAS | aus | – | nein |
| 66 | Canal Algerie | aus | – | nein |
| 67 | Cartoon Network | aus | – | nein |
| 68 | Cartoonito | aus | – | nein |
| 69 | CCTV-4 | aus | – | nein |
| 70 | Channel21 | aus | Channel21 @434: nein; Channel21 HD @570: nein | nein |
| 71 | Channel21 HD | aus | Channel21 @434: nein; Channel21 HD @570: nein | nein |
| 72 | CNN Int. | aus | CNN Int. @570: nein | nein |
| 73 | CNN TURK | aus | – | nein |
| 74 | Comedy Central | aus | Comedy Central @562: nein; Comedy Central @418: ja | ja |
| 75 | Comedy Central HD | an | Comedy Central @562: nein; Comedy Central @418: ja | ja |
| 76 | Crime + Investigation | aus | – | nein |
| 77 | Crime + Investigation HD | aus | – | nein |
| 78 | Curiosity Channel HD | aus | – | nein |
| 79 | DAZN 1 | aus | – | nein |
| 80 | DAZN 2 | aus | – | nein |
| 81 | Deluxe Music HD | an | DELUXE MUSIC @434: ja | ja |
| 82 | DF 1 HD | aus | DF 1 @562: nein; DF 1 HD @554: nein; DF 1 HD @410: ja | ja |
| 83 | Disney Channel | aus | Disney Channel @434: ja | ja |
| 84 | Disney Channel HD | aus | Disney Channel @434: ja | ja |
| 85 | DM SAT | aus | – | nein |
| 86 | DMAX HD | an | DMAX @450: ja | ja |
| 87 | DMF | aus | DMF @434: ja | ja |
| 88 | DOKUSAT | an | DOKUSAT @562: nein; DOKUSAT @418: ja; DOKUSAT HD @570: nein | ja |
| 89 | Duck TV SD | aus | – | nein |
| 90 | ERT World Europe | aus | – | nein |
| 91 | eSports1 HD | aus | – | nein |
| 92 | EspresoTV HD | aus | EspresoTV HD @586: nein; EspresoTV HD @482: ja | ja |
| 93 | EURO D | aus | – | nein |
| 94 | Euro Star | aus | – | nein |
| 95 | EURONEWS GERMAN SD | an | EURONEWS GERMAN SD @474: ja; Euronews GERMAN SD @578: nein | ja |
| 96 | Eurosport 1 Deutschland | aus | Eurosport 1 Deutschland @562: nein; Eurosport 1 Deutschland @418: ja | ja |
| 97 | Eurosport 1 HD | an | Eurosport 1 Deutschland @562: nein; Eurosport 1 Deutschland @418: ja | ja |
| 98 | Fast&Fun Box HD | aus | – | nein |
| 99 | Fix & Foxi | aus | – | nein |
| 100 | France 2 | aus | – | nein |
| 101 | France 24 HD | aus | – | nein |
| 102 | France 3 | aus | – | nein |
| 103 | France 5 | aus | – | nein |
| 104 | Freedom TV | aus | Freedom TV @586: nein | nein |
| 105 | Funbox UHD | aus | – | nein |
| 106 | GEO Television HD | aus | – | nein |
| 107 | Gute Laune TV | aus | – | nein |
| 108 | Handystar TV | aus | Handystar TV @434: ja | ja |
| 109 | Heimatkanal | aus | – | nein |
| 110 | Heimatkanal | aus | – | nein |
| 111 | HGTV | an | HGTV @458: ja | ja |
| 112 | History | aus | – | nein |
| 113 | HISTORY Channel | aus | – | nein |
| 114 | hr-fernsehen HD | an | hr-fernsehen @522: nein; hr-fernsehen HD @418: nein; hr-fernsehen HD @314: ja | ja |
| 115 | HRT-TV1 HD | aus | – | nein |
| 116 | HSE | aus | HSE @450: ja; HSE HD @458: ja | ja |
| 117 | HSE EXTRA HD | aus | HSE EXTRA SD @562: nein; HSE EXTRA SD @418: ja; HSE EXTRA HD @554: nein; HSE EXTRA HD @410: ja | ja |
| 118 | HSE EXTRA SD | aus | HSE EXTRA SD @562: nein; HSE EXTRA SD @418: ja; HSE EXTRA HD @554: nein; HSE EXTRA HD @410: ja | ja |
| 119 | HSE HD | aus | HSE @450: ja; HSE HD @458: ja | ja |
| 120 | HSE Trend | aus | HSE Trend @450: ja | ja |
| 121 | iTVN | aus | – | nein |
| 122 | iTVN | aus | – | nein |
| 123 | iTVS | aus | – | nein |
| 124 | Kabel Eins CLASSICS HD | aus | – | nein |
| 125 | kabel eins Doku | an | Kabel Eins Doku @442: ja | ja |
| 126 | Kanal 7 avrupa | aus | – | nein |
| 127 | KiKA HD | aus | KiKA @514: nein; KiKA HD @330: ja | ja |
| 128 | Kinomir | aus | – | nein |
| 129 | Kinowelt TV | aus | – | nein |
| 130 | kw-tv HD | aus | kw-tv HD @474: ja | ja |
| 131 | Lilo TV | aus | Lilo.TV @426: ja | ja |
| 132 | Marco Polo TV | aus | – | nein |
| 133 | MDR Sachsen HD | aus | MDR Sachsen @530: nein; MDR Sachsen HD @418: nein; MDR Sachsen HD @314: ja | ja |
| 134 | Mediaset Italia | aus | – | nein |
| 135 | Mediaset Italia | aus | – | nein |
| 136 | Melodie TV | aus | Melodie TV @474: ja; Melodie TV @578: nein | ja |
| 137 | Mezzo Live HD | aus | – | nein |
| 138 | MTV | aus | MTV @562: nein; MTV @418: ja | ja |
| 139 | MTV HD | an | MTV @562: nein; MTV @418: ja | ja |
| 140 | MTV Live HD | aus | – | nein |
| 141 | N24 DOKU | bevorzugt | N24 DOKU @434: ja | ja |
| 142 | Nat Geo Wild HD | aus | – | nein |
| 143 | NatGeo | aus | – | nein |
| 144 | NatGeo Wild | aus | – | nein |
| 145 | National Geographic HD | aus | – | nein |
| 146 | NDR FS HH HD | aus | NDR FS HH @530: nein; NDR FS HH HD @322: ja; NDR FS HH HD @522: ja | ja |
| 147 | NDR FS MV HD | aus | NDR FS MV @530: nein; NDR FS MV HD @322: ja; NDR FS MV HD @522: ja | ja |
| 148 | NDR FS NDS HD | aus | NDR FS NDS @530: nein; NDR FS NDS HD @322: ja | ja |
| 149 | NDR FS SH HD | aus | NDR FS SH @530: nein; NDR FS SH HD @322: ja; NDR FS SH HD @522: ja | ja |
| 150 | nice Berlin | aus | nice Berlin @578: nein; nice Berlin @474: ja | ja |
| 151 | Nick Jr. | aus | – | nein |
| 152 | NICK/CC+1 | aus | NICK/CC+1 @562: nein; NICK/CC+1 @418: ja | ja |
| 153 | NICK/CC+1 HD | aus | NICK/CC+1 @562: nein; NICK/CC+1 @418: ja | ja |
| 154 | Nicktoons | aus | – | nein |
| 155 | NITRO HD | an | RTLNITRO @426: ja | ja |
| 156 | NTDTV | aus | – | nein |
| 157 | ntv HD | an | ntv @426: ja | ja |
| 158 | ONE HD | aus | ONE HD @306: ja | ja |
| 159 | OstWest | aus | – | nein |
| 160 | Penthouse Passion HD (20-06) | aus | – | nein |
| 161 | phoenix HD | aus | phoenix HD @322: ja | ja |
| 162 | Playboy TV SD (20-06) | aus | – | nein |
| 163 | PRO TV International | aus | – | nein |
| 164 | Pro7 MAXX | aus | Pro7 MAXX @442: ja | ja |
| 165 | Pro7Sat.1 UHD | an | – | nein |
| 166 | ProSieben FUN HD | aus | – | nein |
| 167 | ProSieben MAXX HD | an | Pro7 MAXX @442: ja | ja |
| 168 | Pyur Infokanal HD | aus | Pyur Infokanal HD @506: ja | ja |
| 169 | QVC 2 HD | aus | QVC2 @562: nein; QVC 2 HD @554: nein | nein |
| 170 | QVC Style HD | aus | QVC Style HD @570: nein; QVC STYLE HD @466: ja | ja |
| 171 | Radio Bremen HD | aus | Radio Bremen HD @306: nein; Radio Bremen HD @522: ja | ja |
| 172 | Rai 1 HD | aus | – | nein |
| 173 | Rai 2 HD | aus | – | nein |
| 174 | Rai 3 HD | aus | – | nein |
| 175 | rbb Berlin HD | aus | rbb Berlin @530: nein; rbb Berlin HD @418: nein; rbb Berlin HD @330: ja | ja |
| 176 | rbb Brandenburg HD | aus | rbb Brandenburg @530: nein; rbb Brandenburg HD @418: nein; rbb Brandenburg HD @522: ja | ja |
| 177 | RIKSat | aus | – | nein |
| 178 | Romance TV | aus | – | nein |
| 179 | Romance TV | aus | – | nein |
| 180 | RTL Crime HD | aus | – | nein |
| 181 | RTL Living | aus | – | nein |
| 182 | RTL Passion HD | aus | – | nein |
| 183 | RTL UHD | an | RTL Television @426: ja | ja |
| 184 | RTLNITRO | an | RTLNITRO @426: ja | ja |
| 185 | RTLup | aus | RTLup @426: ja | ja |
| 186 | RTLup HD | aus | RTLup @426: ja | ja |
| 187 | RTLZWEI HD | an | RTLZWEI @426: ja | ja |
| 188 | RTPi | aus | – | nein |
| 189 | RTV Montenegro HD | aus | – | nein |
| 190 | RTVi | aus | – | nein |
| 191 | RUDAW HD | aus | – | nein |
| 192 | SAT.1 emotions HD | aus | – | nein |
| 193 | SAT.1 Gold | aus | SAT.1 Gold @442: ja | ja |
| 194 | Schlager Deluxe | aus | Schlager Deluxe @458: ja | ja |
| 195 | Service 11000 | aus | Service 11000 @386: nein | nein |
| 196 | Service 65534 | aus | Service 65534 @386: ja | ja |
| 197 | Shop LC | aus | Shop LC @562: nein; Shop LC @418: ja; ShopLC HD @458: ja | ja |
| 198 | ShopLC HD | aus | Shop LC @562: nein; Shop LC @418: ja; ShopLC HD @458: ja | ja |
| 199 | SHOW TURK | aus | – | nein |
| 200 | Silk Way HD | aus | – | nein |
| 201 | Sky Atlantic | aus | – | nein |
| 202 | Sky Cinema Action | aus | – | nein |
| 203 | Sky Cinema Classics | aus | – | nein |
| 204 | Sky Cinema Family | aus | – | nein |
| 205 | Sky Cinema Highlights | aus | – | nein |
| 206 | Sky Cinema Premiere | aus | – | nein |
| 207 | Sky Crime | aus | – | nein |
| 208 | Sky Documentaries | aus | – | nein |
| 209 | Sky Nature | aus | – | nein |
| 210 | Sky News Arabia | aus | Sky News Arabia @586: nein | nein |
| 211 | Sky One | aus | – | nein |
| 212 | Sky Replay | aus | – | nein |
| 213 | Sky Showcase | aus | – | nein |
| 214 | Sky Sport Austria 1 | aus | – | nein |
| 215 | Sky Sport Austria 5 | aus | – | nein |
| 216 | Sky Sport Bundesliga | aus | – | nein |
| 217 | Sky Sport F1 | aus | – | nein |
| 218 | Sky Sport Golf | aus | – | nein |
| 219 | Sky Sport Mix | aus | – | nein |
| 220 | Sky Sport Premier League | aus | – | nein |
| 221 | Sky Sport Tennis | aus | – | nein |
| 222 | Sky Sport Top Event | aus | – | nein |
| 223 | Sky Sport UHD | aus | – | nein |
| 224 | Sonlife Broadcasting Network | aus | Sonlife @458: ja | ja |
| 225 | Spirit TV | aus | – | nein |
| 226 | SPORT1+ HD | aus | SPORT1 @450: ja | ja |
| 227 | SPORTDIGITAL FUSSBALL HD | aus | – | nein |
| 228 | Spreekanal | aus | Spreekanal @474: ja; Spreekanal @578: nein | ja |
| 229 | SR Fernsehen HD | aus | SR Fernsehen @442: nein; SR Fernsehen HD @306: ja | ja |
| 230 | STEST1 | aus | – | nein |
| 231 | STEST2 | aus | – | nein |
| 232 | SUPER RTL HD | aus | SUPER RTL @426: ja | ja |
| 233 | SWR BW HD | aus | SWR Fernsehen BW @522: nein; SWR BW HD @314: ja | ja |
| 234 | SYFY | aus | – | nein |
| 235 | SyFy HD | aus | – | nein |
| 236 | tagesschau24 HD | an | tagesschau24 HD @306: ja | ja |
| 237 | TELE 5 HD | an | TELE 5 @450: ja | ja |
| 238 | TeleBom/TeleDom | aus | – | nein |
| 239 | TELEGOLD | aus | TELEGOLD @426: ja | ja |
| 240 | teltOwkanal HD | aus | teltOwkanal HD @578: nein; teltOwkanal HD @474: ja | ja |
| 241 | TGCom 24 | aus | – | nein |
| 242 | THT Russia | aus | – | nein |
| 243 | TLC | aus | TLC @434: ja | ja |
| 244 | TLC HD | an | TLC @434: ja | ja |
| 245 | TOGGO Plus | aus | TOGGO Plus @426: ja | ja |
| 246 | TOGGO plus HD | aus | TOGGO Plus @426: ja | ja |
| 247 | TRT TURK | aus | – | nein |
| 248 | TV 8 INT | aus | – | nein |
| 249 | TV BERLIN | aus | TV BERLIN @474: ja; TV BERLIN @578: nein | ja |
| 250 | TV Record HD | aus | – | nein |
| 251 | TV5MONDE EUROPE | aus | TV5MONDE EUROPE @586: nein | nein |
| 252 | TV8 Russia | aus | – | nein |
| 253 | TVE INTERNACIONAL EUROPA | aus | – | nein |
| 254 | TVP INFO HD | aus | – | nein |
| 255 | TVP Polonia | aus | – | nein |
| 256 | TVP Polonia | aus | – | nein |
| 257 | Universal TV | aus | – | nein |
| 258 | Universal TV | aus | – | nein |
| 259 | Volksmusik.TV | aus | volksmusik.TV @434: ja | ja |
| 260 | VOXup HD | an | VOXup SD @402: ja | ja |
| 261 | VOXup SD | aus | VOXup SD @402: ja | ja |
| 262 | Warner TV Comedy | aus | – | nein |
| 263 | Warner TV Film | aus | – | nein |
| 264 | Warner TV Serie | aus | – | nein |
| 265 | WDR HD Köln | an | WDR Köln @522: nein; WDR HD Köln @546: nein; WDR HD Köln @322: ja | ja |
| 266 | WDR Mediathek (Internet) | aus | WDR Mediathek (Internet) @546: nein | nein |
| 267 | WELT | aus | WELT @442: ja | ja |
| 268 | WELT HD | an | WELT @442: ja | ja |
| 269 | ZDF | aus | ZDF @514: nein; ZDF HD @410: nein; ZDF HD @322: ja | ja |
| 270 | zdf_neo HD | an | zdf_neo @514: nein; zdf_neo HD @410: nein; zdf_neo HD @330: ja | ja |
| 271 | ZDFinfo HD | bevorzugt | ZDFinfo @514: nein; ZDFinfo HD @330: ja | ja |
