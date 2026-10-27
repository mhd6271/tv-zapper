#!/usr/bin/env python3
"""TV-Zapper: liest die Programmzeitschrift des TCL-Fernsehers (Liste "Favorit1") per adb,
bewertet jede laufende Sendung gegen interessen.json und schaltet auf den besten Treffer.

Bildschirmfotos vom Fernsehbild sind auf dem Geraet schwarz (Kopierschutz); die
Programmzeitschrift ist dagegen normaler Text und laesst sich mit uiautomator lesen.

Aufruf:  python3 zapper.py                 (60 min, alle 5 min pruefen)
         python3 zapper.py --minuten 30
         python3 zapper.py --einmal        (ein Durchgang, zum Testen)
         python3 zapper.py --nur-lesen     (nur auslesen und bewerten, nicht umschalten)
Geraet:  Umgebungsvariable TVZ_TV (Standard 192.168.20.61:5555)
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
TV = os.environ.get("TVZ_TV", "192.168.20.61:5555")
TV_APP = "com.tcl.tv/com.tcl.player.TVActivity"
GUIDE_APP = "com.tcl.tv/com.tcl.tv.epg.EpgProActivity"
LOG = HERE / "protokoll.jsonl"
FAV_TAB = "Favorit1"


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def say(msg):
    print(f"[{now()}] {msg}", flush=True)


def adb(*args, timeout=30):
    r = subprocess.run(["adb", "-s", TV, *args], capture_output=True, text=True, timeout=timeout)
    return r.stdout


def key(*names):
    adb("shell", "input", "keyevent", *names)


def close_guide():
    """BACK nur, wenn die Programmzeitschrift vorn ist: im Fernsehbild springt BACK beim TCL
    auf den vorigen Sender."""
    for _ in range(2):
        if focus_app() != GUIDE_APP:
            return
        key("KEYCODE_BACK")
        time.sleep(1.2)


def focus_app():
    m = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([^}]+)\}", adb("shell", "dumpsys", "window"))
    return m.group(1).strip() if m else ""


def dump(press=None, wait=0.4):
    """Optional eine Taste druecken, dann die Oberflaeche lesen - alles in einem adb-Aufruf."""
    pre = f"input keyevent {press}; sleep {wait}; " if press else ""
    xml = adb("shell", pre + "uiautomator dump /sdcard/tvz.xml >/dev/null 2>&1; cat /sdcard/tvz.xml")
    i = xml.find("<?xml")
    if i < 0:
        return []
    try:
        root = ET.fromstring(xml[i:])
    except ET.ParseError:
        return []
    return [n.attrib for n in root.iter("node")]


def parse_guide(nodes):
    """-> (rows, header). rows: Liste (nummer, sender, sendung) in Bildschirm-Reihenfolge,
    header: dict title/genre/info der gerade markierten Sendung."""
    texts = [(n.get("text", ""), n.get("content-desc", "")) for n in nodes]
    rows, i = [], 0
    while i < len(texts):
        t = texts[i][0]
        if re.fullmatch(r"\d{1,4}", t):
            name, prog, j = None, None, i + 1
            while j < len(texts) and j < i + 6:
                tj, dj = texts[j]
                if tj and not re.fullmatch(r"\d{1,4}", tj) and ":" not in tj:
                    name = tj
                    break
                if re.fullmatch(r"\d{1,4}", tj):
                    break
                j += 1
            if name:
                k = j + 1
                while k < len(texts):
                    tk, dk = texts[k]
                    if re.fullmatch(r"\d{1,4}", tk):
                        break
                    if dk and "drücken Sie OK" in dk:
                        prog = dk.split(",")[0].strip()
                        break
                    k += 1
                rows.append((int(t), name, prog))
                i = j + 1
                continue
        i += 1
    header = {}
    seq = [t for t, _ in texts if t]
    if "Programmzeitschrift" in seq:
        h = []
        for t in seq[seq.index("Programmzeitschrift") + 1:]:
            if t.startswith("Drücken Sie"):
                break
            h.append(t.strip())
        if h:
            header["title"] = h[0]
            header["genre"] = next((x for x in h[1:] if "·" in x), "")
            header["info"] = " ".join(x for x in h[1:] if x and x not in ("Keine", "Stereo", "FHD", "TTX", "Dolby Audio"))
    tab = next((n.get("content-desc") for n in nodes if n.get("selected") == "true"
                and n.get("content-desc") in ("Alle", "Streamen", "Digital", "Radio", "Kostenlos", "Daten/Andere", FAV_TAB)), None)
    return rows, header, tab


def open_guide():
    if focus_app() != GUIDE_APP:
        key("KEYCODE_GUIDE")
    for _ in range(12):
        time.sleep(1)
        nodes = dump()
        rows, header, tab = parse_guide(nodes)
        if rows:
            return nodes
    return dump()


def ensure_fav_tab(nodes):
    _, _, tab = parse_guide(nodes)
    if tab == FAV_TAB:
        return True
    key("KEYCODE_DPAD_LEFT")
    time.sleep(0.8)
    for _ in range(8):
        f = [n.get("content-desc") for n in dump() if n.get("focused") == "true"]
        if FAV_TAB in f:
            key("KEYCODE_DPAD_CENTER")
            time.sleep(1.5)
            key("KEYCODE_DPAD_RIGHT")
            time.sleep(1)
            return True
        key("KEYCODE_DPAD_DOWN")
        time.sleep(0.6)
    return False


def collect():
    """Liest alle Sender der Favoritenliste mit laufender Sendung (+ Genre/Info, wo markiert)."""
    nodes = open_guide()
    rows, header, _ = parse_guide(nodes)
    if not rows:
        raise RuntimeError("Programmzeitschrift liess sich nicht lesen")
    current = rows[0][0]
    if not ensure_fav_tab(nodes):
        say("Favorit1 nicht gefunden - lese die aktuelle Liste")
    chans, infos = {}, {}

    def take(nodes):
        rows, header, _ = parse_guide(nodes)
        new = 0
        for num, name, prog in rows:
            if num not in chans:
                new += 1
            chans[num] = (name, prog or chans.get(num, (None, None))[1])
        if header.get("title"):
            for num, name, prog in rows:
                if prog and prog == header["title"]:
                    infos[num] = header
                    break
        return new

    take(dump())
    key(*["KEYCODE_DPAD_UP"] * 120)          # an den Anfang der Liste
    time.sleep(1.5)
    take(dump())
    idle = 0
    for _ in range(200):
        n = take(dump("KEYCODE_DPAD_DOWN", 0.35))
        idle = idle + 1 if n == 0 else 0
        if idle >= 15:
            break
    close_guide()
    return current, chans, infos


def load_interests():
    return json.loads((HERE / "interessen.json").read_text(encoding="utf-8"))


def word_rx(w):
    w = w.lower()
    pre = w.endswith("*")
    w = w.rstrip("*")
    tail = "" if pre else r"(?![a-zäöüß])"
    return re.compile(r"(?<![a-zäöüß])" + re.escape(w) + tail)


def score(text, cfg):
    text = text.lower()
    if any(word_rx(w).search(text) for w in cfg.get("aus", [])):
        return -1, []
    total, hits = 0, []
    for cat in cfg["interessen"]:
        if any(word_rx(w).search(text) for w in cat["woerter"]):
            total += cat["gewicht"]
            hits.append(cat["name"])
    return total, hits


def tune(num):
    close_guide()
    if focus_app() != TV_APP:
        raise RuntimeError(f"Fernsehbild nicht vorn ({focus_app()}) - schalte nicht um")
    for d in str(num):
        key(f"KEYCODE_{d}")
        time.sleep(0.8)
    key("KEYCODE_DPAD_CENTER")
    time.sleep(4)


def log(entry):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def verify(cand, cfg):
    """Nach dem Umschalten: Programmzeitschrift oeffnen (startet beim laufenden Sender) und
    die nun aktuelle Sendung samt Beschreibung neu bewerten."""
    time.sleep(3)
    nodes = open_guide()
    rows, header, _ = parse_guide(nodes)
    close_guide()
    if not rows or rows[0][0] != cand["nr"]:
        return None
    num, name, prog = rows[0]
    text = " ".join(x for x in (name, prog or "", header.get("genre", ""), header.get("info", "")) if x)
    s, hits = score(text, cfg)
    if s > 0 and name in cfg.get("sender_bevorzugt", {}):
        s += cfg["sender_bevorzugt"][name]
        hits.append("bevorzugter Sender")
    return {"nr": num, "sender": name, "sendung": prog, "genre": header.get("genre", ""),
            "info": header.get("info", ""), "punkte": s, "treffer": hits}


def cycle(read_only=False):
    cfg = load_interests()
    app = focus_app()
    if app not in (TV_APP, GUIDE_APP):
        say(f"Fernseher zeigt gerade etwas anderes ({app or 'nichts/aus'}) - lasse ihn in Ruhe")
        log({"zeit": datetime.datetime.now().isoformat(timespec="seconds"), "aktion": "uebersprungen", "app": app})
        return None
    current, chans, infos = collect()
    scored = []
    for num, (name, prog) in sorted(chans.items()):
        h = infos.get(num, {})
        text = " ".join(x for x in (name, prog or "", h.get("genre", ""), h.get("info", "")) if x)
        s, hits = score(text, cfg)
        if name in cfg.get("sender_nie", []):
            s, hits = -1, ["Sender ausgeschlossen"]
        elif s > 0 and name in cfg.get("sender_bevorzugt", {}):
            s += cfg["sender_bevorzugt"][name]
            hits.append("bevorzugter Sender")
        scored.append({"nr": num, "sender": name, "sendung": prog, "genre": h.get("genre", ""),
                       "info": h.get("info", ""), "punkte": s, "treffer": hits})
    cur = next((x for x in scored if x["nr"] == current), {"nr": current, "punkte": 0})
    best = max(scored, key=lambda x: (x["punkte"], x["nr"] == current), default=None)
    action = "bleibt"
    if best and best["punkte"] > 0 and best["punkte"] > cur.get("punkte", 0) and not read_only:
        # Nur einmal umschalten. Die Beschreibung ist erst nach dem Anwaehlen sicher aktuell -
        # danach nur nachlesen, nicht weiter herumschalten.
        tune(best["nr"])
        action = "umgeschaltet"
        fresh = verify(best, cfg)
        if fresh is not None:
            if fresh["punkte"] <= 0:
                say(f"   nach dem Umschalten: {fresh['sendung']} - passt doch nicht, naechster Durchgang entscheidet neu")
            best = fresh
    say(f"{len(chans)} Sender gelesen, laeuft: {current} {cur.get('sender', '')} - {cur.get('sendung', '')} ({cur.get('punkte', 0)} P.)")
    for x in sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"])[:6]:
        say(f"   {x['punkte']:>2} P. {x['nr']:>4} {x['sender']}: {x['sendung']}  [{', '.join(x['treffer'])}] {x['genre']}")
    if action == "umgeschaltet":
        say(f"-> umgeschaltet auf {best['nr']} {best['sender']}: {best['sendung']}")
    else:
        say("-> bleibt" + ("" if (best and best["punkte"] > 0) else " (nichts Passendes gefunden)"))
    log({"zeit": datetime.datetime.now().isoformat(timespec="seconds"), "aktion": action,
         "vorher": cur, "neu": best if action == "umgeschaltet" else None,
         "treffer": [x for x in scored if x["punkte"] > 0], "sender_gelesen": len(chans)})
    return action


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minuten", type=float, default=60)
    ap.add_argument("--takt", type=float, default=None, help="Minuten zwischen zwei Pruefungen (Standard aus interessen.json)")
    ap.add_argument("--einmal", action="store_true")
    ap.add_argument("--nur-lesen", action="store_true")
    a = ap.parse_args()
    takt = a.takt or load_interests().get("verweilen_min", 5)
    end = time.time() + a.minuten * 60
    fails = 0
    while True:
        try:
            cycle(a.nur_lesen)
            fails = 0
        except Exception as e:
            fails += 1
            say(f"Fehler: {e}")
            log({"zeit": datetime.datetime.now().isoformat(timespec="seconds"), "aktion": "fehler", "fehler": str(e)})
            if fails >= 3:
                say("Dreimal hintereinander fehlgeschlagen - Ende")
                return 1
        if a.einmal or time.time() + takt * 60 > end:
            break
        time.sleep(takt * 60)
    say("Fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main())
