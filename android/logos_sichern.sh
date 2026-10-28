#!/bin/sh
# Holt die am Fernseher gelernten Senderlogos (ABFRAGEN --es was logos) nach assets/logos/<Schluessel>.txt.
# Danach committen: Die naechste Fassung bringt sie mit, ein neues Geraet muss sie nicht neu lernen,
# und nach einer Neuinstallation (Daten geloescht) sind sie nicht verloren.
# Fernseher: TVZ_TV oder ../.tvz_tv (IP:Port). Bestehende Dateien werden nur ueberschrieben, wenn sich der Inhalt aendert.
set -e
cd "$(dirname "$0")"
TV=${TVZ_TV:-$(cat ../.tvz_tv 2>/dev/null)}
[ -n "$TV" ] || { echo "Fernseher unbekannt: TVZ_TV setzen oder ../.tvz_tv anlegen" >&2; exit 1; }
adb -s "$TV" shell am broadcast -a io.github.mhd6271.tvzapper.ABFRAGEN \
    -n io.github.mhd6271.tvzapper/.AbfrageEmpfaenger --es was logos | python3 -I -c '
import json, os, re, sys
t = sys.stdin.read()
if "data=\"" not in t:
    sys.exit("keine Antwort vom Fernseher: " + t.strip()[-200:])
d = json.loads(t[t.index("data=\"") + 6:t.rindex("\"")])
files = d.get("logo_dateien")
if files is None:
    sys.exit("App zu alt: ABFRAGEN liefert keine logo_dateien (ab 0.4.7)")
os.makedirs("assets/logos", exist_ok=True)
for key, txt in sorted(files.items()):
    if not re.fullmatch(r"[a-z0-9äöüß]+", key):   # Schluessel kommen vom Geraet: nur FritzTv.norm-Zeichen
        print("uebersprungen:", repr(key)); continue
    p = "assets/logos/%s.txt" % key
    old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
    if old != txt:
        open(p, "w", encoding="utf-8").write(txt)
    print(("neu    " if old is None else "neuer  " if old != txt else "gleich ") + key)
print("%d Logos vom Fernseher" % len(files))
'
