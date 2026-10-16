"""audio_tap.py — PCM-Quelle für den FM-Sender.

Quellen:
  mirror   Default-Sink-Monitor von PipeWire-Pulse (wie pump_bridge) → spiegelt
           Klinke/HDMI/BT/ESP-Wiedergabe parallel
  tone1k   1-kHz-Sinus (-12 dBFS) — Dauerton für Abgleich/Messung
  silence  Stille (Träger + Pilot + RDS, NF stumm)
  carrier  keine PCM-Quelle → Backend sendet nur Träger (+ RDS)
  announce Boot-Ansage „PiDrive is starting“ (intern, nicht im Quellen-Dropdown)

Ausgabe: WAV (s16le, 44,1 kHz, 1/2 Kanäle) auf stdout für `pi_fm_rds -audio -`.
DAB läuft normalerweise ALSA-direkt; solange der Sender spiegelt, startet
dab_play welle-cli über Pulse (tx_manager.needs_pulse_monitor()).
"""
from __future__ import annotations

import os
import subprocess

from modules.tx.backend_base import AudioCmd

PULSE_SERVER = "unix:/var/run/pulse/native"
SAMPLE_RATE = 44100
TONE_HZ = 1000
TONE_LEVEL = 0.25

# Boot-Ansage: install.sh rendert die WAV per espeak-ng; fehlt sie, kommt ein 1-kHz-Beep
ANNOUNCE_WAV = "/opt/pidrive/share/fmtx/pidrive_starting.wav"
ANNOUNCE_TEXT = "PiDrive is starting"
ANNOUNCE_LEAD_S = 0.5
ANNOUNCE_MAX_S = 5.0

_FFMPEG_HEAD = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error"]


def resolve_monitor(env: dict | None = None) -> str:
    """Name des Default-Sink-Monitors, Fallback @DEFAULT_MONITOR@."""
    e = {**os.environ, "PULSE_SERVER": PULSE_SERVER, **(env or {})}
    try:
        r = subprocess.run(["pactl", "get-default-sink"], capture_output=True,
                           text=True, timeout=3, env=e)
        sink = (r.stdout or "").strip()
        if sink:
            return sink if sink.endswith(".monitor") else sink + ".monitor"
    except Exception:
        pass
    return "@DEFAULT_MONITOR@"


def _out_args(channels: int, raw_rate: int | None) -> list[str]:
    if raw_rate:
        return ["-ac", "1", "-ar", str(raw_rate), "-f", "s16le", "-"]
    return ["-ac", str(channels), "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", "-f", "wav", "-"]


def build_cmd(source: str, stereo: bool = True, monitor: str | None = None,
              raw_rate: int | None = None, narrowband: bool = False,
              announce_wav: str | None = None) -> AudioCmd | None:
    """ffmpeg-Kommando für die Quelle, None für 'carrier'.

    raw_rate: statt WAV rohes s16le mono mit dieser Rate (rpitx/NBFM-Pfad).
    narrowband: NF auf 300–3000 Hz begrenzen (PMR446, 12,5-kHz-Raster).
    announce: Boot-Ansage (WAV oder Beep) mit Vorlauf-Stille, endet nach ANNOUNCE_MAX_S.
    """
    src = (source or "mirror").lower()
    ch = 2 if (stereo and not raw_rate) else 1
    env = {"PULSE_SERVER": PULSE_SERVER}
    nf = "highpass=f=300,lowpass=f=3000" if narrowband else "lowpass=f=15000"
    if src == "carrier":
        return None
    if src == "announce":
        wav = announce_wav or ANNOUNCE_WAV
        lead_ms = int(ANNOUNCE_LEAD_S * 1000)
        tail = ["-t", f"{ANNOUNCE_MAX_S:g}"] + _out_args(ch, raw_rate)
        if os.path.isfile(wav):
            argv = _FFMPEG_HEAD + ["-i", wav, "-af", f"adelay={lead_ms}:all=1,apad"] + tail
        else:
            argv = _FFMPEG_HEAD + [
                "-f", "lavfi",
                "-i", f"sine=frequency={TONE_HZ}:sample_rate={SAMPLE_RATE}:duration=1",
                "-af", f"volume={TONE_LEVEL},adelay={lead_ms}:all=1,apad",
            ] + tail
        return AudioCmd(argv, env)
    if src in ("tone1k", "tone"):
        argv = _FFMPEG_HEAD + [
            "-f", "lavfi", "-i", f"sine=frequency={TONE_HZ}:sample_rate={SAMPLE_RATE}",
            "-af", f"volume={TONE_LEVEL}",
        ] + _out_args(ch, raw_rate)
        return AudioCmd(argv, env)
    if src == "silence":
        layout = "stereo" if ch == 2 else "mono"
        argv = _FFMPEG_HEAD + [
            "-f", "lavfi", "-i", f"anullsrc=channel_layout={layout}:sample_rate={SAMPLE_RATE}",
        ] + _out_args(ch, raw_rate)
        return AudioCmd(argv, env)
    if src == "mirror":
        mon = monitor or resolve_monitor()
        argv = _FFMPEG_HEAD + [
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "pulse", "-i", mon,
            "-af", nf,
        ] + _out_args(ch, raw_rate)
        return AudioCmd(argv, env)
    raise ValueError(f"Quelle unbekannt: {source!r}")
