#!/usr/bin/env python3
"""Tonfenster je Slot-Zugriff: was hat der ESP der HU beim Lesen geliefert?

Verbindet die Einzel-Reads (`trace.jsonl`, feld_trace_poll.py) mit dem
Ringzustand aus `status-poll.jsonl` (1 Hz: absBase, absEnd, playingUid,
underruns, hostAbs) und rechnet `StreamBuffer::readAt` (FW 0.4.46) nach:

  Datei des Live-Slots = [sticky ID3 @0][Ring ab absBase über Host-Cursor][Stille]

Je Zugriff (Episode = zusammenhängende Reads eines Slots) kommen heraus:
Live-Bytes, Sekunden bei --bps, Stille-Bytes, Dateioffsets mit Live-Inhalt,
Alter des Producers, gemessenes underruns-Delta und daraus geschätzte ID3-Länge.
Reads anderer Slots bekommen Mp3Silence (kein Bild, kein Ton).

  python3 tools/feld_live_window.py --run docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep/s3-20261008-074403
  python3 tools/feld_live_window.py --trace T --status S [--marks M] [--out-dir D]
  python3 tools/feld_live_window.py --self-test

Zeitbasis: trace `wall_est` gegen status `wall_iso`. wall_est ist um bootMs
(< 2 s) zu spät; --clock-offset verschiebt die Trace-Zeiten.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SECTOR = 512
RING = 48 * 1024
ID3_MAX = 12 * 1024
HEAD_RESYNC = 8192
SEQ_SLOP = 8192
DEFAULT_BPS = 6000
EPISODE_GAP_S = 1.5


# --- input ---------------------------------------------------------------

def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_status(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not j.get("wall_iso") or _int(j.get("absEnd")) is None:
            continue
        rows.append({
            "t": datetime.fromisoformat(j["wall_iso"]).timestamp(),
            "hms": j["wall_iso"][11:19],
            "serial": j.get("serial") or "",
            "playing": j.get("playingUid") or "",
            "absBase": _int(j.get("absBase")) or 0,
            "absEnd": _int(j.get("absEnd")) or 0,
            "underruns": _int(j.get("underruns")) or 0,
            "hostAbs": _int(j.get("hostAbs")) or 0,
            "armed": bool(j.get("cursorArmed")),
            "active": bool(j.get("stream_active")),
            "uptime": j.get("esp_uptime") or "",
            "slots": [(s.get("uid"), _int(s.get("lba0"))) for s in (j.get("slotMap") or [])],
        })
    rows.sort(key=lambda r: r["t"])
    annotate_streams(rows)
    return rows


def annotate_streams(rows: list[dict]) -> None:
    """Stream identity per row: a new stream starts when absEnd falls back
    (audio_start clears the ring, or the ESP rebooted). Its uid is the
    playingUid seen at/after the start; it survives a replug (playingUid "")."""
    sid = 0
    uid = ""
    t0 = rows[0]["t"] if rows else 0.0
    prev = None
    for r in rows:
        restart = prev is not None and (
            r["absEnd"] < prev["absEnd"] or (r["playing"] and uid and r["playing"] != uid)
        )
        if prev is None or restart:
            sid += 1
            uid = r["playing"]
            t0 = r["t"] if prev is None else prev["t"]
        elif not uid and r["playing"]:
            uid = r["playing"]
        r["sid"] = sid
        r["stream_uid"] = uid if r["active"] else ""
        r["stream_t0"] = t0
        prev = r


def slot_ranges(rows: list[dict]) -> dict[str, tuple[int, int]]:
    """uid -> (lba0, lba_end_exclusive) from the last slotMap; end = next lba0."""
    for r in reversed(rows):
        sl = [(u, l) for u, l in r["slots"] if u and l is not None]
        if sl:
            sl.sort(key=lambda x: x[1])
            out = {}
            for i, (u, l) in enumerate(sl):
                end = sl[i + 1][1] if i + 1 < len(sl) else None
                if end is not None and not u.startswith("pump:"):
                    out[u] = (l, end)
            return out
    return {}


def load_trace(path: Path, offset_s: float = 0.0) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("wall_est") is None or e.get("lba") is None:
            continue
        rows.append({"t": float(e["wall_est"]) + offset_s, "ms": _int(e.get("ms")),
                     "lba": int(e["lba"]), "n": int(e.get("n") or 4096)})
    rows.sort(key=lambda r: r["t"])
    return rows


def load_marks(path: Path | None) -> list[dict]:
    if not path or not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "wall" in m:
            out.append({"t": float(m["wall"]), "hms": m.get("hms", ""), "text": m.get("text", "")})
    return sorted(out, key=lambda m: m["t"])


# --- ring state ------------------------------------------------------------

def ring_at(rows: list[dict], ts: list[float], t: float) -> dict:
    """Interpolated ring state at time t (linear inside one stream)."""
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        r = rows[0]
        return {**r, "exact": False}
    a = rows[i]
    if i + 1 >= len(rows):
        return {**a, "exact": False}
    b = rows[i + 1]
    if b["sid"] != a["sid"]:
        # stream restarted between the two polls: reads here see an (almost) empty ring
        return {**b, "absBase": 0, "absEnd": 0, "exact": False}
    f = (t - a["t"]) / max(1e-6, b["t"] - a["t"])
    end = int(a["absEnd"] + f * (b["absEnd"] - a["absEnd"]))
    base = int(a["absBase"] + f * (b["absBase"] - a["absBase"]))
    base = max(base, end - RING)
    return {**a, "absBase": max(0, base), "absEnd": end, "exact": True}


# --- readAt model ----------------------------------------------------------

@dataclass
class ReadAtModel:
    """State of StreamBuffer::readAt between MSC reads (cleared by start())."""
    id3_len: int = 0
    cursor_armed: bool = False
    host_abs: int = 0
    expect: int = 0

    def read(self, file_off: int, n: int, abs_base: int, abs_end: int, active: bool = True) -> dict:
        size = max(0, abs_end - abs_base)
        near_head = file_off < self.id3_len + HEAD_RESYNC
        seek_back = self.expect != 0 and file_off + 512 < self.expect
        sequential = self.expect == 0 or (file_off + SEQ_SLOP >= self.expect and file_off <= self.expect + SEQ_SLOP)
        use_cursor = False
        snapped = False
        if active:
            if not self.cursor_armed or (near_head and (seek_back or file_off <= self.id3_len + 512)):
                self.host_abs = abs_base
                self.cursor_armed = True
                use_cursor = True
                snapped = True
            elif sequential and self.cursor_armed:
                use_cursor = True
                if size > 0 and self.host_abs < abs_base:
                    self.host_abs = abs_base
        id3_part = max(0, min(self.id3_len, file_off + n) - file_off) if file_off < self.id3_len else 0
        m = n - id3_part
        a0 = self.host_abs if use_cursor else file_off + id3_part - self.id3_len
        live = 0
        live_off = None
        if active and size > 0 and m > 0:
            lo, hi = max(a0, abs_base), min(a0 + m, abs_end)
            if hi > lo:
                live = hi - lo
                live_off = file_off + id3_part + (lo - a0)
        silence = m - live
        if use_cursor:
            self.host_abs += m
        if use_cursor or sequential:
            self.expect = file_off + n
        return {"id3": id3_part, "live": live, "silence": silence, "live_off": live_off,
                "underrun": silence if active else 0, "cursor": use_cursor, "snap": snapped}


# --- episodes ----------------------------------------------------------------

@dataclass
class Episode:
    i: int
    t0: float
    t1: float
    hms: str
    uid: str
    serial: str
    reads: int
    off_min: int
    off_max_end: int
    from_head: bool
    sequential: bool
    stream_uid: str
    live_slot: bool
    producer_age_s: float | None
    ring_fill: int
    id3_bytes: int = 0
    live_bytes: int = 0
    silence_bytes: int = 0
    live_s: float = 0.0
    live_off_first: int | None = None
    live_off_last: int | None = None
    und_delta: int | None = None
    id3_est: int | None = None
    notes: list[str] = field(default_factory=list)


def build_episodes(trace: list[dict], slots: dict[str, tuple[int, int]]) -> list[tuple[str, list[dict]]]:
    def uid_of(lba: int) -> str:
        for u, (a, b) in slots.items():
            if a <= lba < b:
                return u
        return ""

    eps: list[tuple[str, list[dict]]] = []
    for r in trace:
        u = uid_of(r["lba"])
        if not u:
            continue
        if eps and eps[-1][0] == u and r["t"] - eps[-1][1][-1]["t"] <= EPISODE_GAP_S:
            eps[-1][1].append(r)
        else:
            eps.append((u, [r]))
    return eps


def analyze(trace: list[dict], status: list[dict], marks: list[dict], id3_len: int, bps: int) -> list[Episode]:
    slots = slot_ranges(status)
    ts = [r["t"] for r in status]
    models: dict[int, ReadAtModel] = {}
    out: list[Episode] = []
    for k, (uid, reads) in enumerate(build_episodes(trace, slots)):
        lba0 = slots[uid][0]
        st0 = ring_at(status, ts, reads[0]["t"])
        offs = [(r["lba"] - lba0) * SECTOR for r in reads]
        seq = all(offs[j + 1] == offs[j] + reads[j]["n"] for j in range(len(offs) - 1))
        live_slot = bool(st0["stream_uid"]) and st0["stream_uid"] == uid
        ep = Episode(
            i=k, t0=reads[0]["t"], t1=reads[-1]["t"],
            hms=datetime.fromtimestamp(reads[0]["t"]).strftime("%H:%M:%S.%f")[:10],
            uid=uid, serial=st0["serial"], reads=len(reads),
            off_min=min(offs), off_max_end=max(o + r["n"] for o, r in zip(offs, reads)),
            from_head=offs[0] == 0, sequential=seq, stream_uid=st0["stream_uid"], live_slot=live_slot,
            producer_age_s=round(reads[0]["t"] - st0["stream_t0"], 1) if st0["stream_uid"] else None,
            ring_fill=max(0, st0["absEnd"] - st0["absBase"]),
        )
        if live_slot:
            model = models.setdefault(st0["sid"], ReadAtModel(id3_len=id3_len))
            for o, r in zip(offs, reads):
                st = ring_at(status, ts, r["t"])
                res = model.read(o, r["n"], st["absBase"], st["absEnd"])
                ep.id3_bytes += res["id3"]
                ep.live_bytes += res["live"]
                ep.silence_bytes += res["silence"]
                if res["live"]:
                    if ep.live_off_first is None:
                        ep.live_off_first = res["live_off"]
                    ep.live_off_last = res["live_off"] + res["live"]
            ep.live_s = round(ep.live_bytes / bps, 2)
            before = [r for r in status if r["t"] <= ep.t0 and r["sid"] == st0["sid"]]
            after = [r for r in status if r["t"] >= ep.t1 + 1.0 and r["sid"] == st0["sid"]]
            if before and after:
                ep.und_delta = after[0]["underruns"] - before[-1]["underruns"]
                total = ep.off_max_end - ep.off_min
                est = total - ep.live_bytes - ep.und_delta
                if ep.from_head and 0 <= est <= ID3_MAX + 4096:
                    ep.id3_est = est
        else:
            ep.silence_bytes = sum(r["n"] for r in reads)
        ep.notes = [f"{m['hms']} {m['text']}" for m in marks if ep.t0 - 5 <= m["t"] <= ep.t1 + 90]
        out.append(ep)
    return out


def print_table(eps: list[Episode]) -> None:
    print(f"{'#':>3} {'Zeit':10} {'Serial':7} {'Slot':5} {'Reads':>5} {'Bereich':>16} {'seq':3} "
          f"{'Live':4} {'Prod-s':>6} {'Ring':>6} {'Live-B':>7} {'Live-s':>6} {'Stille-B':>8} {'undΔ':>7} {'ID3~':>6}")
    for e in eps:
        rng = f"{e.off_min // 1024}K..{e.off_max_end // 1024}K"
        print(f"{e.i:>3} {e.hms:10} {e.serial:7} {e.uid:5} {e.reads:>5} {rng:>16} {'ja' if e.sequential else 'nein':3} "
              f"{'ja' if e.live_slot else '-':4} {e.producer_age_s if e.producer_age_s is not None else '-':>6} "
              f"{e.ring_fill:>6} {e.live_bytes:>7} {e.live_s:>6} {e.silence_bytes:>8} "
              f"{e.und_delta if e.und_delta is not None else '-':>7} {e.id3_est if e.id3_est is not None else '-':>6}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="", help="Laufordner mit trace.jsonl, status-poll.jsonl, marks.jsonl")
    ap.add_argument("--trace", default="")
    ap.add_argument("--status", default="")
    ap.add_argument("--marks", default="")
    ap.add_argument("--id3-len", type=int, default=0, help="sticky ID3-Länge, falls bekannt (sonst geschätzt)")
    ap.add_argument("--bps", type=int, default=DEFAULT_BPS, help="Producer-Bytes pro Sekunde Audio (48k = 6000)")
    ap.add_argument("--clock-offset", type=float, default=0.0, help="Sekunden auf Trace-Zeiten addieren")
    ap.add_argument("--min-reads", type=int, default=8, help="kürzere Episoden nicht ausgeben")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    run = Path(args.run) if args.run else None
    trace_p = Path(args.trace) if args.trace else (run / "trace.jsonl" if run else None)
    status_p = Path(args.status) if args.status else (run / "status-poll.jsonl" if run else None)
    marks_p = Path(args.marks) if args.marks else (run / "marks.jsonl" if run else None)
    if not trace_p or not status_p:
        ap.error("--run oder --trace und --status angeben")
    status = load_status(status_p)
    trace = load_trace(trace_p, args.clock_offset)
    if not status or not trace:
        print("keine Daten", file=sys.stderr)
        return 2
    eps = [e for e in analyze(trace, status, load_marks(marks_p), args.id3_len, args.bps)
           if e.reads >= args.min_reads]
    print_table(eps)
    for e in eps:
        if e.notes:
            print(f"  #{e.i}: " + " | ".join(e.notes[:4]))
    if args.out_dir:
        od = Path(args.out_dir)
        od.mkdir(parents=True, exist_ok=True)
        (od / "LIVE-WINDOW.json").write_text(json.dumps([asdict(e) for e in eps], indent=2, ensure_ascii=False),
                                             encoding="utf-8")
        with (od / "LIVE-WINDOW.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            cols = [k for k in asdict(eps[0]).keys() if k != "notes"] if eps else []
            w.writerow(cols)
            for e in eps:
                d = asdict(e)
                w.writerow([d[c] for c in cols])
        print(f"wrote {od / 'LIVE-WINDOW.json'}")
    return 0


def self_test() -> int:
    # Feld s3, C3 07:50:49: Ring voll (49152 B), Producer 6 KB/s, HU liest 512 KiB ab 0 in 128 Reads.
    base0, t0 = 303800, 1000.0
    status = []
    for s in range(-3, 6):
        end = base0 + RING + 6000 * s
        status.append({"t": t0 + s, "hms": "", "serial": "PD0099", "playing": "", "absBase": end - RING,
                       "absEnd": end, "underruns": 458752 + (471640 if s >= 2 else 0), "hostAbs": 0,
                       "armed": True, "active": True, "uptime": "",
                       "slots": [("fav0", 81), ("fav1", 16465), ("fav2", 17489), ("pump:page_next", 18513)]})
    annotate_streams(status)
    for r in status:
        r["stream_uid"] = "fav2"
    trace = [{"t": t0 + 0.005 * k, "ms": k, "lba": 17489 + 8 * k, "n": 4096} for k in range(128)]
    eps = analyze(trace, status, [], id3_len=3500, bps=6000)
    assert len(eps) == 1, eps
    e = eps[0]
    assert e.uid == "fav2" and e.live_slot and e.from_head and e.sequential, e
    assert 49152 <= e.live_bytes <= 49152 + 6000, e.live_bytes
    assert e.id3_bytes == 3500, e.id3_bytes
    assert e.live_bytes + e.silence_bytes + e.id3_bytes == 524288
    assert e.live_off_first == 3500, e.live_off_first
    assert 8.1 <= e.live_s <= 9.2, e.live_s
    assert e.und_delta == 471640 and e.id3_est is not None and 2000 <= e.id3_est <= 4500, (e.und_delta, e.id3_est)

    # Tap auf neuen Sender: Ring leer zum Lesezeitpunkt -> kein Live
    m = ReadAtModel(id3_len=0)
    res = m.read(0, 4096, 0, 0)
    assert res["live"] == 0 and res["silence"] == 4096

    # Resume-Read mitten in der Datei nach Kopf-Lesen: Cursor fährt weiter (sequenziell), dann Sprung
    m = ReadAtModel(id3_len=0)
    m.read(0, 4096, 1000, 1000 + RING)
    r2 = m.read(200 * 1024, 4096, 1000, 1000 + RING)  # weit weg, nicht sequenziell -> feste Zuordnung
    assert not r2["cursor"] and r2["live"] == 0
    print("self-test PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
