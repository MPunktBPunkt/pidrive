#!/usr/bin/env python3
"""NBT HU state simulator for Lab ESP (Stufe 2).

Models File-Cache eager-read + next-prefetch + realistic producer, classifies
read bytes, and runs Golden G1–G5 against FW 0.4.46 (stall_ms=0).

  sg disk -c 'python3 tools/nbt_hu_sim.py --golden G1 --sg /dev/sg0'
  python3 tools/nbt_hu_sim.py --self-test   # classifier / producer offline

See docs/betrieb/artifacts-2026-10-06-lab/KONZEPT-HU-SIM-NBT-2026-10-06.md
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SECTOR = 512
SG_IO = 0x2285
KIND_AUDIO = 0x55
KIND_ID3 = 0x56
READ_N = 4096
TOL = 4096  # Golden ±1 read

# MPEG-1 L3 stereo 48k silence frame (Mp3Silence.h / StreamBuffer kSil)
KSIL = bytes(
    [
        0xFF, 0xFB, 0x30, 0x64, 0x00, 0x0F, 0xF0, 0x00, 0x00, 0x69, 0x00, 0x00, 0x00, 0x08,
        0x00, 0x00, 0x0D, 0x20, 0x00, 0x00, 0x01, 0x00, 0x00, 0x01, 0xA4, 0x00, 0x00, 0x00,
        0x20, 0x00, 0x00, 0x34, 0x80, 0x00, 0x00, 0x04, 0x4C, 0x41, 0x4D, 0x45, 0x33, 0x2E,
        0x31, 0x30, 0x30, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x4C, 0x41, 0x4D, 0x45, 0x33, 0x2E, 0x31, 0x30, 0x30, 0x55,
        0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55,
        0x55, 0x55,
    ]
)

# Minimal MPEG-2 L3 mono 48k @ 22.05 kHz header (FF F3 …) + pad; PDSQ stamped in payload
FF_F3_HDR = bytes([0xFF, 0xF3, 0x40, 0xC4])  # rough sync for classifier


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 12) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def http_post_allow_empty(url: str, body: bytes = b"{}", timeout: float = 12) -> dict:
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode())
        except json.JSONDecodeError:
            return {"_raw": raw.decode(errors="replace")[:200]}


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text())


# --- SG_IO (from nbt_replay pattern) ----------------------------------------


def read_sg(sg_fd: int, lba: int, nbytes: int, timeout_ms: int = 5000) -> tuple[bytes, dict]:
    import ctypes
    import fcntl

    if nbytes % SECTOR:
        raise ValueError(f"SG size must be sector-multiple, got {nbytes}")
    nsec = nbytes // SECTOR
    cmd = struct.pack(">BBIBHB", 0x28, 0, lba & 0xFFFFFFFF, 0, nsec & 0xFFFF, 0)

    class SgIoHdr(ctypes.Structure):
        _fields_ = [
            ("interface_id", ctypes.c_int),
            ("dxfer_direction", ctypes.c_int),
            ("cmd_len", ctypes.c_ubyte),
            ("mx_sb_len", ctypes.c_ubyte),
            ("iovec_count", ctypes.c_ushort),
            ("dxfer_len", ctypes.c_uint),
            ("dxferp", ctypes.c_void_p),
            ("cmdp", ctypes.c_void_p),
            ("sbp", ctypes.c_void_p),
            ("timeout", ctypes.c_uint),
            ("flags", ctypes.c_uint),
            ("pack_id", ctypes.c_int),
            ("usr_ptr", ctypes.c_void_p),
            ("status", ctypes.c_ubyte),
            ("masked_status", ctypes.c_ubyte),
            ("msg_status", ctypes.c_ubyte),
            ("sb_len_wr", ctypes.c_ubyte),
            ("host_status", ctypes.c_ushort),
            ("driver_status", ctypes.c_ushort),
            ("resid", ctypes.c_int),
            ("duration", ctypes.c_uint),
            ("info", ctypes.c_uint),
        ]

    SG_DXFER_FROM_DEV = -3
    dxfer_arr = (ctypes.c_ubyte * nbytes)()
    cmd_buf = (ctypes.c_ubyte * len(cmd)).from_buffer_copy(cmd)
    sb_arr = (ctypes.c_ubyte * 32)()
    hdr = SgIoHdr()
    hdr.interface_id = ord("S")
    hdr.dxfer_direction = SG_DXFER_FROM_DEV
    hdr.cmd_len = len(cmd)
    hdr.mx_sb_len = 32
    hdr.dxfer_len = nbytes
    hdr.dxferp = ctypes.addressof(dxfer_arr)
    hdr.cmdp = ctypes.addressof(cmd_buf)
    hdr.sbp = ctypes.addressof(sb_arr)
    hdr.timeout = timeout_ms
    fcntl.ioctl(sg_fd, SG_IO, hdr)
    meta = {
        "status": hdr.status,
        "host_status": hdr.host_status,
        "driver_status": hdr.driver_status,
        "duration_ms": hdr.duration,
        "resid": hdr.resid,
    }
    if hdr.status not in (0,):
        raise OSError(f"SG_IO status={hdr.status} host={hdr.host_status} drv={hdr.driver_status}")
    return bytes(dxfer_arr), meta


# --- Classifier + virtual ear -----------------------------------------------


@dataclass
class LiveStamp:
    seq: int
    abs_off: int


def find_pdsq(blob: bytes) -> LiveStamp | None:
    magic = b"PDSQ"
    i = 0
    while True:
        j = blob.find(magic, i)
        if j < 0 or j + 16 > len(blob):
            return None
        seq, abs_off, crc = struct.unpack_from(">III", blob, j + 4)
        body = blob[j : j + 12]
        if zlib.crc32(body) & 0xFFFFFFFF == crc:
            return LiveStamp(seq=seq, abs_off=abs_off)
        i = j + 1


def classify_block(blob: bytes, file_off: int = 0, id3_len: int = 64) -> str:
    if file_off < id3_len or blob.startswith(b"ID3"):
        return "ID3"
    if b"Q3B1" in blob[:64] or b"Q3B1" in blob:
        return "SEED"
    if find_pdsq(blob) is not None:
        return "LIVE"
    # silence: header + LAME tag
    if blob[:4] == KSIL[:4] or (b"\xff\xfb\x30\x64" in blob[:8] and b"LAME3.100" in blob):
        # majority silence tiles
        hits = sum(1 for o in range(0, len(blob) - 4, 156) if blob[o : o + 4] == KSIL[:4])
        if hits >= max(1, len(blob) // 312) or b"LAME3.100" in blob:
            return "SILENCE"
    if blob[:2] == b"\xff\xf3" or blob[:2] == b"\xff\xfb":
        return "OTHER"
    # dense FF padding / silence-like
    if blob.count(0xFF) > len(blob) * 0.85:
        return "SILENCE"
    return "OTHER"


@dataclass
class EarEvent:
    t_mono: float
    kind: str
    detail: dict = field(default_factory=dict)


class VirtualEar:
    def __init__(self, bitrate_bps: int = 48000, decode_start: str = "incremental:8"):
        self.bps = bitrate_bps // 8  # bytes/s audio
        self.decode_start = decode_start
        self.live_bytes = 0
        self.consumed = 0
        self.play_t0: float | None = None
        self.last_seq: int | None = None
        self.events: list[EarEvent] = []
        self._armed_bytes = 0
        if decode_start.startswith("incremental:"):
            self._need_before_play = int(decode_start.split(":")[1]) * 1024
        else:
            self._need_before_play = 10**12  # after_eof handled externally

    def on_block(self, klass: str, blob: bytes, t_mono: float) -> None:
        if klass == "LIVE":
            st = find_pdsq(blob)
            n = len(blob)
            self.live_bytes += n
            self._armed_bytes += n
            if st:
                if self.last_seq is not None:
                    if st.seq > self.last_seq + 1:
                        self.events.append(
                            EarEvent(t_mono, "gap_in_content", {"from": self.last_seq, "to": st.seq})
                        )
                    elif st.seq < self.last_seq:
                        self.events.append(
                            EarEvent(t_mono, "duplicate", {"seq": st.seq, "last": self.last_seq})
                        )
                self.last_seq = st.seq
            if self.play_t0 is None and self._armed_bytes >= self._need_before_play:
                self.play_t0 = t_mono
        elif klass == "SILENCE" and self.live_bytes > 0 and self.play_t0 is not None:
            self.events.append(EarEvent(t_mono, "silence_in_play", {}))

    def tick(self, t_mono: float) -> None:
        if self.play_t0 is None:
            return
        target = int((t_mono - self.play_t0) * self.bps)
        if target > self.consumed:
            self.consumed = target
        buf = self.live_bytes - self.consumed
        if buf <= 0:
            self.events.append(EarEvent(t_mono, "dropout", {"buf": buf}))

    def report(self) -> dict:
        kinds: dict[str, int] = {}
        for e in self.events:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
        return {
            "live_bytes": self.live_bytes,
            "consumed": self.consumed,
            "events": kinds,
            "event_list": [{"t": e.t_mono, "kind": e.kind, **e.detail} for e in self.events[:50]],
        }


# --- Producer with PDSQ -----------------------------------------------------


def make_pdsq_chunk(seq: int, abs_off: int, n: int = 256) -> bytes:
    """Build n bytes starting with FF F3 sync + PDSQ stamp (CRC over first 12 B of stamp)."""
    stamp_body = b"PDSQ" + struct.pack(">II", seq & 0xFFFFFFFF, abs_off & 0xFFFFFFFF)
    crc = zlib.crc32(stamp_body) & 0xFFFFFFFF
    stamp = stamp_body + struct.pack(">I", crc)
    pad = n - len(FF_F3_HDR) - len(stamp)
    if pad < 0:
        raise ValueError("chunk too small")
    return FF_F3_HDR + stamp + (b"\x00" * pad)


def id3_tag(title: str) -> bytes:
    enc = b"\x03" + title.encode("utf-8")
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    return b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    ) + frame


class PumpTcp:
    def __init__(self, host: str, port: int = 9090, retries: int = 20):
        last: Exception | None = None
        self.s = None
        for _ in range(retries):
            try:
                self.s = socket.create_connection((host, port), timeout=8)
                self.s.settimeout(0.35)
                return
            except Exception as e:
                last = e
                time.sleep(0.5)
        raise ConnectionError(f"pump {host}:{port}: {last}")

    def close(self) -> None:
        try:
            self.s.close()
        except Exception:
            pass

    def send_json(self, obj: dict) -> None:
        self.s.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def send_bin(self, kind: int, payload: bytes) -> None:
        # PumpServer V0.4: 0x01 | kind | len_lo | len_hi | payload (max 512)
        n = len(payload)
        if n > 512:
            raise ValueError(f"bin payload {n} > 512")
        hdr = bytes((0x01, kind, n & 0xFF, (n >> 8) & 0xFF))
        self.s.sendall(hdr + payload)

    def drain(self, seconds: float) -> None:
        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                self.s.recv(4096)
            except Exception:
                time.sleep(0.02)


class RealisticProducer(threading.Thread):
    """1.45× for ~60 s then realtime; optional gaps; PDSQ frames."""

    def __init__(
        self,
        pump: PumpTcp,
        stop: threading.Event,
        bitrate_bps: int = 48000,
        start_delay_s: float = 3.4,
        burst_factor: float = 1.45,
        burst_s: float = 60.0,
        gaps: list[tuple[float, float]] | None = None,
    ):
        super().__init__(daemon=True)
        self.pump = pump
        self.stop = stop
        self.realtime = bitrate_bps // 8
        self.start_delay_s = start_delay_s
        self.burst_factor = burst_factor
        self.burst_s = burst_s
        self.gaps = gaps or []
        self.stats = {"bytes": 0, "seq": 0, "err": None}

    def run(self) -> None:
        t_arm = time.monotonic()
        while not self.stop.is_set() and time.monotonic() - t_arm < self.start_delay_s:
            time.sleep(0.05)
        t0 = time.monotonic()
        abs_off = 0
        seq = 0
        gap_i = 0
        try:
            while not self.stop.is_set():
                elapsed = time.monotonic() - t0
                # inject gaps relative to producer start
                while gap_i < len(self.gaps) and elapsed >= self.gaps[gap_i][0]:
                    pause = self.gaps[gap_i][1]
                    gap_i += 1
                    time.sleep(pause)
                    elapsed = time.monotonic() - t0
                rate = self.realtime * (self.burst_factor if elapsed < self.burst_s else 1.0)
                chunk = make_pdsq_chunk(seq, abs_off, 256)
                self.pump.send_bin(KIND_AUDIO, chunk)
                abs_off += len(chunk)
                seq += 1
                self.stats["bytes"] = abs_off
                self.stats["seq"] = seq
                time.sleep(len(chunk) / max(1.0, rate))
        except Exception as e:
            self.stats["err"] = str(e)


# --- HU model ---------------------------------------------------------------


@dataclass
class SlotInfo:
    uid: str
    lba0: int
    lba1: int
    size: int


@dataclass
class CacheEntry:
    covered: int = 0  # bytes read from head


class HuSim:
    def __init__(
        self,
        sg_path: str,
        profile: dict,
        gap_ms: float | None = None,
        cmd_timeout_ms: int = 5000,
        events: list | None = None,
    ):
        self.sg_path = sg_path
        self.profile = profile
        self.gap_ms = gap_ms if gap_ms is not None else float(profile.get("read", {}).get("gap_ms_target", 4))
        self.cmd_timeout_ms = cmd_timeout_ms
        self.events = events if events is not None else []
        self.cache: dict[str, CacheEntry] = {}
        self.slots: dict[str, SlotInfo] = {}
        self.ear = VirtualEar()
        self.class_counts: dict[str, int] = {}
        self.bytes_before_arm = 0
        self.bytes_after_arm = 0
        self._armed = False
        self.sg_fd = -1

    def open(self) -> None:
        if self.sg_fd >= 0:
            try:
                os.close(self.sg_fd)
            except OSError:
                pass
            self.sg_fd = -1
        # wait for sg node after remount/rst
        t0 = time.time()
        last: Exception | None = None
        while time.time() - t0 < 25:
            try:
                if Path(self.sg_path).exists():
                    self.sg_fd = os.open(self.sg_path, os.O_RDONLY)
                    # probe
                    read_sg(self.sg_fd, 0, SECTOR, 3000)
                    return
            except Exception as e:
                last = e
                if self.sg_fd >= 0:
                    try:
                        os.close(self.sg_fd)
                    except OSError:
                        pass
                    self.sg_fd = -1
                time.sleep(0.4)
        raise SystemExit(f"sg not ready: {self.sg_path}: {last}")

    def close(self) -> None:
        if self.sg_fd >= 0:
            os.close(self.sg_fd)
            self.sg_fd = -1

    def refresh_slots(self, esp: str) -> None:
        st = http_json(f"{esp.rstrip('/')}/api/status")
        sm = (st.get("msc") or {}).get("slotMap") or []
        self.slots.clear()
        for s in sm:
            if not isinstance(s, dict) or not s.get("uid"):
                continue
            l0, l1 = int(s["lba0"]), int(s["lba1"])
            self.slots[s["uid"]] = SlotInfo(s["uid"], l0, l1, max(512, (l1 - l0 + 1) * 512))

    def _log(self, **kw: Any) -> None:
        kw["t"] = time.monotonic()
        self.events.append(kw)

    def read_n(self, uid: str, file_off: int, n: int = READ_N) -> bytes:
        slot = self.slots[uid]
        if file_off + n > slot.size:
            n = slot.size - file_off
        if n <= 0:
            return b""
        n = (n // SECTOR) * SECTOR
        if n <= 0:
            return b""
        lba = slot.lba0 + file_off // SECTOR
        blob, meta = read_sg(self.sg_fd, lba, n, self.cmd_timeout_ms)
        klass = classify_block(blob, file_off)
        self.class_counts[klass] = self.class_counts.get(klass, 0) + 1
        self.ear.on_block(klass, blob, time.monotonic())
        ce = self.cache.setdefault(uid, CacheEntry())
        ce.covered = max(ce.covered, file_off + len(blob))
        if self._armed:
            self.bytes_after_arm += len(blob)
        else:
            self.bytes_before_arm += len(blob)
        self._log(
            op="read",
            uid=uid,
            off=file_off,
            n=len(blob),
            klass=klass,
            dur_ms=meta.get("duration_ms"),
        )
        if self.gap_ms > 0:
            time.sleep(self.gap_ms / 1000.0)
        return blob

    def eager_read(self, uid: str, until: int | None = None, stop_at: int | None = None) -> int:
        """Sequential 4 KiB reads. stop_at = absolute file off to stop before (for G1 mid-arm)."""
        slot = self.slots[uid]
        ce = self.cache.setdefault(uid, CacheEntry())
        off = ce.covered
        limit = until if until is not None else slot.size
        if stop_at is not None:
            limit = min(limit, stop_at)
        while off < limit:
            blob = self.read_n(uid, off)
            if not blob:
                break
            off += len(blob)
        return off

    def mark_armed(self) -> None:
        self._armed = True
        self._log(op="arm")

    def select_heads(self, uid: str) -> None:
        """Selecting: 4+12+32 KiB head pattern (approx)."""
        for n in (4096, 12288, 32768):
            off = self.cache.get(uid, CacheEntry()).covered
            if off >= n:
                continue
            self.read_n(uid, off, min(READ_N, n - off))
            # continue filling to n
            while self.cache[uid].covered < n and self.cache[uid].covered < self.slots[uid].size:
                self.read_n(uid, self.cache[uid].covered)


def snap(esp: str) -> dict:
    st = http_json(f"{esp.rstrip('/')}/api/status")
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    und = int(s.get("underruns") or 0)
    abs_base = int(s.get("absBase") or 0)
    abs_end = int(s.get("absEnd") or 0)
    ring_size = int(s.get("size") or 0)
    if ring_size <= 0 and abs_end >= abs_base:
        ring_size = abs_end - abs_base
    slots = []
    for x in m.get("slotMap") or []:
        if isinstance(x, dict):
            slots.append(
                {
                    "uid": x.get("uid"),
                    "bytes": x.get("bytes"),
                    "maxSeq": x.get("maxSeq"),
                    "lba0": x.get("lba0"),
                    "lba1": x.get("lba1"),
                }
            )
    return {
        "version": st.get("version"),
        "uptime": st.get("uptime"),
        "play": st.get("playingUid"),
        "armed": s.get("cursorArmed"),
        "hostAbs": int(s.get("hostAbsCursor") or 0),
        "absEnd": abs_end,
        "absBase": abs_base,
        "streamBytes": sb,
        "underruns": und,
        "liveBytes": max(0, sb - und),
        "ring_size": ring_size,
        "ring_cap": int(s.get("cap") or 49152),
        "readCount": m.get("readCount"),
        "slots": slots,
    }


def near(a: int, b: int, tol: int = TOL) -> bool:
    return abs(int(a) - int(b)) <= tol


def wait_esp(esp: str, timeout: float = 45.0) -> None:
    """Wait until HTTP status is ok (pumpTcpUp = client connected, not listen-ready)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st = http_json(f"{esp.rstrip('/')}/api/status", timeout=3)
            if st.get("ok"):
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit(f"ESP not ready: {esp}")


def soft_rst(esp: str) -> None:
    try:
        http_post_allow_empty(f"{esp.rstrip('/')}/api/restart", body=b"{}")
    except Exception:
        pass
    wait_esp(esp, 60.0)


def prep_lab(esp: str, esp_ip: str, pump: PumpTcp | None, *, remount: bool = True) -> PumpTcp:
    """Connect pump, set menu, optional remount. Returns live pump (reconnected after remount)."""
    wait_esp(esp, 30.0)
    if pump is not None:
        try:
            pump.close()
        except Exception:
            pass

    def handshake() -> PumpTcp:
        p = PumpTcp(esp_ip)
        p.send_json({"t": "hello", "ver": 1})
        time.sleep(0.25)
        try:
            p.drain(0.25)
        except Exception:
            pass
        # audio_stop is optional; some FW builds drop the socket around stop
        try:
            p.send_json({"t": "audio_stop"})
            time.sleep(0.05)
        except (BrokenPipeError, OSError):
            p.close()
            p = PumpTcp(esp_ip)
            p.send_json({"t": "hello", "ver": 1})
            time.sleep(0.25)
        p.send_json(
            {
                "t": "menu_set",
                "rev": 1,
                "page": 0,
                "items": [
                    {"uid": "fav0", "name": "Rock Antenne", "kind": "station"},
                    {"uid": "fav1", "name": "Rock Antenne Bayern", "kind": "station"},
                    {"uid": "fav2", "name": "Radio BOB!", "kind": "station"},
                    {"uid": "pump:page_next", "name": "Menue", "kind": "action"},
                ],
            }
        )
        time.sleep(0.25)
        try:
            p.drain(0.25)
        except Exception:
            pass
        return p

    last: Exception | None = None
    pump_out: PumpTcp | None = None
    for _ in range(4):
        try:
            pump_out = handshake()
            break
        except (BrokenPipeError, OSError, ConnectionError) as e:
            last = e
            time.sleep(1.0)
            wait_esp(esp, 30.0)
    if pump_out is None:
        raise ConnectionError(f"prep_lab handshake failed: {last}")

    if remount:
        try:
            http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
        except Exception:
            pass
        wait_esp(esp, 60.0)
        time.sleep(1.0)
        try:
            pump_out.close()
        except Exception:
            pass
        last = None
        pump_out = None
        for _ in range(4):
            try:
                pump_out = handshake()
                break
            except (BrokenPipeError, OSError, ConnectionError) as e:
                last = e
                time.sleep(1.0)
                wait_esp(esp, 30.0)
        if pump_out is None:
            raise ConnectionError(f"prep_lab post-remount failed: {last}")
    return pump_out


def arm_uid(pump: PumpTcp, uid: str) -> None:
    pump.send_json(
        {
            "t": "audio_start",
            "uid": uid,
            "codec": "mp3",
            "br": "48k",
            "cSrc": "lab",
            "cPath": "lab",
            "cTry": "lab",
        }
    )
    pump.drain(0.3)
    pump.send_bin(KIND_ID3, id3_tag("nbt_hu_sim"))


# --- Golden scenarios -------------------------------------------------------


def run_g1(hu: HuSim, esp: str, pump: PumpTcp, out: Path, producer: RealisticProducer | None) -> dict:
    """Muster A: ~86 KiB before arm, rest as underrun/silence."""
    pre_arm = 86016
    hu.refresh_slots(esp)
    arm_uid(pump, "fav1")
    # Field: host already reading before ack — simulate by reading first, then mark arm
    # Order: start producer delayed, read pre_arm without counting as armed, then arm flag, rest
    hu._armed = False
    hu.eager_read("fav1", stop_at=pre_arm)
    hu.mark_armed()
    # Muster A = empty/near-empty ring: do not feed producer during the burst read
    # (field 07:58 had live=0). Optional producer after EOF would be a different scenario.
    hu.eager_read("fav1")  # to EOF
    # next prefetch
    hu.eager_read("fav2")
    time.sleep(0.5)
    post = snap(esp)
    (out / "status-g1.json").write_text(json.dumps(post, indent=2))
    size = hu.slots["fav1"].size
    expect_und = size - pre_arm  # ~438272 when silence for rest
    live = int(post.get("liveBytes") or 0)
    ear = hu.ear.report()
    ear_live = int(ear.get("live_bytes") or 0)
    # polluted streamBytesServed_ → ignore FW liveBytes; ear/classifier is source of truth
    checks = {
        "bytes_before_arm": hu.bytes_before_arm,
        "expect_before": pre_arm,
        "before_ok": near(hu.bytes_before_arm, pre_arm),
        "hostAbs": post["hostAbs"],
        "underruns": post["underruns"],
        "expect_und_host": expect_und,
        "und_host_ok": (
            near(post["underruns"], expect_und)
            or near(post["underruns"], post["hostAbs"])
            or near(post["underruns"], size)
            or int(post["underruns"]) >= expect_und - TOL
        ),
        "liveBytes_fw": live,
        "liveBytes_ear": ear_live,
        "live_ok": ear_live < 4096,
        "class_counts": dict(hu.class_counts),
        "ear": ear,
    }
    checks["pass"] = bool(checks["before_ok"] and checks["und_host_ok"] and checks["live_ok"])
    return checks


def fill_ring_fast(pump: PumpTcp, esp: str, target: int = 49152, timeout_s: float = 25.0) -> dict:
    """Push audio until stream ring is full (01.10. / G3 precondition)."""
    seq = 0
    abs_off = 0
    t0 = time.monotonic()
    last_poll = 0.0
    last = snap(esp)
    while time.monotonic() - t0 < timeout_s:
        now = time.monotonic()
        if now - last_poll >= 0.4:
            last = snap(esp)
            last_poll = now
            fill = int(last.get("ring_size") or 0)
            if fill <= 0:
                fill = max(0, int(last.get("absEnd") or 0) - int(last.get("absBase") or 0))
            if fill >= target - 1024:
                return {"fill": fill, "wait_s": round(now - t0, 3), "snap": last}
        chunk = make_pdsq_chunk(seq, abs_off, 256)
        try:
            pump.send_bin(KIND_AUDIO, chunk)
        except Exception as e:
            return {
                "fill": int(last.get("ring_size") or 0),
                "wait_s": round(time.monotonic() - t0, 3),
                "err": str(e),
                "snap": last,
            }
        seq += 1
        abs_off += len(chunk)
        time.sleep(0.004)
    fill = int(last.get("ring_size") or 0)
    if fill <= 0:
        fill = max(0, int(last.get("absEnd") or 0) - int(last.get("absBase") or 0))
    return {"fill": fill, "wait_s": round(time.monotonic() - t0, 3), "snap": last, "timeout": True}


def run_g3(hu: HuSim, esp: str, pump: PumpTcp, out: Path) -> dict:
    """01.10. equivalent: ring full at first body read → ~49152 B LIVE, then silence."""
    expect_live = 49152
    hu.refresh_slots(esp)
    arm_uid(pump, "fav1")
    hu.mark_armed()
    fill = fill_ring_fast(pump, esp, target=expect_live)
    (out / "status-g3-pre-read.json").write_text(json.dumps(fill.get("snap") or {}, indent=2))
    time.sleep(0.5)  # let ESP HTTP/USB settle after fill
    # Host reads whole fav1 while ring cannot be refilled at HU rate (~1 MB/s)
    hu.class_counts.clear()
    hu.ear = VirtualEar(decode_start="incremental:8")
    hu.eager_read("fav1")
    time.sleep(0.8)
    post = snap(esp)
    (out / "status-g3.json").write_text(json.dumps(post, indent=2))
    live = int(post.get("liveBytes") or 0)
    fill_n = int(fill.get("fill") or 0)
    ear = hu.ear.report()
    ear_live = int(ear.get("live_bytes") or 0)
    sil_after_live = int(ear.get("events", {}).get("silence_in_play") or 0) > 0
    # FW liveBytes can be polluted (streamBytesServed_ not reset on startStream — Freeze O2).
    # Prefer classifier/ear LIVE ≈ one ring, then silence.
    live_ok = (
        near(ear_live, expect_live, tol=16384)
        or (35000 <= ear_live <= 60000)
        or near(live, expect_live, tol=16384)
    )
    checks = {
        "fill_pre": fill_n,
        "fill_wait_s": fill.get("wait_s"),
        "fill_ok": fill_n >= expect_live - 4096,
        "liveBytes_fw": live,
        "liveBytes_ear": ear_live,
        "expect_live": expect_live,
        "live_ok": live_ok,
        "underruns": post.get("underruns"),
        "hostAbs": post.get("hostAbs"),
        "class_counts": dict(hu.class_counts),
        "ear": ear,
        "silence_after_live": sil_after_live,
    }
    checks["pass"] = bool(checks["fill_ok"] and checks["live_ok"] and checks["silence_after_live"])
    return checks


def run_g2(hu: HuSim, esp: str, pump: PumpTcp, out: Path) -> dict:
    """Muster B: full file cached before arm → hostAbs≈0 / no further underrun growth."""
    hu.refresh_slots(esp)
    hu.eager_read("fav1")
    pre = snap(esp)
    arm_uid(pump, "fav1")
    time.sleep(0.8)
    # no further body reads — cache full
    post = snap(esp)
    (out / "status-g2-pre.json").write_text(json.dumps(pre, indent=2))
    (out / "status-g2.json").write_text(json.dumps(post, indent=2))
    fav1 = next((s for s in post["slots"] if s["uid"] == "fav1"), {})
    und_delta = int(post["underruns"]) - int(pre["underruns"])
    host_delta = int(post["hostAbs"]) - int(pre["hostAbs"])
    checks = {
        "maxSeq": fav1.get("maxSeq"),
        "hostAbs_pre": pre["hostAbs"],
        "hostAbs_after_arm": post["hostAbs"],
        "und_delta": und_delta,
        "host_delta": host_delta,
        "armed": post["armed"],
        "file_full": near(int(fav1.get("maxSeq") or 0), hu.slots["fav1"].size)
        or int(fav1.get("maxSeq") or 0) >= hu.slots["fav1"].size * 0.9,
        # Ideal field G2: hostAbs=0; lab: no growth after arm (remount may reset counters → negative delta OK)
        "host_ok": post["hostAbs"] == 0 or host_delta == 0,
        "und_ok": und_delta <= 0,
    }
    checks["pass"] = bool(checks["file_full"] and checks["host_ok"] and checks["und_ok"])
    return checks


def run_g4(hu: HuSim, esp: str, pump: PumpTcp, out: Path) -> dict:
    """Next-prefetch: after fav1 EOF, fav2 fully read."""
    hu.refresh_slots(esp)
    arm_uid(pump, "fav1")
    hu.mark_armed()
    hu.eager_read("fav1")
    t_eof = time.monotonic()
    hu.eager_read("fav2")
    dt = time.monotonic() - t_eof
    post = snap(esp)
    (out / "status-g4.json").write_text(json.dumps(post, indent=2))
    fav2 = next((s for s in post["slots"] if s["uid"] == "fav2"), {})
    checks = {
        "fav2_maxSeq": fav2.get("maxSeq"),
        "prefetch_s": round(dt, 3),
        "prefetch_ok": near(int(fav2.get("maxSeq") or 0), hu.slots["fav2"].size)
        or int(fav2.get("maxSeq") or 0) >= hu.slots["fav2"].size * 0.9,
        "within_few_s": dt < 5.0,
    }
    checks["pass"] = bool(checks["prefetch_ok"] and checks["within_few_s"])
    return checks


def run_g5(producer: RealisticProducer, duration_s: float = 70.0) -> dict:
    """Producer profile: ~8.4–8.9 KB/s for ~60 s then ~6 KB/s."""
    t0 = time.monotonic()
    samples = []
    last = 0
    last_t = t0
    while time.monotonic() - t0 < duration_s:
        time.sleep(1.0)
        now = time.monotonic()
        b = producer.stats["bytes"]
        dt = now - last_t
        rate = (b - last) / dt if dt > 0 else 0
        samples.append({"t": round(now - t0, 1), "bps": round(rate, 1), "bytes": b})
        last, last_t = b, now
        if producer.stats.get("err"):
            break
    early = [s["bps"] for s in samples if 3 <= s["t"] <= 55]
    late = [s["bps"] for s in samples if s["t"] >= 62]
    med = sorted(early)[len(early) // 2] if early else 0
    med_late = sorted(late)[len(late) // 2] if late else 0
    checks = {
        "samples": samples[-10:],
        "burst_median_bps": med,
        "late_median_bps": med_late,
        "burst_ok": 7500 <= med <= 10000,
        "late_ok": (not late) or (5000 <= med_late <= 7500),
        "err": producer.stats.get("err"),
    }
    checks["pass"] = bool(checks["burst_ok"] and checks["late_ok"] and not checks["err"])
    return checks


def self_test() -> int:
    # classifier
    assert classify_block(b"ID3" + b"\x00" * 100) == "ID3"
    sil = (KSIL * 30)[:4096]
    assert classify_block(sil, file_off=100) == "SILENCE"
    live = make_pdsq_chunk(1, 0, 256) * 16
    assert classify_block(live[:4096], file_off=100) == "LIVE"
    assert find_pdsq(live).seq == 1
    seed = b"xxxxQ3B1yyyy" + b"\x00" * 100
    assert classify_block(seed, file_off=100) == "SEED"
    # ear
    ear = VirtualEar(decode_start="incremental:1")
    t = time.monotonic()
    for i in range(20):
        ear.on_block("LIVE", make_pdsq_chunk(i, i * 256, 256), t + i * 0.01)
    ear.tick(t + 2)
    # producer chunk size
    assert len(make_pdsq_chunk(0, 0, 256)) == 256
    print("self-test PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NBT HU simulator / Golden G1–G5")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--profile", default="tools/profiles/nbt_evo_2026-10-06.json")
    ap.add_argument("--golden", default="", help="G1,G2,G4,G5 or comma list / all")
    ap.add_argument("--soft-rst", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--g5-s", type=float, default=70.0)
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.golden:
        ap.error("need --golden or --self-test")

    esp = args.esp.rstrip("/")
    profile = load_profile(Path(args.profile))
    stamp = time.strftime("%H%M")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-2026-10-06-lab/lab88-nbt-hu-sim-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    goldens = [g.strip().upper() for g in args.golden.split(",")]
    if "ALL" in goldens:
        goldens = ["G1", "G2", "G3", "G4", "G5"]

    report: dict[str, Any] = {"golden": goldens, "results": {}}

    if args.soft_rst:
        soft_rst(esp)
        time.sleep(2)

    pump: PumpTcp | None = None
    stop = threading.Event()
    producer: RealisticProducer | None = None
    hu = HuSim(args.sg, profile)
    try:
        pump = prep_lab(esp, args.esp_ip, None, remount=True)
        hu.open()
        hu.refresh_slots(esp)

        if "G5" in goldens:
            producer = RealisticProducer(pump, stop, start_delay_s=0.0)
            arm_uid(pump, "fav0")
            producer.start()
            report["results"]["G5"] = run_g5(producer, args.g5_s)
            stop.set()
            producer.join(timeout=2)
            producer = None
            stop.clear()

        if "G1" in goldens:
            pump = prep_lab(esp, args.esp_ip, pump, remount=True)
            hu.open()
            hu.cache.clear()
            hu.class_counts.clear()
            hu.bytes_before_arm = hu.bytes_after_arm = 0
            hu._armed = False
            hu.refresh_slots(esp)
            report["results"]["G1"] = run_g1(hu, esp, pump, out, None)

        if "G3" in goldens:
            pump = prep_lab(esp, args.esp_ip, pump, remount=True)
            hu.open()
            hu.cache.clear()
            hu.class_counts.clear()
            hu.bytes_before_arm = hu.bytes_after_arm = 0
            hu._armed = False
            hu.refresh_slots(esp)
            report["results"]["G3"] = run_g3(hu, esp, pump, out)

        if "G4" in goldens:
            pump = prep_lab(esp, args.esp_ip, pump, remount=False)
            hu.open()
            hu.cache.clear()
            hu.class_counts.clear()
            hu.refresh_slots(esp)
            report["results"]["G4"] = run_g4(hu, esp, pump, out)

        if "G2" in goldens:
            pump = prep_lab(esp, args.esp_ip, pump, remount=True)
            hu.open()
            hu.cache.clear()
            hu.class_counts.clear()
            hu.bytes_before_arm = hu.bytes_after_arm = 0
            hu._armed = False
            hu.refresh_slots(esp)
            report["results"]["G2"] = run_g2(hu, esp, pump, out)

    finally:
        stop.set()
        hu.close()
        if pump is not None:
            try:
                pump.send_json({"t": "audio_stop"})
            except Exception:
                pass
            try:
                pump.close()
            except Exception:
                pass

    try:
        report["snap_final"] = snap(esp)
    except Exception as e:
        report["snap_final"] = {"error": str(e)}
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    passed = all(r.get("pass") for r in report["results"].values()) if report["results"] else False
    print(json.dumps({k: {"pass": v.get("pass"), **{kk: vv for kk, vv in v.items() if kk != "samples"}}
                      for k, v in report["results"].items()}, indent=2))
    print(f"OUT {out} overall={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
