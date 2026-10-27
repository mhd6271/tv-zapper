"""Zahlen "Laufzeit" und "Verweilzeit": aendern die Optionen, wirken auch auf einen laufenden Zapper."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .const import CONF_LAUFZEIT, CONF_VERWEILEN
from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    st = entry.runtime_data
    async_add_entities([
        MinutenZahl(st, CONF_LAUFZEIT, "Laufzeit", "mdi:timer-outline", 1440),
        MinutenZahl(st, CONF_VERWEILEN, "Verweilzeit", "mdi:timer-sand", 120),
    ])


class MinutenZahl(ZapperEntity, NumberEntity):
    _attr_native_min_value = 1
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, st, option, name, icon, maximum):
        super().__init__(st, option, name, icon)
        self.option = option
        self._attr_native_max_value = maximum

    @property
    def native_value(self):
        return self.st.opt(self.option)

    async def async_set_native_value(self, value):
        self.st.setze_option(self.option, int(value))
