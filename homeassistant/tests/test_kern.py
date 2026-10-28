"""tv.Fernseher.durchgang mit nachgebautem Fernseher: Kandidaten, verify, Rueckfall."""
import asyncio
from unittest.mock import AsyncMock, patch

from custom_components.tv_zapper import const, tv
from custom_components.tv_zapper.logik import bewerte_sendung, text_zu_bonus, bonus_zu_text

CFG = {"interessen": const.STANDARD_INTERESSEN, "aus": const.STANDARD_AUS,
       "sender_nie": ["sixx HD"], "sender_bevorzugt": const.STANDARD_SENDER_BEVORZUGT}
CHANS = {23: ("ProSieben HD", "Navy CIS"), 24: ("sixx HD", "Hip-Hop Party"), 141: ("N24 DOKU", "Doku: Hip Hop"),
         271: ("ZDFinfo HD", "Doku über Rap"), 25: ("RTL HD", "Rap am Mittwoch")}


def fernseher(verify_ergebnisse):
    f = tv.Fernseher("x", 1, None)
    f.focus_app = AsyncMock(return_value=tv.TV_APP)
    f.app_abfragen = AsyncMock(return_value=None)   # ohne TV-App: Weg ueber die Programmzeitschrift
    f.collect = AsyncMock(return_value=(23, CHANS, {}))
    f.tune = AsyncMock()
    f.verify = AsyncMock(side_effect=verify_ergebnisse)
    return f


async def test_bewertung_bonus_und_nie():
    assert bewerte_sendung(24, "sixx HD", "Hip-Hop Party", {}, CFG)["punkte"] == -1
    b = bewerte_sendung(141, "N24 DOKU", "Doku: Hip Hop", {}, CFG)
    assert b["punkte"] == 5 + 2 + 1 and "bevorzugter Sender" in b["treffer"]
    assert text_zu_bonus(bonus_zu_text({"N24 DOKU": 1, "ZDFinfo HD": 2})) == {"N24 DOKU": 1, "ZDFinfo HD": 2}
    assert text_zu_bonus("WELT HD") == {"WELT HD": 1}


async def test_einmal_umschalten_und_nachlesen():
    f = fernseher([{"nr": 141, "sender": "N24 DOKU", "sendung": "Doku: Hip Hop", "punkte": 8, "treffer": []}])
    e = await f.durchgang(CFG)
    assert e["aktion"] == "umgeschaltet" and e["neu"]["nr"] == 141 and e["passt_nach_umschalten"] is True
    assert [c.args[0] for c in f.tune.call_args_list] == [141]


async def test_passt_nachher_nicht_trotzdem_nur_einmal():
    f = fernseher([{"nr": 141, "sender": "N24 DOKU", "sendung": "Wetter", "punkte": 0, "treffer": []}])
    e = await f.durchgang(CFG)
    assert e["aktion"] == "umgeschaltet" and e["passt_nach_umschalten"] is False
    assert f.tune.call_count == 1


async def test_back_nur_bei_programmzeitschrift():
    f = tv.Fernseher("x", 1, None)
    f.key = AsyncMock()
    f.focus_app = AsyncMock(return_value=tv.TV_APP)
    await f.close_guide()
    assert f.key.call_count == 0                     # im Fernsehbild kein BACK
    f.focus_app = AsyncMock(side_effect=[tv.GUIDE_APP, tv.TV_APP])
    await f.close_guide()
    assert [c.args for c in f.key.call_args_list] == [("KEYCODE_BACK",)]


async def test_tune_bricht_ab_wenn_kein_fernsehbild():
    f = tv.Fernseher("x", 1, None)
    f.key = AsyncMock()
    f.focus_app = AsyncMock(return_value="com.google.android.apps.tv.launcherx/.Home")
    try:
        await f.tune(23)
        raise AssertionError("haette abbrechen muessen")
    except RuntimeError:
        pass
    assert f.key.call_count == 0


async def test_nur_lesen_schaltet_nicht():
    f = fernseher([])
    e = await f.durchgang(CFG, nur_lesen=True)
    assert e["aktion"] == "bleibt" and f.tune.call_count == 0 and e["bester"]["nr"] == 141


async def test_disney_nie():
    assert bewerte_sendung(30, "Disney Channel HD", "Doku über Rap", {}, const.STANDARD_OPTIONEN | {"interessen": const.STANDARD_INTERESSEN, "sender_nie": const.STANDARD_SENDER_NIE})["punkte"] == -1
    cfg = {"interessen": const.STANDARD_INTERESSEN, "aus": const.STANDARD_AUS}
    from custom_components.tv_zapper.logik import score
    assert score("Micky Maus Wunderhaus", cfg)[0] == -1 and score("Futurama", cfg)[0] > 0


def test_vorlage_gleich_interessen_json():
    import json, pathlib
    repo = pathlib.Path(__file__).resolve().parents[2] / "interessen.json"
    assert json.loads(repo.read_text(encoding="utf-8")) == json.loads(
        (pathlib.Path(const.__file__).parent / "vorlage.json").read_text(encoding="utf-8")), \
        "interessen.json geaendert: nach homeassistant/custom_components/tv_zapper/vorlage.json kopieren"


async def test_blaettert_nicht_in_senderliste():
    """Senderliste statt Programmzeitschrift vorn: keine einzige Hoch/Runter-Taste."""
    f = tv.Fernseher("x", 1, None)
    f.key = AsyncMock()
    liste = "com.tcl.tv/com.tcl.tv.channellist.NewChannelListActivity"
    f.focus_app = AsyncMock(return_value=liste)
    f.dump = AsyncMock(return_value=[{"text": "12"}, {"text": "Drücken Sie OK zur Bestätigung"}])
    with patch("custom_components.tv_zapper.tv.asyncio.sleep", AsyncMock()):
        try:
            await f.collect()
            raise AssertionError("haette abbrechen muessen")
        except RuntimeError as e:
            assert "nicht vorn" in str(e)
    gedrueckt = [a for c in f.key.call_args_list for a in c.args]
    assert not any(k in gedrueckt for k in ("KEYCODE_DPAD_UP", "KEYCODE_DPAD_DOWN", "KEYCODE_DPAD_CENTER")), gedrueckt


def test_echte_programmzeitschrift():
    """Abzug vom Geraet: Altersangabe "12" im Kopf ist keine Sendernummer, erste Zeile = laufender Sender."""
    import pathlib
    from custom_components.tv_zapper.logik import parse_guide, parse_xml
    nodes = parse_xml((pathlib.Path(__file__).parent / "guide_27-10-2026.xml").read_text(encoding="utf-8"))
    rows, header, tab = parse_guide(nodes)
    assert rows[0] == (75, "Comedy Central HD", "Futurama")
    assert [r[0] for r in rows[:4]] == [75, 76, 77, 78]
    assert header["title"] == "Futurama" and tab == "Alle"


async def test_einblenden_app_oder_benachrichtigung():
    from custom_components.tv_zapper import meldung_umgeschaltet
    assert meldung_umgeschaltet({"sender": "MTV HD", "sendung": "Love & Hip Hop", "punkte": 7,
                                 "treffer": ["Hip-Hop/Rap", "Dokumentation"]}) == \
        "MTV HD – Love & Hip Hop  (Hip-Hop/Rap, Dokumentation, 7 P.)"
    f = tv.Fernseher("x", 1, None)
    f.sh = AsyncMock(side_effect=["io.github.mhd6271.tvzapper/.EinblendungEmpfaenger", ""])
    assert await f.einblenden("Bob's Burgers") == "app"
    befehl = f.sh.call_args_list[1].args[0]
    assert "am broadcast" in befehl and "'Bob'\"'\"'s Burgers'" in befehl, befehl
    f.sh = AsyncMock(side_effect=["No receivers found", ""])
    assert await f.einblenden("TV-Zapper an") == "benachrichtigung"
    assert "cmd notification post" in f.sh.call_args_list[1].args[0]


def test_magic_packet():
    p = tv.magic_packet("AA-bb-cc-dd-ee-ff")
    assert len(p) == 102 and p[:6] == b"\xff" * 6 and p[6:12] == bytes.fromhex("aabbccddeeff")
    for falsch in ("", "aa:bb:cc", "zz:bb:cc:dd:ee:ff"):
        try:
            tv.magic_packet(falsch)
            assert False, falsch
        except ValueError:
            pass


async def test_wecken():
    async def mit(verbindungen, wach, mac):
        f = tv.Fernseher("x", 1, None)
        f.verbinden = AsyncMock(side_effect=verbindungen)
        f.wach = AsyncMock(return_value=wach)
        f.key, f.trennen = AsyncMock(), AsyncMock()
        with patch.object(tv, "sende_wol") as wol, patch("asyncio.sleep", AsyncMock()):
            weg = await f.wecken(mac, warten=60)
        return weg, wol.call_count, f.key.call_args_list

    assert await mit([None], True, "") == ("wach", 0, [])
    weg, _, tasten = await mit([None], False, "")
    assert weg == "geweckt" and tasten[0].args == ("KEYCODE_WAKEUP",)
    assert (await mit([OSError("zu"), OSError("zu"), None], True, "aa:bb:cc:dd:ee:ff"))[:2] == ("wol", 2)
    try:   # ohne MAC: Fehler weiterreichen, kein Wake-on-LAN
        await mit([OSError("zu")], True, "")
        assert False
    except OSError:
        pass


# Antwort der TV-App 0.3.0 (am TCL 27.10.2026, gekuerzt)
APP_AUSGABE = '''Broadcasting: Intent { act=io.github.mhd6271.tvzapper.ABFRAGEN flg=0x400000 cmp=io.github.mhd6271.tvzapper/.AbfrageEmpfaenger (has extras) }
Broadcast completed: result=0, data="{"zeit":"2026-10-27T19:29:59+01:00","bildschirm_an":true,"vorn":"com.tcl.tv","fernsehbild_vorn":true,"zapper_laeuft":false,"werbe_sensor":"","werbung":null,"jetzt":{"nr":"23","sender":"ProSieben HD","id":1074,"zustand":"an","sendung":"Galileo","folge":"","genre":"32","beschreibung":"Folge 8314. Magazin, D 2026.","start":"2026-10-27T19:05:00+01:00","ende":"2026-10-27T20:15:00+01:00","punkte":0,"treffer":[]},"liste":[{"nr":"23","sender":"ProSieben HD","id":1074,"zustand":"an","sendung":"Galileo","folge":"","genre":"32","beschreibung":"Folge 8314. Magazin, D 2026.","start":"","ende":"","punkte":0,"treffer":[]},{"nr":"167","sender":"ProSieben MAXX HD","id":1218,"zustand":"an","sendung":"Futurama","folge":"","genre":"83","beschreibung":"4 .Staffel, Folge 9. Zeichentrickserie, USA 2003.","start":"","ende":"","punkte":4,"treffer":["Erwachsenen-Cartoons"]}]}"
'''


def test_broadcast_daten():
    d = tv.broadcast_daten(APP_AUSGABE)
    assert d["jetzt"]["sender"] == "ProSieben HD" and len(d["liste"]) == 2
    assert tv.broadcast_daten("Broadcasting: Intent { … }\nBroadcast completed: result=0") is None


async def test_durchgang_ueber_app():
    f = tv.Fernseher("x", 1, None)
    daten = tv.broadcast_daten(APP_AUSGABE)
    danach = {"jetzt": daten["liste"][1]}
    f.app_abfragen = AsyncMock(side_effect=[daten, danach])
    f.app_umschalten = AsyncMock(return_value={"ok": True})
    f.focus_app, f.collect = AsyncMock(), AsyncMock()
    with patch("asyncio.sleep", AsyncMock()):
        e = await f.durchgang(CFG)
    assert e["quelle"] == "app" and e["aktion"] == "umgeschaltet" and e["neu"]["nr"] == 167
    assert e["passt_nach_umschalten"] is True and f.app_umschalten.call_args.args == (167,)
    f.collect.assert_not_called()   # keine Programmzeitschrift, keine Tasten

    # Zappt die TV-App selbst, schaltet HA nicht dazwischen
    f.app_abfragen = AsyncMock(return_value={**daten, "zapper_laeuft": True})
    f.app_umschalten.reset_mock()
    e = await f.durchgang(CFG)
    assert e["aktion"] == "uebersprungen" and "TV-App" in e["app"]
    assert e["vorher"]["nr"] == 23 and e["vorher"]["sendung"] == "Galileo"   # fuer den Sensor "Aktueller Treffer"
    f.app_umschalten.assert_not_called()


async def test_jetzt():
    f = tv.Fernseher("x", 1, None)
    f.app_abfragen = AsyncMock(return_value=tv.broadcast_daten(APP_AUSGABE))
    j = await f.jetzt(CFG)
    assert j["jetzt"]["sender"] == "ProSieben HD" and j["jetzt"]["beschreibung"].startswith("Folge")
    assert j["ausweichen_bevorzugt"] is None   # aeltere App ohne das Feld
    f.app_abfragen = AsyncMock(return_value=None)
    f.focus_app = AsyncMock(return_value=tv.TV_APP)
    assert (await f.jetzt(CFG)) == {"quelle": "adb", "fernsehbild_vorn": True, "vorn": tv.TV_APP, "jetzt": None}


async def test_app_einstellen():
    f = tv.Fernseher("x", 1, None)
    f.sh = AsyncMock(return_value='Broadcast completed: result=0, data="{"ok":true,"ausweichen_bevorzugt":true}"')
    assert (await f.app_einstellen("ausweichen_bevorzugt", True))["ausweichen_bevorzugt"] is True
    assert "--es ausweichen_bevorzugt true" in f.sh.call_args.args[0] and tv.EINSTELLEN_ACTION in f.sh.call_args.args[0]
    f.sh = AsyncMock(return_value='Broadcast completed: result=1, data="{"fehler":"unbekannt"}"')
    try:
        await f.app_einstellen("ausweichen_bevorzugt", False)
        assert False
    except RuntimeError:
        pass
