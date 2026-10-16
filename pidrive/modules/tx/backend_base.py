"""backend_base.py — gemeinsame Prozess-Pipeline für Sender-Backends.

Pipeline: [audio_cmd (ffmpeg → WAV auf stdout)] | [tx_cmd (liest stdin)]
Stopp: SIGINT an den Sender (DMA sauber beenden), dann SIGTERM/SIGKILL.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time

ERR_LOG = "/tmp/pidrive_fmtx_backend.log"


class AudioCmd:
    """argv + env für die PCM-Quelle (siehe audio_tap.build_cmd)."""

    def __init__(self, argv: list[str], env: dict | None = None):
        self.argv = list(argv)
        self.env = dict(env or {})

    def __repr__(self) -> str:
        return f"AudioCmd({' '.join(self.argv)!r})"


def which(name: str, extra_dirs=("/usr/local/bin", "/opt/pidrive/bin")) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    for d in extra_dirs:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


class PipelineBackend:
    name = "base"
    stop_timeout_s = 3.0

    def __init__(self):
        self._tx: subprocess.Popen | None = None
        self._audio: subprocess.Popen | None = None
        self._err_fh = None
        self._last_rc: int | None = None
        self._last_err = ""

    # Subklassen
    def capabilities(self) -> dict:  # pragma: no cover - abstrakt
        raise NotImplementedError

    def build_tx_cmd(self, cfg: dict, with_audio: bool) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    def before_start(self, cfg: dict) -> None:
        pass

    def after_stop(self) -> None:
        pass

    def set_rds(self, ps: str | None = None, rt: str | None = None) -> bool:
        return False

    # Gemeinsam
    def start(self, cfg: dict, audio_cmd: AudioCmd | None) -> None:
        self.stop()
        caps = self.capabilities()
        if not caps.get("available", False):
            raise RuntimeError(caps.get("why") or f"{self.name} nicht verfügbar")
        self.before_start(cfg)
        tx_argv = self.build_tx_cmd(cfg, with_audio=audio_cmd is not None)
        self._err_fh = open(ERR_LOG, "a", encoding="utf-8")
        self._err_fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {self.name}: {' '.join(tx_argv)}\n")
        self._err_fh.flush()
        stdin = subprocess.DEVNULL
        if audio_cmd is not None:
            env = {**os.environ, **audio_cmd.env}
            self._audio = subprocess.Popen(
                audio_cmd.argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=self._err_fh, env=env, start_new_session=True,
            )
            stdin = self._audio.stdout
        self._tx = subprocess.Popen(
            tx_argv, stdin=stdin, stdout=self._err_fh, stderr=self._err_fh,
            start_new_session=True,
        )
        if self._audio is not None and self._audio.stdout is not None:
            self._audio.stdout.close()
        time.sleep(0.5)
        if self._tx.poll() is not None:
            rc = self._tx.returncode
            self.stop()
            raise RuntimeError(f"{self.name} beendet sofort (rc={rc}, Log {ERR_LOG})")

    def stop(self) -> None:
        tx, audio = self._tx, self._audio
        self._tx = self._audio = None
        if tx is not None:
            if tx.poll() is None:
                try:
                    os.kill(tx.pid, signal.SIGINT)
                    tx.wait(timeout=self.stop_timeout_s)
                except subprocess.TimeoutExpired:
                    try:
                        tx.terminate()
                        tx.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        tx.kill()
                        tx.wait(timeout=2)
                except ProcessLookupError:
                    pass
            self._last_rc = tx.returncode
        if audio is not None and audio.poll() is None:
            try:
                audio.terminate()
                audio.wait(timeout=2)
            except subprocess.TimeoutExpired:
                audio.kill()
            except ProcessLookupError:
                pass
        if self._err_fh is not None:
            try:
                self._err_fh.close()
            except Exception:
                pass
            self._err_fh = None
        if tx is not None:
            self.after_stop()

    def status(self) -> dict:
        tx = self._tx
        running = tx is not None and tx.poll() is None
        audio_ok = self._audio is None or self._audio.poll() is None
        if tx is not None and not running:
            self._last_rc = tx.returncode
        return {
            "running": bool(running and audio_ok),
            "pid": tx.pid if running else None,
            "audio_pid": self._audio.pid if (self._audio is not None and audio_ok) else None,
            "audio_ok": audio_ok,
            "rc": self._last_rc,
            "err": self._last_err,
            "log": ERR_LOG,
        }
