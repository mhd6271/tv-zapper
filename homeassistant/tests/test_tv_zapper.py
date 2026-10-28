import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import custom_components.tv_zapper.tv  # noqa: F401  (fuer patch)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "tv_zapper"

ERGEBNIS = {"aktion": "bleibt", "vorher": {"nr": 23, "sender": "ProSieben HD", "sendung": "Hip Hop Doku", "punkte": 7,
            "treffer": ["Hip-Hop/Rap", "Dokumentation"], "genre": ""},
            "bester": {"nr": 23, "sender": "ProSieben HD", "sendung": "Hip Hop Doku", "punkte": 7, "treffer": ["Hip-Hop/Rap", "Dokumentation"]},
            "neu": None, "treffer": [], "sender_gelesen": 18}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _einrichten(hass):
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.sh", AsyncMock(return_value="tvz-ok\n")):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert r["type"] is FlowResultType.FORM
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "192.0.2.61", "port": 5555, "favorit": "Favorit1"})
        assert r["type"] is FlowResultType.CREATE_ENTRY, r
        await hass.async_block_till_done()
    return r["result"]


async def test_alles(hass: HomeAssistant):
    entry = await _einrichten(hass)
    ids = sorted(hass.states.async_entity_ids())
    print(ids)
    assert "switch.tv_zapper_zapper" in ids and "sensor.tv_zapper_aktueller_treffer" in ids
    assert hass.states.get("number.tv_zapper_verweilzeit").state == "5"

    # Fehler bei Verbindung
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock(side_effect=OSError("weg"))):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "1.2.3.4", "port": 5555, "favorit": "Favorit1"})
        assert r["errors"] == {"base": "cannot_connect"}

    # Optionen
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] is FlowResultType.FORM
    r2 = await hass.config_entries.options.async_configure(r["flow_id"], {
        "interessen": "Kaputt | x | a", "aus": "", "laufzeit_min": 30, "verweilen_min": 3, "favorit": "Favorit1", "nur_lesen": True})
    assert r2["errors"] == {"interessen": "interessen_ungueltig"}
    r2 = await hass.config_entries.options.async_configure(r2["flow_id"], {
        "interessen": "Doku | 2 | doku*", "laufzeit_min": 30, "verweilen_min": 3, "favorit": "Favorit1", "nur_lesen": True,
        "mac": "aa:bb:cc"})
    assert r2["errors"] == {"mac": "mac_ungueltig"}
    r3 = await hass.config_entries.options.async_configure(r2["flow_id"], {
        "interessen": "Hip-Hop | 5 | rap, hip hop\nDoku | 2 | doku*", "aus": "teleshopping, dauerwerbesendung",
        "laufzeit_min": 30, "verweilen_min": 3, "favorit": "Favorit1", "nur_lesen": True, "mac": "AA:BB:CC:DD:EE:FF"})
    assert r3["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["interessen"][1] == {"name": "Doku", "gewicht": 2, "woerter": ["doku*"]}
    assert entry.options["mac"] == "AA:BB:CC:DD:EE:FF"
    assert entry.options["takt_s"] == 15   # Standard, wenn das Feld nicht ausgefuellt wird
    assert hass.states.get("number.tv_zapper_verweilzeit").state == "3"

    # Zahl aendern
    await hass.services.async_call("number", "set_value", {"entity_id": "number.tv_zapper_laufzeit", "value": 45}, blocking=True)
    assert entry.options["laufzeit_min"] == 45

    # Knopf: nur lesen
    dg = AsyncMock(return_value=dict(ERGEBNIS))
    eb = AsyncMock(return_value="app")
    with patch("custom_components.tv_zapper.tv.Fernseher.durchgang", dg), \
         patch("custom_components.tv_zapper.tv.Fernseher.einblenden", eb), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.wecken", AsyncMock(return_value="wach")) as wk, \
         patch("custom_components.tv_zapper.tv.Fernseher.fernsehbild_holen", AsyncMock(return_value=True)) as fh:
        await hass.services.async_call("button", "press", {"entity_id": "button.tv_zapper_jetzt_prufen_nur_lesen"}, blocking=True)
        assert dg.call_args.args[1] is True
        s = hass.states.get("sensor.tv_zapper_aktueller_treffer")
        print(s.state, s.attributes)
        assert s.state == "23 ProSieben HD: Hip Hop Doku" and s.attributes["punkte"] == 7

        # Schalter: laeuft, dann aus
        await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tv_zapper_zapper"}, blocking=True)
        await asyncio.sleep(0.05)
        assert hass.states.get("switch.tv_zapper_zapper").state == "on"
        assert dg.call_count == 2
        assert dg.call_args.args[0]["interessen"][0]["name"] == "Hip-Hop"
        await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.tv_zapper_zapper"}, blocking=True)
        await hass.async_block_till_done()
        assert hass.states.get("switch.tv_zapper_zapper").state == "off"
        texte = [c.args[0] for c in eb.call_args_list]
        assert texte[0].startswith("TV-Zapper an – läuft bis ") and texte[-1] == "TV-Zapper aus", texte
        assert wk.call_count == 1   # nur beim Einschalten wecken, nicht je Durchgang
        assert fh.call_count == 1   # Fernsehbild auch nur beim Einschalten holen

    # Fehler dreimal -> geht aus
    entry.runtime_data.entry.options  # noqa
    hass.config_entries.async_update_entry(entry, options={**entry.options, "verweilen_min": 1, "laufzeit_min": 60})
    with patch("custom_components.tv_zapper.tv.Fernseher.durchgang", AsyncMock(side_effect=OSError("kein TV"))), \
         patch("custom_components.tv_zapper.tv.Fernseher.einblenden", AsyncMock(side_effect=OSError("kein TV"))), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.wecken", AsyncMock(side_effect=OSError("kein TV"))), \
         patch("custom_components.tv_zapper.asyncio.sleep", AsyncMock()):
        await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.tv_zapper_zapper"}, blocking=True)
        await hass.async_block_till_done()
        assert hass.states.get("switch.tv_zapper_zapper").state == "off"
        assert hass.states.get("sensor.tv_zapper_aktueller_treffer").state == "Fehler"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_laeuft_jetzt(hass: HomeAssistant):
    entry = await _einrichten(hass)
    st = entry.runtime_data
    jetzt = {"quelle": "app", "fernsehbild_vorn": True, "bildschirm_an": True, "vorn": "com.tcl.tv",
             "jetzt": {"nr": 167, "sender": "ProSieben MAXX HD", "sendung": "Futurama", "punkte": 4,
                       "treffer": ["Erwachsenen-Cartoons"]}}
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.jetzt", AsyncMock(return_value=jetzt)):
        await st.jetzt_lesen()
    s = hass.states.get("sensor.tv_zapper_lauft_jetzt")
    assert s.state == "167 ProSieben MAXX HD: Futurama" and s.attributes["kategorien"] == ["Erwachsenen-Cartoons"]
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock(side_effect=OSError("aus"))), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()):
        await st.jetzt_lesen()
    assert hass.states.get("sensor.tv_zapper_lauft_jetzt").state == "Fernseher aus"

    # Abfragetakt: Standard 15 s, nach Aendern der Option sofort neu geplant
    assert st._takt_s == 15 and st._takt is not None
    hass.config_entries.async_update_entry(entry, options={**entry.options, "takt_s": 30})
    await hass.async_block_till_done()
    assert st._takt_s == 30


async def test_adresse_aendern(hass: HomeAssistant):
    entry = await _einrichten(hass)
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.sh", AsyncMock(return_value="tvz-ok\n")):
        r = await hass.config_entries.flow.async_init(
            "tv_zapper", context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "reconfigure"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "192.0.2.62", "port": 5556})
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "reconfigure_successful"
    assert entry.data == {"host": "192.0.2.62", "port": 5556} and entry.unique_id == "192.0.2.62:5556"
    assert entry.runtime_data.tv.host == "192.0.2.62"   # neu geladen, Optionen bleiben
    assert entry.options["favorit"] == "Favorit1"


async def test_ausweichen_bevorzugt(hass: HomeAssistant):
    entry = await _einrichten(hass)
    st = entry.runtime_data
    sw = "switch.tv_zapper_bei_werbung_zuerst_bevorzugte_sender"
    assert hass.states.get(sw).state == "unavailable"   # App hat noch nichts gemeldet
    stand = {"wert": False}

    async def jetzt(_cfg):
        return {"quelle": "app", "fernsehbild_vorn": True, "jetzt": None, "ausweichen_bevorzugt": stand["wert"]}

    async def einstellen(name, wert):
        assert name == "ausweichen_bevorzugt"
        stand["wert"] = wert
        return {"ok": True, name: wert}

    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.jetzt", side_effect=jetzt), \
         patch("custom_components.tv_zapper.tv.Fernseher.app_einstellen", side_effect=einstellen) as es:
        await st.jetzt_lesen()
        assert hass.states.get(sw).state == "off"
        await hass.services.async_call("switch", "turn_on", {"entity_id": sw}, blocking=True)
        assert es.call_args.args == ("ausweichen_bevorzugt", True) and hass.states.get(sw).state == "on"
        await hass.services.async_call("switch", "turn_off", {"entity_id": sw}, blocking=True)
        assert hass.states.get(sw).state == "off"
