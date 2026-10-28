"""Gemeinsame Basis: ein Geraet "TV-Zapper", Entitaeten aktualisieren sich bei jeder Aenderung."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import Steuerung
from .const import DOMAIN


class ZapperEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, st: Steuerung, schluessel: str, name: str, icon: str):
        self.st = st
        self._attr_unique_id = f"{st.entry.entry_id}_{schluessel}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, st.entry.entry_id)},
            name="TV-Zapper",
            manufacturer="tv-zapper",
            # KOMPAT: Nur eine Beschriftung, kein Einfluss auf die Funktion; bei anderen Geraeten steht trotzdem TCL da.
            model=f"TCL-Fernseher {st.tv.host}",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(self.st.hinzufuegen(self.async_write_ha_state))
