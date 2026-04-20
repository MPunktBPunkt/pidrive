"""
modules/audio.py - Zentraler Audioausgang fuer PiDrive
PiDrive v0.8.13 - STRICT PulseAudio Only + shared debug state

Neu in v0.8.13:
- _write_audio_state() schreibt letzte Entscheidung in /tmp/pidrive_audio_state.json
- read_last_decision_file() liest daraus (prozessuebergreifend — fuer WebUI)
- WebUI liest damit echte Core-Entscheidung, nicht eigenen Modulzustand
"""

import os
import json
import subprocess
import time
import ipc
import log

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"
AUDIO_STATE_FILE = "/tmp/pidrive_audio_state.json"


def _set_pi_output_klinke():
    """
    Pi 3B: ALSA-Ausgang physisch auf 3.5mm Klinke schalten.
    amixer numid=3: 0=auto, 1=klinke, 2=HDMI
    Muss VOR dem Starten von mpv/PulseAudio-Routing gesetzt werden.
    Verhindert das Problem 'mpv laeuft aber kein Ton' wenn Pi auf HDMI steht.
    """
    try:
        import subprocess as _sp
        _sp.run("amixer -q -c 0 cset numid=3 1 2>/dev/null",
                shell=True, timeout=3)
        log.info("[AUDIO] Pi Ausgang: Klinke (amixer numid=3=1)")
    except Exception as e:
        log.warn("[AUDIO] amixer klinke: " + str(e))


def _set_pi_output_hdmi():
    """Pi 3B: ALSA-Ausgang auf HDMI."""
    try:
        import subprocess as _sp
        _sp.run("amixer -q -c 0 cset numid=3 2 2>/dev/null",
                shell=True, timeout=3)
        log.info("[AUDIO] Pi Ausgang: HDMI (amixer numid=3=2)")
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
    return _run("systemctl is-active pulseaudio 2>/dev/null", 3) == "active"


def _list_sinks() -> list:
    out = _run(PA_ENV + " pactl list sinks short 2>/dev/null", 4)
    sinks = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sinks.append({"id": parts[0], "name": parts[1], "raw": line})
    return sinks


def get_bt_sink() -> str:
    for s in _list_sinks():
        if "bluez_sink." in s["name"] and ".a2dp_sink" in s["name"]:
            return s["name"]
    return ""


def get_alsa_sink() -> str:
    for s in _list_sinks():
        if "alsa_output" in s["name"]:
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
    if not sink_name:
        return False
    try:
        r = subprocess.run(
            PA_ENV + " pactl set-default-sink " + sink_name,
            shell=True, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            log.info("[AUDIO] default sink -> " + sink_name)
            return True
        log.warn("[AUDIO] set-default-sink failed: " + sink_name +
                 " | " + (r.stderr or "").strip()[:60])
        return False
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


def get_mpv_args(settings=None, source: str = "") -> list:
    """
    STRICT zentraler Audio-Pfad — v0.8.13.
    Immer --ao=pulse. Kein ALSA-Fallback.
    Schreibt Entscheidung in /tmp/pidrive_audio_state.json.
    """
    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    requested = settings.get("audio_output", "auto")
    src_tag   = ("source=" + source).ljust(17) if source else "source=-         "

    if not _pa_ok():
        log.error("[AUDIO] " + src_tag + " requested=" + requested +
                  " effective=none reason=pulseaudio_inactive — strict mode")
        _remember_decision(requested, "none", "pulseaudio_inactive", "", source)
        return ["--ao=pulse"]

    bt_sink   = get_bt_sink()
    alsa_sink = get_alsa_sink()
    hdmi_sink = get_hdmi_sink()

    effective = "klinke"
    reason    = "no_a2dp_sink"
    sink      = alsa_sink

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
        if bt_sink:
            effective, reason, sink = "bt",     "a2dp_sink_available",  bt_sink
        else:
            effective, reason, sink = "klinke", "no_a2dp_sink",         alsa_sink

    if sink:
        set_default_sink(sink)
    else:
        effective = "none"
        reason    = "no_sink_available"

    # v0.8.14: Pi 3B physischen ALSA-Ausgang setzen (amixer numid=3)
    # Verhindert dass mpv auf HDMI statt Klinke ausgibt
    if effective == "klinke":
        _set_pi_output_klinke()
    elif effective == "hdmi":
        _set_pi_output_hdmi()

    log.info("[AUDIO] " + src_tag + " requested=" + requested.ljust(6) +
             " effective=" + effective.ljust(7) +
             " reason=" + reason + " sink=" + (sink or "-"))

    _remember_decision(requested, effective, reason, sink, source)
    return ["--ao=pulse"]


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
    Gespeicherte Lautstärke beim Boot auf Default-Sink anwenden (v0.9.0).
    Wird in main_core.py startup_tasks() aufgerufen.
    """
    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}
    vol = settings.get("volume", 90)
    try:
        vol = max(0, min(int(vol), 150))
    except Exception:
        vol = 90
    try:
        import subprocess as _sp
        _sp.run(
            PA_ENV + f" pactl set-sink-volume @DEFAULT_SINK@ {vol}%",
            shell=True, capture_output=True, timeout=4
        )
        log.info(f"[AUDIO] startup volume → {vol}%")
    except Exception as e:
        log.error("[AUDIO] apply_startup_volume: " + str(e))


def volume_up(settings=None):
    try:
        subprocess.run(PA_ENV + " pactl set-sink-volume @DEFAULT_SINK@ +5%",
                       shell=True, capture_output=True, timeout=3)
        if settings is not None:
            try:
                settings["volume"] = min(150, int(settings.get("volume", 90)) + 5)
                from settings import save_settings
                save_settings(settings)
            except Exception:
                pass
        ipc.write_progress("Lautstaerke", "up +5%", color="green")
        time.sleep(0.8)
        ipc.clear_progress()
    except Exception as e:
        log.error("volume_up: " + str(e))


def volume_down(settings=None):
    try:
        subprocess.run(PA_ENV + " pactl set-sink-volume @DEFAULT_SINK@ -5%",
                       shell=True, capture_output=True, timeout=3)
        ipc.write_progress("Lautstaerke", "down -5%", color="orange")
        time.sleep(0.8)
        ipc.clear_progress()
    except Exception as e:
        log.error("volume_down: " + str(e))


def get_alsa_device(settings: dict) -> str:
    """Veraltet — nur Altkompatibilitaet."""
    requested = settings.get("audio_output", "auto")
    if requested in ("bt", "auto"):
        return "pulse"
    if requested == "hdmi":
        return "default"
    return "default"
