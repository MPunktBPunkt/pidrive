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
        Ändert: PulseAudio Default-Sink + amixer.
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
    DAB         ALSA hw:1,0    welle-cli -p NAME (AlsaProgrammeHandler)
                               KEIN PulseAudio — OFDM-Timing-sensitiv
    FM          ALSA hw:1,0    rtl_fm | mpv --ao=alsa --alsa-device=hw:1,0
                               KEIN PulseAudio — raw PCM Resampling-Problem
    Scanner     ALSA hw:N,0    rtl_fm | mpv --ao=alsa
    Webradio    PulseAudio     mpv --ao=pulse PULSE_SERVER=...
    Spotify     PulseAudio     librespot → PulseAudio
    BT (A2DP)   PulseAudio     mpv/librespot + PULSE_SINK=bluez_sink.*

    hw:1,0 = Card 1 = bcm2835 Headphones = Klinke (3.5mm)
    hw:0,0 = Card 0 = bcm2835 HDMI — NIEMALS für PiDrive-Audio verwenden

## State Machine (source_state.py) Rolle

    source_state ist KEIN Regler — nur Zustandsspiegel:
    - get_mpv_args() setzt set_audio_route() als SIDE-EFFECT
    - source_state.get_audio_route() zeigt Stand NACH letzter Entscheidung
    - Um Audio zu wechseln: set_output() oder get_mpv_args() aufrufen,
      NICHT source_state direkt manipulieren

## Bekannte Einschränkungen

    - "Klinke"-Button während DAB/FM läuft: ändert PulseAudio, aber welle-cli/rtl_fm
      laufen ALSA-direkt. Wirkung erst nach Stop + Neustart der Quelle.
    - volume > 100%: wird beim Boot auf 90% korrigiert (settings.json Altlasten).
    - BT + DAB: funktioniert nur wenn asound.conf default=card 1 korrekt gesetzt
      und PulseAudio Sink-Input nach BT-Connect verschoben wird.
"""

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

# v0.10.19: Sink-Cache (2s TTL)
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
    return 1  # Standardannahme: Card 1 = Headphones auf modernem Pi OS


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
    """v0.10.19: decide() + apply() — Rückgabe: Decision-Dict."""
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
    v0.10.19: Socket-Datei zuerst prüfen (~0.1ms statt ~150ms systemctl subprocess).
    Falls Socket existiert: PA läuft definitiv. Sonst: systemctl als Fallback.
    """
    if os.path.exists("/var/run/pulse/native"):
        return True
    return _run("systemctl is-active pulseaudio 2>/dev/null", 3) == "active"


def _list_sinks(force: bool = False) -> list:
    """v0.10.19: Mit 2s TTL-Cache."""
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
    """v0.10.19: Cache nach BT-Connect invalidieren."""
    global _sink_cache_ts
    _sink_cache_ts = 0.0


def get_bt_sink(retry: int = 1) -> str:
    """
    Gibt den BT A2DP Sink zurück (v0.9.21).
    retry=3: wartet bis zu 3x1s auf A2DP-Aushandlung nach BT-Connect.
    PulseAudio registriert A2DP-Sink erst ~1-2s nach bluetoothctl connect.
    """
    import time as _t
    for attempt in range(max(1, retry)):
        for s in _list_sinks():
            if "bluez_sink." in s["name"] and ".a2dp_sink" in s["name"]:
                return s["name"]
        if attempt < retry - 1:
            _t.sleep(1)
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
    Lädt Card 1 (Headphones/Klinke) als PulseAudio-Sink falls noch nicht vorhanden (v0.9.10).
    Root Cause: setup_bt_audio.sh schrieb system.pa nur mit device_id=0 (HDMI).
    Card 1 wurde nie als PA-Sink geladen → kein Klinken-Audio möglich.
    """
    sinks = _list_sinks()
    # Prüfen ob ein Nicht-HDMI alsa_output Sink existiert
    for s in sinks:
        n, r = s["name"].lower(), s["raw"].lower()
        if "hdmi" not in n and "hdmi" not in r and "alsa_output" in s["name"]:
            return True  # Klinken-Sink vorhanden
    # Card 1 dynamisch laden (Fallback wenn system.pa noch nicht aktualisiert)
    try:
        r = _run(
            PA_ENV + " pactl load-module module-alsa-card device_id=1 2>/dev/null",
            timeout=5
        )
        log.info("[AUDIO] _ensure_klinke_sink: module-alsa-card device_id=1 geladen")
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


def set_default_sink(sink_name: str) -> bool:
    """
    Setzt PulseAudio Default-Sink UND verschiebt laufende Sink-Inputs (v0.9.7).
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
    v0.10.19: Pure Policy — keine Side-Effects.
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

    if not sink:
        effective, reason = "none", "no_sink_available"

    return {
        "requested": requested, "effective": effective,
        "reason":    reason,    "sink":      sink or "",
        "source":    source,    "pa_ok":     True,
    }


def apply_audio_route(decision: dict):
    """
    v0.10.19: Side-Effects aus decide_audio_route() anwenden.
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
    """v0.10.19: Baut mpv-Argumente aus Decision — keine Side-Effects."""
    effective = decision.get("effective", "none"); sink = decision.get("sink", "")
    if effective == "bt" and sink:
        return ["PULSE_SERVER=unix:/var/run/pulse/native" + f" PULSE_SINK={sink}", "--ao=pulse"]
    elif effective in ("klinke", "auto") and source in ("fm", "scanner"):
        card = _get_headphone_card()
        return ["", "--ao=alsa", f"--alsa-device=hw:{card},0"]
    else:
        env = "PULSE_SERVER=unix:/var/run/pulse/native"
        if sink: env += f" PULSE_SINK={sink}"
        return [env, "--ao=pulse"]



def get_mpv_args(settings=None, source: str = "") -> list:
    """v0.10.19: Wrapper — nutzt decide_audio_route() + apply_audio_route()."""
    d = decide_audio_route(settings=settings, source=source)
    if not d.get("pa_ok", True):
        src_tag = ("source=" + source).ljust(17) if source else "source=-         "
        log.error("[AUDIO] " + src_tag + " effective=none reason=pulseaudio_inactive")
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
    - Alle PulseAudio-Sinks werden gesetzt
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
        _sp.run(f"amixer -c 1 sset PCM {vol}% 2>/dev/null",
                shell=True, capture_output=True, timeout=3)
        log.info(f"[AUDIO] startup volume → {vol}% auf {n} PA-Sinks + amixer Card 1")
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
    Liest die aktuelle PulseAudio-Lautstärke eines Sinks (v0.9.15).
    Parst aus 'pactl list sinks' statt 'pactl get-sink-volume',
    weil letzteres in PulseAudio --system Mode oft fehlschlägt.
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


def volume_up(settings=None):
    try:
        sink = _get_current_sink()
        target = sink if sink else "@DEFAULT_SINK@"
        subprocess.run(PA_ENV + f" pactl set-sink-volume {target} +5%",
                       shell=True, capture_output=True, timeout=3)
        if settings is not None:
            try:
                settings["volume"] = min(100, int(settings.get("volume", 90)) + 5)
                from settings import save_settings
                save_settings(settings)
            except Exception:
                pass
        try:
            _v = min(100, int(settings.get("volume", 90)) if settings else 90)
            subprocess.run(f"amixer -c 1 sset PCM {_v}% 2>/dev/null",
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
                from settings import save_settings
                save_settings(settings)
            except Exception:
                pass
        try:
            _v = max(0, int(settings.get("volume", 90)) if settings else 90)
            subprocess.run(f"amixer -c 1 sset PCM {_v}% 2>/dev/null",
                           shell=True, capture_output=True, timeout=2)
        except Exception:
            pass
        ipc.write_progress("Lautstaerke", "down -5%", color="orange")
        time.sleep(0.8)
        ipc.clear_progress()
    except Exception as e:
        log.error("volume_down: " + str(e))