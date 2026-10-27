"""Knopf "Jetzt pruefen (nur lesen)": ein Durchgang ohne Umschalten, zum Ausprobieren."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PruefKnopf(entry.runtime_data)])


class PruefKnopf(ZapperEntity, ButtonEntity):
    def __init__(self, st):
        super().__init__(st, "pruefen", "Jetzt prüfen (nur lesen)", "mdi:magnify")

    async def async_press(self):
        await self.st.durchgang(nur_lesen=True)
