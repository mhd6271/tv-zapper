"""Konstanten und Voreinstellungen (Vorlage: interessen.json im Repo)."""
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

STANDARD_INTERESSEN = [
    {
        "name": "Hip-Hop/Rap",
        "gewicht": 5,
        "woerter": [
            "hip-hop",
            "hip hop",
            "hiphop",
            "rap",
            "rapper*",
            "rapperin*",
            "deutschrap",
            "gangsta-rap",
            "grime",
            "drill",
            "beatbox*",
            "breakdance*"
        ]
    },
    {
        "name": "Musik",
        "gewicht": 3,
        "woerter": [
            "musik*",
            "music",
            "konzert*",
            "concert",
            "charts",
            "festival*",
            "musikvideo*",
            "song*",
            "band",
            "sänger*",
            "album",
            "dj",
            "unplugged",
            "live-auftritt*",
            "popstar*",
            "soul",
            "r&b",
            "jazz",
            "rock",
            "techno"
        ]
    },
    {
        "name": "Dokumentation",
        "gewicht": 2,
        "woerter": [
            "doku",
            "dokumentation*",
            "dokumentarfilm*",
            "dokureihe*",
            "documentary"
        ]
    },
    {
        "name": "Lifestyle",
        "gewicht": 2,
        "woerter": [
            "lifestyle",
            "fashion",
            "streetwear",
            "sneaker*",
            "street food",
            "foodtruck*",
            "beauty",
            "luxus*",
            "tattoo*"
        ]
    }
]

STANDARD_AUS = ["teleshopping", "dauerwerbesendung", "verkaufsshow", "shopping-tipps"]

STANDARD_SENDER_NIE = []

STANDARD_SENDER_BEVORZUGT = {"N24 DOKU": 1, "ZDFinfo HD": 1}

STANDARD_OPTIONEN = {
    CONF_FAVORIT: "Favorit1",
    CONF_LAUFZEIT: 60,
    CONF_VERWEILEN: 5,
    CONF_INTERESSEN: STANDARD_INTERESSEN,
    CONF_AUS: STANDARD_AUS,
    CONF_SENDER_NIE: STANDARD_SENDER_NIE,
    CONF_SENDER_BEVORZUGT: STANDARD_SENDER_BEVORZUGT,
    CONF_NUR_LESEN: False,
}
