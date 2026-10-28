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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUS, CONF_FAVORIT, CONF_INTERESSEN, CONF_LAUFZEIT, CONF_NUR_LESEN, CONF_SENDER_BEVORZUGT,
    CONF_EINBLENDUNG, CONF_MAC, CONF_PROTOKOLL, CONF_SENDER_NIE, CONF_SPEICHER_TAKT, CONF_TAKT, CONF_VERWEILEN,
    DOMAIN, EVENT_DURCHGANG, EVENT_UMGESCHALTET, PLATFORMS, SCHLUESSEL_DATEI, STANDARD_OPTIONEN,
)
from .logik import app_umschalt_text, umschalt_text
from .tv import Fernseher, lade_signer

_LOGGER = logging.getLogger(__name__)
MAX_TEXT_LOGBUCH = 1000   # Zeichen je Text im Logbuch-Ereignis

type ZapperEntry = ConfigEntry[Steuerung]


async def async_setup_entry(hass: HomeAssistant, entry: ZapperEntry) -> bool:
    signer = await hass.async_add_executor_job(lade_signer, hass.config.path(SCHLUESSEL_DATEI))
    entry.runtime_data = Steuerung(hass, entry, signer)
    entry.async_on_unload(entry.add_update_listener(_optionen_geaendert))
    entry.runtime_data.takt_starten()
    entry.async_on_unload(entry.runtime_data.takt_stoppen)
    if entry.runtime_data.opt(CONF_SPEICHER_TAKT):   # gleich einmal, nicht erst nach dem ersten Takt
        entry.async_create_background_task(hass, entry.runtime_data.speicher_lesen(), "tv_zapper_speicher_start")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZapperEntry) -> bool:
    await entry.runtime_data.stoppen()
    await entry.runtime_data.tv.trennen()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _optionen_geaendert(hass: HomeAssistant, entry: ZapperEntry) -> None:
    # Kein Neuladen: ein laufender Zapper soll weiterlaufen und liest die Optionen je Durchgang neu.
    entry.runtime_data.tv.fav_tab = entry.runtime_data.opt(CONF_FAVORIT)
    entry.runtime_data.takt_starten()
    entry.runtime_data.benachrichtigen()


def meldung_umgeschaltet(x: dict) -> str:
    """Wie die Einblendung der TV-App: `Sender – Sendung  (Kategorien, 7 P.)`."""
    was = ", ".join(x.get("treffer") or [])
    return f"{x.get('sender')}" + (f" – {x['sendung']}" if x.get("sendung") else "") + \
        f"  ({was + ', ' if was else ''}{x.get('punkte')} P.)"


class Steuerung:
    """Haelt den Zustand fuer die Entitaeten und fuehrt die Zapp-Schleife aus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, signer):
        self.hass, self.entry = hass, entry
        self.tv = Fernseher(entry.data[CONF_HOST], entry.data[CONF_PORT], signer, self.opt(CONF_FAVORIT))
        self.task: asyncio.Task | None = None
        self.start: float | None = None          # time.monotonic() beim Einschalten
        self.ende = None                          # datetime, nur zur Anzeige
        self.letztes: dict | None = None          # Ergebnis des letzten Durchgangs
        self.jetzt: dict | None = None            # was gerade laeuft (Sensor "Laeuft jetzt")
        self.speicher: dict | None = None         # Arbeitsspeicher von Fernseher und TV-App
        self._app_letzte_id = None                # hoechste schon gesehene Umschaltung der TV-App
        self.beschaeftigt = False
        self._lock = asyncio.Lock()
        self._zuhoerer: list[Callable[[], None]] = []
        self._takte: dict[str, tuple[int, Callable[[], None]]] = {}   # name -> (Sekunden, Abmelden)

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

    @callback
    def takt_starten(self):
        """Nachfragen "Was laeuft?" und "Wie viel Speicher?" im eingestellten Takt (neu nur bei geaendertem Takt)."""
        self._takt_setzen("jetzt", int(self.opt(CONF_TAKT)), self.jetzt_lesen)
        self._takt_setzen("speicher", int(self.opt(CONF_SPEICHER_TAKT)) * 60, self.speicher_lesen)

    @callback
    def _takt_setzen(self, name, sekunden, fn):
        alt = self._takte.get(name)
        if alt and alt[0] == sekunden:
            return
        if alt:
            alt[1]()
            del self._takte[name]
        if sekunden > 0:
            self._takte[name] = (sekunden, async_track_time_interval(
                self.hass, fn, datetime.timedelta(seconds=sekunden), name=f"tv_zapper_{name}"))

    @callback
    def takt_stoppen(self):
        for _, abmelden in self._takte.values():
            abmelden()
        self._takte = {}

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
            await self.einblenden("TV-Zapper aus")
        self.task = None

    def _restzeit_s(self) -> float:
        return self.start + self.opt(CONF_LAUFZEIT) * 60 - time.monotonic()

    async def einblenden(self, text: str, ms: int = 6000):
        """Meldung im Fernsehbild (Option "Einblendung"); Fehler dabei stoeren das Zappen nicht."""
        if not self.opt(CONF_EINBLENDUNG):
            return
        async with self._lock:
            try:
                weg = await self.tv.einblenden(text, ms)
                _LOGGER.debug("Einblendung (%s): %s", weg, text)
            except Exception as e:  # noqa: BLE001
                _LOGGER.info("Einblendung nicht moeglich: %s", e)
                await self.tv.trennen()

    async def jetzt_lesen(self, _now=None):
        """Im Takt der Optionen (Standard 15 s): was laeuft gerade. Nur wenn kein Durchgang den Fernseher bedient (sonst beim naechsten Mal)."""
        if not self.opt(CONF_PROTOKOLL) or self._lock.locked():
            return
        async with self._lock:
            try:
                await self.tv.verbinden(timeout=5)
                self.jetzt = await self.tv.jetzt(self.cfg())
                self._app_umschaltungen_melden(self.jetzt.get("umschaltungen") or [])
            except Exception as e:  # noqa: BLE001 - aus oder nicht erreichbar
                _LOGGER.debug("Fernseher nicht erreichbar: %s", e)
                self.jetzt = {"aus": True}
                await self.tv.trennen()
            if not self.laeuft:
                await self.tv.trennen()
        self.benachrichtigen()

    @callback
    def _umgeschaltet_melden(self, daten: dict):
        """Ereignis fuers Logbuch, verknuepft mit dem Geraet "TV-Zapper" und dem Sensor "Laeuft jetzt" - so steht es
        auch im Logbuch der Geraeteseite und im Fenster der Kachel, nicht nur auf der Logbuch-Seite."""
        entity_id = er.async_get(self.hass).async_get_entity_id("sensor", DOMAIN, f"{self.entry.entry_id}_jetzt")
        geraet = dr.async_get(self.hass).async_get_device_by_identifier((DOMAIN, self.entry.entry_id), self.entry.entry_id)
        # Texte begrenzen: Namen und Sendungen kommen vom Fernseher bzw. aus den Optionen, das Ereignis landet in der DB
        daten = {k: (v[:MAX_TEXT_LOGBUCH] if isinstance(v, str) else v) for k, v in daten.items()}
        self.hass.bus.async_fire(EVENT_UMGESCHALTET, {
            **daten, **({"entity_id": entity_id} if entity_id else {}), **({"device_id": geraet.id} if geraet else {})})

    @callback
    def _app_umschaltungen_melden(self, liste):
        """Neue Umschaltungen der TV-App ins Logbuch. Beim ersten Lesen nach dem Start nur merken, wo die Liste
        steht (keine alten Eintraege nachtragen)."""
        # nur ganzzahlige ids (Daten vom Fernseher; ein Text als id liesse den Vergleich scheitern)
        liste = [u for u in liste if isinstance(u, dict) and type(u.get("id")) is int]
        ids = [u["id"] for u in liste]
        if not ids:
            return
        if self._app_letzte_id is None:
            self._app_letzte_id = max(ids)
            return
        neue = (u for u in liste if u["id"] > self._app_letzte_id
                and u.get("grund") != "von_aussen")   # von_aussen = UMSCHALTEN von HA, steht schon im Logbuch
        for u in sorted(neue, key=lambda u: u["id"]):
            self._umgeschaltet_melden({
                "wer": "TV-Zapper (TV-App)", "nr": u.get("nr"), "sender": u.get("sender"), "sendung": u.get("sendung"),
                "punkte": u.get("punkte"), "grund": u.get("grund"), "text": app_umschalt_text(u)})
        self._app_letzte_id = max(self._app_letzte_id, *ids)

    async def speicher_lesen(self, _now=None):
        """Im Speicher-Takt: Arbeitsspeicher des Fernsehers und der TV-App (zum Beobachten von Engpaessen)."""
        if self._lock.locked():
            return
        async with self._lock:
            try:
                await self.tv.verbinden(timeout=5)
                self.speicher = await self.tv.speicher()
            except Exception as e:  # noqa: BLE001 - aus oder nicht erreichbar
                _LOGGER.debug("Speicher nicht lesbar: %s", e)
                self.speicher = None
                await self.tv.trennen()
            if not self.laeuft:
                await self.tv.trennen()
        self.benachrichtigen()

    async def app_einstellen(self, name: str, wert: bool):
        """Einstellung der TV-App setzen und gleich nachlesen (Schalter zeigt den Stand der App)."""
        async with self._lock:
            try:
                await self.tv.app_einstellen(name, wert)
            finally:
                if not self.laeuft:
                    await self.tv.trennen()
        await self.jetzt_lesen()

    async def wecken(self):
        """Fernseher vor dem ersten Durchgang wecken (Wake-on-LAN nur mit MAC in den Optionen) und das
        Fernsehbild holen, falls eine andere App vorn ist.
        Klappt es nicht, meldet der erste Durchgang den Fehler."""
        async with self._lock:
            try:
                weg = await self.tv.wecken(self.opt(CONF_MAC))
                bild = await self.tv.fernsehbild_holen()
                _LOGGER.info("Fernseher vor dem Zappen: %s%s", weg, ", Fernsehbild gestartet" if bild else "")
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Fernseher nicht erreichbar: %s", e)
                await self.tv.trennen()

    async def _schleife(self):
        fails = 0
        try:
            await self.wecken()
            await self.einblenden(f"TV-Zapper an – läuft bis {self.ende:%H:%M}")
            while True:
                ergebnis = await self.durchgang(self.opt(CONF_NUR_LESEN))
                if ergebnis["aktion"] == "umgeschaltet" and ergebnis.get("neu"):
                    # Ist "Umschaltgrund einblenden" der TV-App an, zeigt die App den Grund (aus UMSCHALTEN grund)
                    if not (self.jetzt or {}).get("umschaltgrund_einblenden"):
                        await self.einblenden(meldung_umgeschaltet(ergebnis["neu"]))
                fails = fails + 1 if ergebnis["aktion"] == "fehler" else 0
                if fails >= 3:
                    _LOGGER.warning("Dreimal hintereinander fehlgeschlagen - TV-Zapper aus")
                    break
                takt = self.opt(CONF_VERWEILEN) * 60
                if self._restzeit_s() < takt:
                    break
                await asyncio.sleep(takt)
        finally:
            if not asyncio.current_task().cancelling():
                await self.einblenden("TV-Zapper aus")
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
            if ergebnis.get("aktion") == "umgeschaltet" and ergebnis.get("neu"):
                neu = ergebnis["neu"]
                self._umgeschaltet_melden({
                    "wer": "TV-Zapper (HA)", "nr": neu.get("nr"), "sender": neu.get("sender"), "sendung": neu.get("sendung"),
                    "punkte": neu.get("punkte"), "text": umschalt_text(neu, ergebnis.get("vorher"), self.cfg())})
            self.benachrichtigen()
            return ergebnis
