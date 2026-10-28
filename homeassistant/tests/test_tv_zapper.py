import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import custom_components.tv_zapper.tv  # noqa: F401  (fuer patch)
from custom_components.tv_zapper import tv
from homeassistant.util import dt as dt_util
import datetime
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
    assert entry.options["speicher_min"] == 5
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
    assert st._takte["jetzt"][0] == 15 and st._takte["speicher"][0] == 300
    hass.config_entries.async_update_entry(entry, options={**entry.options, "takt_s": 30, "speicher_min": 0})
    await hass.async_block_till_done()
    assert st._takte["jetzt"][0] == 30 and "speicher" not in st._takte   # 0 = aus

    # Arbeitsspeicher
    sp = tv.speicher_lesen(SPEICHER_AUSGABE)
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()), \
         patch("custom_components.tv_zapper.tv.Fernseher.speicher", AsyncMock(return_value=sp)):
        await st.speicher_lesen()
    assert hass.states.get("sensor.tv_zapper_arbeitsspeicher_verfugbar").state == "840"
    assert hass.states.get("sensor.tv_zapper_speicher_tv_app").state == "37"
    b = hass.states.get("sensor.tv_zapper_tv_app_vom_system_beendet")
    erwartet = datetime.datetime(2026, 10, 28, 5, 24, 44, tzinfo=dt_util.get_default_time_zone())
    assert datetime.datetime.fromisoformat(b.state) == erwartet and b.attributes["wichtigkeit"] == 125
    with patch("custom_components.tv_zapper.tv.Fernseher.verbinden", AsyncMock(side_effect=OSError("aus"))), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()):
        await st.speicher_lesen()
    assert hass.states.get("sensor.tv_zapper_arbeitsspeicher_verfugbar").state == "unknown"


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


# Ausgabe von tv.SPEICHER_BEFEHL am TCL (28.10.2026 06:15)
SPEICHER_AUSGABE = """MemTotal:        2451272 kB
MemAvailable:     860320 kB
SwapTotal:        917500 kB
SwapFree:         386284 kB
@@
           TOTAL PSS:    38258            TOTAL RSS:   107644       TOTAL SWAP PSS:     6456
@@
          timestamp=2026-10-28 06:04:32.889 pid=30978 realUid=10139 packageUid=10139 definingUid=10139 user=0
          process=io.github.mhd6271.tvzapper reason=3 (LOW_MEMORY) subreason=0 (UNKNOWN) status=0
          importance=400 pss=13MB rss=65MB description=null state=empty trace=null
          timestamp=2026-10-28 05:36:11.250 pid=29353 realUid=10139 packageUid=10139 definingUid=10139 user=0
          process=io.github.mhd6271.tvzapper reason=3 (LOW_MEMORY) subreason=0 (UNKNOWN) status=0
          importance=400 pss=12MB rss=59MB description=null state=empty trace=null
          timestamp=2026-10-28 05:24:44.789 pid=19806 realUid=10139 packageUid=10139 definingUid=10139 user=0
          process=io.github.mhd6271.tvzapper reason=3 (LOW_MEMORY) subreason=0 (UNKNOWN) status=0
          importance=125 pss=38MB rss=92MB description=null state=empty trace=null
"""


async def test_logbuch(hass: HomeAssistant):
    from homeassistant.core import callback
    from custom_components.tv_zapper import logbook as tvz_logbook
    entry = await _einrichten(hass)
    st = entry.runtime_data
    ereignisse = []
    hass.bus.async_listen("tv_zapper_umgeschaltet", callback(lambda e: ereignisse.append(e)))

    # HA-Zapper schaltet um -> ein Eintrag mit ausgeschriebenem Grund
    neu = {"nr": 141, "sender": "N24 DOKU", "sendung": "Doku über Rap", "punkte": 7, "treffer": ["Hip-Hop/Rap"],
           "genre": "", "info": ""}
    erg = {**ERGEBNIS, "aktion": "umgeschaltet", "neu": neu}
    with patch("custom_components.tv_zapper.tv.Fernseher.durchgang", AsyncMock(return_value=erg)), \
         patch("custom_components.tv_zapper.tv.Fernseher.trennen", AsyncMock()):
        await st.durchgang(False)
    await hass.async_block_till_done()
    assert len(ereignisse) == 1 and ereignisse[0].data["wer"] == "TV-Zapper (HA)"
    assert ereignisse[0].data["text"].startswith("hat auf 141 N24 DOKU („Doku über Rap“) umgeschaltet")
    assert "Punkte" in ereignisse[0].data["text"]

    # Logbuch beschreibt das Ereignis
    beschreiber = {}
    tvz_logbook.async_describe_events(hass, lambda dom, ev, fn: beschreiber.setdefault(ev, fn))
    b = beschreiber["tv_zapper_umgeschaltet"](ereignisse[0])
    assert b["name"] == "TV-Zapper (HA)" and b["message"] == ereignisse[0].data["text"]

    # TV-App: erstes Lesen nur merken, danach jede neue Umschaltung einmal
    alt = [{"id": 100, "grund": "werbung", "nr": 1, "sender": "Das Erste"}]
    st._app_umschaltungen_melden(alt)
    await hass.async_block_till_done()
    assert len(ereignisse) == 1
    st._app_umschaltungen_melden(alt + [{"id": 101, "grund": "zurueck", "nr": 75, "sender": "Comedy Central HD"}])
    st._app_umschaltungen_melden(alt + [{"id": 101, "grund": "zurueck", "nr": 75, "sender": "Comedy Central HD"}])
    await hass.async_block_till_done()
    assert len(ereignisse) == 2 and ereignisse[1].data["wer"] == "TV-Zapper (TV-App)"
    assert ereignisse[1].data["text"] == "Werbung vorbei, zurück auf 75 Comedy Central HD."
    st._app_umschaltungen_melden([])   # aeltere App ohne das Feld: nichts
    assert len(ereignisse) == 2
