#!/usr/bin/env python3
"""
bmw_avrcp_analyze.py — Auswertung der Phase-(-1)-Probe.

Liest einen btmon-Mitschnitt und beantwortet die Messfragen -1.1, -1.2 und -1.5
maschinell. Der Interpretationsschluessel ist **vorab** festgeschrieben in
docs/archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md, Paket G1. Er wird hier angewendet,
nicht neu erfunden — genau das ist der Zweck: das Ergebnis soll nicht davon
abhaengen, was man sich beim Lesen der Rohdaten wuenscht.

Eingabe:
  - eine btsnoop-Datei (wird mit `btmon -r` dekodiert), oder
  - ein bereits dekodierter Textmitschnitt (laeuft auch ohne btmon,
    z. B. am Entwicklungsrechner)

Ausgabe:
  - JSON mit Befunden, Belegzeilen und Urteil
  - Markdown-Bericht als Vorlage fuer docs/fahrzeug/BMW-AVRCP-PROBE.md

Was dieses Skript NICHT kann:
  -1.3 (SDP-Feature-Bits) braucht die sdptool-Ausgaben, die das Aufnahmeskript
       getrennt ablegt. Sie werden hier nur eingebunden, nicht interpretiert.
  -1.4 (erscheinen die drei Zeilen im Display?) ist eine Sichtpruefung im
       Fahrzeug. Das Skript kann nur belegen, was PiDrive *gesendet* hat.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Interpretationsschluessel — vorab festgeschrieben (G1) ──────────────────
#
# Reihenfolge ist bedeutsam: die staerkste zutreffende Aussage gewinnt.

VERDICT_NO_CHANNEL = "kein_browsing_kanal"
VERDICT_PLAYER_LIST_ONLY = "nur_player_liste"
VERDICT_GREEN = "gruenes_licht"
VERDICT_STRONG_GREEN = "starkes_gruenes_licht"
VERDICT_CHANNEL_SILENT = "kanal_offen_aber_stumm"

INTERPRETATION = {
    VERDICT_NO_CHANNEL: {
        "beobachtung": "BMW oeffnet L2CAP PSM 0x001B nicht",
        "bedeutung": (
            "Browsing ist am NBT Evo nicht nutzbar. Ein echtes Listen-Menue "
            "faellt weg, der 3-Zeilen-Pfad bleibt Zielbild."
        ),
        "folge_gateway": "S3 gestrichen, S1 bleibt Zielbild. A17 entspannt sich.",
    },
    VERDICT_CHANNEL_SILENT: {
        "beobachtung": "Kanal wird geoeffnet, aber keine Browse-PDU beobachtet",
        "bedeutung": (
            "Kein Beweis in beide Richtungen. Moeglich ist, dass die "
            "Bedienschritte im Fahrzeug den Browse-Pfad nicht ausgeloest haben."
        ),
        "folge_gateway": "Messung wiederholen, Bedienschritte aus G1 Schritt 4 vollstaendig durchgehen.",
    },
    VERDICT_PLAYER_LIST_ONLY: {
        "beobachtung": "Kanal offen, nur GetFolderItems(scope=Media Player List)",
        "bedeutung": (
            "Das Fahrzeug prueft nur die Player-Liste. Noch kein Beweis fuer "
            "nutzbares Browsing."
        ),
        "folge_gateway": "S3 bleibt offen. Zweite Messreihe mit Titelliste im iDrive.",
    },
    VERDICT_GREEN: {
        "beobachtung": "BMW sendet SetBrowsedPlayer",
        "bedeutung": (
            "Gruenes Licht. Das Auto *will* browsen, BlueZ kann es nur nicht "
            "beantworten. Genau diese Luecke fuellt ein eigener "
            "AVRCP-Target-Stack auf dem ESP32."
        ),
        "folge_gateway": "S3 wird Zielbild, BTstack Standardoption, A18 wird scharf.",
    },
    VERDICT_STRONG_GREEN: {
        "beobachtung": "BMW sendet GetFolderItems(scope=Virtual Filesystem) oder ChangePath",
        "bedeutung": (
            "Starkes gruenes Licht, inklusive Hinweis auf die erwartete "
            "Attributliste und Seitengroesse."
        ),
        "folge_gateway": "S3 ist Zielbild. Seitengroesse aus den Rohdaten in A18 uebernehmen.",
    },
}

# ── Signaturen, die btmons AVCTP-Dekoder im Klartext ausgibt ────────────────
# Quelle: BlueZ monitor/avctp.c (pdu2str, scope2str).

BROWSE_PDUS = [
    "SetBrowsedPlayer",
    "GetFolderItems",
    "ChangePath",
    "GetItemAttributes",
    "PlayItem",
    "GetTotalNumberOfItems",
    "Search",
    "AddToNowPlaying",
]

CONTROL_PDUS = [
    "SetAddressedPlayer",
    "GetElementAttributes",
    "RegisterNotification",
    "GetCapabilities",
    "GetPlayStatus",
    "SetAbsoluteVolume",
]

SCOPE_STRINGS = {
    "Media Player List": 0x00,
    "Media Player Virtual Filesystem": 0x01,
    "Search": 0x02,
    "Now Playing": 0x03,
}

RE_DIRECTION = re.compile(r"^([<>])\s")
# btmon setzt den Zeitstempel rechtsbuendig an das ENDE der Kopfzeile, nicht an
# den Anfang. Mit -T zusaetzlich mit Datum. Beide Formen werden akzeptiert.
RE_TIMESTAMP = re.compile(r"(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{2}:\d{2}:\d{2}\.\d+)\s*$")
RE_PSM_REQUEST = re.compile(r"PSM:\s*(\d+)\s*\(0x([0-9a-fA-F]+)\)")
RE_PSM_CHANNEL = re.compile(r"\[PSM\s+(\d+)\b")
RE_AVRCP_PDU = re.compile(r"AVRCP:\s*([A-Za-z ]+?)\s*\(0x([0-9a-fA-F]{2})\)")
RE_AVCTP_KIND = re.compile(r"AVCTP\s+(Browsing|Control):\s*(Command|Response)")
RE_SCOPE = re.compile(r"Scope:\s*(.+?)\s*\(0x([0-9a-fA-F]+)\)")
# Je nach BlueZ-Version "Status: 0x0a (Invalid Scope)" oder umgekehrt.
RE_STATUS_A = re.compile(r"Status:\s*0x([0-9a-fA-F]+)\s*\((.+?)\)")
RE_STATUS_B = re.compile(r"Status:\s*([A-Za-z][A-Za-z ]+?)\s*\(0x([0-9a-fA-F]+)\)")
RE_PASSTHROUGH_OP = re.compile(r"Operation(?:\s+ID)?:\s*(.+?)\s*\(0x([0-9a-fA-F]+)\)")
RE_UID_COUNTER = re.compile(r"UIDCounter:\s*(\d+)")
RE_NUM_ITEMS = re.compile(r"NumberOfItems:\s*(\d+)")
# StartItem/EndItem verraten die vom Fahrzeug erwartete Seitengroesse — der
# unmittelbar verwertbare Wert fuer A18, falls Browsing genutzt wird.
RE_ITEM_RANGE = re.compile(r"(Start|End)Item:\s*0x([0-9a-fA-F]+)")

PSM_AVCTP_CONTROL = 23  # 0x0017
PSM_AVCTP_BROWSING = 27  # 0x001B


@dataclass
class Hit:
    """Eine Belegzeile. Rohtext bleibt erhalten, damit das Urteil pruefbar ist."""

    lineno: int
    direction: str  # "vom_bmw" | "zum_bmw" | "unbekannt"
    text: str
    ts: str = ""
    step: str = ""

    def __str__(self) -> str:
        pre = f"{self.ts} " if self.ts else ""
        st = f" [{self.step}]" if self.step else ""
        return f"L{self.lineno} {pre}{self.direction}{st}: {self.text}"


@dataclass
class Findings:
    quelle: str = ""
    zeilen_gelesen: int = 0

    psm_browsing_geoeffnet_von: Optional[str] = None
    psm_control_geoeffnet_von: Optional[str] = None
    psm_hits: list[Hit] = field(default_factory=list)

    browse_pdus: dict[str, int] = field(default_factory=dict)
    browse_pdu_hits: list[Hit] = field(default_factory=list)
    control_pdus: dict[str, int] = field(default_factory=dict)

    folder_item_scopes: dict[str, int] = field(default_factory=dict)
    scope_hits: list[Hit] = field(default_factory=list)

    browse_status_antworten: dict[str, int] = field(default_factory=dict)
    passthrough_ops: dict[str, int] = field(default_factory=dict)

    uid_counter_werte: list[int] = field(default_factory=list)
    item_anzahlen: list[int] = field(default_factory=list)
    angefragte_seitengroessen: list[int] = field(default_factory=list)

    urteil: str = ""
    urteil_begruendung: str = ""


def _decode(path: str) -> list[str]:
    """btsnoop -> Textzeilen. Bereits dekodierte Textdateien werden durchgelassen."""
    with open(path, "rb") as fh:
        magic = fh.read(8)

    if magic == b"btsnoop\x00":
        btmon = shutil.which("btmon")
        if not btmon:
            sys.exit(
                f"'{path}' ist ein btsnoop-Mitschnitt, aber btmon fehlt.\n"
                "Entweder btmon installieren (bluez), oder den Mitschnitt vorher\n"
                f"dekodieren:  btmon -r {path} -T > mitschnitt.txt"
            )
        # -T: absolute Zeitstempel, damit die Bedienschritte zuordenbar sind.
        res = subprocess.run(
            [btmon, "-r", path, "-T"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if res.returncode != 0 and not res.stdout:
            sys.exit(f"btmon konnte '{path}' nicht lesen:\n{res.stderr.strip()}")
        return res.stdout.splitlines()

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def _load_markers(path: Optional[str]) -> list[tuple[float, str]]:
    """Bedienschritte des Aufnahmeskripts, nach Zeit sortiert."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    out = []
    for m in data.get("schritte", []):
        try:
            out.append((float(m["ts"]), str(m["name"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out)


def _ts_to_epoch(ts_text: str, day0: float) -> Optional[float]:
    """btmon-Zeitstempel -> Epoch. Mit Datum (-T) exakt, ohne Datum ueber day0."""
    if not ts_text:
        return None
    parts = ts_text.split()
    clock = parts[-1]
    try:
        h, m, s = clock.split(":")
        secs = int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        return None
    if len(parts) == 2:  # Datum vorhanden
        try:
            tm = time.strptime(parts[0], "%Y-%m-%d")
            midnight = time.mktime(
                (tm.tm_year, tm.tm_mon, tm.tm_mday, 0, 0, 0, 0, 0, -1)
            )
            return midnight + secs
        except (ValueError, OverflowError):
            return None
    return day0 + secs if day0 else None


def _step_for(ts_text: str, markers: list[tuple[float, str]], day0: float) -> str:
    """Ordnet einem btmon-Zeitstempel den zuletzt begonnenen Bedienschritt zu."""
    if not markers:
        return ""
    absolute = _ts_to_epoch(ts_text, day0)
    if absolute is None:
        return ""
    name = ""
    for mts, mname in markers:
        if mts <= absolute:
            name = mname
        else:
            break
    return name


def analyse(path: str, marker_path: Optional[str] = None) -> Findings:
    lines = _decode(path)
    markers = _load_markers(marker_path)
    day0 = 0.0
    if markers:
        # Lokale Mitternacht des Messtages. btmon schreibt Lokalzeit, deshalb
        # nicht ueber Modulo 86400 rechnen — das ergaebe UTC-Mitternacht und
        # verschoebe die Zuordnung um den Zeitzonen-Offset.
        lt = time.localtime(markers[0][0])
        day0 = time.mktime(
            (lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)
        )

    f = Findings(quelle=os.path.abspath(path), zeilen_gelesen=len(lines))

    direction = "unbekannt"
    ts = ""
    pending_psm: Optional[int] = None
    avctp_kind = ""
    last_browse_pdu = ""
    last_browse_was_command = False

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()

        m = RE_DIRECTION.match(line)
        if m:
            # Kopfzeile eines Pakets: Richtung und ggf. Zeitstempel neu setzen.
            if "ACL Data RX" in line:
                direction = "vom_bmw"
            elif "ACL Data TX" in line:
                direction = "zum_bmw"
            else:
                direction = "vom_bmw" if m.group(1) == ">" else "zum_bmw"
            tm = RE_TIMESTAMP.search(line)
            ts = " ".join(p for p in tm.groups() if p) if tm else ""
            pending_psm = None
            avctp_kind = ""
            last_browse_pdu = ""
            last_browse_was_command = False
            continue

        step = _step_for(ts, markers, day0)

        def hit(text: str) -> Hit:
            return Hit(lineno=i, direction=direction, text=text.strip(), ts=ts, step=step)

        # ── L2CAP: wer oeffnet welchen PSM? ────────────────────────────────
        if "Connection Request" in line:
            pending_psm = -1  # naechste PSM-Zeile gehoert zu diesem Request
        pm = RE_PSM_REQUEST.search(line)
        if pm and pending_psm == -1:
            psm = int(pm.group(1))
            pending_psm = psm
            opener = direction  # Request kommt von der oeffnenden Seite
            if psm == PSM_AVCTP_BROWSING and f.psm_browsing_geoeffnet_von is None:
                f.psm_browsing_geoeffnet_von = opener
                f.psm_hits.append(hit(f"Connection Request PSM 27 (0x001b) — {opener}"))
            elif psm == PSM_AVCTP_CONTROL and f.psm_control_geoeffnet_von is None:
                f.psm_control_geoeffnet_von = opener
                f.psm_hits.append(hit(f"Connection Request PSM 23 (0x0017) — {opener}"))
            continue

        # Fallback: Datenkanaele nennen den PSM in der Channel-Zeile. Das belegt,
        # dass der Kanal benutzt wird, sagt aber nichts ueber den Oeffner.
        cm = RE_PSM_CHANNEL.search(line)
        if cm:
            psm = int(cm.group(1))
            if psm == PSM_AVCTP_BROWSING and f.psm_browsing_geoeffnet_von is None:
                f.psm_browsing_geoeffnet_von = "benutzt_oeffner_unbekannt"
                f.psm_hits.append(hit("Datenverkehr auf PSM 27, Oeffner nicht erfasst"))

        km = RE_AVCTP_KIND.search(line)
        if km:
            avctp_kind = km.group(1)
            last_browse_was_command = km.group(2) == "Command"
            continue

        # ── AVRCP-PDUs ────────────────────────────────────────────────────
        pm2 = RE_AVRCP_PDU.search(line)
        if pm2:
            name = pm2.group(1).strip().replace(" ", "")
            for known in BROWSE_PDUS:
                if known.lower() == name.lower():
                    f.browse_pdus[known] = f.browse_pdus.get(known, 0) + 1
                    f.browse_pdu_hits.append(hit(line))
                    last_browse_pdu = known
                    break
            else:
                for known in CONTROL_PDUS:
                    if known.lower() == name.lower():
                        f.control_pdus[known] = f.control_pdus.get(known, 0) + 1
                        break
            continue

        # ── Scope von GetFolderItems ──────────────────────────────────────
        sm = RE_SCOPE.search(line)
        if sm:
            scope_name = sm.group(1).strip()
            f.folder_item_scopes[scope_name] = f.folder_item_scopes.get(scope_name, 0) + 1
            f.scope_hits.append(hit(line))
            continue

        # ── Ablehnungen von BlueZ (erwartet, und genau der Beleg) ─────────
        # Nur Antworten auf dem Browsing-Kanal: auf dem Control-Kanal traegt
        # schon die AV/C-Zeile ein "Status:", das hier nichts zu suchen hat.
        if (
            "Status:" in line
            and last_browse_pdu
            and not last_browse_was_command
            and avctp_kind == "Browsing"
        ):
            sa = RE_STATUS_A.search(line)
            sb = RE_STATUS_B.search(line)
            text = sa.group(2).strip() if sa else (sb.group(1).strip() if sb else "")
            if text:
                label = f"{last_browse_pdu}: {text}"
                f.browse_status_antworten[label] = (
                    f.browse_status_antworten.get(label, 0) + 1
                )
                continue

        om = RE_PASSTHROUGH_OP.search(line)
        if om:
            op = om.group(1).strip()
            f.passthrough_ops[op] = f.passthrough_ops.get(op, 0) + 1
            continue

        um = RE_UID_COUNTER.search(line)
        if um:
            f.uid_counter_werte.append(int(um.group(1)))
        nm = RE_NUM_ITEMS.search(line)
        if nm:
            f.item_anzahlen.append(int(nm.group(1)))
        im = RE_ITEM_RANGE.search(line)
        if im and im.group(1) == "End":
            # EndItem ist 0-basiert und inklusiv -> Seitengroesse = Wert + 1.
            ende = int(im.group(2), 16)
            if 0 <= ende < 0xFFFF:
                f.angefragte_seitengroessen.append(ende + 1)

    _urteil(f)
    return f


def _urteil(f: Findings) -> None:
    """Interpretationsschluessel anwenden. Staerkste zutreffende Aussage gewinnt."""
    vfs = f.folder_item_scopes.get("Media Player Virtual Filesystem", 0)
    player_list = f.folder_item_scopes.get("Media Player List", 0)
    change_path = f.browse_pdus.get("ChangePath", 0)
    set_browsed = f.browse_pdus.get("SetBrowsedPlayer", 0)
    get_folder = f.browse_pdus.get("GetFolderItems", 0)

    if f.psm_browsing_geoeffnet_von is None:
        f.urteil = VERDICT_NO_CHANNEL
        f.urteil_begruendung = (
            "Kein Connection Request und kein Datenverkehr auf PSM 27 (0x001b) "
            "im gesamten Mitschnitt."
        )
        return

    if vfs or change_path:
        f.urteil = VERDICT_STRONG_GREEN
        teile = []
        if vfs:
            teile.append(f"GetFolderItems(Virtual Filesystem) {vfs}x")
        if change_path:
            teile.append(f"ChangePath {change_path}x")
        f.urteil_begruendung = " und ".join(teile) + "."
        return

    if set_browsed:
        f.urteil = VERDICT_GREEN
        antw = ", ".join(f"{k} ({v}x)" for k, v in f.browse_status_antworten.items())
        f.urteil_begruendung = f"SetBrowsedPlayer {set_browsed}x beobachtet." + (
            f" Antwort von BlueZ: {antw}." if antw else ""
        )
        return

    if get_folder and player_list:
        f.urteil = VERDICT_PLAYER_LIST_ONLY
        f.urteil_begruendung = (
            f"GetFolderItems {get_folder}x, ausschliesslich mit "
            f"scope=Media Player List ({player_list}x)."
        )
        return

    f.urteil = VERDICT_CHANNEL_SILENT
    f.urteil_begruendung = (
        "PSM 27 ist belegt, aber keine der Browse-PDUs aus G1 wurde beobachtet."
    )


# ── Berichte ────────────────────────────────────────────────────────────────


def _zaehl(d: dict) -> str:
    if not d:
        return "—"
    return ", ".join(f"`{k}` {v}x" for k, v in sorted(d.items(), key=lambda kv: -kv[1]))


def bericht_markdown(f: Findings, sdp_dir: Optional[str] = None) -> str:
    key = INTERPRETATION[f.urteil]
    L = []
    A = L.append

    A("# BMW-AVRCP-Probe — Ergebnis Phase (-1)")
    A("")
    A(f"**Gemessen:** {time.strftime('%Y-%m-%d %H:%M')}  ")
    A(f"**Mitschnitt:** `{f.quelle}` ({f.zeilen_gelesen} dekodierte Zeilen)  ")
    A("**Auftrag:** [../archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](../archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) Paket G1  ")
    A("**Auswertung:** `tools/bmw_avrcp_analyze.py` — Interpretationsschluessel vorab festgeschrieben")
    A("")
    A("---")
    A("")
    A("## Urteil")
    A("")
    A(f"### {key['beobachtung']}")
    A("")
    A(f"**Beleg:** {f.urteil_begruendung}")
    A("")
    A(f"**Bedeutung:** {key['bedeutung']}")
    A("")
    A(f"**Folge fuer das Gateway:** {key['folge_gateway']}")
    A("")
    A("> Ein negatives Ergebnis ist **wertvoll**, nicht enttaeuschend. Es spart im")
    A("> Gateway-Repo die Entscheidung fuer einen aufwendigen Stackwechsel.")
    A("")
    A("---")
    A("")
    A("## Messfragen")
    A("")
    A("| ID | Frage | Ergebnis |")
    A("|----|-------|----------|")
    browsing = f.psm_browsing_geoeffnet_von or "nicht beobachtet"
    A(f"| -1.1 | Wird PSM 0x001B (Browsing) vom BMW geoeffnet? | {browsing} |")
    A(f"| -1.2 | Kommen SetBrowsedPlayer / GetFolderItems / ChangePath? | {_zaehl(f.browse_pdus)} |")
    A("| -1.3 | SDP-Feature-Bits (59 Browsing, 60 Searching, 65 NowPlaying) | siehe Abschnitt SDP — **manuell auszuwerten** |")
    A("| -1.4 | Erscheinen Title/Artist/Album im iDrive? | **Sichtpruefung im Fahrzeug** — siehe unten |")
    A(f"| -1.5 | Pass-Through-Subset | {_zaehl(f.passthrough_ops)} |")
    A("")
    A("---")
    A("")
    A("## Rohbefunde")
    A("")
    A("### L2CAP-Kanaele")
    A("")
    A(f"- Control (PSM 23 / 0x0017): {f.psm_control_geoeffnet_von or 'nicht beobachtet'}")
    A(f"- Browsing (PSM 27 / 0x001B): {f.psm_browsing_geoeffnet_von or 'nicht beobachtet'}")
    A("")
    if f.psm_hits:
        A("```")
        for h in f.psm_hits[:20]:
            A(str(h))
        A("```")
        A("")
    A("### Browse-PDUs")
    A("")
    A(f"{_zaehl(f.browse_pdus)}")
    A("")
    if f.folder_item_scopes:
        A("**Scopes:** " + _zaehl(f.folder_item_scopes))
        A("")
    if f.browse_status_antworten:
        A("**Antworten von BlueZ:** " + _zaehl(f.browse_status_antworten))
        A("")
        A("Ablehnungen sind hier **erwartet** — BlueZ beantwortet target-seitig nur")
        A("die Media Player List und lehnt Virtual Filesystem / Search / Now Playing")
        A("mit `Invalid Scope` ab. Der Punkt, an dem BlueZ aufgibt, ist genau die")
        A("Luecke, die ein eigener AVRCP-Target-Stack fuellen wuerde.")
        A("")
    if f.browse_pdu_hits:
        A("<details><summary>Belegzeilen (erste 40)</summary>")
        A("")
        A("```")
        for h in f.browse_pdu_hits[:40]:
            A(str(h))
        A("```")
        A("")
        A("</details>")
        A("")
    A("### Control-PDUs")
    A("")
    A(f"{_zaehl(f.control_pdus)}")
    A("")
    if f.uid_counter_werte or f.item_anzahlen or f.angefragte_seitengroessen:
        A("### Seitengroesse und UID-Zaehler")
        A("")
        if f.angefragte_seitengroessen:
            A(f"- Vom BMW **angefragte** Seitengroesse (EndItem+1): "
              f"{sorted(set(f.angefragte_seitengroessen))}")
        if f.item_anzahlen:
            A(f"- `NumberOfItems` in den Antworten: {sorted(set(f.item_anzahlen))}")
        if f.uid_counter_werte:
            A(f"- `UIDCounter`: {sorted(set(f.uid_counter_werte))}")
        A("")
        A("Die angefragte Seitengroesse ist der unmittelbar verwertbare Wert: sie")
        A("geht bei S3 direkt in A18 ein und begrenzt, wie viele Eintraege der")
        A("ESP32 pro Antwort vorhalten muss.")
        A("")
    A("---")
    A("")
    A("## SDP (-1.3)")
    A("")
    if sdp_dir and os.path.isdir(sdp_dir):
        names = sorted(os.listdir(sdp_dir))
        if names:
            A("Abgelegt vom Aufnahmeskript:")
            A("")
            for n in names:
                A(f"- `{os.path.join(sdp_dir, n)}`")
        else:
            A("Keine SDP-Ausgaben abgelegt.")
    else:
        A("Keine SDP-Ausgaben uebergeben (`--sdp-dir`).")
    A("")
    A("Festzuhalten ist: AVRCP-Version aus dem Profile Descriptor, der rohe")
    A("`SupportedFeatures`-Wert, und — der verlaesslichste Hinweis — ob ein")
    A("**Additional Protocol Descriptor mit AVCTP-Browsing-PSM 0x001B** vorhanden")
    A("ist. Das ist ein eindeutiges Ja/Nein und nicht von der Bitnummerierung")
    A("abhaengig.")
    A("")
    A("---")
    A("")
    A("## Sichtpruefung im Fahrzeug (-1.4)")
    A("")
    A("Vom Skript **nicht** entscheidbar — hier eintragen, was das Display gezeigt hat:")
    A("")
    A("| Gesendet | Am iDrive sichtbar? | Feld |")
    A("|----------|---------------------|------|")
    A("| `xesam:title` | | |")
    A("| `xesam:artist` | | |")
    A("| `xesam:album` | | |")
    A("")
    A("Ohne diesen Abschnitt ist die Probe unvollstaendig: erscheinen die drei")
    A("Zeilen nicht, ist S1 als Produktziel gefaehrdet, und A17 eskaliert")
    A("unabhaengig vom Browsing-Ergebnis.")
    A("")
    return "\n".join(L) + "\n"


# ── Selbsttest ──────────────────────────────────────────────────────────────
#
# Die Mustererkennung haengt am Textformat von btmons AVCTP-Dekoder. Diese
# Auszuege sind nach BlueZ monitor/avctp.c gebaut und pruefen, dass jede Zeile
# des Interpretationsschluessels auch tatsaechlich erreichbar ist. Der Test
# ersetzt die Messung nicht — er stellt nur sicher, dass ein echter Mitschnitt
# nicht stillschweigend als "kein Browsing" durchfaellt, weil ein Muster
# nicht greift.

_FIXTURE_KOPF = """\
= Note: Bluetooth subsystem version 2.22                              0.000000
< ACL Data TX: Handle 3585 flags 0x00 dlen 12          2026-09-15 16:00:01.100000
      L2CAP: Connection Request (0x02) ident 2 len 4
        PSM: 23 (0x0017)
        Source CID: 64
> ACL Data RX: Handle 3585 flags 0x02 dlen 16          2026-09-15 16:00:01.200000
      Channel: 64 len 12 [PSM 23 mode 0] {chan 1}
        AVCTP Control: Command: type 0x00 label 0 PID 0x110e
          AV/C: Control: address 0x48 opcode 0x7c
            Subunit: Panel
            Opcode: Passthrough (0x7c)
            Operation: Play (0x44)
            Press: Pressed (0)
> ACL Data RX: Handle 3585 flags 0x02 dlen 20          2026-09-15 16:00:02.000000
      Channel: 64 len 16 [PSM 23 mode 0] {chan 1}
        AVCTP Control: Command: type 0x00 label 1 PID 0x110e
          AV/C: Status: address 0x48 opcode 0x00
            Opcode: Vendor Dependent (0x00)
            AVRCP: GetElementAttributes (0x20) pt Single len 0x0009
"""

_FIXTURE_BROWSE_KANAL = """\
> ACL Data RX: Handle 3585 flags 0x02 dlen 12          2026-09-15 16:01:00.000000
      L2CAP: Connection Request (0x02) ident 5 len 4
        PSM: 27 (0x001b)
        Source CID: 65
"""

_FIXTURE_PLAYER_LISTE = """\
> ACL Data RX: Handle 3585 flags 0x02 dlen 22          2026-09-15 16:01:05.000000
      Channel: 65 len 18 [PSM 27 mode 0] {chan 2}
        AVCTP Browsing: Command: type 0x00 label 2 PID 0x110e
          AVRCP: GetFolderItems (0x71) len 0x000a
            Scope: Media Player List (0x00)
            StartItem: 0x00000000
            EndItem: 0x00000004
            AttributeCount: 0x00
"""

_FIXTURE_SET_BROWSED = """\
> ACL Data RX: Handle 3585 flags 0x02 dlen 14          2026-09-15 16:01:10.000000
      Channel: 65 len 10 [PSM 27 mode 0] {chan 2}
        AVCTP Browsing: Command: type 0x00 label 3 PID 0x110e
          AVRCP: SetBrowsedPlayer (0x70) len 0x0002
            PlayerID: 1 (0x0001)
< ACL Data TX: Handle 3585 flags 0x00 dlen 13          2026-09-15 16:01:10.050000
      Channel: 65 len 9 [PSM 27 mode 0] {chan 2}
        AVCTP Browsing: Response: type 0x00 label 3 PID 0x110e
          AVRCP: SetBrowsedPlayer (0x70) len 0x0001
            Status: 0x0a (Invalid Scope)
"""

_FIXTURE_VFS = """\
> ACL Data RX: Handle 3585 flags 0x02 dlen 22          2026-09-15 16:01:20.000000
      Channel: 65 len 18 [PSM 27 mode 0] {chan 2}
        AVCTP Browsing: Command: type 0x00 label 4 PID 0x110e
          AVRCP: GetFolderItems (0x71) len 0x000a
            Scope: Media Player Virtual Filesystem (0x01)
            StartItem: 0x00000000
            EndItem: 0x00000031
            AttributeCount: 0x00
< ACL Data TX: Handle 3585 flags 0x00 dlen 30          2026-09-15 16:01:20.060000
      Channel: 65 len 26 [PSM 27 mode 0] {chan 2}
        AVCTP Browsing: Response: type 0x00 label 4 PID 0x110e
          AVRCP: GetFolderItems (0x71) len 0x0016
            Status: 0x04 (Invalid Scope)
            UIDCounter: 0
            NumberOfItems: 0
"""

_SELFTESTS = [
    ("kein Browsing-Kanal", _FIXTURE_KOPF, VERDICT_NO_CHANNEL),
    ("Kanal offen, stumm", _FIXTURE_KOPF + _FIXTURE_BROWSE_KANAL, VERDICT_CHANNEL_SILENT),
    (
        "nur Player-Liste",
        _FIXTURE_KOPF + _FIXTURE_BROWSE_KANAL + _FIXTURE_PLAYER_LISTE,
        VERDICT_PLAYER_LIST_ONLY,
    ),
    (
        "SetBrowsedPlayer",
        _FIXTURE_KOPF + _FIXTURE_BROWSE_KANAL + _FIXTURE_PLAYER_LISTE + _FIXTURE_SET_BROWSED,
        VERDICT_GREEN,
    ),
    (
        "Virtual Filesystem",
        _FIXTURE_KOPF + _FIXTURE_BROWSE_KANAL + _FIXTURE_SET_BROWSED + _FIXTURE_VFS,
        VERDICT_STRONG_GREEN,
    ),
]


def selbsttest() -> int:
    import tempfile

    fehler = 0
    print("Selbsttest der Mustererkennung")
    print("=" * 62)

    for name, text, erwartet in _SELFTESTS:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(text)
            pfad = tf.name
        try:
            f = analyse(pfad)
            ok = f.urteil == erwartet
            print(f"  [{'ok ' if ok else 'FEHL'}] {name:24s} -> {f.urteil}")
            if not ok:
                print(f"         erwartet: {erwartet}")
                print(f"         Begruendung: {f.urteil_begruendung}")
                fehler += 1
        finally:
            os.unlink(pfad)

    # Nebenbefunde, die in den Bericht gehen, ebenfalls pruefen.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(_FIXTURE_KOPF + _FIXTURE_BROWSE_KANAL + _FIXTURE_SET_BROWSED + _FIXTURE_VFS)
        pfad = tf.name
    try:
        f = analyse(pfad)
        pruefungen = [
            ("Browsing-Kanal vom BMW geoeffnet", f.psm_browsing_geoeffnet_von == "vom_bmw"),
            ("Control-Kanal von uns geoeffnet", f.psm_control_geoeffnet_von == "zum_bmw"),
            ("SetBrowsedPlayer gezaehlt", f.browse_pdus.get("SetBrowsedPlayer") == 2),
            ("GetElementAttributes erkannt", "GetElementAttributes" in f.control_pdus),
            ("Pass-Through 'Play' erkannt", "Play" in f.passthrough_ops),
            ("Scope Virtual Filesystem erkannt",
             "Media Player Virtual Filesystem" in f.folder_item_scopes),
            ("BlueZ-Ablehnung erfasst", any(
                "Invalid Scope" in k for k in f.browse_status_antworten)),
            ("Seitengroesse 50 erkannt", 50 in f.angefragte_seitengroessen),
        ]
        for label, ok in pruefungen:
            print(f"  [{'ok ' if ok else 'FEHL'}] {label}")
            if not ok:
                fehler += 1
    finally:
        os.unlink(pfad)

    print("=" * 62)
    if fehler:
        print(f"{fehler} Pruefung(en) fehlgeschlagen.")
        print("Die Mustererkennung passt nicht zum btmon-Format dieser Version.")
        print("Vor der Fahrzeugmessung klaeren — sonst faellt ein echter")
        print("Mitschnitt stillschweigend als 'kein Browsing' durch.")
        return 1
    print("Alle Pruefungen bestanden.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Auswertung der Phase-(-1)-Probe (Paket G1).",
        epilog="Aufnahme: tools/bmw_avrcp_probe.sh",
    )
    ap.add_argument("mitschnitt", nargs="?",
                    help="btsnoop-Datei oder dekodierter btmon-Text")
    ap.add_argument("--selftest", action="store_true",
                    help="Mustererkennung gegen synthetische btmon-Auszuege pruefen")
    ap.add_argument("--marker", help="Bedienschritte des Aufnahmeskripts (JSON)")
    ap.add_argument("--sdp-dir", help="Verzeichnis mit den sdptool-Ausgaben")
    ap.add_argument("--json", help="Befunde als JSON hierhin schreiben")
    ap.add_argument("--markdown", help="Bericht hierhin schreiben (sonst stdout)")
    args = ap.parse_args()

    if args.selftest:
        return selbsttest()

    if not args.mitschnitt:
        ap.error("Mitschnitt fehlt (oder --selftest verwenden)")

    if not os.path.exists(args.mitschnitt):
        print(f"Mitschnitt nicht gefunden: {args.mitschnitt}", file=sys.stderr)
        return 2

    f = analyse(args.mitschnitt, args.marker)

    if args.json:
        payload = asdict(f)
        payload["interpretation"] = INTERPRETATION[f.urteil]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"JSON:     {args.json}", file=sys.stderr)

    bericht = bericht_markdown(f, args.sdp_dir)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(bericht)
        print(f"Bericht:  {args.markdown}", file=sys.stderr)
    else:
        print(bericht)

    print("", file=sys.stderr)
    print(f"Urteil:   {f.urteil}", file=sys.stderr)
    print(f"Beleg:    {f.urteil_begruendung}", file=sys.stderr)

    # Exit-Code trägt das Ergebnis, damit die Probe automatisierbar bleibt.
    #   0 = Browsing nutzbar (gruen oder stark gruen)
    #   1 = kein Browsing-Kanal
    #   3 = unklar, Messung wiederholen
    if f.urteil in (VERDICT_GREEN, VERDICT_STRONG_GREEN):
        return 0
    if f.urteil == VERDICT_NO_CHANNEL:
        return 1
    return 3


if __name__ == "__main__":
    sys.exit(main())
