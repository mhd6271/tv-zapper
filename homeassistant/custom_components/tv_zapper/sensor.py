"""Sensor "Aktueller Treffer": was nach dem letzten Durchgang laeuft, mit Punkten und Kategorien."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TrefferSensor(entry.runtime_data)])


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
        if e["aktion"] == "uebersprungen":
            return "Fernseher zeigt etwas anderes"
        x = self._laeuft()
        text = f"{x.get('nr')} {x.get('sender') or ''}: {x.get('sendung') or '?'}"
        return text[:255]

    @property
    def extra_state_attributes(self):
        e = self.st.letztes or {}
        x = self._laeuft() or {}
        return {
            "sender": x.get("sender"), "nr": x.get("nr"), "sendung": x.get("sendung"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", []), "genre": x.get("genre"),
            "aktion": e.get("aktion"), "zeit": e.get("zeit"), "fehler": e.get("fehler"),
            "app": e.get("app"), "passt_nach_umschalten": e.get("passt_nach_umschalten"), "sender_gelesen": e.get("sender_gelesen"),
            "bester_treffer": _kurz(e.get("bester")),
            "weitere_treffer": [_kurz(t) for t in (e.get("treffer") or [])[:6]],
        }
