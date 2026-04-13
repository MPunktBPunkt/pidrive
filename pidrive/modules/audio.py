"""
modules/audio.py - Audioausgang Modul v0.7.8
PiDrive — pygame-frei

Audio-Routing:
  Klinke:    hw:1,0  (Pi 3.5mm Klinke → Auto AUX-IN)
  HDMI:      hw:0,0  (Pi HDMI Audio)
  Bluetooth: bluealsa/A2DP → BMW Lautsprecher (direkt, kein AUX)

WICHTIG: Audio läuft immer nur auf EINEM Ausgang gleichzeitig.
  - Bei BT aktiv: alle mpv-Instanzen auf BT-Sink
  - Bei Klinke: mpv auf hw:1,0
  - NICHT parallel auf BT + Klinke (würde doppelt klingen)
"""

import subprocess
import time
import ipc
import log

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_bt_sink():
    """Aktiven PulseAudio BT-Sink zurückgeben (leer wenn nicht verfügbar)."""
    out = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    for line in out.splitlines():
        if "bluez_sink." in line and ".a2dp_sink" in line:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]   # Sink-Name, z.B. bluez_sink.00_16_94_2E_85_DB.a2dp_sink
    return ""


def get_mpv_args(settings=None):
    """MPV-Audioargumente für aktuellen Ausgang zurückgeben.
    Alle Module (Webradio, FM, DAB, Bibliothek) sollen diese Funktion nutzen.

    Log-Beispiele:
      [AUDIO] requested=auto  effective=bt    sink=bluez_sink.XX.a2dp_sink → --ao=pulse
      [AUDIO] requested=auto  effective=klinke                              → --ao=alsa --audio-device=alsa/hw:1,0
    """
    if settings is None:
        from main_core import load_settings
        settings = load_settings()

    mode = settings.get("audio_output", "auto")

    if mode in ("bt", "auto"):
        sink = get_bt_sink()
        if sink:
            log.info(f"[AUDIO] requested={mode:<6} effective=bt     sink={sink} → --ao=pulse")
            return ["--ao=pulse"]

    log.info(f"[AUDIO] requested={mode:<6} effective=klinke device=hw:1,0 → --ao=alsa")
    return ["--ao=alsa", "--audio-device=alsa/hw:1,0"]


def set_output(mode, settings):
    """Audioausgang setzen. mode: 'klinke' | 'hdmi' | 'bt' | 'auto'"""
    mode = mode.lower().replace("audio_","")

    if mode in ("klinke", "klinke (aux)", "aux"):
        # ALSA: hw:1,0 = Pi 3.5mm Klinke
        _bg("amixer -c 0 cset numid=3 1 2>/dev/null")
        settings["audio_output"] = "klinke"
        settings["alsa_device"]  = "hw:1,0"
        ipc.write_progress("Audio", "Klinke (AUX) aktiv", color="green")
        log.info("AUDIO: Klinke hw:1,0")

    elif mode == "hdmi":
        _bg("amixer -c 0 cset numid=3 2 2>/dev/null")
        settings["audio_output"] = "hdmi"
        settings["alsa_device"]  = "hw:0,0"
        ipc.write_progress("Audio", "HDMI aktiv", color="green")
        log.info("AUDIO: HDMI hw:0,0")

    elif mode in ("bt", "bluetooth", "a2dp"):
        # Bluetooth A2DP: bluealsa oder pipewire
        mac = get_bt_sink()
        if mac:
            settings["audio_output"] = "bt"
            settings["bt_sink_mac"]  = mac
            settings["alsa_device"]  = f"bluealsa:DEV={mac},PROFILE=a2dp"
            ipc.write_progress("Audio", f"BT A2DP: {mac[:8]}...", color="green")
            log.info(f"AUDIO: Bluetooth A2DP {mac}")
        else:
            ipc.write_progress("Audio", "Kein BT-Gerät verbunden", color="orange")
            log.warn("AUDIO: BT gewählt aber kein Gerät verbunden")

    elif mode == "auto":
        # Auto: BT wenn verbunden, sonst Klinke
        mac = get_bt_sink()
        if mac:
            set_output("bt", settings)
        else:
            set_output("klinke", settings)
        return

    time.sleep(1)
    ipc.clear_progress()


def get_alsa_device(settings):
    """Kompatibilitätsfunktion — nutze get_mpv_args() für neue Module."""
    mode = settings.get("audio_output", "klinke")
    if mode == "hdmi":
        return "hw:0,0"
    if mode in ("bt", "auto"):
        sink = get_bt_sink()
        if sink:
            return "pulse"   # PulseAudio nutzt Default-Sink
    return "hw:1,0"


def volume_up(settings):
    """Lautstärke +5%."""
    try:
        subprocess.run(["amixer", "sset", "PCM", "5%+"],
                       capture_output=True, timeout=3)
        ipc.write_progress("Lautstärke", "↑ +5%", color="green")
        time.sleep(0.8); ipc.clear_progress()
    except Exception as e:
        log.error(f"volume_up: {e}")


def volume_down(settings):
    """Lautstärke -5%."""
    try:
        subprocess.run(["amixer", "sset", "PCM", "5%-"],
                       capture_output=True, timeout=3)
        ipc.write_progress("Lautstärke", "↓ -5%", color="orange")
        time.sleep(0.8); ipc.clear_progress()
    except Exception as e:
        log.error(f"volume_down: {e}")


def select_output_interactive(S, settings):
    """Audioausgang via headless_pick wählen."""
    options = ["Klinke (AUX)", "Bluetooth A2DP", "HDMI"]
    chosen  = ipc.headless_pick("Audioausgang", options)
    if chosen:
        mapping = {
            "Klinke (AUX)":    "klinke",
            "Bluetooth A2DP":  "bt",
            "HDMI":            "hdmi",
        }
        set_output(mapping.get(chosen, "klinke"), settings)
