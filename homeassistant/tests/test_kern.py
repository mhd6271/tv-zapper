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


async def test_erster_kandidat_passt():
    f = fernseher([{"nr": 141, "sender": "N24 DOKU", "sendung": "Doku: Hip Hop", "punkte": 8, "treffer": []}])
    e = await f.durchgang(CFG)
    assert e["aktion"] == "umgeschaltet" and e["neu"]["nr"] == 141
    assert [c.args[0] for c in f.tune.call_args_list] == [141]


async def test_rueckfall_auf_alten_sender():
    f = fernseher([None, {"nr": 271, "punkte": 0, "sendung": "Heute"}, {"nr": 25, "punkte": -1, "sendung": "Shop"}])
    e = await f.durchgang(CFG)
    assert e["aktion"].startswith("bleibt (") and len(e["verworfen"]) == 3
    assert [c.args[0] for c in f.tune.call_args_list][-1] == 23


async def test_nur_lesen_schaltet_nicht():
    f = fernseher([])
    e = await f.durchgang(CFG, nur_lesen=True)
    assert e["aktion"] == "bleibt" and f.tune.call_count == 0 and e["bester"]["nr"] == 141
