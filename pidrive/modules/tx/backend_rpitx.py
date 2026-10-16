"""backend_rpitx.py — rpitx (gepinnt ee7ff57): PMR446 nur Labor, Testträger/-ton.

Upstream: https://github.com/F5OEO/rpitx — Pi 4 „beta“, braucht gpu_freq=250.
Ausgang: GPIO 4 (fest). Kein RDS.

Pfade:
  carrier            tune -f <Hz>
  tone1k/mirror/…    ffmpeg (s16le 48 kHz mono) | nbfm_mod (Hub 2,5 kHz) | sendiq -t i16

PMR446 aus einem GPIO ist nicht zulässig — tx_manager.consent_check lässt
band=pmr446 nur mit mode=lab_dummy zu. UKW über rpitx ist nur als
Schmalband-Testsignal gedacht (Abgleich/Oberwellenmessung), nicht für Musik.
"""
from __future__ import annotations

import os
import shlex
import sys

from modules.tx import audio_tap
from modules.tx.backend_base import AudioCmd, PipelineBackend, which

PINNED_COMMIT = "ee7ff57"
IQ_RATE = 48000
DEV_PMR_HZ = 2500
DEV_UKW_TEST_HZ = 5000


class RpitxBackend(PipelineBackend):
    name = "rpitx"

    def capabilities(self) -> dict:
        sendiq = which("sendiq")
        tune = which("tune")
        dev_mem = os.path.exists("/dev/mem")
        available = bool(sendiq and tune and dev_mem)
        why = ""
        if not (sendiq and tune):
            why = f"rpitx fehlt (install.sh mit PIDRIVE_FMTX_RPITX=1, Commit {PINNED_COMMIT})"
        elif not dev_mem:
            why = "/dev/mem fehlt (kein Raspberry Pi?)"
        return {
            "name": self.name,
            "available": available,
            "why": why,
            "binary": sendiq,
            "commit": PINNED_COMMIT,
            "bands": ["pmr446", "ukw"],
            "pins": [4],
            "stereo": False,
            "rds": False,
            "sources": ["tone1k", "carrier", "silence", "mirror", "announce"],
            "lab_only": True,
        }

    def _freq_hz(self, cfg: dict) -> int:
        return int(round(float(cfg.get("freq_effective_mhz") or cfg.get("freq_mhz")) * 1e6))

    def build_audio(self, cfg: dict) -> AudioCmd | None:
        src = cfg.get("source")
        if src == "carrier":
            return None
        pmr = cfg.get("band") == "pmr446"
        ff = audio_tap.build_cmd(src, stereo=False, raw_rate=IQ_RATE, narrowband=pmr)
        if ff is None:
            return None
        dev = DEV_PMR_HZ if pmr else DEV_UKW_TEST_HZ
        mod = [sys.executable or "python3", "-m", "modules.tx.nbfm_mod",
               "--rate", str(IQ_RATE), "--dev", str(dev)]
        script = shlex.join(ff.argv) + " | " + shlex.join(mod)
        return AudioCmd(["/bin/bash", "-o", "pipefail", "-c", script], ff.env)

    def build_tx_cmd(self, cfg: dict, with_audio: bool) -> list[str]:
        f = self._freq_hz(cfg)
        if not with_audio:
            return [which("tune") or "tune", "-f", str(f)]
        return [which("sendiq") or "sendiq", "-i", "/dev/stdin", "-s", str(IQ_RATE),
                "-f", str(f), "-t", "i16"]

    def start(self, cfg: dict, audio_cmd: AudioCmd | None) -> None:
        if cfg.get("band") == "pmr446" and cfg.get("mode") != "lab_dummy":
            raise RuntimeError("PMR446 nur in Betriebsart Labor/Dummy-Load")
        super().start(cfg, self.build_audio(cfg))
