"""Schalter "TV-Zapper": an = fuer die eingestellte Laufzeit zappen, dann geht er von selbst aus."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ZapperSchalter(entry.runtime_data)])


class ZapperSchalter(ZapperEntity, SwitchEntity):
    def __init__(self, st):
        super().__init__(st, "aktiv", "Zapper", "mdi:television-shimmer")

    @property
    def is_on(self):
        return self.st.laeuft

    @property
    def extra_state_attributes(self):
        return {"laeuft_bis": self.st.ende.isoformat(timespec="minutes") if self.st.ende else None,
                "liest_gerade": self.st.beschaeftigt}

    async def async_turn_on(self, **kwargs):
        await self.st.starten()

    async def async_turn_off(self, **kwargs):
        await self.st.stoppen()
