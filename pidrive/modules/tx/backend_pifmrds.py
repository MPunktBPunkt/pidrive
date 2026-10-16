"""backend_pifmrds.py — UKW + RDS über PiFmRds (gepinnt 2707ecc).

Upstream: https://github.com/ChristopheJacquet/PiFmRds
Aufruf:  pi_fm_rds -freq 88.4 [-audio -] -pi D3A2 -ps PIDRIVE -rt "…" -ctl <fifo>
Ausgang: GPCLK0 an GPIO 4 (fest im Upstream). Ohne -audio: Träger + RDS.
Live-RDS: Zeilen "PS <text>" / "RT <text>" in die Control-Pipe (-ctl).
"""
from __future__ import annotations

import errno
import os
import stat

from modules.tx.backend_base import PipelineBackend, which

PINNED_COMMIT = "2707ecc"
BINARY = "pi_fm_rds"
CTL_FIFO = "/tmp/pidrive_fmtx_rds.ctl"


class PiFmRdsBackend(PipelineBackend):
    name = "pifmrds"

    def capabilities(self) -> dict:
        path = which(BINARY)
        available = bool(path) and os.path.exists("/dev/mem")
        why = ""
        if not path:
            why = f"{BINARY} fehlt (install.sh baut PiFmRds {PINNED_COMMIT})"
        elif not os.path.exists("/dev/mem"):
            why = "/dev/mem fehlt (kein Raspberry Pi?)"
        return {
            "name": self.name,
            "available": available,
            "why": why,
            "binary": path,
            "commit": PINNED_COMMIT,
            "bands": ["ukw"],
            "pins": [4],
            "stereo": True,
            "rds": True,
            "sources": ["mirror", "tone1k", "carrier", "silence", "announce"],
        }

    def before_start(self, cfg: dict) -> None:
        try:
            st = os.stat(CTL_FIFO)
            if not stat.S_ISFIFO(st.st_mode):
                os.unlink(CTL_FIFO)
                os.mkfifo(CTL_FIFO, 0o600)
        except FileNotFoundError:
            os.mkfifo(CTL_FIFO, 0o600)

    def build_tx_cmd(self, cfg: dict, with_audio: bool) -> list[str]:
        f = float(cfg.get("freq_effective_mhz") or cfg.get("freq_mhz"))
        argv = [which(BINARY) or BINARY, "-freq", f"{f:.2f}"]
        if with_audio:
            argv += ["-audio", "-"]
        rds = cfg.get("rds") or {}
        if rds.get("enabled", True):
            argv += ["-pi", str(rds.get("pi") or "D3A2"),
                     "-ps", (cfg.get("rds_ps") or rds.get("ps") or "PIDRIVE")[:8],
                     "-rt", (cfg.get("rds_rt") or rds.get("rt") or "")[:64],
                     "-ctl", CTL_FIFO]
        return argv

    def set_rds(self, ps: str | None = None, rt: str | None = None) -> bool:
        lines = []
        if ps is not None:
            lines.append("PS " + ps[:8])
        if rt is not None:
            lines.append("RT " + rt[:64])
        if not lines:
            return True
        try:
            fd = os.open(CTL_FIFO, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as e:
            if e.errno in (errno.ENXIO, errno.ENOENT):
                self._last_err = "RDS-Control-Pipe ohne Leser"
                return False
            raise
        try:
            os.write(fd, ("\n".join(lines) + "\n").encode("latin-1", "replace"))
        finally:
            os.close(fd)
        return True
