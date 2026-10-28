"""Einrichtung (Fernseher-Adresse) und Optionen (Interessen, Laufzeit, Verweilzeit ...) in der HA-Oberflaeche."""
from __future__ import annotations

import logging
import re

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .const import (
    CONF_AUS, CONF_EINBLENDUNG, CONF_FAVORIT, CONF_MAC, CONF_PROTOKOLL, CONF_SPEICHER_TAKT, CONF_TAKT, CONF_INTERESSEN, CONF_LAUFZEIT, CONF_NUR_LESEN, CONF_SENDER_BEVORZUGT,
    CONF_SENDER_NIE, CONF_VERWEILEN,
    DOMAIN, SCHLUESSEL_DATEI, STANDARD_OPTIONEN,
)
from .logik import (
    MAX_SENDER, MAX_WOERTER, MAX_WORT, bonus_zu_text, interessen_zu_text, pruefe_woerter, text_zu_bonus, text_zu_interessen, woerter_zu_liste)
from .tv import Fernseher, lade_signer, magic_packet

_LOGGER = logging.getLogger(__name__)

TEXT_MEHRZEILIG = selector.TextSelector(selector.TextSelectorConfig(multiline=True))


def _minuten(maximum):
    return selector.NumberSelector(selector.NumberSelectorConfig(
        min=1, max=maximum, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX))


_SEKUNDEN = selector.NumberSelector(selector.NumberSelectorConfig(
    min=5, max=600, step=1, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX))

_SPEICHER_MINUTEN = selector.NumberSelector(selector.NumberSelectorConfig(
    min=0, max=60, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX))


_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))


def _adresse_ok(host: str) -> bool:
    """IPv4, IPv6 oder Rechnername - nur die dafuer noetigen Zeichen, hoechstens 253."""
    return 0 < len(host) <= 253 and re.fullmatch(r"[A-Za-z0-9.:\-\[\]]+", host) is not None


def _favorit_ok(name: str) -> bool:
    return 0 < len(name) <= MAX_WORT and not re.search(r"[\x00-\x1f\x7f]", name)


class TvZapperConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _verbindung_pruefen(self, host, port, errors, platzhalter):
        signer = await self.hass.async_add_executor_job(lade_signer, self.hass.config.path(SCHLUESSEL_DATEI))
        tv = Fernseher(host, port, signer)
        try:
            # 60 s Zeit, um am Fernseher "USB-Debugging zulassen" (immer zulassen) zu bestaetigen
            await tv.verbinden(auth_timeout=60)
            antwort = await tv.sh("echo tvz-ok")
            if "tvz-ok" not in antwort:
                raise RuntimeError(f"unerwartete Antwort: {antwort!r}")
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Verbindung zu %s:%s fehlgeschlagen: %r", host, port, e)
            errors["base"] = "cannot_connect"
            platzhalter["fehler"] = f"{type(e).__name__}: {e}"
        finally:
            await tv.trennen()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors, platzhalter = {}, {"fehler": ""}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), int(user_input[CONF_PORT])
            if not _adresse_ok(host):
                errors[CONF_HOST] = "host_ungueltig"
            if not _favorit_ok(user_input[CONF_FAVORIT].strip()):
                errors[CONF_FAVORIT] = "favorit_ungueltig"
            if not errors:
                # raise_on_progress=False: ein fehlgeschlagener, noch offener Versuch soll keinen neuen blockieren
                await self.async_set_unique_id(f"{host}:{port}", raise_on_progress=False)
                self._abort_if_unique_id_configured()
                await self._verbindung_pruefen(host, port, errors, platzhalter)
            if not errors:
                return self.async_create_entry(
                    title=f"TV-Zapper {host}",
                    data={CONF_HOST: host, CONF_PORT: port},
                    options={**STANDARD_OPTIONEN, CONF_FAVORIT: user_input[CONF_FAVORIT].strip()},
                )
        vorgabe = user_input or {}
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=vorgabe.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=vorgabe.get(CONF_PORT, 5555)): _PORT,
            vol.Required(CONF_FAVORIT, default=vorgabe.get(CONF_FAVORIT, "Favorit1")): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors,
                                    description_placeholders=platzhalter)

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Adresse oder Port spaeter aendern (z. B. neue IP vom Router), ohne neu einzurichten."""
        entry = self._get_reconfigure_entry()
        errors, platzhalter = {}, {"fehler": ""}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), int(user_input[CONF_PORT])
            if not _adresse_ok(host):
                errors[CONF_HOST] = "host_ungueltig"
            else:
                await self._verbindung_pruefen(host, port, errors, platzhalter)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, unique_id=f"{host}:{port}", title=f"TV-Zapper {host}",
                    data_updates={CONF_HOST: host, CONF_PORT: port})
        vorgabe = user_input or entry.data
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=vorgabe.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=vorgabe.get(CONF_PORT, 5555)): _PORT,
        })
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors,
                                    description_placeholders=platzhalter)

    @staticmethod
    def async_get_options_flow(config_entry):
        return TvZapperOptionsFlow()


class TvZapperOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        errors, platzhalter = {}, {"fehler": ""}
        opt = {**STANDARD_OPTIONEN, **self.config_entry.options}
        if user_input is not None:
            try:
                interessen = text_zu_interessen(user_input[CONF_INTERESSEN])
            except ValueError as e:
                errors[CONF_INTERESSEN] = "interessen_ungueltig"
                platzhalter["fehler"] = str(e)
            try:
                bonus = text_zu_bonus(user_input.get(CONF_SENDER_BEVORZUGT, ""))
            except ValueError as e:
                errors[CONF_SENDER_BEVORZUGT] = "bonus_ungueltig"
                platzhalter["fehler"] = str(e)
            aus = woerter_zu_liste(user_input.get(CONF_AUS, ""))
            nie = woerter_zu_liste(user_input.get(CONF_SENDER_NIE, ""))
            for feld, liste, was, hoechstens in ((CONF_AUS, aus, "Wort", MAX_WOERTER),
                                                 (CONF_SENDER_NIE, nie, "Sendername", MAX_SENDER)):
                try:
                    pruefe_woerter(liste, was, hoechstens)
                except ValueError as e:
                    errors[feld] = "woerter_ungueltig"
                    platzhalter["fehler"] = str(e)
            if not _favorit_ok(user_input[CONF_FAVORIT].strip()):
                errors[CONF_FAVORIT] = "favorit_ungueltig"
            mac = user_input.get(CONF_MAC, "").strip()
            if mac:
                try:
                    magic_packet(mac)
                except ValueError as e:
                    errors[CONF_MAC] = "mac_ungueltig"
                    platzhalter["fehler"] = str(e)
            if not errors:
                return self.async_create_entry(data={
                    CONF_FAVORIT: user_input[CONF_FAVORIT].strip(),
                    CONF_LAUFZEIT: int(user_input[CONF_LAUFZEIT]),
                    CONF_VERWEILEN: int(user_input[CONF_VERWEILEN]),
                    CONF_INTERESSEN: interessen,
                    CONF_AUS: aus,
                    CONF_SENDER_NIE: nie,
                    CONF_SENDER_BEVORZUGT: bonus,
                    CONF_NUR_LESEN: user_input[CONF_NUR_LESEN],
                    CONF_EINBLENDUNG: user_input[CONF_EINBLENDUNG],
                    CONF_MAC: mac,
                    CONF_PROTOKOLL: user_input.get(CONF_PROTOKOLL, True),
                    CONF_TAKT: int(user_input.get(CONF_TAKT, STANDARD_OPTIONEN[CONF_TAKT])),
                    CONF_SPEICHER_TAKT: int(user_input.get(CONF_SPEICHER_TAKT, STANDARD_OPTIONEN[CONF_SPEICHER_TAKT])),
                })
        vorgabe = user_input or {
            **opt,
            CONF_INTERESSEN: interessen_zu_text(opt[CONF_INTERESSEN]),
            CONF_AUS: ", ".join(opt[CONF_AUS]),
            CONF_SENDER_NIE: ", ".join(opt[CONF_SENDER_NIE]),
            CONF_SENDER_BEVORZUGT: bonus_zu_text(opt[CONF_SENDER_BEVORZUGT]),
        }
        schema = vol.Schema({
            vol.Required(CONF_INTERESSEN, default=vorgabe[CONF_INTERESSEN]): TEXT_MEHRZEILIG,
            vol.Optional(CONF_AUS, default=vorgabe[CONF_AUS]): TEXT_MEHRZEILIG,
            vol.Optional(CONF_SENDER_NIE, default=vorgabe[CONF_SENDER_NIE]): TEXT_MEHRZEILIG,
            vol.Optional(CONF_SENDER_BEVORZUGT, default=vorgabe[CONF_SENDER_BEVORZUGT]): TEXT_MEHRZEILIG,
            vol.Required(CONF_LAUFZEIT, default=vorgabe[CONF_LAUFZEIT]): _minuten(1440),
            vol.Required(CONF_VERWEILEN, default=vorgabe[CONF_VERWEILEN]): _minuten(120),
            vol.Required(CONF_FAVORIT, default=vorgabe[CONF_FAVORIT]): str,
            vol.Required(CONF_NUR_LESEN, default=vorgabe[CONF_NUR_LESEN]): bool,
            vol.Required(CONF_EINBLENDUNG, default=vorgabe[CONF_EINBLENDUNG]): bool,
            vol.Required(CONF_PROTOKOLL, default=vorgabe.get(CONF_PROTOKOLL, True)): bool,
            vol.Required(CONF_TAKT, default=vorgabe.get(CONF_TAKT, STANDARD_OPTIONEN[CONF_TAKT])): _SEKUNDEN,
            vol.Required(CONF_SPEICHER_TAKT,
                         default=vorgabe.get(CONF_SPEICHER_TAKT, STANDARD_OPTIONEN[CONF_SPEICHER_TAKT])): _SPEICHER_MINUTEN,
            vol.Optional(CONF_MAC, default=vorgabe.get(CONF_MAC, "")): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors,
                                    description_placeholders=platzhalter)
