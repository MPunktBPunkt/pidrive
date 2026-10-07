#!/usr/bin/env python3
"""NBT HU state simulator for Lab ESP (Stufe 2).

Models File-Cache eager-read + next-prefetch + realistic producer, classifies
read bytes, and runs Golden G1–G5 (ALL) plus optional G6 against FW 0.4.46 (stall_ms=0).

  sg disk -c 'python3 tools/nbt_hu_sim.py --golden G1 --sg /dev/sg0'
  python3 tools/nbt_hu_sim.py --self-test   # classifier / producer offline

Field-fit scenarios (s1-morgen 07.10., HU-Facts R15–R21):
  --period-ms 4.0|5.1     start-to-start schedule instead of gap after read
  --golden G7             fresh select from head (368640 / fragments / 5201920)
  --golden GW             resume around position P (out-of-order segments, R16)
  --golden G8             restart after remount (rc=167 signature)
  --golden G4N            next-prefetch 15 s before playback end
  --golden BENCH          C1/C3 back-to-back reads per size
  --golden REPLAY --replay <msc_reads.jsonl|bridge.log> [--replay-ms-from/--replay-ms-to]  (C6)
Every read goes to <out>/reads.jsonl (off, lba, n, klass, dur_ms, wall_ms, seq0/seq1).

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
from typing import Any, Callable

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


def find_pdsq_all(blob: bytes) -> list[LiveStamp]:
    magic = b"PDSQ"
    out: list[LiveStamp] = []
    i = 0
    while True:
        j = blob.find(magic, i)
        if j < 0 or j + 16 > len(blob):
            return out
        seq, abs_off, crc = struct.unpack_from(">III", blob, j + 4)
        body = blob[j : j + 12]
        if zlib.crc32(body) & 0xFFFFFFFF == crc:
            out.append(LiveStamp(seq=seq, abs_off=abs_off))
            i = j + 16
        else:
            i = j + 1


def find_pdsq(blob: bytes) -> LiveStamp | None:
    stamps = find_pdsq_all(blob)
    return stamps[0] if stamps else None


def silence_hits(blob: bytes) -> tuple[int, int]:
    """Return (best_phase, hit_count) for kSil sync tiles at any phase 0..155."""
    sync = KSIL[:4]
    best_p, best_n = 0, 0
    for p in range(156):
        n = 0
        for o in range(p, len(blob) - 3, 156):
            if blob[o : o + 4] == sync:
                n += 1
        if n > best_n:
            best_p, best_n = p, n
    return best_p, best_n


def classify_block(blob: bytes, file_off: int = 0, id3_len: int = 64) -> str:
    """Classify a 4 KiB MSC read. Silence detection is phase-tolerant (C2)."""
    if file_off < id3_len or blob.startswith(b"ID3"):
        return "ID3"
    if b"Q3B1" in blob[:64] or b"Q3B1" in blob:
        return "SEED"
    if find_pdsq(blob) is not None:
        return "LIVE"
    # Silence: kSil frames may start at any offset within the 4 KiB block (ID3 /
    # prior frame phase). Do not require sync at blob[0].
    sync = KSIL[:4]
    has_lame = b"LAME3.100" in blob
    has_sync = blob.find(sync) >= 0
    if has_sync or has_lame:
        _phase, hits = silence_hits(blob)
        # ~26 frames / 4 KiB when fully tiled
        need = max(2, len(blob) // 400)
        if hits >= need or (has_lame and hits >= 1):
            return "SILENCE"
        if has_lame and blob.count(0x55) > len(blob) * 0.5:
            return "SILENCE"
    if blob[:2] == b"\xff\xf3" or blob[:2] == b"\xff\xfb":
        return "OTHER"
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
            n = len(blob)
            self.live_bytes += n
            self._armed_bytes += n
            # A 4 KiB block carries ~16 stamps (256 B chunks); compare every stamp and
            # keep the last one, otherwise each block looks like a +16 gap.
            for st in find_pdsq_all(blob):
                if self.last_seq is not None:
                    if st.seq > self.last_seq + 1:
                        self.events.append(
                            EarEvent(t_mono, "gap_in_content", {"from": self.last_seq, "to": st.seq})
                        )
                    elif st.seq <= self.last_seq:
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
    blocks: set[int] = field(default_factory=set)  # 4 KiB block indices read (any order)


# s1-morgen 07.10. (HU-Facts R17/R18): fresh select of fav0 (8 MiB)
SELECT_HEAD_RUN = 368640
SELECT_FINAL_RUN = 5201920
SELECT_HOLE = 208896  # 51 blocks never read; position is a hypothesis (C6)
# msc.reads 03./04.10. (HU-Facts R16): resume around position P
# p1-run-a/b: 1 982 464 B around P = LBA 1953, then the sequential run starts at LBA 4625 = P + 1336 KiB
# -> forward 8+360+968 KiB, backward 120+120+360 KiB (interleave order per msc.reads timeline)
WINDOW_SEGS_KIB = (("F", 8), ("B", 120), ("B", 120), ("F", 360), ("B", 360), ("F", 968))
WINDOW_PAUSE_S = 5.0
# HU-Facts R20: restart after RST
REMOUNT_META_READS = 31
REMOUNT_PROBES = 8


def percentiles(xs: list[float], ps: tuple[int, ...] = (5, 50, 95, 99)) -> dict:
    if not xs:
        return {}
    s = sorted(xs)
    out = {f"p{p}": round(s[min(len(s) - 1, int(len(s) * p / 100))], 3) for p in ps}
    out["min"] = round(s[0], 3)
    out["max"] = round(s[-1], 3)
    out["n"] = len(s)
    return out


class HuSim:
    def __init__(
        self,
        sg_path: str,
        profile: dict,
        gap_ms: float | None = None,
        cmd_timeout_ms: int = 5000,
        events: list | None = None,
        period_ms: float | None = None,
        reads_jsonl: Path | None = None,
    ):
        self.sg_path = sg_path
        self.profile = profile
        self.gap_ms = gap_ms if gap_ms is not None else float(profile.get("read", {}).get("gap_ms_target", 4))
        # period_ms: start-to-start schedule like the HU (4.0 / 5.1 ms). None = legacy gap after read.
        self.period_ms = period_ms
        self._t_next: float | None = None
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
        self.dur_ms: list[float] = []
        self.wall_ms: list[float] = []
        self.start_gap_ms: list[float] = []
        self.late_reads = 0
        self._t_last_start: float | None = None
        self._reads_fh = open(reads_jsonl, "a", encoding="utf-8") if reads_jsonl else None

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
        if self._reads_fh is not None:
            self._reads_fh.close()
            self._reads_fh = None

    def timing_report(self) -> dict:
        return {
            "period_ms": self.period_ms,
            "gap_ms": None if self.period_ms else self.gap_ms,
            "sg_duration_ms": percentiles(self.dur_ms),
            "wall_ms": percentiles(self.wall_ms),
            "start_to_start_ms": percentiles(self.start_gap_ms),
            "late_reads": self.late_reads,
        }

    def _pace_before(self) -> None:
        if not self.period_ms:
            return
        now = time.monotonic()
        period = self.period_ms / 1000.0
        if self._t_next is None:
            self._t_next = now
        elif now > self._t_next + period:
            # previous read (or a status poll) overran its slot: restart the schedule, no catch-up burst
            self.late_reads += 1
            self._t_next = now
        delay = self._t_next - now
        if delay > 0:
            time.sleep(delay)
        self._t_next += period

    def idle(self, seconds: float) -> None:
        time.sleep(seconds)
        self._t_next = None

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
        if self._reads_fh is not None:
            kw["wall"] = time.time()
            self._reads_fh.write(json.dumps(kw, separators=(",", ":")) + "\n")

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
        blob, meta = self._timed_read(lba, n)
        klass = classify_block(blob, file_off)
        self.class_counts[klass] = self.class_counts.get(klass, 0) + 1
        self.ear.on_block(klass, blob, time.monotonic())
        ce = self.cache.setdefault(uid, CacheEntry())
        if file_off <= ce.covered:
            ce.covered = max(ce.covered, file_off + len(blob))
        for b in range(file_off // READ_N, (file_off + len(blob) + READ_N - 1) // READ_N):
            ce.blocks.add(b)
        if self._armed:
            self.bytes_after_arm += len(blob)
        else:
            self.bytes_before_arm += len(blob)
        stamps = find_pdsq_all(blob) if klass == "LIVE" else []
        self._log(
            op="read",
            uid=uid,
            off=file_off,
            lba=lba,
            n=len(blob),
            klass=klass,
            dur_ms=meta.get("duration_ms"),
            wall_ms=meta.get("wall_ms"),
            seq0=stamps[0].seq if stamps else None,
            seq1=stamps[-1].seq if stamps else None,
            abs0=stamps[0].abs_off if stamps else None,
        )
        return blob

    def read_raw(self, lba: int, n: int = READ_N, tag: str = "meta") -> bytes:
        """Non-file read (FAT/root/dir), counted by the ESP as a meta read."""
        blob, meta = self._timed_read(lba, n)
        self._log(op="read", uid=tag, off=None, lba=lba, n=len(blob), klass="META",
                  dur_ms=meta.get("duration_ms"), wall_ms=meta.get("wall_ms"))
        return blob

    def _timed_read(self, lba: int, n: int) -> tuple[bytes, dict]:
        self._pace_before()
        t0 = time.monotonic()
        if self._t_last_start is not None:
            self.start_gap_ms.append((t0 - self._t_last_start) * 1000.0)
        self._t_last_start = t0
        blob, meta = read_sg(self.sg_fd, lba, n, self.cmd_timeout_ms)
        wall = (time.monotonic() - t0) * 1000.0
        meta["wall_ms"] = round(wall, 3)
        self.wall_ms.append(wall)
        if meta.get("duration_ms") is not None:
            self.dur_ms.append(float(meta["duration_ms"]))
        if not self.period_ms and self.gap_ms > 0:
            time.sleep(self.gap_ms / 1000.0)
        return blob, meta

    # --- read-order models (HU-Facts R16/R17/R20/R21) -------------------

    def read_segment(self, uid: str, start: int, length: int, backward: bool = False) -> int:
        """Read [start, start+length) in 4 KiB steps, ascending (backward only changes the log tag)."""
        size = self.slots[uid].size
        start = max(0, (start // READ_N) * READ_N)
        end = min(size, start + length)
        self._log(op="segment", uid=uid, start=start, end=end, backward=backward)
        off = start
        n = 0
        while off < end:
            blob = self.read_n(uid, off, min(READ_N, end - off))
            if not blob:
                break
            off += len(blob)
            n += len(blob)
        return n

    def select_head(self, uid: str, head_run: int = SELECT_HEAD_RUN, final_run: int = SELECT_FINAL_RUN,
                    hole: int = SELECT_HOLE, frag_seg: int = 64 * 1024,
                    autoplay_pause_at: int | None = None, autoplay_pause_s: float = 2.5,
                    on_phase: Callable[[str], None] | None = None) -> dict:
        """Fresh select from head, field model R17/R18 (fav0 8 MiB).

        head_run sequential, then the fragment region [head_run, size-final_run-hole) in
        frag_seg pieces with pairwise swapped order (breaks the ESP maxSeq run), then a
        never-read hole, then the final run to EOF. With the defaults the total equals the
        field sum 8 179 712 B for an 8 MiB slot.
        """
        size = self.slots[uid].size
        final_start = max(head_run, size - final_run)
        frag_end = max(head_run, final_start - hole)
        t0 = time.monotonic()
        total = 0
        paused = False

        def maybe_pause() -> None:
            nonlocal paused
            if autoplay_pause_at is not None and not paused and total >= autoplay_pause_at:
                paused = True
                self._log(op="autoplay_pause", at=total, s=autoplay_pause_s)
                self.idle(autoplay_pause_s)

        total += self.read_segment(uid, 0, min(head_run, size))
        if on_phase:
            on_phase("head")
        segs = list(range(head_run, frag_end, frag_seg))
        order = []
        for i in range(0, len(segs), 2):
            order.extend(reversed(segs[i : i + 2]))
        for s in order:
            total += self.read_segment(uid, s, min(frag_seg, frag_end - s))
            maybe_pause()
        if on_phase:
            on_phase("frag")
        if final_start < size:
            total += self.read_segment(uid, final_start, size - final_start)
        return {"bytes": total, "head_run": head_run, "frag_end": frag_end,
                "final_start": final_start, "dt_s": round(time.monotonic() - t0, 3)}

    def window_read(self, uid: str, pos: int, segs_kib: tuple[tuple[str, int], ...] = WINDOW_SEGS_KIB,
                    pause_s: float = WINDOW_PAUSE_S, to_eof: bool = True) -> dict:
        """Resume around play position pos, field model R16: "F" segments extend above the
        highest read offset, "B" segments extend below the lowest one."""
        size = self.slots[uid].size
        pos = (pos // READ_N) * READ_N
        lo = hi = pos
        total = 0
        for direction, kib in segs_kib:
            n = kib * 1024
            if direction == "F":
                total += self.read_segment(uid, hi, n)
                hi = min(size, hi + n)
            else:
                start = max(0, lo - n)
                total += self.read_segment(uid, start, lo - start, backward=True)
                lo = start
        if to_eof and hi < size:
            self.idle(pause_s)
            total += self.read_segment(uid, hi, size - hi)
        return {"bytes": total, "lo": lo, "hi": size if to_eof else hi}

    def remount_restart(self, current_uid: str, probe_uid: str = "fav0",
                        meta_reads: int = REMOUNT_META_READS, probes: int = REMOUNT_PROBES) -> dict:
        """Restart after RST/remount, field model R20: meta reads, scattered probes on
        probe_uid, then the current track. A large current track starts select_head."""
        first_file_lba = min(s.lba0 for s in self.slots.values()) if self.slots else 81
        for i in range(meta_reads):
            lba = (i * 8) % max(8, first_file_lba - 8)
            self.read_raw(lba)
        ps = self.slots[probe_uid].size
        for k in range(probes):
            self.read_n(probe_uid, ((ps * k // probes) // READ_N) * READ_N)
        cur = self.slots[current_uid]
        if cur.size > 1024 * 1024:
            res = self.select_head(current_uid)
        else:
            res = {"bytes": self.read_segment(current_uid, 0, cur.size)}
        res["expect_readCount"] = meta_reads + probes + (cur.size // READ_N)
        return res

    def prefetch_at_playback(self, play_uid: str, next_uid: str, t_play0: float,
                             bitrate_bps: int = 48000, lead_s: float = 15.0, id3_len: int = 3044) -> dict:
        """Next-track prefetch tied to playback time (R21): read next_uid at t_play_end - lead_s."""
        play_s = (self.slots[play_uid].size - id3_len) / (bitrate_bps / 8)
        t_fire = t_play0 + max(0.0, play_s - lead_s)
        wait = t_fire - time.monotonic()
        if wait > 0:
            self.idle(wait)
        t0 = time.monotonic()
        n = self.read_segment(next_uid, 0, self.slots[next_uid].size)
        return {"play_s": round(play_s, 1), "lead_s": lead_s, "fired_after_s": round(t0 - t_play0, 2),
                "bytes": n, "dt_s": round(time.monotonic() - t0, 3)}

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
    """Muster A: ~86 KiB cold file-read before arm, rest as underrun/silence on empty ring.

    Field 07:58: 86016 + 438272 = 524288 with und≈hostAbs≈438272 (post-arm only).
    Arm ESP *after* pre_arm so those bytes are not counted as live underruns (C1).
    """
    pre_arm = 86016
    hu.refresh_slots(esp)
    # Field order: HU already reading before audio_start ack — do NOT arm ESP first.
    hu._armed = False
    hu.eager_read("fav1", stop_at=pre_arm)
    arm_uid(pump, "fav1")
    hu.mark_armed()
    # Muster A = empty/near-empty ring: no producer during the post-arm burst
    # (field 07:58 had live=0). Optional producer after EOF would be a different scenario.
    hu.eager_read("fav1")  # to EOF
    # next prefetch
    hu.eager_read("fav2")
    time.sleep(0.5)
    post = snap(esp)
    (out / "status-g1.json").write_text(json.dumps(post, indent=2))
    size = hu.slots["fav1"].size
    expect_und = size - pre_arm  # ~438272 when silence for rest
    und = int(post["underruns"])
    host = int(post["hostAbs"])
    live = int(post.get("liveBytes") or 0)
    ear = hu.ear.report()
    ear_live = int(ear.get("live_bytes") or 0)
    # Strict C1: underruns == expect_und ± TOL; hostAbs matches underruns (empty ring).
    # Do not accept und==size or und>=expect-TOL alone — that masked pre-arm-after-arm bugs.
    und_ok = near(und, expect_und)
    host_ok = near(host, expect_und) and near(host, und)
    # polluted streamBytesServed_ → ignore FW liveBytes; ear/classifier is source of truth
    checks = {
        "bytes_before_arm": hu.bytes_before_arm,
        "expect_before": pre_arm,
        "before_ok": near(hu.bytes_before_arm, pre_arm),
        "hostAbs": host,
        "underruns": und,
        "expect_und_host": expect_und,
        "und_ok": und_ok,
        "host_ok": host_ok,
        "und_host_ok": und_ok and host_ok,
        "liveBytes_fw": live,
        "liveBytes_ear": ear_live,
        "live_ok": ear_live < 4096,
        "class_counts": dict(hu.class_counts),
        "ear": ear,
    }
    body = sum(int(hu.class_counts.get(k, 0)) for k in ("SILENCE", "OTHER", "LIVE", "SEED"))
    other = int(hu.class_counts.get("OTHER", 0))
    sil = int(hu.class_counts.get("SILENCE", 0))
    checks["silence_ratio"] = round(sil / body, 3) if body else 0.0
    checks["other_ratio"] = round(other / body, 3) if body else 0.0
    # C2 soft gate: OTHER < 20% of body reads (phase-tolerant silence)
    checks["classifier_ok"] = body == 0 or other / body < 0.20
    checks["pass"] = bool(
        checks["before_ok"] and checks["und_host_ok"] and checks["live_ok"] and checks["classifier_ok"]
    )
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


def run_g6(hu: HuSim, esp: str, esp_ip: str, pump: PumpTcp, out: Path) -> tuple[dict, PumpTcp]:
    """Lab F2 rehearsal: cache hit on re-select; remount + cleared sim-cache re-reads.

    Not part of ALL — field F2 (HU cache over OTG) remains open. This checks the
    simulator cache model and ESP remount read growth.
    """
    hu.refresh_slots(esp)
    pre0 = snap(esp)
    rc0 = int(pre0.get("readCount") or 0)
    hu.eager_read("fav1")
    mid1 = snap(esp)
    fav1 = next((s for s in mid1["slots"] if s["uid"] == "fav1"), {})
    a_full = near(int(fav1.get("maxSeq") or 0), hu.slots["fav1"].size) or int(
        fav1.get("maxSeq") or 0
    ) >= hu.slots["fav1"].size * 0.9
    hu.eager_read("fav2")
    mid2 = snap(esp)
    fav2 = next((s for s in mid2["slots"] if s["uid"] == "fav2"), {})
    b_full = near(int(fav2.get("maxSeq") or 0), hu.slots["fav2"].size) or int(
        fav2.get("maxSeq") or 0
    ) >= hu.slots["fav2"].size * 0.9
    rc_after_prefetch = int(mid2.get("readCount") or 0)
    # c) re-select fav1 with sim cache — must not issue SCSI reads
    covered_before = hu.cache.get("fav1", CacheEntry()).covered
    n_events_before = len(hu.events)
    again = hu.eager_read("fav1")
    n_new_reads = sum(1 for e in hu.events[n_events_before:] if e.get("op") == "read")
    rc_after_cache = int(snap(esp).get("readCount") or 0)
    cache_hit = n_new_reads == 0 and again == covered_before and rc_after_cache == rc_after_prefetch
    # d) remount + clear sim cache → body reads again
    pump = prep_lab(esp, esp_ip, pump, remount=True)
    hu.open()
    hu.cache.clear()
    hu.class_counts.clear()
    hu.refresh_slots(esp)
    pre_rm = snap(esp)
    rc_rm = int(pre_rm.get("readCount") or 0)
    hu.eager_read("fav1")
    post_rm = snap(esp)
    (out / "status-g6-pre.json").write_text(json.dumps(pre0, indent=2))
    (out / "status-g6-after-prefetch.json").write_text(json.dumps(mid2, indent=2))
    (out / "status-g6-after-remount.json").write_text(json.dumps(post_rm, indent=2))
    fav1_rm = next((s for s in post_rm["slots"] if s["uid"] == "fav1"), {})
    rc_delta_rm = int(post_rm.get("readCount") or 0) - rc_rm
    reread_ok = rc_delta_rm >= (hu.slots["fav1"].size // READ_N) * 0.8 or near(
        int(fav1_rm.get("maxSeq") or 0), hu.slots["fav1"].size
    )
    checks = {
        "a_fav1_full": a_full,
        "b_fav2_full": b_full,
        "c_cache_hit": cache_hit,
        "c_new_sim_reads": n_new_reads,
        "c_readCount_delta": rc_after_cache - rc_after_prefetch,
        "d_remount_reread": reread_ok,
        "d_readCount_delta": rc_delta_rm,
        "d_fav1_maxSeq": fav1_rm.get("maxSeq"),
        "note": "Lab G6 models sim-cache + ESP remount; field HU-cache over OTG is F2/M5",
    }
    checks["pass"] = bool(a_full and b_full and cache_hit and reread_ok)
    return checks, pump


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


def slot_of(s: dict, uid: str) -> dict:
    return next((x for x in s.get("slots") or [] if x.get("uid") == uid), {})


def run_gw(hu: HuSim, esp: str, out: Path, uid: str = "fav0", pos: int = 958464) -> dict:
    """Resume around position P (R16, msc.reads 03./04.10.). Report-only: the ESP has no
    per-read export without the bridge, compare reads.jsonl against bridge msc.reads (C6)."""
    hu.refresh_slots(esp)
    pre = snap(esp)
    res = hu.window_read(uid, pos)
    post = snap(esp)
    (out / "status-gw.json").write_text(json.dumps(post, indent=2))
    res["bytes_delta_esp"] = int(slot_of(post, uid).get("bytes") or 0) - int(slot_of(pre, uid).get("bytes") or 0)
    res["maxSeq"] = slot_of(post, uid).get("maxSeq")
    res["pass"] = near(res["bytes_delta_esp"], res["bytes"])
    return res


def run_g7(hu: HuSim, esp: str, out: Path, uid: str = "fav0", autoplay: bool = False) -> dict:
    """Fresh select from head (R17/R18): maxSeq 368640 after the first run, final run
    5201920, slot bytes 8179712 for an 8 MiB slot. Checks the sim model against the ESP
    counters, not the HU itself (replay of the field pattern, C6)."""
    hu.refresh_slots(esp)
    pre = snap(esp)
    size = hu.slots[uid].size
    head = SELECT_HEAD_RUN
    snaps: dict[str, dict] = {}
    res = hu.select_head(uid, autoplay_pause_at=4194304 if autoplay else None,
                         on_phase=lambda name: snaps.__setitem__(name, snap(esp)))
    time.sleep(0.5)
    post = snap(esp)
    mid, frag = snaps.get("head", {}), snaps.get("frag", {})
    final_start, frag_end = res["final_start"], res["frag_end"]
    for name, s in (("pre", pre), ("mid", mid), ("frag", frag), ("post", post)):
        (out / f"status-g7-{name}.json").write_text(json.dumps(s, indent=2))
    b_pre = int(slot_of(pre, uid).get("bytes") or 0)
    expect_total = res["bytes"]
    checks = {
        "slot_size": size,
        "maxSeq_after_head": slot_of(mid, uid).get("maxSeq"),
        "maxSeq_after_frag": slot_of(frag, uid).get("maxSeq"),
        "maxSeq_final": slot_of(post, uid).get("maxSeq"),
        "bytes_delta": int(slot_of(post, uid).get("bytes") or 0) - b_pre,
        "expect_total": expect_total,
        "field_total_8mib": 8179712,
        "timing": hu.timing_report(),
    }
    checks["head_ok"] = near(int(checks["maxSeq_after_head"] or 0), head)
    checks["frag_ok"] = int(checks["maxSeq_after_frag"] or 0) < head + 2 * 64 * 1024
    checks["final_ok"] = near(int(checks["maxSeq_final"] or 0), size - final_start)
    checks["total_ok"] = near(checks["bytes_delta"], expect_total)
    checks["pass"] = bool(checks["head_ok"] and checks["frag_ok"] and checks["final_ok"] and checks["total_ok"])
    return checks


def run_g8(hu: HuSim, esp: str, out: Path, current_uid: str = "fav2") -> dict:
    """Restart after remount (R20): field signature rc=167, current 512 KiB track complete,
    fav0 8 scattered 4 KiB probes (bytes 32768, maxSeq 4096)."""
    hu.refresh_slots(esp)
    pre = snap(esp)
    res = hu.remount_restart(current_uid)
    time.sleep(0.5)
    post = snap(esp)
    (out / "status-g8-pre.json").write_text(json.dumps(pre, indent=2))
    (out / "status-g8.json").write_text(json.dumps(post, indent=2))
    rc_delta = int(post.get("readCount") or 0) - int(pre.get("readCount") or 0)
    cur = slot_of(post, current_uid)
    f0 = slot_of(post, "fav0")
    f0_pre = slot_of(pre, "fav0")
    checks = {
        "readCount_delta": rc_delta,
        "expect_readCount": res.get("expect_readCount"),
        "field_readCount": 167,
        "current_maxSeq": cur.get("maxSeq"),
        "fav0_bytes_delta": int(f0.get("bytes") or 0) - int(f0_pre.get("bytes") or 0),
        "fav0_maxSeq": f0.get("maxSeq"),
    }
    checks["rc_ok"] = abs(rc_delta - int(res.get("expect_readCount") or 0)) <= 2
    checks["current_ok"] = near(int(cur.get("maxSeq") or 0), hu.slots[current_uid].size)
    checks["probes_ok"] = checks["fav0_bytes_delta"] == REMOUNT_PROBES * READ_N
    checks["pass"] = bool(checks["rc_ok"] and checks["current_ok"] and checks["probes_ok"])
    return checks


def run_g4n(hu: HuSim, esp: str, out: Path, play_uid: str = "fav2", next_uid: str = "fav1",
            lead_s: float = 15.0) -> dict:
    """Next-prefetch tied to playback (R21): play_uid read, prefetch next_uid at play_end - lead_s.
    Runs ~play time - lead (512 KiB @ 48k: ~72 s)."""
    hu.refresh_slots(esp)
    hu.read_segment(play_uid, 0, hu.slots[play_uid].size)
    t_play0 = time.monotonic()
    pf = hu.prefetch_at_playback(play_uid, next_uid, t_play0, lead_s=lead_s)
    post = snap(esp)
    (out / "status-g4n.json").write_text(json.dumps(post, indent=2))
    nxt = slot_of(post, next_uid)
    checks = {**pf, "next_maxSeq": nxt.get("maxSeq")}
    checks["timing_ok"] = abs(pf["fired_after_s"] - (pf["play_s"] - lead_s)) < 1.0
    checks["next_full"] = near(int(nxt.get("maxSeq") or 0), hu.slots[next_uid].size)
    checks["pass"] = bool(checks["timing_ok"] and checks["next_full"])
    return checks


def load_msc_reads(path: Path, ms_from: int | None = None, ms_to: int | None = None) -> list[dict]:
    """Bridge msc.reads rows from JSONL (/tmp/pidrive_msc_reads.jsonl copies) or from a
    bridge journal log ('[rx] {...\"op\":\"msc.reads\"...}' lines)."""
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        j = line.find("{")
        if j < 0 or "msc.reads" not in line and "lba0" not in line:
            continue
        try:
            r = json.loads(line[j:])
        except json.JSONDecodeError:
            continue
        if "lba0" not in r or "bytes" not in r:
            continue
        ms = r.get("ms")
        if ms is None:
            continue
        if ms_from is not None and ms < ms_from:
            continue
        if ms_to is not None and ms > ms_to:
            continue
        rows.append(r)
    return rows


def run_replay(hu: HuSim, esp: str, out: Path, rows: list[dict], speed: float = 1.0) -> dict:
    """C6: replay field msc.reads bursts (absolute LBAs, same L3 geometry) with their ESP
    timestamps; within a burst the sim pacing applies. Compare slot bytes/maxSeq with the field."""
    hu.refresh_slots(esp)
    pre = snap(esp)
    if not rows:
        return {"pass": False, "err": "no rows"}
    ms0 = int(rows[0]["ms"])
    t0 = time.monotonic()
    n_reads = 0
    ov = [int(r.get("ov") or 0) for r in rows]
    for r in rows:
        t_due = t0 + (int(r["ms"]) - ms0) / 1000.0 / speed
        wait = t_due - time.monotonic()
        if wait > 0.002:
            hu.idle(wait)
        lba = int(r["lba0"])
        left = int(r["bytes"])
        while left > 0:
            n = min(READ_N, left)
            hu.read_raw(lba, n, tag=f"replay:k{r.get('kind')}")
            lba += n // SECTOR
            left -= n
            n_reads += 1
    time.sleep(0.5)
    post = snap(esp)
    (out / "status-replay.json").write_text(json.dumps(post, indent=2))
    slots = {}
    for s in post.get("slots") or []:
        p = slot_of(pre, s.get("uid"))
        slots[s.get("uid")] = {"bytes_delta": int(s.get("bytes") or 0) - int(p.get("bytes") or 0),
                               "maxSeq": s.get("maxSeq")}
    return {
        "rows": len(rows),
        "reads": n_reads,
        "field_span_s": round((int(rows[-1]["ms"]) - ms0) / 1000.0, 2),
        "replay_s": round(time.monotonic() - t0, 2),
        "field_ov_first_last": [ov[0], ov[-1]],
        "readCount_delta": int(post.get("readCount") or 0) - int(pre.get("readCount") or 0),
        "slots": slots,
        "timing": hu.timing_report(),
        "pass": True,
    }


def run_bench(hu: HuSim, esp: str, out: Path, uid: str, sizes: list[int], n_reads: int) -> dict:
    """C1/C3: back-to-back sequential reads per size (no pacing): reads/s, MB/s, durations."""
    hu.refresh_slots(esp)
    saved = (hu.period_ms, hu.gap_ms)
    hu.period_ms, hu.gap_ms = None, 0.0
    res: dict[str, Any] = {}
    try:
        for sz in sizes:
            hu.dur_ms.clear(); hu.wall_ms.clear(); hu.start_gap_ms.clear()
            hu._t_last_start = None
            pre = snap(esp)
            size = hu.slots[uid].size
            off = 0
            t0 = time.monotonic()
            done = 0
            for _ in range(n_reads):
                if off + sz > size:
                    off = 0
                blob = hu.read_n(uid, off, sz)
                off += len(blob)
                done += len(blob)
            dt = time.monotonic() - t0
            post = snap(esp)
            res[str(sz)] = {
                "reads": n_reads,
                "bytes": done,
                "dt_s": round(dt, 3),
                "reads_per_s": round(n_reads / dt, 1) if dt else None,
                "MBps": round(done / dt / 1e6, 3) if dt else None,
                "ms_per_4k": round(dt * 1000 / (done / 4096), 3) if done else None,
                "esp_readCount_delta": int(post.get("readCount") or 0) - int(pre.get("readCount") or 0),
                **{k: v for k, v in hu.timing_report().items() if k.endswith("_ms")},
            }
    finally:
        hu.period_ms, hu.gap_ms = saved
    (out / "bench.json").write_text(json.dumps(res, indent=2))
    return {"sizes": res, "pass": True}


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
    # C2: phase-shifted silence (sync not at block start)
    for phase in (1, 17, 56, 100):
        pad = b"\x55" * phase
        phased = (pad + KSIL * 30)[:4096]
        assert classify_block(phased, file_off=100) == "SILENCE", f"phase={phase}"
    live = make_pdsq_chunk(1, 0, 256) * 16
    assert classify_block(live[:4096], file_off=100) == "LIVE"
    assert find_pdsq(live).seq == 1
    seed = b"xxxxQ3B1yyyy" + b"\x00" * 100
    assert classify_block(seed, file_off=100) == "SEED"
    # mix: live stamp then silence tail — LIVE wins (PDSQ first)
    mixed = (make_pdsq_chunk(0, 0, 256) + KSIL * 20)[:4096]
    assert classify_block(mixed, file_off=100) == "LIVE"
    # silence-only mid-block padding (no sync at [0]) must not be OTHER
    mid = (b"\x55" * 80 + KSIL * 28)[:4096]
    assert classify_block(mid, file_off=200) == "SILENCE"
    # ear
    ear = VirtualEar(decode_start="incremental:1")
    t = time.monotonic()
    for i in range(20):
        ear.on_block("LIVE", make_pdsq_chunk(i, i * 256, 256), t + i * 0.01)
    ear.tick(t + 2)
    # ear: contiguous 4 KiB blocks (16 stamps each) must not report gaps
    ear2 = VirtualEar(decode_start="incremental:1")
    for b in range(4):
        blk = b"".join(make_pdsq_chunk(b * 16 + i, (b * 16 + i) * 256, 256) for i in range(16))
        ear2.on_block("LIVE", blk, t + b * 0.004)
    assert ear2.report()["events"] == {}, ear2.report()["events"]
    assert ear2.last_seq == 63
    gap = b"".join(make_pdsq_chunk(100 + i, 0, 256) for i in range(16))
    ear2.on_block("LIVE", gap, t + 1)
    assert ear2.report()["events"].get("gap_in_content") == 1
    assert percentiles([1.0, 2.0, 3.0])["p50"] == 2.0
    # producer chunk size
    assert len(make_pdsq_chunk(0, 0, 256)) == 256
    print("self-test PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NBT HU simulator / Golden G1–G6")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--profile", default="tools/profiles/nbt_evo_2026-10-06.json")
    ap.add_argument("--golden", default="",
                    help="G1..G8, G4N, BENCH or comma list / all (ALL=G1–G5 only)")
    ap.add_argument("--soft-rst", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--g5-s", type=float, default=70.0)
    ap.add_argument("--period-ms", type=float, default=None,
                    help="HU start-to-start schedule (field: 4.0 idle, 5.1 with ESP play). "
                         "Default: legacy gap after each read")
    ap.add_argument("--gap-ms", type=float, default=None, help="legacy pause after each read")
    ap.add_argument("--reads-jsonl", default="", help="per-read JSONL (default: <out>/reads.jsonl)")
    ap.add_argument("--no-reads-jsonl", action="store_true")
    ap.add_argument("--g4n-lead", type=float, default=15.0)
    ap.add_argument("--g7-autoplay", action="store_true", help="2.5 s pause after 4 MiB (R19)")
    ap.add_argument("--gw-pos", type=int, default=958464, help="file offset P for GW (field LBA 1953)")
    ap.add_argument("--live", default="", help="arm this uid before G7/G8/GW/G4N/BENCH/REPLAY (C2/C4)")
    ap.add_argument("--live-no-producer", action="store_true", help="with --live: armed, no audio")
    ap.add_argument("--live-prefill-s", type=float, default=8.0, help="producer head start before reads")
    ap.add_argument("--replay", default="", help="msc.reads JSONL or bridge log for REPLAY (C6)")
    ap.add_argument("--replay-ms-from", type=int, default=None, help="ESP ms window start")
    ap.add_argument("--replay-ms-to", type=int, default=None)
    ap.add_argument("--replay-speed", type=float, default=1.0)
    ap.add_argument("--bench-uid", default="fav0")
    ap.add_argument("--bench-sizes", default="512,4096,16384,65536")
    ap.add_argument("--bench-n", type=int, default=1000)
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

    report: dict[str, Any] = {"golden": goldens, "results": {},
                              "period_ms": args.period_ms, "gap_ms": args.gap_ms}

    if args.soft_rst:
        soft_rst(esp)
        time.sleep(2)

    reads_path = None if args.no_reads_jsonl else Path(args.reads_jsonl or (out / "reads.jsonl"))
    pump: PumpTcp | None = None
    stop = threading.Event()
    producer: RealisticProducer | None = None
    hu = HuSim(args.sg, profile, gap_ms=args.gap_ms, period_ms=args.period_ms, reads_jsonl=reads_path)

    live_prod: list[RealisticProducer] = []

    def fresh(remount: bool = True) -> None:
        nonlocal pump
        stop_live()
        pump = prep_lab(esp, args.esp_ip, pump, remount=remount)
        hu.open()
        hu.cache.clear()
        hu.class_counts.clear()
        hu.bytes_before_arm = hu.bytes_after_arm = 0
        hu._armed = False
        hu.ear = VirtualEar()
        hu.refresh_slots(esp)
        if args.live:
            # C2/C4: ESP armed on a live slot (optionally with PDSQ producer) during the scenario
            arm_uid(pump, args.live)
            hu.mark_armed()
            if not args.live_no_producer:
                p = RealisticProducer(pump, stop, start_delay_s=0.0)
                p.start()
                live_prod.append(p)
                time.sleep(args.live_prefill_s)

    def stop_live() -> None:
        if not live_prod:
            return
        stop.set()
        for p in live_prod:
            p.join(timeout=2)
        live_prod.clear()
        stop.clear()
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

        if "G6" in goldens:
            pump = prep_lab(esp, args.esp_ip, pump, remount=True)
            hu.open()
            hu.cache.clear()
            hu.class_counts.clear()
            hu.bytes_before_arm = hu.bytes_after_arm = 0
            hu._armed = False
            hu.events.clear()
            hu.refresh_slots(esp)
            g6, pump = run_g6(hu, esp, args.esp_ip, pump, out)
            report["results"]["G6"] = g6

        if "G7" in goldens:
            fresh()
            report["results"]["G7"] = run_g7(hu, esp, out, autoplay=args.g7_autoplay)

        if "GW" in goldens:
            fresh()
            report["results"]["GW"] = run_gw(hu, esp, out, pos=args.gw_pos)

        if "G8" in goldens:
            fresh()
            report["results"]["G8"] = run_g8(hu, esp, out)

        if "G4N" in goldens:
            fresh()
            report["results"]["G4N"] = run_g4n(hu, esp, out, lead_s=args.g4n_lead)

        if "BENCH" in goldens:
            fresh()
            sizes = [int(x) for x in args.bench_sizes.split(",") if x.strip()]
            report["results"]["BENCH"] = run_bench(hu, esp, out, args.bench_uid, sizes, args.bench_n)

        if "REPLAY" in goldens:
            if not args.replay:
                ap.error("REPLAY needs --replay <msc_reads.jsonl|bridge.log>")
            fresh()
            rows = load_msc_reads(Path(args.replay), args.replay_ms_from, args.replay_ms_to)
            report["results"]["REPLAY"] = run_replay(hu, esp, out, rows, args.replay_speed)

        stop_live()
        report["timing"] = hu.timing_report()
        report["ear"] = hu.ear.report()

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
