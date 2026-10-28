"""Sensoren: "Aktueller Treffer" (letzter Durchgang), "Laeuft jetzt" (TV-Protokoll) und der Arbeitsspeicher
von Fernseher und TV-App (Diagnose)."""
from __future__ import annotations

import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.util import dt as dt_util

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    st = entry.runtime_data
    async_add_entities([TrefferSensor(st), JetztSensor(st), SpeicherFreiSensor(st), AppSpeicherSensor(st),
                        AppBeendetSensor(st)])


MAX_ATTR_TEXT = 1000   # Zeichen je Text-Attribut (Beschreibungen kommen vom Fernseher und landen in der DB)


def _kurz_texte(attr: dict) -> dict:
    return {k: (v[:MAX_ATTR_TEXT] if isinstance(v, str) else v) for k, v in attr.items()}


def _kurz(x):
    if not x:
        return None
    return {"nr": x.get("nr"), "sender": x.get("sender"), "sendung": x.get("sendung"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", [])}


class TrefferSensor(ZapperEntity, SensorEntity):
    def __init__(self, st):
        super().__init__(st, "treffer", "Aktueller Treffer", "mdi:television-guide")

    def _laeuft(self):
        e = self.st.letztes or {}
        return e.get("neu") or e.get("vorher")

    @property
    def native_value(self):
        e = self.st.letztes
        if not e:
            return None
        if e["aktion"] == "fehler":
            return "Fehler"
        x = self._laeuft()
        if e["aktion"] == "uebersprungen" and not x:
            return "TV-App zappt gerade" if "TV-App" in (e.get("app") or "") else "Fernseher zeigt etwas anderes"
        text = f"{x.get('nr')} {x.get('sender') or ''}: {x.get('sendung') or '?'}"
        return text[:255]

    @property
    def extra_state_attributes(self):
        e = self.st.letztes or {}
        x = self._laeuft() or {}
        return _kurz_texte({
            "sender": x.get("sender"), "nr": x.get("nr"), "sendung": x.get("sendung"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", []), "genre": x.get("genre"),
            "aktion": e.get("aktion"), "zeit": e.get("zeit"), "fehler": e.get("fehler"),
            "app": e.get("app"), "passt_nach_umschalten": e.get("passt_nach_umschalten"), "sender_gelesen": e.get("sender_gelesen"),
            "bester_treffer": _kurz(e.get("bester")),
            "weitere_treffer": [_kurz(t) for t in (e.get("treffer") or [])[:6]],
        })


class JetztSensor(ZapperEntity, SensorEntity):
    """Was gerade laeuft, im Abfragetakt nachgefragt - auch ohne Zapper. Der Verlauf in HA ist das TV-Protokoll."""

    def __init__(self, st):
        super().__init__(st, "jetzt", "Läuft jetzt", "mdi:television-classic")

    @property
    def native_value(self):
        j = self.st.jetzt
        if not j:
            return None
        if j.get("aus") or j.get("bildschirm_an") is False:
            return "Fernseher aus"
        x = j.get("jetzt")
        if x:
            return f"{x.get('nr')} {x.get('sender') or ''}: {x.get('sendung') or '?'}"[:255]
        if j.get("fernsehbild_vorn"):
            return "Fernsehbild"   # ohne TV-App ist der Sender nicht ohne Tastendruck lesbar
        return f"Andere App: {j.get('vorn') or '?'}"[:255]

    @property
    def extra_state_attributes(self):
        j = self.st.jetzt or {}
        x = j.get("jetzt") or {}
        return _kurz_texte({
            "sender": x.get("sender"), "nr": x.get("nr"), "sendung": x.get("sendung"), "folge": x.get("folge"),
            "beschreibung": x.get("beschreibung"), "start": x.get("start"), "ende": x.get("ende"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", []), "werbung": j.get("werbung"),
            "zapper_der_tv_app": j.get("zapper_app"), "werbung_umgehen": j.get("werbung_umgehen"),
            "ausweichen_bevorzugt": j.get("ausweichen_bevorzugt"), "vorn": j.get("vorn"), "quelle": j.get("quelle"),
        })


class _SpeicherSensor(ZapperEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def _sp(self) -> dict:
        return self.st.speicher or {}


class SpeicherFreiSensor(_SpeicherSensor):
    """Verfuegbarer Arbeitsspeicher des Fernsehers (MemAvailable). Faellt er stark, beendet Android Apps."""
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES

    def __init__(self, st):
        super().__init__(st, "speicher_frei", "Arbeitsspeicher verfügbar", "mdi:memory")

    @property
    def native_value(self):
        return self._sp.get("verfuegbar_mb")

    @property
    def extra_state_attributes(self):
        return {k: self._sp.get(k) for k in ("gesamt_mb", "swap_gesamt_mb", "swap_belegt_mb")}


class AppSpeicherSensor(_SpeicherSensor):
    """Speicher der TV-App (PSS). Waechst er ueber Tage, deutet das auf ein Leck."""
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES

    def __init__(self, st):
        super().__init__(st, "speicher_app", "Speicher TV-App", "mdi:application-cog")

    @property
    def native_value(self):
        return self._sp.get("app_mb")   # None (unbekannt), wenn die TV-App gerade nicht laeuft


def _ortszeit(text: str | None) -> datetime.datetime | None:
    """`2026-10-28 05:24:44.789` (Ortszeit des Fernsehers) -> datetime mit der Zeitzone von HA."""
    if not text:
        return None
    try:
        # KOMPAT: Annahme: Fernseher und HA haben dieselbe Zeitzone (exit-info liefert Ortszeit ohne Zone).
        # Sonst ist der Sensor um den Unterschied verschoben.
        return datetime.datetime.fromisoformat(text).replace(tzinfo=dt_util.get_default_time_zone())
    except ValueError:
        return None


class AppBeendetSensor(_SpeicherSensor):
    """Wann Android die TV-App zuletzt wegen Speichermangel beendet hat, waehrend sie etwas tat (Zapper,
    Werbe-Sensor). Das Ende eines nur zwischengespeicherten Prozesses zaehlt nicht."""
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, st):
        super().__init__(st, "app_beendet", "TV-App vom System beendet", "mdi:skull-crossbones-outline")

    @property
    def native_value(self):
        return _ortszeit((self._sp.get("app_beendet") or {}).get("zeit"))

    @property
    def extra_state_attributes(self):
        e = self._sp.get("app_beendet") or {}
        z = self._sp.get("app_beendet_irgendwie") or {}
        return {
            "speicher_mb_beim_beenden": e.get("speicher_mb"), "wichtigkeit": e.get("wichtigkeit"),
            "zuletzt_beendet": z.get("zeit"), "zuletzt_grund": z.get("grund"),
            "wegen_speicher_beendet_anzahl": self._sp.get("app_beendet_speicher_anzahl"),
        }
