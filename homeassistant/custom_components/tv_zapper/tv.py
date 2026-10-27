"""Fernseher per adb-shell bedienen (ohne Home Assistant): Ablauf 1:1 aus zapper.py.

Statt des adb-Programms spricht die Integration selbst ADB ueber TCP (Bibliothek adb-shell,
dieselbe wie in der eingebauten Integration "Android Debug Bridge") mit eigenem Schluessel.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex

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


class Fernseher:
    def __init__(self, host: str, port: int, signer: PythonRSASigner, fav_tab: str = "Favorit1"):
        self.host, self.port, self.signer, self.fav_tab = host, port, signer, fav_tab
        self.dev: AdbDeviceTcpAsync | None = None

    # --- Verbindung -------------------------------------------------------------------
    async def verbinden(self, auth_timeout: float = 10.0):
        if self.dev and self.dev.available:
            return
        self.dev = AdbDeviceTcpAsync(self.host, self.port, default_transport_timeout_s=30.0)  # uiautomator dump braucht manchmal >9 s
        # auth_timeout: so lange wird auf "USB-Debugging zulassen?" am Fernseher gewartet
        await self.dev.connect(rsa_keys=[self.signer], auth_timeout_s=auth_timeout)

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
        """Ein Durchgang wie zapper.cycle(). Ergebnis-dict (aktion: uebersprungen/bleibt/umgeschaltet/...)."""
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
