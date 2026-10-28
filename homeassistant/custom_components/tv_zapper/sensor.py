"""Sensor "Aktueller Treffer": was nach dem letzten Durchgang laeuft, mit Punkten und Kategorien."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TrefferSensor(entry.runtime_data), JetztSensor(entry.runtime_data)])


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
        return {
            "sender": x.get("sender"), "nr": x.get("nr"), "sendung": x.get("sendung"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", []), "genre": x.get("genre"),
            "aktion": e.get("aktion"), "zeit": e.get("zeit"), "fehler": e.get("fehler"),
            "app": e.get("app"), "passt_nach_umschalten": e.get("passt_nach_umschalten"), "sender_gelesen": e.get("sender_gelesen"),
            "bester_treffer": _kurz(e.get("bester")),
            "weitere_treffer": [_kurz(t) for t in (e.get("treffer") or [])[:6]],
        }


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
        return {
            "sender": x.get("sender"), "nr": x.get("nr"), "sendung": x.get("sendung"), "folge": x.get("folge"),
            "beschreibung": x.get("beschreibung"), "start": x.get("start"), "ende": x.get("ende"),
            "punkte": x.get("punkte"), "kategorien": x.get("treffer", []), "werbung": j.get("werbung"),
            "zapper_der_tv_app": j.get("zapper_app"), "werbung_umgehen": j.get("werbung_umgehen"),
            "ausweichen_bevorzugt": j.get("ausweichen_bevorzugt"), "vorn": j.get("vorn"), "quelle": j.get("quelle"),
        }
