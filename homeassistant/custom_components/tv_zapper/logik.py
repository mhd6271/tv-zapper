"""Reine Logik aus zapper.py (ohne Home Assistant, ohne adb): Programmzeitschrift lesen und bewerten.

Bewusst 1:1 aus zapper.py uebernommen; dort ist sie am Fernseher erprobt.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

TABS = ("Alle", "Streamen", "Digital", "Radio", "Kostenlos", "Daten/Andere")


def parse_xml(xml: str) -> list[dict]:
    """Ausgabe von `uiautomator dump; cat` -> Liste der Knoten-Attribute."""
    i = xml.find("<?xml")
    if i < 0:
        return []
    try:
        root = ET.fromstring(xml[i:])
    except ET.ParseError:
        return []
    return [n.attrib for n in root.iter("node")]


def parse_guide(nodes, fav_tab="Favorit1"):
    """-> (rows, header, tab). rows: Liste (nummer, sender, sendung) in Bildschirm-Reihenfolge,
    header: dict title/genre/info der gerade markierten Sendung, tab: gewaehlter Reiter."""
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
                and n.get("content-desc") in (*TABS, fav_tab)), None)
    return rows, header, tab


def word_rx(w):
    w = w.lower()
    pre = w.endswith("*")
    w = w.rstrip("*")
    tail = "" if pre else r"(?![a-zäöüß])"
    return re.compile(r"(?<![a-zäöüß])" + re.escape(w) + tail)


def score(text, cfg):
    """cfg wie interessen.json: {"interessen": [{name, gewicht, woerter}], "aus": [...]}."""
    text = text.lower()
    if any(word_rx(w).search(text) for w in cfg.get("aus", [])):
        return -1, []
    total, hits = 0, []
    for cat in cfg["interessen"]:
        if any(word_rx(w).search(text) for w in cat["woerter"]):
            total += cat["gewicht"]
            hits.append(cat["name"])
    return total, hits


def bewerte_sendung(num, name, prog, h, cfg):
    """Eine Zeile der Programmzeitschrift bewerten (inkl. sender_nie / sender_bevorzugt)."""
    text = " ".join(x for x in (name, prog or "", h.get("genre", ""), h.get("info", "")) if x)
    s, hits = score(text, cfg)
    if name in cfg.get("sender_nie", []):
        s, hits = -1, ["Sender ausgeschlossen"]
    elif s > 0 and name in cfg.get("sender_bevorzugt", {}):
        s += cfg["sender_bevorzugt"][name]
        hits.append("bevorzugter Sender")
    return {"nr": num, "sender": name, "sendung": prog, "genre": h.get("genre", ""),
            "info": h.get("info", ""), "punkte": s, "treffer": hits}


def bewerte(current, chans, infos, cfg):
    """-> (scored, cur, best) wie in zapper.cycle()."""
    scored = [bewerte_sendung(num, name, prog, infos.get(num, {}), cfg)
              for num, (name, prog) in sorted(chans.items())]
    cur = next((x for x in scored if x["nr"] == current), {"nr": current, "punkte": 0})
    best = max(scored, key=lambda x: (x["punkte"], x["nr"] == current), default=None)
    return scored, cur, best


def soll_umschalten(cur, best):
    return bool(best and best["punkte"] > 0 and best["punkte"] > cur.get("punkte", 0))


# --- Interessen als Text (fuer die Eingabe in Home Assistant) ---------------------------

def interessen_zu_text(interessen):
    """[{name, gewicht, woerter}] -> eine Zeile je Kategorie: `Name | Gewicht | wort1, wort2*`."""
    return "\n".join(f"{c['name']} | {c['gewicht']} | {', '.join(c['woerter'])}" for c in interessen)


def text_zu_interessen(text):
    """Umkehrung von interessen_zu_text. Wirft ValueError mit verstaendlicher Meldung."""
    out = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        teile = [t.strip() for t in zeile.split("|")]
        if len(teile) != 3:
            raise ValueError(f"Zeile {nr}: bitte `Name | Gewicht | Wörter` schreiben")
        name, gewicht, woerter = teile
        try:
            gewicht = int(gewicht)
        except ValueError as e:
            raise ValueError(f"Zeile {nr}: Gewicht muss eine ganze Zahl sein") from e
        liste = woerter_zu_liste(woerter)
        if not name or not liste:
            raise ValueError(f"Zeile {nr}: Name und mindestens ein Wort nötig")
        out.append({"name": name, "gewicht": gewicht, "woerter": liste})
    if not out:
        raise ValueError("Mindestens eine Interessen-Zeile nötig")
    return out


def woerter_zu_liste(text):
    return [w.strip() for w in re.split(r"[,\n]", text) if w.strip()]


def bonus_zu_text(bonus):
    """{"N24 DOKU": 1} -> eine Zeile je Sender: `N24 DOKU | 1`."""
    return "\n".join(f"{name} | {punkte}" for name, punkte in bonus.items())


def text_zu_bonus(text):
    out = {}
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        name, _, punkte = (t.strip() for t in zeile.rpartition("|"))
        try:
            out[name or punkte] = int(punkte) if name else 1   # ohne `| Zahl`: 1 Bonuspunkt
        except ValueError as e:
            raise ValueError(f"Zeile {nr}: bitte `Sendername | Bonuspunkte` schreiben") from e
    return out
