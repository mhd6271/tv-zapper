#!/usr/bin/env python3
"""Den Kern der HA-Integration (custom_components/tv_zapper/tv.py) ohne Home Assistant am Fernseher ausprobieren.

Braucht adb-shell:  pip install "adb-shell[async]==0.4.4"
Aufruf:  python3 probe_tv.py --nur-verbinden              (eigener neuer Schluessel wie in HA -> Abfrage am TV)
         python3 probe_tv.py --schluessel ~/.android/adbkey --einmal   (Mac-Schluessel, ein Durchgang nur lesen)
"""
import argparse
import asyncio
import importlib
import json
import pathlib
import sys
import types

HIER = pathlib.Path(__file__).resolve().parent
# Paket ohne __init__.py (das braucht Home Assistant) laden
pkg = types.ModuleType("tvz")
pkg.__path__ = [str(HIER / "custom_components" / "tv_zapper")]
sys.modules["tvz"] = pkg
tv_mod = importlib.import_module("tvz.tv")
const = importlib.import_module("tvz.const")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.20.61")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--schluessel", default=str(HIER / "probe_adbkey"), help="wird angelegt, falls nicht vorhanden")
    ap.add_argument("--nur-verbinden", action="store_true")
    ap.add_argument("--einmal", action="store_true", help="ein Durchgang, nur lesen")
    ap.add_argument("--umschalten", action="store_true", help="beim Durchgang wirklich umschalten")
    a = ap.parse_args()
    signer = tv_mod.lade_signer(str(pathlib.Path(a.schluessel).expanduser()))
    tv = tv_mod.Fernseher(a.host, a.port, signer, const.STANDARD_OPTIONEN[const.CONF_FAVORIT])
    print("verbinde (bis 60 s fuer die Abfrage am Fernseher) ...", flush=True)
    await tv.verbinden(auth_timeout=60)
    print("verbunden:", (await tv.sh("echo tvz-ok; getprop ro.product.model")).split())
    print("vorn:", await tv.focus_app())
    if a.einmal:
        cfg = {"interessen": const.STANDARD_INTERESSEN, "aus": const.STANDARD_AUS}
        e = await tv.durchgang(cfg, nur_lesen=not a.umschalten)
        print(json.dumps(e, ensure_ascii=False, indent=1))
    await tv.trennen()


if __name__ == "__main__":
    asyncio.run(main())
