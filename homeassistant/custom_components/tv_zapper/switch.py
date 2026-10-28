"""Schalter "TV-Zapper": an = fuer die eingestellte Laufzeit zappen, dann geht er von selbst aus."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .entity import ZapperEntity


async def async_setup_entry(hass, entry, async_add_entities):
    st = entry.runtime_data
    async_add_entities([ZapperSchalter(st), AusweichenSchalter(st), GrundSchalter(st)])


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


class AppEinstellungSchalter(ZapperEntity, SwitchEntity):
    """Eine Einstellung der TV-App, gesetzt ueber EINSTELLEN und gelesen ueber ABFRAGEN; nicht verfuegbar,
    solange die App sie nicht meldet (aeltere Version, Fernseher aus)."""

    def __init__(self, st, schluessel, name, icon):
        super().__init__(st, schluessel, name, icon)
        self._schluessel = schluessel

    @property
    def available(self):
        return (self.st.jetzt or {}).get(self._schluessel) is not None

    @property
    def is_on(self):
        return bool((self.st.jetzt or {}).get(self._schluessel))

    async def async_turn_on(self, **kwargs):
        await self.st.app_einstellen(self._schluessel, True)

    async def async_turn_off(self, **kwargs):
        await self.st.app_einstellen(self._schluessel, False)


def AusweichenSchalter(st):  # noqa: N802
    """Bei Werbung zuerst auf einen bevorzugten Sender ausweichen. HA weicht selbst nicht aus."""
    return AppEinstellungSchalter(st, "ausweichen_bevorzugt", "Bei Werbung zuerst bevorzugte Sender", "mdi:star-circle")


def GrundSchalter(st):  # noqa: N802
    """Zum Nachvollziehen: bei jeder Umschaltung den Grund mit Punkten im Fernsehbild einblenden (Standard aus)."""
    return AppEinstellungSchalter(st, "umschaltgrund_einblenden", "Umschaltgrund einblenden", "mdi:message-text-outline")
