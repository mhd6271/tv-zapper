"""Fernseher per adb-shell bedienen (ohne Home Assistant): Ablauf 1:1 aus zapper.py.

Statt des adb-Programms spricht die Integration selbst ADB ueber TCP (Bibliothek adb-shell,
dieselbe wie in der eingebauten Integration "Android Debug Bridge") mit eigenem Schluessel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import socket

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

from .logik import bewerte, bewerte_sendung, parse_guide, parse_xml, soll_umschalten

_LOGGER = logging.getLogger(__name__)

TV_APP = "com.tcl.tv/com.tcl.player.TVActivity"
# Einblendung ueber die TV-App aus android/ (Overlay wie deren eigene Meldung nach dem Umschalten)
EINBLENDEN_ACTION = "io.github.mhd6271.tvzapper.EINBLENDEN"
EINBLENDEN_EMPFAENGER = "io.github.mhd6271.tvzapper/.EinblendungEmpfaenger"
GUIDE_APP = "com.tcl.tv/com.tcl.tv.epg.EpgProActivity"
# Schnittstelle der TV-App ab 0.3.0: Sender und Sendungen aus TvContract, Umschalten ohne Tasten
ABFRAGEN_ACTION = "io.github.mhd6271.tvzapper.ABFRAGEN"
UMSCHALTEN_ACTION = "io.github.mhd6271.tvzapper.UMSCHALTEN"
EINSTELLEN_ACTION = "io.github.mhd6271.tvzapper.EINSTELLEN"
ABFRAGE_EMPFAENGER = "io.github.mhd6271.tvzapper/.AbfrageEmpfaenger"


def broadcast_daten(ausgabe: str) -> dict | None:
    """`Broadcast completed: result=0, data="{...}"` -> dict; None, wenn kein Empfaenger geantwortet hat."""
    m = re.search(r'Broadcast completed: result=(-?\d+), data="(.*)"\s*$', ausgabe, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(2))
    except ValueError:
        return None


def app_sendung(x: dict, cfg) -> dict:
    """Ein Sender aus der TV-App wie eine Zeile der Programmzeitschrift bewerten. genre ist bei TCL ein
    DVB-Zahlencode und wird nicht mitbewertet; Folge und Beschreibung zaehlen wie die Info im Kopf."""
    info = " ".join(t for t in (x.get("folge"), x.get("beschreibung")) if t)
    b = bewerte_sendung(int(x["nr"]), x.get("sender", ""), x.get("sendung") or None, {"info": info}, cfg)
    b.update(id=x.get("id"), start=x.get("start"), ende=x.get("ende"))
    return b


def lade_signer(pfad: str) -> PythonRSASigner:
    """Schluessel laden, beim ersten Mal anlegen (blockierend, im Executor aufrufen)."""
    if not os.path.isfile(pfad):
        os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
        keygen(pfad)
    with open(pfad, encoding="utf-8") as f:
        priv = f.read()
    pub = None   # ohne .pub geht nur ein schon freigegebener Schluessel (z. B. ~/.android/adbkey)
    if os.path.isfile(pfad + ".pub"):
        with open(pfad + ".pub", encoding="utf-8") as f:
            pub = f.read()
    return PythonRSASigner(pub, priv)


def magic_packet(mac: str) -> bytes:
    """Wake-on-LAN-Paket: 6x FF, dann 16x die MAC. Wirft ValueError bei ungueltiger MAC."""
    ziffern = re.sub(r"[:\-. ]", "", mac.strip())
    if not re.fullmatch(r"[0-9a-fA-F]{12}", ziffern):
        raise ValueError("MAC-Adresse bitte als 12 Hex-Ziffern, z. B. aa:bb:cc:dd:ee:ff")
    return b"\xff" * 6 + bytes.fromhex(ziffern) * 16


def sende_wol(mac: str, host: str):
    """Paket an die Broadcast-Adresse (Port 9) und direkt an den Fernseher schicken (blockierend)."""
    paket = magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for ziel in ("255.255.255.255", host):
            try:
                s.sendto(paket, (ziel, 9))
            except OSError as e:
                _LOGGER.debug("Wake-on-LAN an %s nicht gesendet: %s", ziel, e)


class Fernseher:
    def __init__(self, host: str, port: int, signer: PythonRSASigner, fav_tab: str = "Favorit1"):
        self.host, self.port, self.signer, self.fav_tab = host, port, signer, fav_tab
        self.dev: AdbDeviceTcpAsync | None = None

    # --- Verbindung -------------------------------------------------------------------
    async def verbinden(self, auth_timeout: float = 10.0, timeout: float | None = None):
        if self.dev and self.dev.available:
            return
        self.dev = AdbDeviceTcpAsync(self.host, self.port, default_transport_timeout_s=30.0)  # uiautomator dump braucht manchmal >9 s
        # auth_timeout: so lange wird auf "USB-Debugging zulassen?" am Fernseher gewartet
        await self.dev.connect(rsa_keys=[self.signer], transport_timeout_s=timeout, auth_timeout_s=auth_timeout)

    async def trennen(self):
        if self.dev:
            try:
                await self.dev.close()
            except Exception:  # noqa: BLE001 - beim Aufraeumen egal
                pass
            self.dev = None

    async def sh(self, cmd: str, timeout: float = 30) -> str:
        await self.verbinden()
        try:
            return await self.dev.shell(cmd, timeout_s=timeout, read_timeout_s=timeout) or ""
        except Exception:
            await self.trennen()
            raise

    # --- Wecken ---------------------------------------------------------------------------
    async def wach(self) -> bool:
        return "mWakefulness=Awake" in await self.sh("dumpsys power | grep mWakefulness=")

    async def wecken(self, mac: str = "", warten: float = 90) -> str:
        """Vor dem Zappen: Fernseher nicht erreichbar -> Wake-on-LAN (nur mit MAC) und warten, bis ADB antwortet;
        erreichbar, aber Bild aus -> Taste WAKEUP. -> "wach", "geweckt" oder "wol"."""
        weg = "wach"
        try:
            await self.verbinden(timeout=8)
        except Exception:
            await self.trennen()
            if not mac:
                raise
            loop = asyncio.get_running_loop()
            ende = loop.time() + warten
            while True:
                await loop.run_in_executor(None, sende_wol, mac, self.host)
                await asyncio.sleep(5)
                try:
                    await self.verbinden(timeout=8)
                    break
                except Exception:  # noqa: BLE001 - weiter warten
                    await self.trennen()
                    if loop.time() > ende:
                        raise RuntimeError(f"Fernseher antwortet {warten:.0f} s nach Wake-on-LAN nicht") from None
            weg = "wol"
        if not await self.wach():
            await self.key("KEYCODE_WAKEUP")
            weg = "geweckt" if weg == "wach" else weg
        if weg != "wach":
            await asyncio.sleep(8)   # Fernsehbild und Tuner brauchen nach dem Aufwachen ein paar Sekunden
        return weg

    # --- Bausteine wie in zapper.py -------------------------------------------------------
    async def key(self, *names):
        await self.sh("input keyevent " + " ".join(names))

    async def close_guide(self):
        """BACK nur, wenn die Programmzeitschrift vorn ist: im Fernsehbild springt BACK beim TCL
        auf den vorigen Sender."""
        for _ in range(2):
            if await self.focus_app() != GUIDE_APP:
                return
            await self.key("KEYCODE_BACK")
            await asyncio.sleep(1.2)

    async def nur_in_guide(self, was: str):
        """Schutz: Hoch/Runter/OK nur in der Programmzeitschrift. In der Senderliste
        (z. B. NewChannelListActivity) schaltet jedes Hoch/Runter um."""
        if (app := await self.focus_app()) != GUIDE_APP:
            raise RuntimeError(f"Programmzeitschrift nicht vorn ({app or 'nichts'}) - {was} abgebrochen")

    async def focus_app(self) -> str:
        out = await self.sh("dumpsys window | grep mCurrentFocus")
        m = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([^}]+)\}", out)
        return m.group(1).strip() if m else ""

    async def dump(self, press=None, wait=0.4):
        """Optional eine Taste druecken, dann die Oberflaeche lesen - alles in einem Aufruf."""
        pre = f"input keyevent {press}; sleep {wait}; " if press else ""
        xml = await self.sh(pre + "uiautomator dump /sdcard/tvz.xml >/dev/null 2>&1; cat /sdcard/tvz.xml")
        return parse_xml(xml)

    def guide(self, nodes):
        return parse_guide(nodes, self.fav_tab)

    async def open_guide(self):
        if await self.focus_app() != GUIDE_APP:
            await self.key("KEYCODE_GUIDE")
        for _ in range(12):
            await asyncio.sleep(1)
            nodes = await self.dump()
            rows, _, _ = self.guide(nodes)
            if rows and await self.focus_app() == GUIDE_APP:
                return nodes
        await self.nur_in_guide("Lesen")
        return await self.dump()

    async def ensure_fav_tab(self, nodes):
        _, _, tab = self.guide(nodes)
        if tab == self.fav_tab:
            return True
        await self.nur_in_guide("Reiterwahl")
        await self.key("KEYCODE_DPAD_LEFT")
        await asyncio.sleep(0.8)
        for _ in range(8):
            await self.nur_in_guide("Reiterwahl")
            f = [n.get("content-desc") for n in await self.dump() if n.get("focused") == "true"]
            if self.fav_tab in f:
                await self.key("KEYCODE_DPAD_CENTER")
                await asyncio.sleep(1.5)
                await self.key("KEYCODE_DPAD_RIGHT")
                await asyncio.sleep(1)
                # nachpruefen, dass wirklich die Favoritenliste gewaehlt ist
                return self.guide(await self.dump())[2] == self.fav_tab
            await self.key("KEYCODE_DPAD_DOWN")
            await asyncio.sleep(0.6)
        return False

    async def collect(self):
        """Liest alle Sender der Favoritenliste mit laufender Sendung (+ Genre/Info, wo markiert)."""
        nodes = await self.open_guide()
        rows, _, _ = self.guide(nodes)
        if not rows:
            raise RuntimeError("Programmzeitschrift liess sich nicht lesen")
        current = rows[0][0]
        if not await self.ensure_fav_tab(nodes):
            # nie in "Alle" blaettern: dort sind Hunderte Sender
            raise RuntimeError(f"Reiter {self.fav_tab} liess sich nicht waehlen - Abbruch")
        chans, infos = {}, {}

        def take(nodes):
            rows, header, _ = self.guide(nodes)
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

        take(await self.dump())
        # an den Anfang der Liste - in kleinen Stuecken und jedes Mal pruefen, dass die
        # Programmzeitschrift noch vorn ist: im Fernsehbild schaltet jedes Hoch einen Sender weiter.
        for _ in range(6):
            await self.nur_in_guide("Blaettern")
            await self.key(*["KEYCODE_DPAD_UP"] * 20)
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        take(await self.dump())
        idle = 0
        for schritt in range(200):
            if schritt % 5 == 0:
                await self.nur_in_guide("Blaettern")
            n = take(await self.dump("KEYCODE_DPAD_DOWN", 0.35))
            idle = idle + 1 if n == 0 else 0
            if idle >= 15:
                break
        await self.close_guide()
        return current, chans, infos

    async def tune(self, num):
        await self.close_guide()
        if (app := await self.focus_app()) != TV_APP:
            raise RuntimeError(f"Fernsehbild nicht vorn ({app}) - schalte nicht um")
        for d in str(num):                      # Ziffern einzeln, sonst wird die erste verschluckt
            await self.key(f"KEYCODE_{d}")
            await asyncio.sleep(0.8)
        await self.key("KEYCODE_DPAD_CENTER")
        await asyncio.sleep(4)

    async def aufraeumen(self):
        """Nach einem Fehler: Programmzeitschrift schliessen, falls sie noch offen ist (neue Verbindung)."""
        await self.trennen()
        try:
            await self.close_guide()
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Programmzeitschrift liess sich nach Fehler nicht schliessen: %s", e)

    async def app_abfragen(self, liste: bool = False) -> dict | None:
        """Zustand von der TV-App (ab 0.3.0); None, wenn sie nicht installiert ist oder nicht antwortet."""
        zusatz = " --es was liste" if liste else ""
        return broadcast_daten(await self.sh(f"am broadcast -a {ABFRAGEN_ACTION} -n {ABFRAGE_EMPFAENGER}{zusatz}"))

    async def app_umschalten(self, nr: int, text: str = "") -> dict:
        zusatz = f" --es text {shlex.quote(text)}" if text else ""
        antwort = broadcast_daten(await self.sh(
            f"am broadcast -a {UMSCHALTEN_ACTION} -n {ABFRAGE_EMPFAENGER} --es nr {int(nr)}{zusatz}"))
        if not antwort or not antwort.get("ok"):
            raise RuntimeError(f"TV-App hat nicht umgeschaltet: {antwort}")
        return antwort

    async def app_einstellen(self, name: str, wert: bool) -> dict:
        """Eine Einstellung der TV-App setzen (z. B. ausweichen_bevorzugt)."""
        antwort = broadcast_daten(await self.sh(
            f"am broadcast -a {EINSTELLEN_ACTION} -n {ABFRAGE_EMPFAENGER} --es {name} {'true' if wert else 'false'}"))
        if not antwort or not antwort.get("ok"):
            raise RuntimeError(f"TV-App hat {name} nicht gesetzt: {antwort}")
        return antwort

    async def jetzt(self, cfg) -> dict:
        """Was laeuft gerade (fuer das TV-Protokoll, ohne Tasten). Ohne TV-App nur, ob das Fernsehbild vorn ist."""
        daten = await self.app_abfragen()
        if daten is None:
            app = await self.focus_app()
            return {"quelle": "adb", "fernsehbild_vorn": app == TV_APP, "vorn": app, "jetzt": None}
        x = daten.get("jetzt")
        return {"quelle": "app", "fernsehbild_vorn": daten.get("fernsehbild_vorn"), "vorn": daten.get("vorn"),
                "bildschirm_an": daten.get("bildschirm_an"), "werbung": daten.get("werbung"),
                "zapper_app": daten.get("zapper_laeuft"),
                # Einstellungen der TV-App (ab dem Stand nach 0.3.0), nur zur Anzeige
                "werbung_umgehen": daten.get("werbung_umgehen"), "ausweichen_bevorzugt": daten.get("ausweichen_bevorzugt"),
                "jetzt": app_sendung(x, cfg) | {"folge": x.get("folge"), "beschreibung": x.get("beschreibung")}
                if x else None}

    async def durchgang_app(self, daten: dict, cfg, nur_lesen: bool) -> dict:
        """Durchgang ueber die TV-App: Liste lesen, bewerten, einmal umschalten, nachfragen."""
        scored = [app_sendung(x, cfg) for x in daten["liste"]]
        jetzt = daten.get("jetzt") or {}
        current = int(jetzt["nr"]) if jetzt.get("nr") else None
        cur = next((x for x in scored if x["nr"] == current), {"nr": current, "punkte": 0})
        best = max(scored, key=lambda x: (x["punkte"], x["nr"] == current), default=None)
        aktion, neu, nachgelesen = "bleibt", None, None
        if soll_umschalten(cur, best) and not nur_lesen:
            await self.app_umschalten(best["nr"])
            aktion, neu = "umgeschaltet", best
            await asyncio.sleep(1)
            danach = await self.app_abfragen()
            if danach and danach.get("jetzt") and int(danach["jetzt"]["nr"]) == best["nr"]:
                nachgelesen = neu = app_sendung(danach["jetzt"], cfg)
        return {"aktion": aktion, "quelle": "app", "vorher": cur, "bester": best, "neu": neu,
                "passt_nach_umschalten": None if nachgelesen is None else nachgelesen["punkte"] > 0,
                "treffer": sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"]),
                "sender_gelesen": len(scored)}

    async def einblenden(self, text: str, ms: int = 6000) -> str:
        """Text im Fernsehbild zeigen. Ueber die TV-App, wenn sie den Auftrag annimmt, sonst als
        Android-Benachrichtigung (ob Google TV die sichtbar einblendet, ist geraeteabhaengig).
        -> "app" / "benachrichtigung"."""
        app = await self.sh(f"cmd package query-receivers --brief -a {EINBLENDEN_ACTION}")
        if "EinblendungEmpfaenger" in app:
            await self.sh(f"am broadcast -a {EINBLENDEN_ACTION} -n {EINBLENDEN_EMPFAENGER} "
                          f"--es text {shlex.quote(text)} --ei ms {int(ms)}")
            return "app"
        await self.sh(f"cmd notification post -S bigtext -t {shlex.quote('TV-Zapper')} tvzapper {shlex.quote(text)}")
        return "benachrichtigung"

    async def verify(self, cand, cfg):
        """Nach dem Umschalten: Programmzeitschrift oeffnen (startet beim laufenden Sender) und
        die nun aktuelle Sendung samt Beschreibung neu bewerten."""
        await asyncio.sleep(3)
        nodes = await self.open_guide()
        rows, header, _ = self.guide(nodes)
        await self.close_guide()
        if not rows or rows[0][0] != cand["nr"]:
            return None
        num, name, prog = rows[0]
        return bewerte_sendung(num, name, prog, header, cfg)

    async def durchgang(self, cfg, nur_lesen=False) -> dict:
        """Ein Durchgang wie zapper.cycle(). Ergebnis-dict (aktion: uebersprungen/bleibt/umgeschaltet/...).
        Mit TV-App ab 0.3.0 ueber deren Schnittstelle, sonst ueber die Programmzeitschrift."""
        daten = await self.app_abfragen(liste=True)
        if daten is not None and daten.get("liste"):
            if not daten.get("fernsehbild_vorn"):
                return {"aktion": "uebersprungen", "quelle": "app", "app": daten.get("vorn")}
            if daten.get("zapper_laeuft") and not nur_lesen:
                # Zappen beide, schalten sie gegeneinander: dann bewertet nur die TV-App
                x = daten.get("jetzt")
                return {"aktion": "uebersprungen", "quelle": "app", "app": "Zapper der TV-App laeuft",
                        "vorher": app_sendung(x, cfg) if x else None}
            return await self.durchgang_app(daten, cfg, nur_lesen)
        app = await self.focus_app()
        if app not in (TV_APP, GUIDE_APP):
            return {"aktion": "uebersprungen", "app": app}
        try:
            current, chans, infos = await self.collect()
        except Exception:
            await self.aufraeumen()
            raise
        scored, cur, best = bewerte(current, chans, infos, cfg)
        aktion, neu, nachgelesen = "bleibt", None, None
        if soll_umschalten(cur, best) and not nur_lesen:
            # Nur einmal umschalten. Die Beschreibung ist erst nach dem Anwaehlen sicher aktuell -
            # danach nur nachlesen, nicht weiter herumschalten (naechster Durchgang entscheidet neu).
            await self.tune(best["nr"])
            aktion, neu = "umgeschaltet", best
            nachgelesen = await self.verify(best, cfg)
            if nachgelesen is not None:
                neu = nachgelesen
        return {"aktion": aktion, "vorher": cur, "bester": best, "neu": neu,
                "passt_nach_umschalten": None if nachgelesen is None else nachgelesen["punkte"] > 0,
                "treffer": sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"]),
                "sender_gelesen": len(chans)}
