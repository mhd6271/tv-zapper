"""Reine Logik aus zapper.py (ohne Home Assistant, ohne adb): Programmzeitschrift lesen und bewerten.

Bewusst 1:1 aus zapper.py uebernommen; dort ist sie am Fernseher erprobt.
"""
from __future__ import annotations

from html import escape
import re
from urllib.parse import quote
import xml.etree.ElementTree as ET

# KOMPAT: Reiternamen der TCL-Programmzeitschrift mit deutscher Oberflaeche. In anderer Sprache oder bei
# anderem Hersteller wird kein Reiter erkannt; ensure_fav_tab bricht dann ab (nie in "Alle" blaettern).
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


# KOMPAT: "Favorit1" ist der Name der ersten Favoritenliste beim TCL auf Deutsch (englisch vermutlich
# "Favorite1" oder aehnlich, nicht nachgeschaut). Einstellbar in den Optionen (Feld Favoritenliste).
def parse_guide(nodes, fav_tab="Favorit1"):
    """-> (rows, header, tab). rows: Liste (nummer, sender, sendung) in Bildschirm-Reihenfolge,
    header: dict title/genre/info der gerade markierten Sendung, tab: gewaehlter Reiter."""
    texts = [(n.get("text", ""), n.get("content-desc", "")) for n in nodes]
    # Zeilen erst nach dem Kopf der markierten Sendung suchen: dort steht z. B. die Altersangabe "12"
    # als eigene Zahl und wurde sonst als Sendernummer gelesen (Befund am Geraet 27.10.2026).
    start = 0
    for k, (t, _) in enumerate(texts):
        # KOMPAT: Erkennung ueber deutsche Texte der TCL-Oberflaeche: "Programmzeitschrift", "Drücken Sie ..."
        # (Kopf), "drücken Sie OK" (content-desc einer Sendung). Bei anderer Systemsprache oder anderer Firmware
        # werden keine Sendungen und kein Kopf gefunden. Die Sendernummern sind hoechstens vierstellig (\d{1,4}),
        # Sendernamen ohne ":".
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
            # KOMPAT: "·" als Trenner beim Genre und die herausgefilterten Merkmale sind wie beim TCL (Deutsch).
            # Anderswo landen solche Woerter mit in der Info und koennen mitbewertet werden.
            header["info"] = " ".join(x for x in h[1:] if x and x not in ("Keine", "Stereo", "FHD", "TTX", "Dolby Audio"))
    tab = next((n.get("content-desc") for n in nodes if n.get("selected") == "true"
                and n.get("content-desc") in (*TABS, fav_tab)), None)
    return rows, header, tab


# KOMPAT: Als Buchstaben fuer Wortgrenzen zaehlen nur a-z und äöüß. In anderen Sprachen (é, ñ, ø ...)
# gilt ein Akzentbuchstabe als Grenze. Dann trifft "cafe" auch "café", und Woerter mit Akzent werden
# eventuell mitten im Wort gefunden.
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


# KOMPAT: Gleichsetzungen fuer deutsche Sender (Kabel/DVB-C bei Max, FRITZ!Box). In anderen Laendern
# oder bei anderen Anbietern heissen Sender anders; die Liste muss mit FritzTv.norm der TV-App gleich bleiben.
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
    # KOMPAT: Nur a-z, 0-9 und äöüß bleiben uebrig. Sendernamen in anderen Schriften (kyrillisch, griechisch,
    # arabisch) oder mit Akzenten werden leer bzw. verlieren Buchstaben. Ein leerer Schluessel passt nie
    # (siehe sender_nie/sender_bonus); verschiedene Sender koennen aber zusammenfallen.
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


# KOMPAT: Liest den deutschen Statustext der TV-App (WerbeWaechter.status()); aendert die App den Wortlaut,
# gibt es hier einfach keinen Logo-Stand (None) statt eines falschen.
_WERBE_STATUS = (
    (re.compile(r"^Werbe-Sensor: lernt Logo von (.+) \((\d+) %\)$"), lambda m: f"lernt {m.group(2)} %"),
    (re.compile(r"^Werbe-Sensor: (.+?) – (?:Sendung|WERBUNG)(?:, ausgewichen)?$"), lambda m: "gelernt"),
    (re.compile(r"^Werbe-Sensor: (.+) wird nicht beobachtet$"), lambda m: "nicht beobachtet"),
)


def logo_status(werbe_sensor, sender) -> str | None:
    """Logo-Stand des laufenden Senders aus dem Werbe-Sensor-Status der TV-App: "gelernt", "lernt 40 %",
    "nicht beobachtet" oder None (unbekannt, anderer Sender, App ohne Werbe-Sensor)."""
    if not isinstance(werbe_sensor, str) or not sender:
        return None
    for rx, stand in _WERBE_STATUS:
        m = rx.match(werbe_sensor.strip())
        if m:
            return stand(m) if sender_schluessel(m.group(1)) == sender_schluessel(sender) else None
    return None


# Gelaeufige Kuerzel bekannter Sender (Schluessel wie sender_schluessel), sonst Anfangsbuchstaben
_KUERZEL = {"prosieben": "P7", "pro7maxx": "P7M", "daserste": "ARD", "kabeleins": "K1", "kabeleinsdoku": "K1D",
            "sat1": "SAT1", "rtlzwei": "RTL2", "comedycentral": "CC", "n24doku": "N24", "sport1": "S1",
            "eurosport1": "ES1", "tele5": "T5", "zdfneo": "NEO", "deluxemusic": "DLX", "ntv": "NTV",
            "rtlnitro": "NITRO", "euronewsgerman": "EN"}


def sender_kuerzel(name) -> str:
    """Kurzzeichen fuers kleine Senderabzeichen: `ProSieben HD` -> `P7`, `ZDF HD` -> `ZDF`, `VOXup HD` -> `VOXU`."""
    if sender_schluessel(name) in _KUERZEL:
        return _KUERZEL[sender_schluessel(name)]
    woerter = [w for w in re.split(r"\s+", (name or "").strip()) if w and w.upper() not in ("HD", "UHD", "SD")]
    if not woerter:
        return "?"
    if len(woerter) == 1:
        return woerter[0][:4].upper()
    return "".join(w if w.isdigit() else w[0] for w in woerter)[:4].upper()


def logo_bild(sender, stand) -> str | None:
    """Kleines, nachgemachtes Senderabzeichen als SVG-Daten-URL: farbig bei gelerntem Logo, grau umrandet sonst."""
    if not sender or not stand:
        return None
    text = escape(sender_kuerzel(sender))
    groesse = {1: 30, 2: 26, 3: 21, 4: 16}.get(len(text), 16)
    if stand == "gelernt":
        farbe = ("#1565c0", "#2e7d32", "#c62828", "#6a1b9a", "#ef6c00", "#00838f")[
            sum(map(ord, sender_schluessel(sender))) % 6]
        form = f'<rect x="2" y="2" width="60" height="60" rx="14" fill="{farbe}"/>'
        schrift = "#fff"
    else:
        form = '<rect x="3" y="3" width="58" height="58" rx="14" fill="none" stroke="#9e9e9e" stroke-width="3" stroke-dasharray="6 4"/>'
        schrift = "#9e9e9e"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{form}'
           f'<text x="32" y="33" font-family="Arial,sans-serif" font-weight="700" font-size="{groesse}" '
           f'fill="{schrift}" text-anchor="middle" dominant-baseline="central">{text}</text></svg>')
    return "data:image/svg+xml;charset=utf-8," + quote(svg)
