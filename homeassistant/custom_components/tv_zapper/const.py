"""Konstanten und Voreinstellungen (Vorlage: interessen.json im Repo)."""
import json
import pathlib

DOMAIN = "tv_zapper"
PLATFORMS = ["switch", "sensor", "number", "button"]
EVENT_DURCHGANG = "tv_zapper_durchgang"
EVENT_UMGESCHALTET = "tv_zapper_umgeschaltet"   # erscheint im Logbuch (logbook.py)
# KOMPAT: Der Schluessel liegt im HA-Konfigordner. Bei einem Backup ohne .storage oder einer neuen Installation
# entsteht ein neuer Schluessel, dann fragt der Fernseher erneut "USB-Debugging zulassen?".
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
CONF_PROTOKOLL = "protokoll"
CONF_TAKT = "takt_s"
CONF_SPEICHER_TAKT = "speicher_min"

# Grundeinstellung = Kopie von interessen.json im Repo (beim Aendern dort neu kopieren, ein Test prueft das)
# KOMPAT: Die Vorlage (Interessen, Ausschluesse, Sendernamen) ist auf Deutsch und auf deutsche Sender
# zugeschnitten. In anderen Sprachen oder Laendern trifft sie kaum etwas und muss angepasst werden.
_VORLAGE = json.loads((pathlib.Path(__file__).parent / "vorlage.json").read_text(encoding="utf-8"))
STANDARD_INTERESSEN = _VORLAGE["interessen"]
STANDARD_AUS = _VORLAGE.get("aus", [])
STANDARD_SENDER_NIE = _VORLAGE.get("sender_nie", [])
STANDARD_SENDER_BEVORZUGT = _VORLAGE.get("sender_bevorzugt", {})

STANDARD_OPTIONEN = {
    # KOMPAT: Name der Favoritenliste beim TCL mit deutscher Oberflaeche.
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
    CONF_PROTOKOLL: True,
    CONF_TAKT: 15,   # Sekunden zwischen zwei Nachfragen "Was laeuft?"
    CONF_SPEICHER_TAKT: 5,   # Minuten zwischen zwei Blicken auf den Arbeitsspeicher, 0 = aus
}
