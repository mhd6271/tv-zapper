"""Logbuch: jede Umschaltung durch einen TV-Zapper mit ausgeschriebenem Grund."""
from __future__ import annotations

from homeassistant.core import callback

from .const import DOMAIN, EVENT_UMGESCHALTET


@callback
def async_describe_events(hass, async_describe_event):
    @callback
    def beschreiben(event):
        d = event.data
        aus = {"name": d.get("wer") or "TV-Zapper", "message": d.get("text") or f"hat auf {d.get('nr')} umgeschaltet"}
        if d.get("entity_id"):
            aus["entity_id"] = d["entity_id"]   # Sensor "Laeuft jetzt": Eintrag auch im Fenster der Kachel
        return aus

    async_describe_event(DOMAIN, EVENT_UMGESCHALTET, beschreiben)
