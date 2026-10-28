"""Fernseher per adb-shell bedienen (ohne Home Assistant): Ablauf 1:1 aus zapper.py.

Statt des adb-Programms spricht die Integration selbst ADB ueber TCP (Bibliothek adb-shell,
dieselbe wie in der eingebauten Integration "Android Debug Bridge") mit eigenem Schluessel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import socket

# KOMPAT: adb-shell[async]==0.4.4 ist im manifest.json fest gepinnt (dieselbe Fassung wie die eingebaute
# Integration androidtv in HA 2026.10). Pinnt HA core spaeter eine andere Fassung, kann die Installation
# scheitern. Braucht rsa, pyasn1, cryptography (bringt HA mit), daher ARM und x86. adb-shell kann das Koppeln per
# "Kabelloses Debugging" (Android 11+, TLS mit Kopplungscode) nicht (Issue JeffLIrion/adb_shell#206, offen
# seit 2022; letzte Fassung 0.4.4 von 2023). Geraete ohne klassisches ADB ueber TCP sind nicht erreichbar.
from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

from .logik import bewerte, bewerte_sendung, grund_zeilen, parse_guide, parse_xml, soll_umschalten

_LOGGER = logging.getLogger(__name__)

# KOMPAT: Paket und Activity des Fernsehbilds gibt es nur bei TCL (Android 14, Google TV). Sony, Philips,
# Hisense oder ein Google TV Streamer haben eine andere Live-TV-App, oft gar keinen Tuner. Dann gilt das
# Fernsehbild nie als "vorn": Der Durchgang ohne TV-App wird immer uebersprungen, und fernsehbild_holen()
# startet eine Activity, die es nicht gibt (am start meldet einen Fehler).
TV_APP = "com.tcl.tv/com.tcl.player.TVActivity"
# Einblendung ueber die TV-App aus android/ (Overlay wie deren eigene Meldung nach dem Umschalten)
EINBLENDEN_ACTION = "io.github.mhd6271.tvzapper.EINBLENDEN"
EINBLENDEN_EMPFAENGER = "io.github.mhd6271.tvzapper/.EinblendungEmpfaenger"
# KOMPAT: Programmzeitschrift des TCL (Paket com.tcl.tv). Andere Hersteller haben eine andere Activity,
# dann klappt nur der Weg ueber die TV-App.
GUIDE_APP = "com.tcl.tv/com.tcl.tv.epg.EpgProActivity"
# Schnittstelle der TV-App ab 0.3.0: Sender und Sendungen aus TvContract, Umschalten ohne Tasten
ABFRAGEN_ACTION = "io.github.mhd6271.tvzapper.ABFRAGEN"
UMSCHALTEN_ACTION = "io.github.mhd6271.tvzapper.UMSCHALTEN"
EINSTELLEN_ACTION = "io.github.mhd6271.tvzapper.EINSTELLEN"
ABFRAGE_EMPFAENGER = "io.github.mhd6271.tvzapper/.AbfrageEmpfaenger"
APP_PAKET = "io.github.mhd6271.tvzapper"
# Wichtigkeit eines Prozesses bei Android: bis 200 laeuft etwas Sichtbares oder ein Vordergrunddienst (der Zapper
# der TV-App), 300 ein Dienst, ab 400 nur noch ein zwischengespeicherter Prozess - dessen Ende ist harmlos.
WICHTIG_BIS = 200


def speicher_lesen(ausgabe: str) -> dict:
    """Ausgabe von SPEICHER_BEFEHL -> Arbeitsspeicher des Fernsehers, Speicher der TV-App und wann Android
    die TV-App beendet hat (alles in MB; Zeiten in Ortszeit des Fernsehers, ohne Zeitzone)."""
    teile = (ausgabe.split("@@") + ["", ""])[:3]
    # KOMPAT: /proc/meminfo ist auf jedem Linux gleich. Der Text von `dumpsys meminfo -s` und
    # `dumpsys activity exit-info` ist nicht festgelegt. exit-info gibt es erst ab Android 11 (ApplicationExitInfo),
    # Format und Gruende (LOW_MEMORY ...) wie unter Android 14 am TCL gesehen. Passt das Format nicht, bleiben
    # die Speicher-Sensoren leer (None), es gibt keinen Fehler. Die Zeiten sind Ortszeit des Fernsehers ohne Zeitzone.
    kb = {k: int(v) for k, v in re.findall(r"^(\w+):\s+(\d+) kB", teile[0], re.M)}
    mb = lambda k: round(kb[k] / 1024) if k in kb else None  # noqa: E731
    pss = re.search(r"TOTAL PSS:\s+(\d+)", teile[1])
    enden = [{"zeit": z, "grund": g, "wichtigkeit": int(w), "speicher_mb": int(p)}
             for z, g, w, p in re.findall(
                 r"timestamp=(\S+ \S+) .*?reason=\d+ \((\w+)\).*?importance=(\d+) pss=([\d]+)", teile[2], re.S)]
    knapp = [e for e in enden if e["grund"] == "LOW_MEMORY"]
    return {
        "gesamt_mb": mb("MemTotal"), "verfuegbar_mb": mb("MemAvailable"),
        "swap_gesamt_mb": mb("SwapTotal"),
        "swap_belegt_mb": mb("SwapTotal") - mb("SwapFree") if "SwapFree" in kb and "SwapTotal" in kb else None,
        "app_mb": round(int(pss.group(1)) / 1024) if pss else None,
        "app_beendet": next((e for e in knapp if e["wichtigkeit"] <= WICHTIG_BIS), None),
        "app_beendet_irgendwie": enden[0] if enden else None,
        "app_beendet_speicher_anzahl": len(knapp),
    }


SPEICHER_BEFEHL = (
    'grep -E "^(MemTotal|MemAvailable|SwapTotal|SwapFree):" /proc/meminfo; echo @@; '
    f'dumpsys meminfo -s {APP_PAKET} | grep "TOTAL PSS"; echo @@; '
    f'dumpsys activity exit-info {APP_PAKET} | grep -E "timestamp=|reason=|importance="')


MAX_SHELL_TEXT = 500   # Zeichen fuer Texte, die per adb shell an die TV-App gehen (Einblendung, Grund)


def shell_text(text, laenge: int = MAX_SHELL_TEXT) -> str:
    """Text fuer `am broadcast --es ...`: Steuerzeichen raus, Laenge begrenzen, fuer die Shell quoten."""
    sauber = re.sub(r"[\x00-\x1f\x7f]", " ", str(text))[:laenge]
    return shlex.quote(sauber)


def gueltige_sender(liste) -> list[dict]:
    """Senderliste aus ABFRAGEN: nur Eintraege mit ganzzahliger Nummer (Daten vom Fernseher, nicht blind trauen)."""
    out = []
    for x in liste if isinstance(liste, list) else []:
        if isinstance(x, dict):
            try:
                int(x.get("nr"))
            except (TypeError, ValueError):
                continue
            out.append(x)
    return out


def logo_zaehler(x) -> dict | None:
    """Logo-Zaehler der TV-App nur uebernehmen, wenn beide Zahlen ganze Zahlen sind."""
    if isinstance(x, dict) and all(isinstance(x.get(k), int) and not isinstance(x.get(k), bool)
                                   for k in ("gelernt", "beobachtet")):
        return {"gelernt": x["gelernt"], "beobachtet": x["beobachtet"]}
    return None


def broadcast_daten(ausgabe: str) -> dict | None:
    """`Broadcast completed: result=0, data="{...}"` -> dict; None, wenn kein Empfaenger geantwortet hat."""
    m = re.search(r'Broadcast completed: result=(-?\d+), data="(.*)"\s*$', ausgabe, re.S)
    if not m:
        return None
    try:
        daten = json.loads(m.group(2))
    except ValueError:
        return None
    return daten if isinstance(daten, dict) else None


def app_sendung(x: dict, cfg) -> dict:
    # KOMPAT: Die Felder kommen aus TvContract ueber die TV-App. Was der Hersteller dort eintraegt (Genre als
    # DVB-Code beim TCL, Folge, Beschreibung), ist unterschiedlich. Fehlt die Beschreibung, gibt es weniger Treffer.
    """Ein Sender aus der TV-App wie eine Zeile der Programmzeitschrift bewerten. genre ist bei TCL ein
    DVB-Zahlencode und wird nicht mitbewertet; Folge und Beschreibung zaehlen wie die Info im Kopf."""
    info = " ".join(t for t in (x.get("folge"), x.get("beschreibung")) if t)
    b = bewerte_sendung(int(x["nr"]), x.get("sender", ""), x.get("sendung") or None, {"info": info}, cfg)
    b.update(id=x.get("id"), start=x.get("start"), ende=x.get("ende"))
    return b


def lade_signer(pfad: str) -> PythonRSASigner:
    """Schluessel laden, beim ersten Mal anlegen (blockierend, im Executor aufrufen)."""
    if not os.path.isfile(pfad):
        os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
        keygen(pfad)
    for datei in (pfad, pfad + ".pub"):   # privater ADB-Schluessel: nur fuer den Besitzer lesbar
        if os.path.isfile(datei):
            os.chmod(datei, 0o600)
    with open(pfad, encoding="utf-8") as f:
        priv = f.read()
    pub = None   # ohne .pub geht nur ein schon freigegebener Schluessel (z. B. ~/.android/adbkey)
    if os.path.isfile(pfad + ".pub"):
        with open(pfad + ".pub", encoding="utf-8") as f:
            pub = f.read()
    return PythonRSASigner(pub, priv)


# KOMPAT: Wake-on-LAN muss der Fernseher koennen und erlauben (bei vielen Geraeten nur ueber LAN-Kabel oder
# mit einer Option wie "Netzwerk-Standby"/"Per WLAN einschalten"). Am TCL klappt es (geweckt in etwa 2 s).
def magic_packet(mac: str) -> bytes:
    """Wake-on-LAN-Paket: 6x FF, dann 16x die MAC. Wirft ValueError bei ungueltiger MAC."""
    ziffern = re.sub(r"[:\-. ]", "", mac.strip())
    if not re.fullmatch(r"[0-9a-fA-F]{12}", ziffern):
        raise ValueError("MAC-Adresse bitte als 12 Hex-Ziffern, z. B. aa:bb:cc:dd:ee:ff")
    return b"\xff" * 6 + bytes.fromhex(ziffern) * 16


def sende_wol(mac: str, host: str):
    """Paket an die Broadcast-Adresse (Port 9) und direkt an den Fernseher schicken (blockierend)."""
    paket = magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # KOMPAT: Broadcast an 255.255.255.255 erreicht nur dasselbe Netz. HA in Docker ohne host-Netz, ein anderes
        # VLAN/Subnetz oder ein WLAN, das Broadcasts filtert, laesst das Paket nicht durch. Dann hilft nur das Paket
        # direkt an die IP, und das kommt bei einem schlafenden Geraet meist nicht an (kein ARP-Eintrag).
        for ziel in ("255.255.255.255", host):
            try:
                s.sendto(paket, (ziel, 9))
            except OSError as e:
                _LOGGER.debug("Wake-on-LAN an %s nicht gesendet: %s", ziel, e)


class Fernseher:
    def __init__(self, host: str, port: int, signer: PythonRSASigner, fav_tab: str = "Favorit1"):
        self.host, self.port, self.signer, self.fav_tab = host, port, signer, fav_tab
        self.dev: AdbDeviceTcpAsync | None = None

    # --- Verbindung -------------------------------------------------------------------
    async def verbinden(self, auth_timeout: float = 10.0, timeout: float | None = None):
        if self.dev and self.dev.available:
            return
        # KOMPAT: Netzwerk-ADB (Standard-Port 5555) muss in den Entwickleroptionen eingeschaltet sein. Manche Geraete
        # vergessen das nach einem Neustart oder Update, oder sie bieten nur Kabelloses Debugging mit wechselndem
        # Port. Die Abfrage "USB-Debugging zulassen?" erscheint je nach Hersteller anders oder gar nicht.
        # 30 s Zeitlimit wegen uiautomator am TCL; schwaechere Geraete brauchen eventuell laenger.
        self.dev = AdbDeviceTcpAsync(self.host, self.port, default_transport_timeout_s=30.0)  # uiautomator dump braucht manchmal >9 s
        # auth_timeout: so lange wird auf "USB-Debugging zulassen?" am Fernseher gewartet
        await self.dev.connect(rsa_keys=[self.signer], transport_timeout_s=timeout, auth_timeout_s=auth_timeout)

    async def trennen(self):
        if self.dev:
            try:
                await self.dev.close()
            except Exception:  # noqa: BLE001 - beim Aufraeumen egal
                pass
            self.dev = None

    async def sh(self, cmd: str, timeout: float = 30) -> str:
        await self.verbinden()
        try:
            return await self.dev.shell(cmd, timeout_s=timeout, read_timeout_s=timeout) or ""
        except Exception:
            await self.trennen()
            raise

    # --- Wecken ---------------------------------------------------------------------------
    async def wach(self) -> bool:
        # KOMPAT: mWakefulness steht in AOSP-dumpsys (Awake/Asleep/Dreaming/Dozing). Bei Bildschirmschoner (Dreaming)
        # gilt der Fernseher als nicht wach und bekommt WAKEUP, das ist gewollt. Andere Firmware kann das Feld
        # anders nennen; dann wird bei jedem Start WAKEUP gesendet (meist harmlos).
        return "mWakefulness=Awake" in await self.sh("dumpsys power | grep mWakefulness=")

    async def wecken(self, mac: str = "", warten: float = 90) -> str:
        """Vor dem Zappen: Fernseher nicht erreichbar -> Wake-on-LAN (nur mit MAC) und warten, bis ADB antwortet;
        erreichbar, aber Bild aus -> Taste WAKEUP. -> "wach", "geweckt" oder "wol"."""
        weg = "wach"
        try:
            await self.verbinden(timeout=8)
        except Exception:
            await self.trennen()
            if not mac:
                raise
            loop = asyncio.get_running_loop()
            ende = loop.time() + warten
            while True:
                await loop.run_in_executor(None, sende_wol, mac, self.host)
                await asyncio.sleep(5)
                try:
                    await self.verbinden(timeout=8)
                    break
                except Exception:  # noqa: BLE001 - weiter warten
                    await self.trennen()
                    if loop.time() > ende:
                        raise RuntimeError(f"Fernseher antwortet {warten:.0f} s nach Wake-on-LAN nicht") from None
            weg = "wol"
        if not await self.wach():
            # KOMPAT: KEYCODE_WAKEUP gibt es ab Android 5. Manche Fernseher schalten damit nur den Bildschirm an,
            # nicht das Fernsehbild/den Tuner. Die Wartezeit von 8 s darunter ist am TCL gemessen.
            await self.key("KEYCODE_WAKEUP")
            weg = "geweckt" if weg == "wach" else weg
        if weg != "wach":
            await asyncio.sleep(8)   # Fernsehbild und Tuner brauchen nach dem Aufwachen ein paar Sekunden
        return weg

    async def speicher(self) -> dict:
        return speicher_lesen(await self.sh(SPEICHER_BEFEHL))

    async def fernsehbild_holen(self) -> bool:
        """Beim Einschalten des Zappers: ist eine andere App vorn (Startbildschirm, Netflix ...), das Fernsehbild
        starten. -> True, wenn es dafuer gestartet wurde. Waehrend der Zapper laeuft, wird das nicht gemacht."""
        if await self.focus_app() in (TV_APP, GUIDE_APP):
            return False
        await self.sh(f"am start -n {TV_APP}")
        # KOMPAT: 5 s sind am TCL ausprobiert; langsamere Geraete brauchen eventuell laenger.
        await asyncio.sleep(5)   # Tuner und Senderliste brauchen nach dem Start ein paar Sekunden
        return True

    # --- Bausteine wie in zapper.py -------------------------------------------------------
    async def key(self, *names):
        # KOMPAT: Mehrere Tasten in einem `input keyevent` kann Android laut AOSP-Quelltext seit 4.4 (am TCL mit
        # Android 14 geprueft). Ob jeder Hersteller sie schnell genug verarbeitet, ist offen.
        await self.sh("input keyevent " + " ".join(names))

    async def close_guide(self):
        """BACK nur, wenn die Programmzeitschrift vorn ist: im Fernsehbild springt BACK beim TCL
        auf den vorigen Sender."""
        for _ in range(2):
            if await self.focus_app() != GUIDE_APP:
                return
            # KOMPAT: Das Verhalten von BACK ist herstellerabhaengig. Am TCL springt es im Fernsehbild auf den vorigen
            # Sender, deshalb nur, wenn die Programmzeitschrift vorn ist.
            await self.key("KEYCODE_BACK")
            await asyncio.sleep(1.2)

    async def nur_in_guide(self, was: str):
        """Schutz: Hoch/Runter/OK nur in der Programmzeitschrift. In der Senderliste
        (z. B. NewChannelListActivity) schaltet jedes Hoch/Runter um."""
        if (app := await self.focus_app()) != GUIDE_APP:
            raise RuntimeError(f"Programmzeitschrift nicht vorn ({app or 'nichts'}) - {was} abgebrochen")

    async def focus_app(self) -> str:
        # KOMPAT: Format `mCurrentFocus=Window{hash u0 paket/activity}` wie unter Android 14. Andere Fassungen
        # schreiben teils `mCurrentFocus=null` oder haben mehrere Displays (dann die erste Zeile). Passt das Format
        # nicht, kommt "" zurueck und alles gilt als "nicht vorn" (sicher, aber der Zapper tut nichts).
        out = await self.sh("dumpsys window | grep mCurrentFocus")
        m = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([^}]+)\}", out)
        return m.group(1).strip() if m else ""

    async def dump(self, press=None, wait=0.4):
        """Optional eine Taste druecken, dann die Oberflaeche lesen - alles in einem Aufruf."""
        pre = f"input keyevent {press}; sleep {wait}; " if press else ""
        # KOMPAT: uiautomator dump braucht ein beschreibbares /sdcard fuer den shell-Benutzer. Bei Videos oder
        # Animationen scheitert es manchmal ("could not get idle state"). Auf schwachen Geraeten dauert es mehrere
        # Sekunden. Dann kommt eine leere Liste zurueck, und der Durchgang meldet einen Fehler.
        xml = await self.sh(pre + "uiautomator dump /sdcard/tvz.xml >/dev/null 2>&1; cat /sdcard/tvz.xml")
        return parse_xml(xml)

    def guide(self, nodes):
        return parse_guide(nodes, self.fav_tab)

    async def open_guide(self):
        if await self.focus_app() != GUIDE_APP:
            # KOMPAT: KEYCODE_GUIDE oeffnet am TCL die Programmzeitschrift. Andere Live-TV-Apps reagieren nicht oder
            # oeffnen eine andere Ansicht.
            await self.key("KEYCODE_GUIDE")
        for _ in range(12):
            await asyncio.sleep(1)
            nodes = await self.dump()
            rows, _, _ = self.guide(nodes)
            if rows and await self.focus_app() == GUIDE_APP:
                return nodes
        await self.nur_in_guide("Lesen")
        return await self.dump()

    async def ensure_fav_tab(self, nodes):
        _, _, tab = self.guide(nodes)
        if tab == self.fav_tab:
            return True
        await self.nur_in_guide("Reiterwahl")
        # KOMPAT: Aufbau der TCL-Programmzeitschrift: Reiter links (Alle, Favorit1 ...), mit LINKS erreichbar,
        # per content-desc erkannt. Bei anderem Layout findet die Schleife den Reiter nicht und bricht ab.
        await self.key("KEYCODE_DPAD_LEFT")
        await asyncio.sleep(0.8)
        for _ in range(8):
            await self.nur_in_guide("Reiterwahl")
            f = [n.get("content-desc") for n in await self.dump() if n.get("focused") == "true"]
            if self.fav_tab in f:
                await self.key("KEYCODE_DPAD_CENTER")
                await asyncio.sleep(1.5)
                await self.key("KEYCODE_DPAD_RIGHT")
                await asyncio.sleep(1)
                # nachpruefen, dass wirklich die Favoritenliste gewaehlt ist
                return self.guide(await self.dump())[2] == self.fav_tab
            await self.key("KEYCODE_DPAD_DOWN")
            await asyncio.sleep(0.6)
        return False

    async def collect(self):
        """Liest alle Sender der Favoritenliste mit laufender Sendung (+ Genre/Info, wo markiert)."""
        nodes = await self.open_guide()
        rows, _, _ = self.guide(nodes)
        if not rows:
            raise RuntimeError("Programmzeitschrift liess sich nicht lesen")
        current = rows[0][0]
        if not await self.ensure_fav_tab(nodes):
            # nie in "Alle" blaettern: dort sind Hunderte Sender
            raise RuntimeError(f"Reiter {self.fav_tab} liess sich nicht waehlen - Abbruch")
        chans, infos = {}, {}

        def take(nodes):
            rows, header, _ = self.guide(nodes)
            new = 0
            for num, name, prog in rows:
                if num not in chans:
                    new += 1
                chans[num] = (name, prog or chans.get(num, (None, None))[1])
            if header.get("title"):
                for num, name, prog in rows:
                    if prog and prog == header["title"]:
                        infos[num] = header
                        break
            return new

        take(await self.dump())
        # an den Anfang der Liste - in kleinen Stuecken und jedes Mal pruefen, dass die
        # Programmzeitschrift noch vorn ist: im Fernsehbild schaltet jedes Hoch einen Sender weiter.
        for _ in range(6):
            await self.nur_in_guide("Blaettern")
            # KOMPAT: 6 x 20 Schritte nach oben genuegen fuer Favoritenlisten bis etwa 120 Sender. Bei laengeren Listen
            # beginnt das Lesen nicht ganz oben. Die Grenzen (200 Schritte, 15 ohne neuen Sender, 0,35 s je Schritt)
            # sind am TCL eingestellt; langsamere Geraete brauchen mehr Zeit je Schritt.
            await self.key(*["KEYCODE_DPAD_UP"] * 20)
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        take(await self.dump())
        idle = 0
        for schritt in range(200):
            if schritt % 5 == 0:
                await self.nur_in_guide("Blaettern")
            n = take(await self.dump("KEYCODE_DPAD_DOWN", 0.35))
            idle = idle + 1 if n == 0 else 0
            if idle >= 15:
                break
        await self.close_guide()
        return current, chans, infos

    async def tune(self, num):
        await self.close_guide()
        if (app := await self.focus_app()) != TV_APP:
            raise RuntimeError(f"Fernsehbild nicht vorn ({app}) - schalte nicht um")
        # KOMPAT: Umschalten per Zifferntasten und OK mit 0,8 s Abstand, so wie es der TCL braucht. Andere Fernseher
        # schalten ohne OK nach einer Pause um, oder OK oeffnet eine Info- bzw. Senderliste.
        for d in str(num):                      # Ziffern einzeln, sonst wird die erste verschluckt
            await self.key(f"KEYCODE_{d}")
            await asyncio.sleep(0.8)
        await self.key("KEYCODE_DPAD_CENTER")
        await asyncio.sleep(4)

    async def aufraeumen(self):
        """Nach einem Fehler: Programmzeitschrift schliessen, falls sie noch offen ist (neue Verbindung)."""
        await self.trennen()
        try:
            await self.close_guide()
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Programmzeitschrift liess sich nach Fehler nicht schliessen: %s", e)

    async def app_abfragen(self, liste: bool = False) -> dict | None:
        """Zustand von der TV-App (ab 0.3.0); None, wenn sie nicht installiert ist oder nicht antwortet."""
        zusatz = " --es was liste" if liste else ""
        return broadcast_daten(await self.sh(f"am broadcast -a {ABFRAGEN_ACTION} -n {ABFRAGE_EMPFAENGER}{zusatz}"))

    async def app_umschalten(self, nr: int, text: str = "", grund: str = "") -> dict:
        """`grund`: Zeilen mit „|“ getrennt; zeigt die App bei ihrer Option „Umschaltgrund einblenden“ (ab 0.4.0)."""
        zusatz = (f" --es text {shell_text(text)}" if text else "") + (f" --es grund {shell_text(grund)}" if grund else "")
        antwort = broadcast_daten(await self.sh(
            f"am broadcast -a {UMSCHALTEN_ACTION} -n {ABFRAGE_EMPFAENGER} --es nr {int(nr)}{zusatz}"))
        if not antwort or not antwort.get("ok"):
            raise RuntimeError(f"TV-App hat nicht umgeschaltet: {antwort}")
        return antwort

    async def app_einstellen(self, name: str, wert: bool) -> dict:
        """Eine Einstellung der TV-App setzen (z. B. ausweichen_bevorzugt)."""
        if not re.fullmatch(r"[a-z_]{1,40}", name):   # landet ungequotet im Befehl
            raise ValueError(f"ungueltiger Name einer Einstellung: {name!r}")
        antwort = broadcast_daten(await self.sh(
            f"am broadcast -a {EINSTELLEN_ACTION} -n {ABFRAGE_EMPFAENGER} --es {name} {'true' if wert else 'false'}"))
        if not antwort or not antwort.get("ok"):
            raise RuntimeError(f"TV-App hat {name} nicht gesetzt: {antwort}")
        return antwort

    async def jetzt(self, cfg) -> dict:
        """Was laeuft gerade (fuer das TV-Protokoll, ohne Tasten). Ohne TV-App nur, ob das Fernsehbild vorn ist."""
        daten = await self.app_abfragen()
        if daten is None:
            app = await self.focus_app()
            return {"quelle": "adb", "fernsehbild_vorn": app == TV_APP, "vorn": app, "jetzt": None}
        x = daten.get("jetzt")
        x = x if gueltige_sender([x]) else None
        umschaltungen = daten.get("umschaltungen")
        return {"quelle": "app", "fernsehbild_vorn": daten.get("fernsehbild_vorn"), "vorn": daten.get("vorn"),
                "bildschirm_an": daten.get("bildschirm_an"), "werbung": daten.get("werbung"),
                "zapper_app": daten.get("zapper_laeuft"),
                # Einstellungen der TV-App (ab dem Stand nach 0.3.0), nur zur Anzeige
                "werbung_umgehen": daten.get("werbung_umgehen"), "ausweichen_bevorzugt": daten.get("ausweichen_bevorzugt"),
                "umschaltgrund_einblenden": daten.get("umschaltgrund_einblenden"),
                # ab der App-Version mit Logo-Zaehler: {"gelernt": n, "beobachtet": m}, sonst None
                "logos": logo_zaehler(daten.get("logos")),
                "werbe_sensor": daten.get("werbe_sensor") if isinstance(daten.get("werbe_sensor"), str) else None,
                # ab der App-Version mit Umschaltgruenden; nur die letzten 50 (Daten vom Fernseher)
                "umschaltungen": [u for u in umschaltungen[-50:] if isinstance(u, dict)]
                if isinstance(umschaltungen, list) else [],
                "jetzt": app_sendung(x, cfg) | {"folge": x.get("folge"), "beschreibung": x.get("beschreibung")}
                if x else None}

    async def durchgang_app(self, daten: dict, cfg, nur_lesen: bool) -> dict:
        """Durchgang ueber die TV-App: Liste lesen, bewerten, einmal umschalten, nachfragen."""
        scored = [app_sendung(x, cfg) for x in gueltige_sender(daten["liste"])]
        jetzt = (gueltige_sender([daten.get("jetzt")]) or [{}])[0]
        current = int(jetzt["nr"]) if jetzt.get("nr") is not None else None
        cur = next((x for x in scored if x["nr"] == current), {"nr": current, "punkte": 0})
        best = max(scored, key=lambda x: (x["punkte"], x["nr"] == current), default=None)
        aktion, neu, nachgelesen = "bleibt", None, None
        if soll_umschalten(cur, best) and not nur_lesen:
            await self.app_umschalten(best["nr"], grund=" | ".join(grund_zeilen(best, cfg)))
            aktion, neu = "umgeschaltet", best
            await asyncio.sleep(1)
            danach = await self.app_abfragen()
            if danach and gueltige_sender([danach.get("jetzt")]) and int(danach["jetzt"]["nr"]) == best["nr"]:
                nachgelesen = neu = app_sendung(danach["jetzt"], cfg)
        return {"aktion": aktion, "quelle": "app", "vorher": cur, "bester": best, "neu": neu,
                "passt_nach_umschalten": None if nachgelesen is None else nachgelesen["punkte"] > 0,
                "treffer": sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"]),
                "sender_gelesen": len(scored)}

    async def einblenden(self, text: str, ms: int = 6000) -> str:
        """Text im Fernsehbild zeigen. Ueber die TV-App, wenn sie den Auftrag annimmt, sonst als
        Android-Benachrichtigung (ob Google TV die sichtbar einblendet, ist geraeteabhaengig).
        -> "app" / "benachrichtigung"."""
        # KOMPAT: `cmd package query-receivers` und `cmd notification post` gibt es nicht auf jeder Android-Fassung
        # (seit wann, ist nicht nachgeschaut; unter Android 14 vorhanden). Google TV zeigt solche Benachrichtigungen
        # meist nicht im Bild. Ohne die TV-App aus android/ gibt es also oft keine sichtbare Einblendung.
        app = await self.sh(f"cmd package query-receivers --brief -a {EINBLENDEN_ACTION}")
        if "EinblendungEmpfaenger" in app:
            await self.sh(f"am broadcast -a {EINBLENDEN_ACTION} -n {EINBLENDEN_EMPFAENGER} "
                          f"--es text {shell_text(text)} --ei ms {max(1000, min(int(ms), 60000))}")
            return "app"
        await self.sh(f"cmd notification post -S bigtext -t {shlex.quote('TV-Zapper')} tvzapper {shell_text(text)}")
        return "benachrichtigung"

    async def verify(self, cand, cfg):
        """Nach dem Umschalten: Programmzeitschrift oeffnen (startet beim laufenden Sender) und
        die nun aktuelle Sendung samt Beschreibung neu bewerten."""
        await asyncio.sleep(3)
        nodes = await self.open_guide()
        rows, header, _ = self.guide(nodes)
        await self.close_guide()
        if not rows or rows[0][0] != cand["nr"]:
            return None
        num, name, prog = rows[0]
        return bewerte_sendung(num, name, prog, header, cfg)

    async def durchgang(self, cfg, nur_lesen=False) -> dict:
        """Ein Durchgang wie zapper.cycle(). Ergebnis-dict (aktion: uebersprungen/bleibt/umgeschaltet/...).
        Mit TV-App ab 0.3.0 ueber deren Schnittstelle, sonst ueber die Programmzeitschrift."""
        daten = await self.app_abfragen(liste=True)
        if daten is not None and gueltige_sender(daten.get("liste")):
            if not daten.get("fernsehbild_vorn"):
                return {"aktion": "uebersprungen", "quelle": "app", "app": daten.get("vorn")}
            if daten.get("zapper_laeuft") and not nur_lesen:
                # Zappen beide, schalten sie gegeneinander: dann bewertet nur die TV-App
                x = daten.get("jetzt")
                return {"aktion": "uebersprungen", "quelle": "app", "app": "Zapper der TV-App laeuft",
                        "vorher": app_sendung(x, cfg) if gueltige_sender([x]) else None}
            return await self.durchgang_app(daten, cfg, nur_lesen)
        app = await self.focus_app()
        if app not in (TV_APP, GUIDE_APP):
            return {"aktion": "uebersprungen", "app": app}
        try:
            current, chans, infos = await self.collect()
        except Exception:
            await self.aufraeumen()
            raise
        scored, cur, best = bewerte(current, chans, infos, cfg)
        aktion, neu, nachgelesen = "bleibt", None, None
        if soll_umschalten(cur, best) and not nur_lesen:
            # Nur einmal umschalten. Die Beschreibung ist erst nach dem Anwaehlen sicher aktuell -
            # danach nur nachlesen, nicht weiter herumschalten (naechster Durchgang entscheidet neu).
            await self.tune(best["nr"])
            aktion, neu = "umgeschaltet", best
            nachgelesen = await self.verify(best, cfg)
            if nachgelesen is not None:
                neu = nachgelesen
        return {"aktion": aktion, "vorher": cur, "bester": best, "neu": neu,
                "passt_nach_umschalten": None if nachgelesen is None else nachgelesen["punkte"] > 0,
                "treffer": sorted((x for x in scored if x["punkte"] > 0), key=lambda x: -x["punkte"]),
                "sender_gelesen": len(chans)}
