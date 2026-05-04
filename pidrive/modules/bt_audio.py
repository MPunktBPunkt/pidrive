#!/usr/bin/env python3
"""bt_audio.py — PulseAudio-Sink und A2DP-Management  v0.10.22
Ausgelagert aus bluetooth.py."""

from modules.bt_helpers import (
    _run, _normalize_mac, _read_json, _now, _sleep_s,
    PA_ENV, A2DP_WAIT_SECONDS,
)
import subprocess
import time
import log
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

def _set_pulseaudio_sink(sink_name):
    if not sink_name:
        return False
    try:
        # warten bis Sink sichtbar
        for _ in range(8):
            r = subprocess.run(
                PA_ENV + " pactl list sinks short 2>/dev/null",
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            if sink_name in (r.stdout or ""):
                break
            _sleep_s(1.0)

        r = subprocess.run(
            PA_ENV + " pactl set-default-sink " + sink_name,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if r.returncode == 0:
            log.info("PulseAudio: Default-Sink=" + sink_name)
            return True
        log.warn("PulseAudio sink nicht gefunden/setzbar: " + sink_name)
        return False
    except Exception as e:
        log.error("PulseAudio sink-Fehler: " + str(e))
        return False


def _set_raspotify_device(device, restart=True):
    conf = "/etc/raspotify/conf"
    try:
        try:
            with open(conf) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            log.warn("Raspotify: /etc/raspotify/conf nicht gefunden")
            return

        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith("LIBRESPOT_DEVICE="):
                new_lines.append("LIBRESPOT_DEVICE=" + device + "\n")
                replaced = True
            else:
                new_lines.append(line)

        if not replaced:
            new_lines.append("LIBRESPOT_DEVICE=" + device + "\n")

        with open(conf, "w") as fh:
            fh.writelines(new_lines)

        log.info("Raspotify: LIBRESPOT_DEVICE=" + device)

        if restart:
            subprocess.run(
                ["systemctl", "restart", "raspotify"],
                capture_output=True,
                timeout=10
            )
            log.info("Raspotify: neu gestartet")

    except Exception as e:
        log.error("Raspotify Device-Wechsel fehlgeschlagen: " + str(e))


def get_bt_sink():
    try:
        r = subprocess.run(
            PA_ENV + " pactl list sinks short 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in (r.stdout or "").splitlines():
            low = line.lower()
            if "bluez" in low or "a2dp" in low:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return ""


def _expected_pa_sink_for_mac(mac: str) -> str:
    return "bluez_sink." + _normalize_mac(mac).replace(":", "_") + ".a2dp_sink"


def _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS):
    pa_sink = _expected_pa_sink_for_mac(mac)
    end = time.time() + timeout
    while time.time() < end:
        out = _run(PA_ENV + " pactl list sinks short 2>/dev/null", timeout=4)
        if pa_sink in out:
            return True, pa_sink
        _sleep_s(1.0)
    return False, pa_sink



