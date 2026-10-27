"""Konstanten und Voreinstellungen (Vorlage: interessen.json im Repo)."""
import json
import pathlib

DOMAIN = "tv_zapper"
PLATFORMS = ["switch", "sensor", "number", "button"]
EVENT_DURCHGANG = "tv_zapper_durchgang"
SCHLUESSEL_DATEI = ".storage/tv_zapper_adbkey"

CONF_FAVORIT = "favorit"
CONF_LAUFZEIT = "laufzeit_min"
CONF_VERWEILEN = "verweilen_min"
CONF_INTERESSEN = "interessen"
CONF_AUS = "aus"
CONF_NUR_LESEN = "nur_lesen"
CONF_SENDER_NIE = "sender_nie"
CONF_SENDER_BEVORZUGT = "sender_bevorzugt"
CONF_EINBLENDUNG = "einblendung"
CONF_MAC = "mac"

# Grundeinstellung = Kopie von interessen.json im Repo (beim Aendern dort neu kopieren, ein Test prueft das)
_VORLAGE = json.loads((pathlib.Path(__file__).parent / "vorlage.json").read_text(encoding="utf-8"))
STANDARD_INTERESSEN = _VORLAGE["interessen"]
STANDARD_AUS = _VORLAGE.get("aus", [])
STANDARD_SENDER_NIE = _VORLAGE.get("sender_nie", [])
STANDARD_SENDER_BEVORZUGT = _VORLAGE.get("sender_bevorzugt", {})

STANDARD_OPTIONEN = {
    CONF_FAVORIT: "Favorit1",
    CONF_LAUFZEIT: 60,
    CONF_VERWEILEN: _VORLAGE.get("verweilen_min", 5),
    CONF_INTERESSEN: STANDARD_INTERESSEN,
    CONF_AUS: STANDARD_AUS,
    CONF_SENDER_NIE: STANDARD_SENDER_NIE,
    CONF_SENDER_BEVORZUGT: STANDARD_SENDER_BEVORZUGT,
    CONF_NUR_LESEN: False,
    CONF_EINBLENDUNG: True,
    CONF_MAC: "",
}
