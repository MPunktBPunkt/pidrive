"""backend_chip.py — Phase 2: externer FM/RDS-Chip per I2C (QN8027 oder Si4713).

Vorteile gegenüber GPCLK: echter Sinusträger mit eingebautem Filter, deutlich
weniger Oberwellen, Leistung einstellbar, kein DMA/root-Risiko am Takt.
Audio kommt analog (Klinke des Pi oder USB-DAC → Line-In des Moduls);
„mirror“ heißt hier: der Chip sendet, was am Line-In anliegt.
„tone1k“ und die Boot-Ansage („announce“) laufen über Pulse auf den Default-Sink.

Konfiguration (fm_tx.chip):
  type        qn8027 | si4713
  bus         I2C-Bus (Pi: 1)
  addr        0x2C (QN8027) | 0x63 (Si4713, SEN=1) bzw. 0x11
  power       QN8027: PA_TRGT 0–127 · Si4713: 88–115 dBµV
  reset_gpio  Si4713 RST (optional, über pinctrl)
  xtal_24mhz  QN8027: true = 24-MHz-Quarz, false = 12 MHz

Registerwerte nach Datenblatt (QN8027 Rev 1.0, Si4712/13 AN332). Nicht am
Gerät verifiziert — vor Einsatz im Lab prüfen (Lab-Gate E-1, Abschnitt Chip).
Optionaler Import: smbus2. ESP-Knoten (Audio per TCP) folgt separat.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time

from modules.tx import audio_tap
from modules.tx.rds import groups_0a, groups_2a

try:
    from smbus2 import SMBus, i2c_msg  # type: ignore
except Exception:  # pragma: no cover - optional
    SMBus = None
    i2c_msg = None

CHIP_DEFAULTS = {
    "type": "qn8027",
    "bus": 1,
    "addr": "",
    "power": 0,
    "reset_gpio": None,
    "xtal_24mhz": False,
}

# QN8027
QN_ADDR = 0x2C
QN_SYSTEM, QN_CH1, QN_GPLT, QN_XTL, QN_VGA = 0x00, 0x01, 0x02, 0x03, 0x04
QN_STATUS, QN_RDSD0, QN_PAC, QN_FDEV, QN_RDS = 0x07, 0x08, 0x10, 0x11, 0x12
QN_SWRST, QN_RECAL, QN_TXREQ, QN_MONO, QN_RDSRDY = 0x80, 0x40, 0x20, 0x10, 0x04

# Si4713
SI_ADDR = 0x63
SI_POWER_UP, SI_POWER_DOWN, SI_SET_PROPERTY = 0x01, 0x11, 0x12
SI_TX_TUNE_FREQ, SI_TX_TUNE_POWER, SI_TX_RDS_BUFF, SI_TX_RDS_PS = 0x30, 0x31, 0x35, 0x36
SI_GET_INT_STATUS = 0x14
SI_PROP = {
    "TX_COMPONENT_ENABLE": 0x2100, "TX_AUDIO_DEVIATION": 0x2101,
    "TX_PILOT_DEVIATION": 0x2102, "TX_RDS_DEVIATION": 0x2103,
    "TX_PREEMPHASIS": 0x2106, "TX_RDS_PI": 0x2C01, "TX_RDS_PS_MIX": 0x2C02,
    "TX_RDS_PS_MISC": 0x2C03, "TX_RDS_PS_REPEAT_COUNT": 0x2C04,
    "TX_RDS_PS_MESSAGE_COUNT": 0x2C05, "TX_RDS_FIFO_SIZE": 0x2C07,
}


def qn8027_channel(freq_mhz: float) -> int:
    """QN8027: f = 76 MHz + CH · 50 kHz (CH 10 bit)."""
    ch = int(round((float(freq_mhz) - 76.0) / 0.05))
    if not 0 <= ch <= 0x3FF:
        raise ValueError(f"QN8027: Frequenz außerhalb 76–127 MHz ({freq_mhz})")
    return ch


def si4713_freq_units(freq_mhz: float) -> int:
    """Si4713: Frequenz in 10-kHz-Einheiten, 76–108 MHz, Raster 50 kHz."""
    u = int(round(float(freq_mhz) * 100))
    if not 7600 <= u <= 10800:
        raise ValueError(f"Si4713: Frequenz außerhalb 76–108 MHz ({freq_mhz})")
    return u


class ChipBackend:
    name = "chip"

    def __init__(self):
        self._bus = None
        self._cfg: dict = {}
        self._chip: dict = dict(CHIP_DEFAULTS)
        self._on = False
        self._tone: subprocess.Popen | None = None
        self._rds_thread: threading.Thread | None = None
        self._rds_stop = threading.Event()
        self._rds_lock = threading.Lock()
        self._ps = "PIDRIVE"
        self._rt = ""
        self._rt_ab = 0
        self._err = ""
        self._qn_rdsrdy = 0

    # ── Interface ──
    def capabilities(self) -> dict:
        chip = dict(CHIP_DEFAULTS)
        why = ""
        if SMBus is None:
            why = "smbus2 fehlt (pip install smbus2)"
        elif not os.path.exists(f"/dev/i2c-{int(chip['bus'])}"):
            why = f"/dev/i2c-{chip['bus']} fehlt (raspi-config → I2C aktivieren)"
        return {
            "name": self.name,
            "available": not why,
            "why": why,
            "bands": ["ukw"],
            "pins": [],
            "stereo": True,
            "rds": True,
            "sources": ["mirror", "tone1k", "carrier", "silence", "announce"],
            "chips": ["qn8027", "si4713"],
        }

    def start(self, cfg: dict, audio_cmd=None) -> None:
        self.stop()
        if SMBus is None:
            raise RuntimeError("smbus2 fehlt")
        self._cfg = dict(cfg)
        self._chip = {**CHIP_DEFAULTS, **(cfg.get("chip") or {})}
        f = float(cfg.get("freq_effective_mhz") or cfg.get("freq_mhz"))
        rds = cfg.get("rds") or {}
        self._ps = cfg.get("rds_ps") or rds.get("ps") or "PIDRIVE"
        self._rt = cfg.get("rds_rt") or rds.get("rt") or ""
        self._bus = SMBus(int(self._chip["bus"]))
        try:
            if self._chip["type"] == "si4713":
                self._si_start(f, cfg)
            else:
                self._qn_start(f, cfg)
        except Exception:
            self._close_bus()
            raise
        self._on = True
        if cfg.get("source") in ("tone1k", "silence", "announce"):
            self._start_tone(cfg.get("source"))
        if rds.get("enabled", True):
            self._rds_stop.clear()
            self._rds_thread = threading.Thread(target=self._rds_loop, daemon=True)
            self._rds_thread.start()

    def stop(self) -> None:
        self._rds_stop.set()
        if self._rds_thread is not None:
            self._rds_thread.join(timeout=2)
            self._rds_thread = None
        if self._tone is not None:
            try:
                self._tone.terminate()
                self._tone.wait(timeout=2)
            except Exception:
                try:
                    self._tone.kill()
                except Exception:
                    pass
            self._tone = None
        if self._bus is not None and self._on:
            try:
                if self._chip["type"] == "si4713":
                    self._si_cmd(SI_POWER_DOWN, [])
                else:
                    self._bus.write_byte_data(self._addr(), QN_SYSTEM, 0x00)
            except Exception as e:
                self._err = f"Stop: {e}"
        self._on = False
        self._close_bus()

    def set_rds(self, ps: str | None = None, rt: str | None = None) -> bool:
        with self._rds_lock:
            if ps is not None:
                self._ps = ps
                if self._on and self._chip["type"] == "si4713":
                    try:
                        self._si_write_ps()
                    except Exception as e:
                        self._err = f"RDS PS: {e}"
                        return False
            if rt is not None and rt != self._rt:
                self._rt = rt
                self._rt_ab ^= 1
        return self._on

    def status(self) -> dict:
        tone_ok = self._tone is None or self._tone.poll() is None
        return {
            "running": bool(self._on and tone_ok),
            "pid": None,
            "chip": self._chip.get("type"),
            "addr": hex(self._addr()) if self._chip else None,
            "rc": None,
            "err": self._err,
        }

    # ── intern ──
    def _addr(self) -> int:
        a = self._chip.get("addr")
        if a not in (None, ""):
            return int(str(a), 0)
        return SI_ADDR if self._chip.get("type") == "si4713" else QN_ADDR

    def _close_bus(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None

    def _start_tone(self, source: str) -> None:
        ff = audio_tap.build_cmd(source, stereo=True)
        if ff is None:
            return
        argv = [a for a in ff.argv]
        argv = argv[:argv.index("-ac")] + ["-f", "pulse", "fmtx-tone"]
        self._tone = subprocess.Popen(argv, env={**os.environ, **ff.env},
                                      stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # QN8027
    def _qn_w(self, reg: int, val: int) -> None:
        self._bus.write_byte_data(self._addr(), reg, val & 0xFF)

    def _qn_start(self, f: float, cfg: dict) -> None:
        ch = qn8027_channel(f)
        self._qn_w(QN_SYSTEM, QN_SWRST)
        time.sleep(0.02)
        self._qn_w(QN_SYSTEM, QN_RECAL)
        time.sleep(0.02)
        self._qn_w(QN_SYSTEM, 0x00)
        vga = 0x80 if self._chip.get("xtal_24mhz") else 0x00
        self._qn_w(QN_VGA, vga | 0x3B)
        preemph_75 = 0x80 if int(cfg.get("preemph_us", 50)) == 75 else 0x00
        self._qn_w(QN_GPLT, preemph_75 | 0x30 | 0x09)
        self._qn_w(QN_CH1, ch & 0xFF)
        if self._chip.get("power"):
            self._qn_w(QN_PAC, int(self._chip["power"]) & 0x7F)
        rds_en = 0x80 if (cfg.get("rds") or {}).get("enabled", True) else 0x00
        self._qn_w(QN_RDS, rds_en | 0x06)
        mono = 0x00 if cfg.get("stereo", True) else QN_MONO
        self._qn_rdsrdy = 0
        self._qn_w(QN_SYSTEM, QN_TXREQ | mono | ((ch >> 8) & 0x03))

    def _qn_send_group(self, blocks: tuple) -> None:
        data = []
        for b in blocks:
            data += [(b >> 8) & 0xFF, b & 0xFF]
        for i, v in enumerate(data):
            self._qn_w(QN_RDSD0 + i, v)
        sys_val = self._bus.read_byte_data(self._addr(), QN_SYSTEM)
        self._qn_rdsrdy ^= QN_RDSRDY
        self._qn_w(QN_SYSTEM, (sys_val & ~QN_RDSRDY) | self._qn_rdsrdy)
        time.sleep(0.088)

    # Si4713
    def _si_cmd(self, cmd: int, args: list[int], wait_s: float = 0.01) -> None:
        msg = i2c_msg.write(self._addr(), [cmd] + [a & 0xFF for a in args])
        self._bus.i2c_rdwr(msg)
        time.sleep(wait_s)
        for _ in range(50):
            rd = i2c_msg.read(self._addr(), 1)
            self._bus.i2c_rdwr(rd)
            if list(rd)[0] & 0x80:
                return
            time.sleep(0.01)
        raise RuntimeError(f"Si4713: CTS-Timeout nach Kommando 0x{cmd:02X}")

    def _si_prop(self, name: str, val: int) -> None:
        p = SI_PROP[name]
        self._si_cmd(SI_SET_PROPERTY, [0x00, p >> 8, p & 0xFF, (val >> 8) & 0xFF, val & 0xFF])

    def _si_start(self, f: float, cfg: dict) -> None:
        rst = self._chip.get("reset_gpio")
        if rst not in (None, ""):
            subprocess.run(["pinctrl", "set", str(int(rst)), "op", "dl"], check=False)
            time.sleep(0.01)
            subprocess.run(["pinctrl", "set", str(int(rst)), "op", "dh"], check=False)
            time.sleep(0.11)
        self._si_cmd(SI_POWER_UP, [0x12, 0x50], wait_s=0.2)
        self._si_prop("TX_PREEMPHASIS", 0 if int(cfg.get("preemph_us", 50)) == 75 else 1)
        self._si_prop("TX_AUDIO_DEVIATION", 6625)
        self._si_prop("TX_PILOT_DEVIATION", 675)
        self._si_prop("TX_RDS_DEVIATION", 200)
        rds = cfg.get("rds") or {}
        comp = 0x0001 | (0x0002 if cfg.get("stereo", True) else 0) | (0x0004 if rds.get("enabled", True) else 0)
        self._si_prop("TX_COMPONENT_ENABLE", comp)
        self._si_prop("TX_RDS_PI", int(str(rds.get("pi") or "D3A2"), 16))
        self._si_prop("TX_RDS_PS_MIX", 0x03)
        self._si_prop("TX_RDS_PS_MISC", 0x1808)
        self._si_prop("TX_RDS_PS_REPEAT_COUNT", 3)
        self._si_prop("TX_RDS_PS_MESSAGE_COUNT", 1)
        self._si_prop("TX_RDS_FIFO_SIZE", 0)
        u = si4713_freq_units(f)
        self._si_cmd(SI_TX_TUNE_FREQ, [0x00, u >> 8, u & 0xFF], wait_s=0.1)
        power = int(self._chip.get("power") or 88)
        power = max(88, min(115, power))
        self._si_cmd(SI_TX_TUNE_POWER, [0x00, 0x00, power, 0x00], wait_s=0.1)
        self._si_write_ps()

    def _si_write_ps(self) -> None:
        ps = (self._ps or "").ljust(8)[:8]
        for i in range(2):
            chars = [ord(c) for c in ps[4 * i:4 * i + 4]]
            self._si_cmd(SI_TX_RDS_PS, [i] + chars)

    def _si_send_rt(self) -> None:
        pi = int(str((self._cfg.get("rds") or {}).get("pi") or "D3A2"), 16)
        groups = groups_2a(pi, self._rt, self._rt_ab)
        first = True
        for _a, b, c, d in groups:
            flags = 0x06 if first else 0x04
            first = False
            self._si_cmd(SI_TX_RDS_BUFF, [flags, b >> 8, b & 0xFF, c >> 8, c & 0xFF, d >> 8, d & 0xFF])

    def _rds_loop(self) -> None:
        last_rt = None
        pi = int(str((self._cfg.get("rds") or {}).get("pi") or "D3A2"), 16)
        while not self._rds_stop.is_set():
            try:
                with self._rds_lock:
                    ps, rt, ab = self._ps, self._rt, self._rt_ab
                if self._chip["type"] == "si4713":
                    if rt != last_rt:
                        self._si_send_rt()
                        last_rt = rt
                    self._rds_stop.wait(1.0)
                    continue
                for g in groups_0a(pi, ps) + groups_2a(pi, rt, ab):
                    if self._rds_stop.is_set():
                        break
                    self._qn_send_group(g)
            except Exception as e:
                self._err = f"RDS: {e}"
                self._rds_stop.wait(2.0)
