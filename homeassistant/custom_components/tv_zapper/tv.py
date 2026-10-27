"""Fernseher per adb-shell bedienen (ohne Home Assistant): Ablauf 1:1 aus zapper.py.

Statt des adb-Programms spricht die Integration selbst ADB ueber TCP (Bibliothek adb-shell,
dieselbe wie in der eingebauten Integration "Android Debug Bridge") mit eigenem Schluessel.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

from .logik import bewerte, bewerte_sendung, kandidaten, parse_guide, parse_xml

_LOGGER = logging.getLogger(__name__)

TV_APP = "com.tcl.tv/com.tcl.player.TVActivity"
GUIDE_APP = "com.tcl.tv/com.tcl.tv.epg.EpgProActivity"


def lade_signer(pfad: str) -> PythonRSASigner:
    """Schluessel laden, beim ersten Mal anlegen (blockierend, im Executor aufrufen)."""
    if not os.path.isfile(pfad):
        os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
        keygen(pfad)
    with open(pfad, encoding="utf-8") as f:
        priv = f.read()
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
        self.dev = AdbDeviceTcpAsync(self.host, self.port, default_transport_timeout_s=9.0)
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
            if rows:
                return nodes
        return await self.dump()

    async def ensure_fav_tab(self, nodes):
        _, _, tab = self.guide(nodes)
        if tab == self.fav_tab:
            return True
        await self.key("KEYCODE_DPAD_LEFT")
        await asyncio.sleep(0.8)
        for _ in range(8):
            f = [n.get("content-desc") for n in await self.dump() if n.get("focused") == "true"]
            if self.fav_tab in f:
                await self.key("KEYCODE_DPAD_CENTER")
                await asyncio.sleep(1.5)
                await self.key("KEYCODE_DPAD_RIGHT")
                await asyncio.sleep(1)
                return True
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
            _LOGGER.warning("%s nicht gefunden - lese die aktuelle Liste", self.fav_tab)
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
        await self.key(*["KEYCODE_DPAD_UP"] * 120)          # an den Anfang der Liste
        await asyncio.sleep(1.5)
        take(await self.dump())
        idle = 0
        for _ in range(200):
            n = take(await self.dump("KEYCODE_DPAD_DOWN", 0.35))
            idle = idle + 1 if n == 0 else 0
            if idle >= 15:
                break
        await self.key("KEYCODE_BACK")
        await asyncio.sleep(1.2)
        return current, chans, infos

    async def tune(self, num):
        if await self.focus_app() != TV_APP:
            await self.key("KEYCODE_BACK")
            await asyncio.sleep(1)
        for d in str(num):                      # Ziffern einzeln, sonst wird die erste verschluckt
            await self.key(f"KEYCODE_{d}")
            await asyncio.sleep(0.8)
        await self.key("KEYCODE_DPAD_CENTER")
        await asyncio.sleep(4)

    async def verify(self, cand, cfg):
        """Nach dem Umschalten: Programmzeitschrift oeffnen (startet beim laufenden Sender) und
        die nun aktuelle Sendung samt Beschreibung neu bewerten."""
        await asyncio.sleep(3)
        nodes = await self.open_guide()
        rows, header, _ = self.guide(nodes)
        await self.key("KEYCODE_BACK")
        await asyncio.sleep(1.2)
        if not rows or rows[0][0] != cand["nr"]:
            return None
        num, name, prog = rows[0]
        return bewerte_sendung(num, name, prog, header, cfg)

    async def durchgang(self, cfg, nur_lesen=False) -> dict:
        """Ein Durchgang wie zapper.cycle(). Ergebnis-dict (aktion: uebersprungen/bleibt/umgeschaltet/...)."""
        app = await self.focus_app()
        if app not in (TV_APP, GUIDE_APP):
            return {"aktion": "uebersprungen", "app": app}
        current, chans, infos = await self.collect()
        scored, cur, best = bewerte(current, chans, infos, cfg)
        aktion, neu, verworfen = "bleibt", None, []
        if not nur_lesen:
            # Die Beschreibung in der Programmzeitschrift ist erst nach dem Anwaehlen sicher aktuell:
            # nach dem Umschalten neu lesen und notfalls den naechstbesten Treffer nehmen.
            versucht = kandidaten(scored, cur)
            for cand in versucht:
                await self.tune(cand["nr"])
                fresh = await self.verify(cand, cfg)
                if fresh is not None and fresh["punkte"] > 0:
                    aktion, neu = "umgeschaltet", fresh
                    break
                verworfen.append({**cand, "danach": (fresh or {}).get("sendung")})
            if aktion != "umgeschaltet" and versucht:
                await self.tune(current)
                aktion = "bleibt (Treffer passten nach dem Anwaehlen nicht)"
        return {"aktion": aktion, "vorher": cur, "bester": best, "neu": neu, "verworfen": verworfen,
                "treffer": sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"]),
                "sender_gelesen": len(chans)}
