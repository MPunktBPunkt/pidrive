"""
modules/audio.py - Zentraler Audioausgang für PiDrive
PiDrive v0.8.11 - Zielarchitektur Option B

Ziel:
- Ein zentraler Audio-Server: systemweiter PulseAudio
- ALLE Quellen (FM, DAB, Webradio, Scanner) über denselben Routing-Pfad
- Klinke / HDMI / BT nur noch als Sink-Entscheidung
- Kein Sonderpfad für aplay/ALSA direkt mehr
- WebUI/IPC-Debug bleibt erhalten (get_last_decision())

Audio-Pfad:
  rtl_fm | mpv --ao=pulse    (FM, Scanner)
  welle-cli | mpv --ao=pulse (DAB)
  mpv --ao=pulse             (Webradio)
  librespot -> PulseAudio    (Spotify via Raspotify)

Sinks:
  Klinke = PulseAudio Default-Sink auf ALSA-Ausgang (hw:1,0)
  BT     = PulseAudio Default-Sink auf bluez_sink.*.a2dp_sink
  HDMI   = PulseAudio Default-Sink auf HDMI-Ausgang
"""

import subprocess
import time
import ipc
import log

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"

_last_decision = {
    "requested": "auto",
    "effective": "",
    "reason":    "",
    "sink":      "",
    "source":    "",
    "ts":        0,
}


def get_last_decision() -> dict:
    """Letzte Audio-Routing-Entscheidung — fuer WebUI-Debug."""
    return dict(_last_decision)


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _pa_ok() -> bool:
    """PulseAudio-Systemdaemon laeuft?"""
    out = _run("systemctl is-active pulseaudio 2>/dev/null", timeout=3)
    return out.strip() == "active"


def _list_sinks() -> list:
    """Alle PulseAudio-Sinks (system) als Liste von Dicts."""
    out = _run(PA_ENV + " pactl list sinks short 2>/dev/null", timeout=4)
    sinks = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sinks.append({"id": parts[0], "name": parts[1], "raw": line})
    return sinks


def get_bt_sink() -> str:
    """Aktiven Bluetooth A2DP Sink finden."""
    for s in _list_sinks():
        name = s["name"]
        if "bluez_sink." in name and ".a2dp_sink" in name:
            return name
    return ""


def get_alsa_sink() -> str:
    """ALSA-Klinke-Sink finden."""
    for s in _list_sinks():
        if "alsa_output" in s["name"]:
            return s["name"]
    return ""


def get_hdmi_sink() -> str:
    """HDMI-Sink finden."""
    for s in _list_sinks():
        name = s["name"].lower()
        raw  = s["raw"].lower()
        if "hdmi" in name or "hdmi" in raw:
            return s["name"]
    return ""


def set_default_sink(sink_name: str) -> bool:
    """PulseAudio Default-Sink setzen."""
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
                     " | " + (r.stderr or "").strip()[:80])
        return r.returncode == 0
    except Exception as e:
        log.error("[AUDIO] set_default_sink: " + str(e))
        return False


def get_mpv_args(settings=None, source: str = "") -> list:
    """
    Einheitlicher Audio-Pfad fuer ALLE Quellen - v0.8.11.

    Gibt immer ["--ao=pulse"] zurueck.
    Die Sink-Entscheidung (Klinke / BT / HDMI) wird ueber set_default_sink()
    im systemweiten PulseAudio gesetzt, bevor mpv gestartet wird.

    Fallback: wenn PulseAudio nicht aktiv ist, direkt via ALSA.
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
        # v0.8.12 STRICT MODE: kein stiller ALSA-Fallback mehr
        # Klare Fehlermeldung, aber Pfad bleibt bei --ao=pulse
        log.error("[AUDIO] " + src_tag + " requested=" + requested +
                  " effective=none reason=pulseaudio_inactive — KEIN ALSA-Fallback (strict mode)")
        _last_decision.update({
            "requested": requested, "effective": "none",
            "reason": "pulseaudio_inactive", "sink": "", "source": source,
            "ts": int(time.time()),
        })
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

    log.info("[AUDIO] " + src_tag + " requested=" + requested.ljust(6) +
             " effective=" + effective.ljust(7) +
             " reason=" + reason + " sink=" + (sink or "-"))

    _last_decision.update({
        "requested": requested, "effective": effective,
        "reason": reason, "sink": sink or "", "source": source,
        "ts": int(time.time()),
    })

    return ["--ao=pulse"]


def set_output(mode: str, settings: dict):
    """Audio-Ausgang wechseln und in settings speichern."""
    mode = mode.lower().replace("audio_", "").strip()

    if mode in ("klinke", "aux", "klinke (aux)"):
        settings["audio_output"] = "klinke"
        sink = get_alsa_sink()
        if sink:
            set_default_sink(sink)
        ipc.write_progress("Audio", "Klinke aktiv", color="green")
        log.info("[AUDIO] set_output -> klinke")

    elif mode == "hdmi":
        settings["audio_output"] = "hdmi"
        sink = get_hdmi_sink()
        if sink:
            set_default_sink(sink)
            ipc.write_progress("Audio", "HDMI aktiv", color="green")
        else:
            ipc.write_progress("Audio", "Kein HDMI-Sink", color="orange")
        log.info("[AUDIO] set_output -> hdmi")

    elif mode in ("bt", "bluetooth", "a2dp"):
        settings["audio_output"] = "bt"
        sink = get_bt_sink()
        if sink:
            set_default_sink(sink)
            ipc.write_progress("Audio", "Bluetooth aktiv", color="green")
            log.info("[AUDIO] set_output -> bt  sink=" + sink)
        else:
            ipc.write_progress("Audio", "Kein BT-Sink (A2DP)", color="orange")
            log.warn("[AUDIO] set_output -> bt  aber kein A2DP-Sink")

    elif mode in ("auto", "all"):
        settings["audio_output"] = "auto"
        sink = get_bt_sink()
        if sink:
            set_default_sink(sink)
            ipc.write_progress("Audio", "Auto: BT", color="green")
        else:
            sink = get_alsa_sink()
            if sink:
                set_default_sink(sink)
            ipc.write_progress("Audio", "Auto: Klinke", color="green")
        log.info("[AUDIO] set_output -> auto")

    time.sleep(1)
    ipc.clear_progress()


def volume_up(settings=None):
    try:
        subprocess.run(PA_ENV + " pactl set-sink-volume @DEFAULT_SINK@ +5%",
                       shell=True, capture_output=True, timeout=3)
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
    """Veraltet - nur noch fuer Altcode. Neue Architektur nutzt get_mpv_args()."""
    requested = settings.get("audio_output", "auto")
    if requested in ("bt", "auto"):
        return "pulse"
    if requested == "hdmi":
        return "default"
    return "default"
