"""TV-Zapper: liest die Programmzeitschrift des TCL-Fernsehers per ADB und schaltet auf Sendungen,
die zu den eingestellten Interessen passen. Home-Assistant-Fassung von zapper.py."""
from __future__ import annotations

import asyncio
import datetime
import logging
import time
from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUS, CONF_FAVORIT, CONF_INTERESSEN, CONF_LAUFZEIT, CONF_NUR_LESEN, CONF_SENDER_BEVORZUGT,
    CONF_SENDER_NIE, CONF_VERWEILEN,
    DOMAIN, EVENT_DURCHGANG, PLATFORMS, SCHLUESSEL_DATEI, STANDARD_OPTIONEN,
)
from .tv import Fernseher, lade_signer

_LOGGER = logging.getLogger(__name__)

type ZapperEntry = ConfigEntry[Steuerung]


async def async_setup_entry(hass: HomeAssistant, entry: ZapperEntry) -> bool:
    signer = await hass.async_add_executor_job(lade_signer, hass.config.path(SCHLUESSEL_DATEI))
    entry.runtime_data = Steuerung(hass, entry, signer)
    entry.async_on_unload(entry.add_update_listener(_optionen_geaendert))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZapperEntry) -> bool:
    await entry.runtime_data.stoppen()
    await entry.runtime_data.tv.trennen()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _optionen_geaendert(hass: HomeAssistant, entry: ZapperEntry) -> None:
    # Kein Neuladen: ein laufender Zapper soll weiterlaufen und liest die Optionen je Durchgang neu.
    entry.runtime_data.tv.fav_tab = entry.runtime_data.opt(CONF_FAVORIT)
    entry.runtime_data.benachrichtigen()


class Steuerung:
    """Haelt den Zustand fuer die Entitaeten und fuehrt die Zapp-Schleife aus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, signer):
        self.hass, self.entry = hass, entry
        self.tv = Fernseher(entry.data[CONF_HOST], entry.data[CONF_PORT], signer, self.opt(CONF_FAVORIT))
        self.task: asyncio.Task | None = None
        self.start: float | None = None          # time.monotonic() beim Einschalten
        self.ende = None                          # datetime, nur zur Anzeige
        self.letztes: dict | None = None          # Ergebnis des letzten Durchgangs
        self.beschaeftigt = False
        self._lock = asyncio.Lock()
        self._zuhoerer: list[Callable[[], None]] = []

    # --- Optionen und Benachrichtigung ----------------------------------------------------
    def opt(self, name):
        return self.entry.options.get(name, STANDARD_OPTIONEN[name])

    def cfg(self) -> dict:
        return {"interessen": self.opt(CONF_INTERESSEN), "aus": self.opt(CONF_AUS),
                "sender_nie": self.opt(CONF_SENDER_NIE), "sender_bevorzugt": self.opt(CONF_SENDER_BEVORZUGT)}

    def setze_option(self, name, wert):
        self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, name: wert})

    @callback
    def hinzufuegen(self, fn: Callable[[], None]) -> Callable[[], None]:
        self._zuhoerer.append(fn)
        return lambda: self._zuhoerer.remove(fn)

    @callback
    def benachrichtigen(self):
        for fn in list(self._zuhoerer):
            fn()

    @property
    def laeuft(self) -> bool:
        return self.task is not None and not self.task.done()

    # --- Ein/Aus --------------------------------------------------------------------------
    async def starten(self):
        if self.laeuft:
            return
        self.start = time.monotonic()
        self.ende = dt_util.now() + datetime.timedelta(minutes=self.opt(CONF_LAUFZEIT))
        self.task = self.entry.async_create_background_task(self.hass, self._schleife(), "tv_zapper_schleife")
        self.benachrichtigen()

    async def stoppen(self):
        if self.laeuft:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    def _restzeit_s(self) -> float:
        return self.start + self.opt(CONF_LAUFZEIT) * 60 - time.monotonic()

    async def _schleife(self):
        fails = 0
        try:
            while True:
                ergebnis = await self.durchgang(self.opt(CONF_NUR_LESEN))
                fails = fails + 1 if ergebnis["aktion"] == "fehler" else 0
                if fails >= 3:
                    _LOGGER.warning("Dreimal hintereinander fehlgeschlagen - TV-Zapper aus")
                    break
                takt = self.opt(CONF_VERWEILEN) * 60
                if self._restzeit_s() < takt:
                    break
                await asyncio.sleep(takt)
        finally:
            self.task = None
            self.start = self.ende = None
            await self.tv.trennen()
            self.benachrichtigen()

    # --- Ein Durchgang ----------------------------------------------------------------------
    async def durchgang(self, nur_lesen: bool) -> dict:
        async with self._lock:
            self.beschaeftigt = True
            self.benachrichtigen()
            try:
                ergebnis = await self.tv.durchgang(self.cfg(), nur_lesen)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - jeder Fehler zaehlt als Fehlversuch
                _LOGGER.warning("Durchgang fehlgeschlagen: %s", e)
                ergebnis = {"aktion": "fehler", "fehler": str(e) or type(e).__name__}
                await self.tv.trennen()
            finally:
                self.beschaeftigt = False
            ergebnis["zeit"] = dt_util.now().isoformat(timespec="seconds")
            if not self.laeuft:
                await self.tv.trennen()   # Verbindung nicht halten, wenn nur einmal geprueft wurde
            self.letztes = ergebnis
            _LOGGER.info("Durchgang: %s", {k: ergebnis.get(k) for k in ("aktion", "vorher", "neu", "fehler")})
            self.hass.bus.async_fire(EVENT_DURCHGANG, ergebnis)
            self.benachrichtigen()
            return ergebnis
