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
    # Zeilen erst nach dem Kopf der markierten Sendung suchen: dort steht z. B. die Altersangabe "12"
    # als eigene Zahl und wurde sonst als Sendernummer gelesen (Befund am Geraet 27.10.2026).
    start = 0
    for k, (t, _) in enumerate(texts):
        if t == "Programmzeitschrift":
            start = next((m + 1 for m in range(k + 1, len(texts)) if texts[m][0].startswith("Drücken Sie")), k + 1)
            break
    rows, i = [], start
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


_SENDER_ALIAS = {"nitro": "rtlnitro", "swr bw": "swr fernsehen bw", "swr rp": "swr fernsehen rp",
                 "sonlife broadcasting network": "sonlife"}
_SENDER_ERSETZEN = (("prosieben maxx", "pro7 maxx"), ("rtl television", "rtl"),
                    ("eurosport 1 deutschland", "eurosport 1"), ("n-tv", "ntv"), ("rtl2", "rtlzwei"))


def sender_schluessel(name) -> str:
    """Sendername zum Vergleichen, gleiche Regeln wie FritzTv.norm der TV-App: klein, HD/UHD/SD als eigenes Wort
    weg (auch mittendrin), feste Gleichsetzungen, dann nur a-z, 0-9, äöüß. `WDR HD Köln` = `WDR Köln`,
    `RTL Nitro` = `RTLNITRO` = `NITRO HD`, `ProSieben MAXX HD` = `Pro7 MAXX`, `RTL HD` = `RTL UHD`."""
    s = (name or "").lower().strip()
    s = re.sub(r"(^|\s)(hd|uhd|sd)(?=\s|$)", " ", s).strip()
    s = _SENDER_ALIAS.get(s, s)
    for alt, neu in _SENDER_ERSETZEN:
        s = s.replace(alt, neu)
    return re.sub(r"[^a-z0-9äöüß]", "", s)


def sender_nie(name, cfg) -> bool:
    k = sender_schluessel(name)
    return bool(k) and any(sender_schluessel(n) == k for n in cfg.get("sender_nie", []))


def sender_bonus(name, cfg) -> int:
    """Bonuspunkte fuer einen bevorzugten Sender (tolerant verglichen), sonst 0."""
    k = sender_schluessel(name)
    return next((b for n, b in cfg.get("sender_bevorzugt", {}).items() if k and sender_schluessel(n) == k), 0)


def bewerte_sendung(num, name, prog, h, cfg):
    """Eine Zeile der Programmzeitschrift bewerten (inkl. sender_nie / sender_bevorzugt)."""
    text = " ".join(x for x in (name, prog or "", h.get("genre", ""), h.get("info", "")) if x)
    s, hits = score(text, cfg)
    if sender_nie(name, cfg):
        s, hits = -1, ["Sender ausgeschlossen"]
    elif s > 0 and (bonus := sender_bonus(name, cfg)):
        s += bonus
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


def punkte_text(n, dativ=False) -> str:
    """`1 Punkt`, `3 Punkte`; nach "mit" (dativ): `3 Punkten`."""
    return "1 Punkt" if n == 1 else f"{n} Punkte{'n' if dativ else ''}"


def gruende(x, cfg) -> list[str]:
    """Warum eine bewertete Sendung (aus bewerte_sendung) Punkte hat, ausgeschrieben:
    `Doku: 2 Punkte, „doku*“ in der Beschreibung`, `bevorzugter Sender: 1 Punkt extra`."""
    titel = " ".join(t for t in (x.get("sender"), x.get("sendung")) if t).lower()
    rest = " ".join(t for t in (x.get("genre"), x.get("info")) if t).lower()
    out = []
    for name in x.get("treffer") or []:
        if name == "bevorzugter Sender":
            bonus = sender_bonus(x.get("sender"), cfg)
            out.append(f"bevorzugter Sender: {punkte_text(bonus)} extra")
            continue
        cat = next((c for c in cfg.get("interessen", []) if c["name"] == name), None)
        if not cat:
            out.append(name)
            continue
        wo = ""
        for w in cat["woerter"]:
            if word_rx(w).search(titel):
                wo = f", „{w}“ im Titel"
                break
            if word_rx(w).search(rest):
                wo = f", „{w}“ in der Beschreibung"
                break
        out.append(f"{name}: {punkte_text(cat['gewicht'])}{wo}")
    return out


def grund_zeilen(x, cfg) -> list[str]:
    """Kurze Zeilen fuer die Einblendung der TV-App: `Hip-Hop +5 („hip hop“ im Titel)`, `★ bevorzugter Sender +1`,
    `= 6 Punkte`."""
    zeilen = ["Zapper-Runde (HA)"]
    for g in gruende(x, cfg):
        name, _, rest = g.partition(": ")
        if name == "bevorzugter Sender":
            zeilen.append(f"★ bevorzugter Sender +{rest.split()[0]}")
            continue
        p, _, wo = rest.partition(", ")
        zeilen.append(f"{name} +{p.split()[0]}" + (f" ({wo})" if wo else ""))
    zeilen.append(f"= {punkte_text(x.get('punkte') or 0)}")
    return zeilen


def _sender(x) -> str:
    s = f"{x.get('nr')} {x.get('sender') or ''}".strip()
    return s + (f" („{x['sendung']}“)" if x.get("sendung") else "")


def umschalt_text(neu, vorher, cfg) -> str:
    """Logbuch-Eintrag fuer eine Umschaltung des HA-Zappers, ganz ausgeschrieben."""
    text = f"hat auf {_sender(neu)} umgeschaltet"
    if vorher and vorher.get("nr") is not None:
        p = vorher.get("punkte") or 0
        text += f", vorher {_sender(vorher)} " + (f"mit {punkte_text(p, dativ=True)}" if p >= 0 else "(ausgeschlossen)")
    g = gruende(neu, cfg)
    if g:
        text += ". Grund: " + "; ".join(g)
    return text + f". Zusammen {punkte_text(neu.get('punkte') or 0)}."


def app_umschalt_text(u) -> str:
    """Logbuch-Eintrag fuer eine Umschaltung des Zappers der TV-App (Feld `umschaltungen` aus ABFRAGEN)."""
    ziel, von = _sender(u), _sender(u["von"]) if u.get("von") else None
    grund = u.get("grund")
    if grund == "werbung":
        text = (f"Werbung auf {von or 'dem Sender'}, ausgewichen auf "
                + ("den bevorzugten Sender " if u.get("bevorzugt") else "") + ziel)
    elif grund == "zurueck":
        text = f"Werbung vorbei, zurück auf {ziel}"
    elif grund == "zurueck_zeitgrenze":
        text = f"Zeitgrenze fürs Ausweichen erreicht, zurück auf {ziel}"
    elif grund == "zurueck_fehlalarm":
        text = f"doch keine Werbung (Fehlalarm), zurück auf {ziel}"
    else:
        text = f"hat auf {ziel} umgeschaltet" + (f", vorher {von}" if von else "")
        if von and (u["von"].get("punkte") is not None):
            text += f" mit {punkte_text(u['von']['punkte'], dativ=True)}"
    g = [f"{k.get('name')}: {punkte_text(k.get('punkte') or 0)}" for k in u.get("kategorien") or []]
    if u.get("bevorzugt_bonus"):
        g.append(f"bevorzugter Sender: {punkte_text(u['bevorzugt_bonus'])} extra")
    if g:
        text += ". Grund: " + "; ".join(g)
    elif grund not in ("werbung", "zurueck") and u.get("text"):
        text += f". {u['text']}"
    if u.get("punkte") is not None:
        text += f". Zusammen {punkte_text(u['punkte'])}"
    if u.get("bestaetigt") is False:
        text += ". Der Fernseher hat den Wechsel nicht bestätigt"
    return text + "."


def soll_umschalten(cur, best):
    return bool(best and best["punkte"] > 0 and best["punkte"] > cur.get("punkte", 0))


# --- Interessen als Text (fuer die Eingabe in Home Assistant) ---------------------------

# Grenzen fuer Eingaben aus "Konfigurieren": schuetzen vor versehentlich riesigen Listen (jede Sendung wird gegen
# jedes Wort geprueft) und vor Woertern, die auf alles passen (`*`, `a*`).
MAX_KATEGORIEN = 50
MAX_WOERTER = 200          # Suchwoerter je Kategorie bzw. in "aus"
MAX_SENDER = 500           # Sendernamen in "nie" und "bevorzugt" (am TCL stehen 377 Tuner-Sender)
MAX_WORT = 60              # Zeichen je Wort / Sendername
MAX_NAME = 60              # Zeichen je Kategoriename
MAX_GEWICHT = 100          # Gewicht und Bonuspunkte: -100 ... 100
MAX_TEXT = 20000           # Zeichen je Eingabefeld
MAX_TEXT_SENDER = 40000    # Zeichen fuer die Senderlisten (500 Namen mit bis zu 60 Zeichen)


def _zahl(text, nr, was):
    try:
        z = int(text)
    except ValueError as e:
        raise ValueError(f"Zeile {nr}: {was} muss eine ganze Zahl sein") from e
    if not -MAX_GEWICHT <= z <= MAX_GEWICHT:
        raise ValueError(f"Zeile {nr}: {was} muss zwischen -{MAX_GEWICHT} und {MAX_GEWICHT} liegen")
    return z


def pruefe_woerter(liste, was="Wort", hoechstens=MAX_WOERTER):
    """Suchwoerter bzw. Sendernamen pruefen: Anzahl, Laenge, und kein Wort, das auf fast alles passt
    (`*` allein oder ein Buchstabe mit `*`). Wirft ValueError mit verstaendlicher Meldung."""
    if len(liste) > hoechstens:
        raise ValueError(f"Höchstens {hoechstens} Einträge je Liste (jetzt {len(liste)})")
    for w in liste:
        if len(w) > MAX_WORT:
            raise ValueError(f"{was} „{w[:20]}…“ ist zu lang (höchstens {MAX_WORT} Zeichen)")
        if len(w.rstrip("*").strip()) < 2:
            raise ValueError(f"{was} „{w}“ ist zu kurz und würde auf fast alles passen (mindestens 2 Zeichen)")
    return liste


def interessen_zu_text(interessen):
    """[{name, gewicht, woerter}] -> eine Zeile je Kategorie: `Name | Gewicht | wort1, wort2*`."""
    return "\n".join(f"{c['name']} | {c['gewicht']} | {', '.join(c['woerter'])}" for c in interessen)


def text_zu_interessen(text):
    """Umkehrung von interessen_zu_text. Wirft ValueError mit verstaendlicher Meldung."""
    if len(text) > MAX_TEXT:
        raise ValueError(f"Zu viel Text (höchstens {MAX_TEXT} Zeichen)")
    out = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        teile = [t.strip() for t in zeile.split("|")]
        if len(teile) != 3:
            raise ValueError(f"Zeile {nr}: bitte `Name | Gewicht | Wörter` schreiben")
        name, gewicht, woerter = teile
        gewicht = _zahl(gewicht, nr, "Gewicht")
        liste = woerter_zu_liste(woerter)
        if not name or not liste:
            raise ValueError(f"Zeile {nr}: Name und mindestens ein Wort nötig")
        if len(name) > MAX_NAME:
            raise ValueError(f"Zeile {nr}: Name zu lang (höchstens {MAX_NAME} Zeichen)")
        try:
            pruefe_woerter(liste)
        except ValueError as e:
            raise ValueError(f"Zeile {nr}: {e}") from None
        out.append({"name": name, "gewicht": gewicht, "woerter": liste})
        if len(out) > MAX_KATEGORIEN:
            raise ValueError(f"Höchstens {MAX_KATEGORIEN} Kategorien")
    if not out:
        raise ValueError("Mindestens eine Interessen-Zeile nötig")
    return out


def woerter_zu_liste(text):
    return [w.strip() for w in re.split(r"[,\n]", text) if w.strip()]


def bonus_zu_text(bonus):
    """{"N24 DOKU": 1} -> eine Zeile je Sender: `N24 DOKU | 1`."""
    return "\n".join(f"{name} | {punkte}" for name, punkte in bonus.items())


def text_zu_bonus(text):
    if len(text) > MAX_TEXT_SENDER:
        raise ValueError(f"Zu viel Text (höchstens {MAX_TEXT_SENDER} Zeichen)")
    out = {}
    for nr, zeile in enumerate(text.splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        name, _, punkte = (t.strip() for t in zeile.rpartition("|"))
        if not name:   # ohne `| Zahl`: 1 Bonuspunkt
            name, punkte = punkte, "1"
        try:
            out[name] = _zahl(punkte, nr, "Bonuspunkte")
        except ValueError as e:
            raise ValueError(f"Zeile {nr}: bitte `Sendername | Bonuspunkte` schreiben ({e})") from e
        if len(name) > MAX_WORT or len(out) > MAX_SENDER:
            raise ValueError(f"Zeile {nr}: Sendername zu lang oder zu viele Sender "
                             f"(höchstens {MAX_WORT} Zeichen, {MAX_SENDER} Sender)")
    return out
