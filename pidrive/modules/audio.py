"""
modules/audio.py — Zentraler Audio-Pfad für PiDrive
===========================================================

SCHNITTSTELLENBESCHREIBUNG (v0.9.29)
────────────────────────────────────

## Wer ruft was auf?

    main_core.py        → get_mpv_args(), set_output(), apply_startup_volume(),
                          volume_up(), volume_down(), is_radio_source()
    modules/dab.py      → get_mpv_args(settings, source="dab")
    modules/fm.py       → get_mpv_args(settings, source="fm")
    modules/webradio.py → get_mpv_args(settings, source="webradio")
    modules/bluetooth.py→ get_mpv_args(settings, source="bt_auto_reconnect")
    webui.py            → read_last_decision_file(), get_sink_volume(),
                          volume_up(), volume_down()

## Öffentliche API

    get_mpv_args(settings, source) → list
        Zentrale Routing-Entscheidung. Immer vor mpv/welle-cli-Start aufrufen.
        Schreibt Entscheidung nach /tmp/pidrive_audio_state.json.
        Rückgabe: [env_prefix, "--ao=...", "--alsa-device=..."] oder [env, "--ao=pulse"]

        WICHTIG FÜR DAB/FM: Die zurückgegebenen mpv-Args werden von welle-cli
        ignoriert! Der einzig relevante SIDE-EFFECT ist _set_pi_output_klinke()
        → amixer setzt Card 1 als physischen Ausgang.
        welle-cli nutzt immer den ALSA-Default aus /etc/asound.conf.

    set_output(mode, settings)
        Schaltet Ausgang manuell: klinke / hdmi / bt / all.
        Ändert: Audio Default-Sink (PipeWire/PA) + amixer.
        NICHT geändert: Laufende welle-cli/mpv-Prozesse. Diese müssen neu gestartet
        werden damit der neue Ausgang wirkt.
        → "Klinke"-Button hat KEINEN Live-Effekt auf laufendes welle-cli (DAB/FM).

    apply_startup_volume(settings)
        Boot: Alle PA-Sinks + amixer Card 1 auf gespeichertem Volume (max 100%).

    volume_up(settings) / volume_down(settings)
        +5% / -5% auf aktiven PA-Sink + amixer Card 1. Speichert in settings.json.

    is_radio_source(radio_type) → bool
        True wenn FM | DAB | WEB | SCANNER.

    get_last_decision() / read_last_decision_file() → dict
        Letzte Routing-Entscheidung prozessübergreifend aus
        /tmp/pidrive_audio_state.json. Felder: requested, effective, reason, sink, source.

## Audio-Pfade nach Quelle

    Quelle      Ausgabe         Pfad
    ──────────────────────────────────────────────────────────────
    DAB         ALSA hw:{_get_headphone_card()},0    welle-cli -p NAME (AlsaProgrammeHandler)
                               kein PA-Routing — ALSA-direkt
    FM          ALSA hw:{_get_headphone_card()},0    rtl_fm | mpv --ao=alsa --alsa-device=hw:{_get_headphone_card()},0
                               kein PA-Routing — raw PCM direkt
    Scanner     ALSA hw:N,0    rtl_fm | mpv --ao=alsa
    Webradio    PipeWire-Pulse mpv --ao=pulse PULSE_SERVER=...
    Spotify     PipeWire-Pulse librespot --device pulse
    BT (A2DP)   PipeWire       WirePlumber → bluez_sink.* automatisch

    # hw:X,0 = Klinken-Karte (dynamisch per _get_headphone_card())
    hw:0,0 = Card 0 = bcm2835 HDMI — NIEMALS für PiDrive-Audio verwenden

## State Machine (source_state.py) Rolle

    source_state ist KEIN Regler — nur Zustandsspiegel:
    - get_mpv_args() setzt set_audio_route() als SIDE-EFFECT
    - source_state.get_audio_route() zeigt Stand NACH letzter Entscheidung
    - Um Audio zu wechseln: set_output() oder get_mpv_args() aufrufen,
      NICHT source_state direkt manipulieren

## Bekannte Einschränkungen

    - "Klinke"-Button während DAB/FM läuft: ändert Audio-Routing, aber welle-cli/rtl_fm
      laufen ALSA-direkt. Wirkung erst nach Stop + Neustart der Quelle.
    - volume > 100%: wird beim Boot auf 90% korrigiert (settings.json Altlasten).
    - BT + DAB: funktioniert nur wenn asound.conf default=card 1 korrekt gesetzt
      und Sink-Input nach BT-Connect verschoben wird.
"""

try:
    from modules.platform import CAPS as _CAPS
except ImportError:
    _CAPS = None

import os
import json
import re
import subprocess
import time
import ipc
import log
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"

# v0.10.55: Sink-Cache (2s TTL)
_sink_cache: list = []
_sink_cache_ts: float = 0.0
_SINK_CACHE_TTL: float = 2.0
AUDIO_STATE_FILE = "/tmp/pidrive_audio_state.json"


def _get_headphone_card() -> int:
    """
    Pi 3B Kartenindex für die analoge Klinke ermitteln (v0.9.9).

    Auf aktuellen Pi OS (Kernel ≥ 5.x):
      Card 0 = bcm2835 HDMI 1  (kein analoger Ausgang!)
      Card 1 = bcm2835 Headphones  ← Klinke

    Auf sehr alten Kerneln war Card 0 der kombinierte Ausgang (numid=3-Switch).
    Wir suchen explizit nach der Headphones-Karte.
    """
    try:
        import subprocess as _sp
        r = _sp.run("aplay -l 2>/dev/null", shell=True,
                    capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            low = line.lower()
            if "headphones" in low or ("card" in low and "analog" in low):
                # Zeile: "Karte 1: Headphones [bcm2835 Headphones]..."
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1].rstrip(":"))
                    except ValueError:
                        pass
    except Exception:
        pass
    # Fallback über CAPS wenn verfügbar, sonst /proc/cpuinfo
    if _CAPS and _CAPS.get("alsa_card") is not None:
        return _CAPS["alsa_card"]
    try:
        if 'raspberry pi' in open('/proc/cpuinfo').read().lower():
            return 1
    except Exception:
        pass
    return 0


def _set_pi_output_klinke():
    """
    Pi 3B: ALSA-Ausgang auf 3.5mm Klinke schalten (v0.9.9).

    Root Cause v0.9.8 und früher: amixer -c 0 → HDMI-Karte!
    Auf modernem Pi OS (Kernel ≥ 5.x):
      Card 0 = bcm2835 HDMI   → alles was wir vorher taten, ging zu HDMI
      Card 1 = bcm2835 Headphones = Klinke

    Fix: _get_headphone_card() sucht die richtige Karte, dann amixer -c N.
    """
    try:
        import subprocess as _sp
        card = _get_headphone_card()
        # Volume + UNMUTE auf der richtigen Karte
        _sp.run(f"amixer -q -c {card} sset 'PCM' 85% unmute 2>/dev/null",
                shell=True, timeout=3)
        log.info(f"[AUDIO] Pi Ausgang: Klinke (card {card} PCM unmute 85%)")
    except Exception as e:
        log.warn("[AUDIO] amixer klinke: " + str(e))


def _set_pi_output_hdmi():
    """Pi 3B: ALSA-Ausgang auf HDMI (Card 0 auf modernem Pi OS)."""
    try:
        import subprocess as _sp
        # HDMI ist immer Card 0 auf Pi 3B
        _sp.run("amixer -q -c 0 sset 'PCM' 85% unmute 2>/dev/null",
                shell=True, timeout=3)
        log.info("[AUDIO] Pi Ausgang: HDMI (card 0 PCM unmute 85%)")
    except Exception as e:
        log.warn("[AUDIO] amixer hdmi: " + str(e))

_last_vol_save: float = 0.0  # Debounce: Lautstärke-Speicherung max. 1×/2s

_last_decision = {
    "requested": "auto",
    "effective": "",
    "reason":    "",
    "sink":      "",
    "source":    "",
    "ts":        0,
}


def _write_audio_state():
    """Schreibt letzte Entscheidung atomar in shared state file."""
    try:
        tmp = AUDIO_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_last_decision, f, indent=2, ensure_ascii=False)
        os.replace(tmp, AUDIO_STATE_FILE)
    except Exception:
        pass


def prepare_audio_route(settings=None, source: str = "") -> dict:
    """v0.10.55: decide() + apply() — Rückgabe: Decision-Dict."""
    d = decide_audio_route(settings=settings, source=source)
    if d.get("pa_ok", True):
        apply_audio_route(d)
    return d

def get_player_args(settings=None, source: str = "") -> list:
    """Alias für get_mpv_args() — rückwärtskompatibel."""
    return get_mpv_args(settings=settings, source=source)

def get_last_decision() -> dict:
    """In-Prozess-Zustand (fuer Strict-Mode-Guards in fm/dab/webradio)."""
    return dict(_last_decision)



def get_audio_status() -> dict:
    """Semantisch reiches Status-Dict für pidrivectl audio status / WebUI.
    Unterscheidet: backend_ok, sink_present, bt_connected, route.
    """
    import subprocess as _sp

    bt_connected = False
    sink_name    = ""
    sink_present = False
    degraded_reason = ""

    # BT-Verbindung prüfen
    try:
        _r = _sp.run(["bluetoothctl", "info"], capture_output=True, text=True, timeout=3)
        bt_connected = "Connected: yes" in _r.stdout
    except Exception:
        pass

    # PA-Sink prüfen
    try:
        _sinks = _list_sinks()
        sink_present = len(_sinks) > 0
        _s0 = _sinks[0] if _sinks else {}
        sink_name = _s0.get("name", str(_s0)) if isinstance(_s0, dict) else str(_s0)
    except Exception:
        pass

    # PA Backend
    pa_ok = _pa_ok()

    d = get_last_decision()
    requested  = d.get("requested", "auto")
    effective  = d.get("effective", "none")
    reason     = d.get("reason", "")

    if not pa_ok:
        degraded_reason = "audio_server_fehlt"
    elif not sink_present and not bt_connected:
        degraded_reason = "kein_audiogeraet"
    elif not sink_present and bt_connected:
        degraded_reason = "bt_verbunden_kein_a2dp_sink"
    elif not sink_present:
        degraded_reason = "kein_sink"

    return {
        "backend_ok":     pa_ok,
        "sink_present":   sink_present,
        "sink":           sink_name,
        "bt_connected":   bt_connected,
        "requested":      requested,
        "effective":      effective,
        "reason":         reason,
        "degraded":       bool(degraded_reason),
        "degraded_reason": degraded_reason,
    }


def read_last_decision_file() -> dict:
    """Liest shared state file — prozessuebergreifend fuer WebUI."""
    try:
        with open(AUDIO_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _pa_ok() -> bool:
    """
    v0.10.55: Socket-Datei zuerst prüfen (~0.1ms statt ~150ms systemctl subprocess).
    Falls Socket existiert: PA läuft definitiv. Sonst: systemctl als Fallback.
    """
    # PipeWire-Pulse oder PulseAudio — Socket-Existenz ist entscheidend
    if os.path.exists("/var/run/pulse/native"):
        return True
    if _run("systemctl is-active pipewire-pulse 2>/dev/null", 3) == "active":
        return True
    return _run("systemctl is-active pulseaudio 2>/dev/null", 3) == "active"


def _list_sinks(force: bool = False) -> list:
    """v0.10.55: Mit 2s TTL-Cache."""
    global _sink_cache, _sink_cache_ts
    import time as _t
    now = _t.time()
    if not force and _sink_cache and (now - _sink_cache_ts) < _SINK_CACHE_TTL:
        return _sink_cache
    out = _run(PA_ENV + " pactl list sinks short 2>/dev/null", 4)
    sinks = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sinks.append({"id": parts[0], "name": parts[1], "raw": line})
    _sink_cache = sinks; _sink_cache_ts = now
    return sinks


def invalidate_sink_cache():
    """v0.10.55: Cache nach BT-Connect invalidieren."""
    global _sink_cache_ts
    _sink_cache_ts = 0.0


def get_bt_sink(retry: int = 1) -> str:
    """
    Gibt den BT A2DP Sink zurück.
    Bei PipeWire: WirePlumber lädt BT automatisch.
    Bei Legacy-PA: versucht module-bluetooth-discover nachzuladen.
    """
    import time as _t
    for attempt in range(max(1, retry)):
        for s in _list_sinks():
            if "bluez_sink." in s["name"] and ".a2dp_sink" in s["name"]:
                return s["name"]
        if attempt < retry - 1:
            _t.sleep(1)

    # Kein A2DP-Sink gefunden — versuche BT-Module nachzuladen
    try:
        _pa = PA_ENV + " pactl load-module module-bluetooth-discover 2>/dev/null"
        subprocess.run(_pa, shell=True, capture_output=True, timeout=3)
        _t.sleep(1)
        for s in _list_sinks():
            if "bluez_sink." in s["name"] and ".a2dp_sink" in s["name"]:
                log.info("[AUDIO] A2DP-Sink nach load-module gefunden (Legacy-PA)")
                return s["name"]
    except Exception:
        pass
    return ""


def is_radio_source(radio_type: str) -> bool:
    """True wenn eine Radio-Quelle läuft die nach BT-Wechsel neugestartet werden soll."""
    return str(radio_type or "").upper() in ("FM", "DAB", "WEB", "SCANNER")


def _sink_is_hdmi(sink_name: str) -> bool:
    """
    Card 0 = HDMI, Card 1 = Headphones (Klinke) auf Pi 3B mit modernem Pi OS.
    alsa_output.0.stereo-fallback → HDMI
    alsa_output.1.stereo-fallback → Klinke
    Der Name enthält KEIN 'hdmi' — Card-Nummer ist der einzig zuverlässige Indikator.
    """
    n = sink_name.lower()
    if "hdmi" in n:
        return True
    # .0. im Namen = Card 0 = HDMI auf Pi 3B
    if re.search(r'alsa_output\.0\.', sink_name):
        return True
    return False


def _ensure_klinke_sink() -> bool:
    """
    Lädt Card 1 (Headphones/Klinke) als Audio-Sink falls noch nicht vorhanden.
    ALSA-Karte dynamisch via pactl laden (PipeWire-kompatibel).
    Card 1 wurde nie als PA-Sink geladen → kein Klinken-Audio möglich.
    """
    sinks = _list_sinks()
    # Prüfen ob ein Nicht-HDMI alsa_output Sink existiert
    for s in sinks:
        n, r = s["name"].lower(), s["raw"].lower()
        if "hdmi" not in n and "hdmi" not in r and "alsa_output" in s["name"]:
            return True  # Klinken-Sink vorhanden
    # Klinken-Karte dynamisch laden (Pi 4: card 0, Pi 3B: meist card 1)
    try:
        card = _get_headphone_card()
        r = _run(
            PA_ENV + f" pactl load-module module-alsa-card device_id={card} 2>/dev/null",
            timeout=5
        )
        log.info(f"[AUDIO] _ensure_klinke_sink: module-alsa-card device_id={card} geladen")
        import time as _t; _t.sleep(1)
        return True
    except Exception as e:
        log.warn("[AUDIO] _ensure_klinke_sink: " + str(e))
        return False


def get_alsa_sink() -> str:
    """
    Gibt den ALSA Klinken-Sink zurück (v0.9.13).
    Card 0 = HDMI, Card 1 = Headphones/Klinke.
    alsa_output.0.* wird via _sink_is_hdmi() ausgeschlossen.
    """
    sinks = _list_sinks()
    for s in sinks:
        if "alsa_output" in s["name"] and not _sink_is_hdmi(s["name"]):
            return s["name"]
    return ""


def get_hdmi_sink() -> str:
    for s in _list_sinks():
        n = s["name"].lower()
        r = s["raw"].lower()
        if "hdmi" in n or "hdmi" in r:
            return s["name"]
    return ""


def unsuspend_sink(sink_name: str = "") -> bool:
    """PipeWire/Pulse: SUSPENDED-Sink aktivieren (welle-cli/mpv brauchen aktiven Sink)."""
    sink = sink_name or get_alsa_sink() or get_bt_sink()
    if not sink:
        return False
    try:
        import shlex as _sq
        r = subprocess.run(
            PA_ENV + " pactl suspend-sink " + _sq.quote(sink) + " 0",
            shell=True, capture_output=True, text=True, timeout=4,
        )
        if r.returncode == 0:
            log.info("[AUDIO] unsuspend sink -> " + sink)
            return True
        log.warn("[AUDIO] unsuspend failed: " + (r.stderr or "").strip()[:80])
    except Exception as e:
        log.warn("[AUDIO] unsuspend_sink: " + str(e))
    return False


def set_default_sink(sink_name: str) -> bool:
    """
    Setzt Audio Default-Sink UND verschiebt laufende Sink-Inputs.
    Ohne move-sink-input hat ein bereits laufender mpv-Prozess keinen Ton auf
    dem neuen Sink — er bleibt auf dem alten verbunden.
    """
    if not sink_name:
        return False
    try:
        r = subprocess.run(
            PA_ENV + " pactl set-default-sink " + sink_name,
            shell=True, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            log.info("[AUDIO] default sink -> " + sink_name)
        else:
            log.warn("[AUDIO] set-default-sink failed: " + sink_name +
                     " | " + (r.stderr or "").strip()[:60])
            return False
        # Laufende Streams auf neuen Sink verschieben (verhindert "kein Ton" bei mpv)
        try:
            ri = subprocess.run(
                PA_ENV + " pactl list sink-inputs short 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=4
            )
            moved = 0
            for line in ri.stdout.splitlines():
                parts = line.split()
                if parts:
                    mv = subprocess.run(
                        PA_ENV + f" pactl move-sink-input {parts[0]} {sink_name}",
                        shell=True, capture_output=True, text=True, timeout=4
                    )
                    if mv.returncode == 0:
                        moved += 1
            if moved:
                log.info(f"[AUDIO] moved {moved} sink-input(s) -> {sink_name}")
        except Exception as em:
            log.warn("[AUDIO] move-sink-input: " + str(em))
        return True
    except Exception as e:
        log.error("[AUDIO] set_default_sink: " + str(e))
        return False


def _remember_decision(requested, effective, reason, sink, source):
    _last_decision.update({
        "requested": requested,
        "effective": effective,
        "reason":    reason,
        "sink":      sink or "",
        "source":    source or "",
        "ts":        int(time.time()),
    })
    _write_audio_state()



def decide_audio_route(settings=None, source: str = "") -> dict:
    """
    v0.10.55: Pure Policy — keine Side-Effects.
    Entscheidet requested→effective Audio-Route und gibt ein Decision-Dict zurück.
    Für Diagnose, Tests und explizite Kontrolle verwendbar.
    """
    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    requested = settings.get("audio_output", "auto")

    if not _pa_ok():
        return {
            "requested": requested, "effective": "none",
            "reason": "pulseaudio_inactive", "sink": "",
            "source": source, "pa_ok": False,
        }

    if requested in ("klinke", "auto"):
        _ensure_klinke_sink()

    bt_sink   = get_bt_sink()
    alsa_sink = get_alsa_sink()
    hdmi_sink = get_hdmi_sink()

    if requested == "bt":
        if bt_sink:
            effective, reason, sink = "bt",     "bt_requested",               bt_sink
        else:
            effective, reason, sink = "klinke", "bt_requested_no_a2dp_sink",  alsa_sink

    elif requested == "hdmi":
        if hdmi_sink:
            effective, reason, sink = "hdmi",   "hdmi_requested",             hdmi_sink
        else:
            effective, reason, sink = "klinke", "hdmi_requested_no_hdmi_sink", alsa_sink

    elif requested == "klinke":
        effective, reason, sink = "klinke", "klinke_requested", alsa_sink

    else:  # auto
        if not bt_sink:
            bt_sink = get_bt_sink(retry=3)
        if bt_sink:
            effective, reason, sink = "bt",     "a2dp_sink_available",  bt_sink
        else:
            effective, reason, sink = "klinke", "no_a2dp_sink",         alsa_sink

    # Null-Sink (Container/Entwicklung) → virtueller Audio-Ausgang
    if not sink:
        import subprocess as _pctl
        try:
            _r = _pctl.run("pactl --server unix:/var/run/pulse/native list sinks short 2>/dev/null",
                           shell=True, capture_output=True, text=True, timeout=2)
            if "null" in _r.stdout.lower() or "auto_null" in _r.stdout.lower():
                # PipeWire: auto_null; PA: pidrive_null
                _null_name = "auto_null" if "auto_null" in _r.stdout else "pidrive_null"
                effective, reason, sink = "virtual", "null_sink_container", _null_name
            else:
                effective, reason = "none", "no_sink_available"
        except Exception:
            effective, reason = "none", "no_sink_available"

    return {
        "requested": requested, "effective": effective,
        "reason":    reason,    "sink":      sink or "",
        "source":    source,    "pa_ok":     True,
    }


def apply_audio_route(decision: dict):
    """
    v0.10.55: Side-Effects aus decide_audio_route() anwenden.
    Setzt PA Default-Sink, amixer, source_state — getrennt von der Policy-Logik.
    """
    effective = decision.get("effective", "none")
    sink      = decision.get("sink", "")
    source    = decision.get("source", "")

    if sink:
        set_default_sink(sink)

    if effective == "klinke":
        _set_pi_output_klinke()
    elif effective == "hdmi":
        _set_pi_output_hdmi()

    try:
        if _src_state:
            _src_state.set_audio_route(effective)
    except Exception as _ae:
        log.warn("[AUDIO] source_state route: " + str(_ae))

    src_tag = ("source=" + source).ljust(17) if source else "source=-         "
    log.info(
        "[AUDIO] " + src_tag
        + " requested=" + decision.get("requested", "?").ljust(6)
        + " effective=" + effective.ljust(7)
        + " reason="    + decision.get("reason", "?")
        + " sink="      + (sink or "-")
    )
    _remember_decision(
        decision.get("requested", ""), effective,
        decision.get("reason", ""), sink, source,
    )


def build_player_args(decision: dict, source: str = "") -> list:
    """v0.10.55: Baut mpv-Argumente aus Decision — keine Side-Effects."""
    effective = decision.get("effective", "none"); sink = decision.get("sink", "")
    if effective == "bt" and sink:
        return ["PULSE_SERVER=unix:/var/run/pulse/native" + f" PULSE_SINK={sink}", "--ao=pulse"]
    elif effective in ("klinke", "auto") and source in ("fm", "scanner"):
        # v0.10.55: PA System-Mode ist aktiv → PA hält ALSA-Card exklusiv.
        # mpv muss durch PA routen, nicht ALSA-direkt (sonst: Device busy → kein Ton).
        # Fallback auf ALSA-direkt nur wenn PA-Socket nicht existiert.
        import os as _os
        if _os.path.exists("/var/run/pulse/native"):
            env = "PULSE_SERVER=unix:/var/run/pulse/native"
            if sink: env += f" PULSE_SINK={sink}"
            return [env, "--ao=pulse"]
        else:
            card = _get_headphone_card()
            return ["", "--ao=alsa", f"--alsa-device=hw:{card},0"]
    else:
        env = "PULSE_SERVER=unix:/var/run/pulse/native"
        if sink: env += f" PULSE_SINK={sink}"
        return [env, "--ao=pulse"]



def get_mpv_args(settings=None, source: str = "") -> list:
    """v0.10.55: Wrapper — nutzt decide_audio_route() + apply_audio_route()."""
    d = decide_audio_route(settings=settings, source=source)
    if not d.get("pa_ok", True):
        src_tag = ("source=" + source).ljust(17) if source else "source=-         "
        log.error("[AUDIO] " + src_tag + " effective=none reason=audio_inactive")
        return ["--ao=pulse"]
    apply_audio_route(d)
    return build_player_args(d, source)

def set_output(mode: str, settings: dict):
    mode = mode.lower().replace("audio_", "").strip()

    if mode in ("klinke", "aux", "klinke (aux)"):
        settings["audio_output"] = "klinke"
        sink = get_alsa_sink()
        if sink:
            set_default_sink(sink)
            _remember_decision("klinke", "klinke", "klinke_requested", sink, "manual")
            ipc.write_progress("Audio", "Klinke aktiv", color="green")
        else:
            _remember_decision("klinke", "none", "no_alsa_sink", "", "manual")
            ipc.write_progress("Audio", "Kein ALSA-Sink", color="orange")
        _set_pi_output_klinke()
        log.info("[AUDIO] set_output -> klinke")

    elif mode == "hdmi":
        settings["audio_output"] = "hdmi"
        sink = get_hdmi_sink()
        if sink:
            set_default_sink(sink)
            _remember_decision("hdmi", "hdmi", "hdmi_requested", sink, "manual")
            ipc.write_progress("Audio", "HDMI aktiv", color="green")
        else:
            _remember_decision("hdmi", "none", "no_hdmi_sink", "", "manual")
            ipc.write_progress("Audio", "Kein HDMI-Sink", color="orange")
        _set_pi_output_hdmi()
        log.info("[AUDIO] set_output -> hdmi")

    elif mode in ("bt", "bluetooth", "a2dp"):
        settings["audio_output"] = "bt"
        sink = get_bt_sink()
        if sink:
            set_default_sink(sink)
            _remember_decision("bt", "bt", "bt_requested", sink, "manual")
            ipc.write_progress("Audio", "Bluetooth aktiv", color="green")
            log.info("[AUDIO] set_output -> bt  sink=" + sink)
        else:
            _remember_decision("bt", "none", "no_a2dp_sink", "", "manual")
            ipc.write_progress("Audio", "Kein BT-Sink (A2DP)", color="orange")
            log.warn("[AUDIO] set_output -> bt  aber kein A2DP-Sink")

    elif mode in ("auto", "all"):
        settings["audio_output"] = "auto"
        get_mpv_args(settings, source="set_output:auto")
        ipc.write_progress("Audio", "Auto gesetzt", color="green")
        log.info("[AUDIO] set_output -> auto")

    time.sleep(1)
    ipc.clear_progress()


def apply_startup_volume(settings=None):
    """
    Lautstärke beim Boot anwenden. v0.9.24:
    - Default 90% (kein volume > 100% beim Start)
    - Alle Audio-Sinks werden gesetzt
    - amixer Card 1 mitziehen (FM/Scanner ALSA direkt)
    - Gespeicherter Wert bleibt über Neustarts erhalten
    """
    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}
    vol = settings.get("volume", 90)
    try:
        vol = max(0, min(int(vol), 100))   # Hard cap 100%
    except Exception:
        vol = 90
    try:
        import subprocess as _sp
        # Alle PA-Sinks setzen
        sinks_r = _sp.run(PA_ENV + " pactl list sinks short 2>/dev/null",
                          shell=True, capture_output=True, text=True, timeout=4)
        n = 0
        for _ln in sinks_r.stdout.splitlines():
            _p = _ln.split()
            if len(_p) >= 2:
                _sp.run(PA_ENV + f" pactl set-sink-volume {_p[1]} {vol}%",
                        shell=True, capture_output=True, timeout=3)
                n += 1
        # amixer Card 1 für FM/Scanner
        _card = _get_headphone_card()
        _sp.run(f"amixer -c {_card} sset PCM {vol}% 2>/dev/null",
                shell=True, capture_output=True, timeout=3)
        log.info(f"[AUDIO] startup volume → {vol}% auf {n} PA-Sinks + amixer Card {_card}")
    except Exception as e:
        log.error("[AUDIO] apply_startup_volume: " + str(e))


def _get_current_sink() -> str:
    """Gibt den aktiven Sink zurück — BT > ALSA. Fallback: leer."""
    bt = get_bt_sink()
    if bt:
        return bt
    return get_alsa_sink()


def get_sink_volume(sink_name: str = "") -> str:
    """
    Liest die aktuelle Lautstärke eines Sinks via pactl.
    Parst aus 'pactl list sinks' statt 'pactl get-sink-volume',
    weil letzteres im System-Mode (PA/PipeWire) oft fehlschlägt.
    """
    if not sink_name:
        sink_name = _get_current_sink()
    if not sink_name:
        return ""
    try:
        out = _run(PA_ENV + " pactl list sinks 2>/dev/null", 5)
        in_sink = False
        for ln in out.splitlines():
            if sink_name in ln and ("Name:" in ln or "alsa_output" in ln):
                in_sink = True
            if in_sink:
                if ln.strip().startswith("Volume:") and "%" in ln:
                    import re as _re
                    m = _re.search(r"(\d+)%", ln)
                    if m:
                        return m.group(1) + "%"
                # Nächster Sink-Block
                if ln.startswith("    Name:") or ln.startswith("Sink #"):
                    if sink_name not in ln:
                        in_sink = False
        return ""
    except Exception:
        return ""



def set_volume(level: int, settings=None) -> int:
    """Lautstärke direkt auf level% setzen (0-100).
    Aktualisiert PA-Sink, amixer UND settings["volume"].
    Gibt tatsächlich gesetzte Lautstärke zurück.
    """
    global _last_vol_save
    level = max(0, min(100, int(level)))
    pct = f"{level}%"

    # PA-Sink setzen
    try:
        sink = _get_current_sink()
        target = sink if sink else "@DEFAULT_SINK@"
        subprocess.run(PA_ENV + f" pactl set-sink-volume {target} {pct}",
                       shell=True, capture_output=True, timeout=3)
    except Exception:
        pass

    # amixer synchronisieren
    try:
        card = _get_headphone_card()
        subprocess.run(f"amixer -c {card} sset PCM {pct} 2>/dev/null",
                       shell=True, capture_output=True, timeout=2)
    except Exception:
        pass

    # settings["volume"] aktualisieren + speichern
    if settings is not None:
        settings["volume"] = level
        try:
            from settings import save_settings as _ss_sv
            import time as _time_sv
            if _time_sv.time() - _last_vol_save > 0.5:
                _ss_sv(settings)
                _last_vol_save = _time_sv.time()
        except Exception:
            pass

    return level

def volume_up(settings=None):
    try:
        sink = _get_current_sink()
        target = sink if sink else "@DEFAULT_SINK@"
        subprocess.run(PA_ENV + f" pactl set-sink-volume {target} +5%",
                       shell=True, capture_output=True, timeout=3)
        if settings is not None:
            try:
                settings["volume"] = min(100, int(settings.get("volume", 90)) + 5)
                from settings import save_settings as _ss_fn
                import time as _time_vol
                global _last_vol_save
                if _time_vol.time() - _last_vol_save > 2.0:
                    _ss_fn(settings)
                    _last_vol_save = _time_vol.time()
            except Exception:
                pass
        try:
            _v = min(100, int(settings.get("volume", 90)) if settings else 90)
            _card_up = _get_headphone_card()
            subprocess.run(f"amixer -c {_card_up} sset PCM {_v}% 2>/dev/null",
                           shell=True, capture_output=True, timeout=2)
        except Exception:
            pass
        ipc.write_progress("Lautstaerke", "up +5%", color="green")
        time.sleep(0.8)
        ipc.clear_progress()
    except Exception as e:
        log.error("volume_up: " + str(e))


def volume_down(settings=None):
    try:
        sink = _get_current_sink()
        target = sink if sink else "@DEFAULT_SINK@"
        subprocess.run(PA_ENV + f" pactl set-sink-volume {target} -5%",
                       shell=True, capture_output=True, timeout=3)
        if settings is not None:
            try:
                settings["volume"] = max(0, int(settings.get("volume", 90)) - 5)
                from settings import save_settings as _ss_fn
                import time as _time_vol
                global _last_vol_save
                if _time_vol.time() - _last_vol_save > 2.0:
                    _ss_fn(settings)
                    _last_vol_save = _time_vol.time()
            except Exception:
                pass
        try:
            _v = max(0, int(settings.get("volume", 90)) if settings else 90)
            _card_dn = _get_headphone_card()
            subprocess.run(f"amixer -c {_card_dn} sset PCM {_v}% 2>/dev/null",
                           shell=True, capture_output=True, timeout=2)
        except Exception:
            pass
        ipc.write_progress("Lautstaerke", "down -5%", color="orange")
        time.sleep(0.8)
        ipc.clear_progress()
    except Exception as e:
        log.error("volume_down: " + str(e))