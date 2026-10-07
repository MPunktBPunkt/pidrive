#!/usr/bin/env python3
"""Q8 / R10: Lesereihenfolge aus Bridge-msc.reads (Feld s2).

Wertet Burst-Segmente, Dateioffsets und ungelesene Blöcke aus und schlägt
eine Stall-Entscheidung vor (Fragmente nah / weit voraus / R16-ähnlich).

  python3 tools/feld_q8_msc_order.py \\
    --reads path/msc_reads.jsonl \\
    [--ms-from 364034 --ms-to 376757] \\
    [--lba0 81 --slot-bytes 8388608] \\
    [--pause-ms 2000] [--out-dir DIR]

Ohne --ms-from/--ms-to: Episoden an Pausen > pause-ms schneiden und alle listen.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SECTOR = 512
READ_N = 4096
# L3 fav0 (Rock 8 MiB) — wie Sim / HU-Facts
DEFAULT_LBA0 = 81
DEFAULT_SLOT = 8 * 1024 * 1024  # 8388608
SELECT_HEAD = 368640
# R16 resume signature (bytes around P)
R16_RESUME_BYTES = 1_982_464


@dataclass
class Segment:
    i: int
    ms0: int
    ms1: int
    dt_ms: int
    lba0: int
    lba1: int
    bytes: int
    file_off0: int | None
    file_off1: int | None
    direction: str  # forward | backward | mixed | meta
    in_slot: bool


def load_msc_reads(path: Path, ms_from: int | None = None, ms_to: int | None = None) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        j = line.find("{")
        if j < 0:
            continue
        if "lba0" not in line and "msc.reads" not in line:
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
        ms = int(ms)
        if ms_from is not None and ms < ms_from:
            continue
        if ms_to is not None and ms > ms_to:
            continue
        rows.append(r)
    return rows


def file_off(lba: int, slot_lba0: int, slot_bytes: int) -> int | None:
    off = (int(lba) - slot_lba0) * SECTOR
    if off < 0 or off >= slot_bytes:
        return None
    return off


def coalesce_bursts(rows: list[dict], pause_ms: int) -> list[list[dict]]:
    if not rows:
        return []
    episodes: list[list[dict]] = [[rows[0]]]
    for r in rows[1:]:
        prev = episodes[-1][-1]
        gap = int(r.get("gap") or 0)
        # bridge gap saturates at 65535; also use ms delta
        dt = int(r["ms"]) - int(prev["ms"])
        if gap >= pause_ms or dt >= pause_ms:
            episodes.append([r])
        else:
            episodes[-1].append(r)
    return episodes


def row_span(r: dict, slot_lba0: int, slot_bytes: int) -> tuple[int | None, int | None, bool]:
    """Return (file_off_first, file_off_last_inclusive_start, entirely_in_slot)."""
    l0 = int(r["lba0"])
    nbytes = int(r["bytes"])
    nsec = max(1, nbytes // SECTOR)
    l_last = l0 + nsec - 1
    o0 = file_off(l0, slot_lba0, slot_bytes)
    o1 = file_off(l_last, slot_lba0, slot_bytes)
    in_slot = o0 is not None or o1 is not None
    return o0, o1, in_slot


def segments_from_episode(
    ep: list[dict], slot_lba0: int, slot_bytes: int
) -> list[Segment]:
    """Merge consecutive adjacent slot reads (LBA±1) into segments; else new segment."""
    segs: list[Segment] = []
    cur: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal cur
        if not cur:
            return
        fo0, fo1 = cur["fo0"], cur["fo1"]
        if fo0 is not None and fo1 is not None and fo1 < fo0:
            fo0, fo1 = fo1, fo0
        segs.append(
            Segment(
                i=len(segs),
                ms0=cur["ms0"],
                ms1=cur["ms1"],
                dt_ms=cur["ms1"] - cur["ms0"],
                lba0=min(cur["lba0"], cur["lba1"]),
                lba1=max(cur["lba0"], cur["lba1"]),
                bytes=cur["bytes"],
                file_off0=fo0,
                file_off1=fo1,
                direction=cur["dir"],
                in_slot=cur["in_slot"],
            )
        )
        cur = None

    for r in ep:
        l0 = int(r["lba0"])
        nbytes = int(r["bytes"])
        nsec = max(1, nbytes // SECTOR)
        l1 = l0 + nsec - 1
        fo0, _, in_slot = row_span(r, slot_lba0, slot_bytes)
        fo_end = fo0 + nbytes - SECTOR if fo0 is not None else None
        if not in_slot or fo0 is None:
            flush()
            segs.append(
                Segment(
                    i=len(segs),
                    ms0=int(r["ms"]),
                    ms1=int(r["ms"]),
                    dt_ms=0,
                    lba0=l0,
                    lba1=l1,
                    bytes=nbytes,
                    file_off0=None,
                    file_off1=None,
                    direction="meta",
                    in_slot=False,
                )
            )
            continue
        if cur is None:
            cur = {
                "ms0": int(r["ms"]),
                "ms1": int(r["ms"]),
                "lba0": l0,
                "lba1": l1,
                "bytes": nbytes,
                "fo0": fo0,
                "fo1": fo_end,
                "dir": "forward",
                "in_slot": True,
                "last_lba_end": l1,
                "first_lba": l0,
            }
            continue
        fwd = l0 == cur["last_lba_end"] + 1
        bwd = l1 + 1 == cur["first_lba"]
        if fwd or bwd:
            cur["ms1"] = int(r["ms"])
            cur["bytes"] += nbytes
            cur["lba0"] = min(cur["lba0"], l0)
            cur["lba1"] = max(cur["lba1"], l1)
            cur["fo0"] = min(x for x in (cur["fo0"], fo0) if x is not None)
            cur["fo1"] = max(x for x in (cur["fo1"], fo_end) if x is not None)
            if fwd and bwd:
                cur["dir"] = "mixed"
            elif fwd:
                cur["dir"] = "forward" if cur["dir"] == "forward" else "mixed"
            else:
                cur["dir"] = "backward" if cur["dir"] in ("backward", "forward") else "mixed"
                if cur["dir"] == "forward":
                    cur["dir"] = "backward"
            cur["last_lba_end"] = max(cur["last_lba_end"], l1)
            cur["first_lba"] = min(cur["first_lba"], l0)
        else:
            flush()
            cur = {
                "ms0": int(r["ms"]),
                "ms1": int(r["ms"]),
                "lba0": l0,
                "lba1": l1,
                "bytes": nbytes,
                "fo0": fo0,
                "fo1": fo_end,
                "dir": "forward",
                "in_slot": True,
                "last_lba_end": l1,
                "first_lba": l0,
            }
    flush()
    return segs


def covered_blocks(ep: list[dict], slot_lba0: int, slot_bytes: int) -> set[int]:
    """4 KiB block indices within the slot that were touched."""
    touched: set[int] = set()
    nblocks = slot_bytes // READ_N
    for r in ep:
        fo0, _, in_slot = row_span(r, slot_lba0, slot_bytes)
        if not in_slot or fo0 is None:
            continue
        nbytes = int(r["bytes"])
        # map each byte range into blocks
        l0 = int(r["lba0"])
        for sec in range(max(1, nbytes // SECTOR)):
            off = file_off(l0 + sec, slot_lba0, slot_bytes)
            if off is None:
                continue
            touched.add(off // READ_N)
    # clamp
    return {b for b in touched if 0 <= b < nblocks}


def max_off_first_s(ep: list[dict], slot_lba0: int, slot_bytes: int, window_ms: int = 2000) -> int | None:
    if not ep:
        return None
    t0 = int(ep[0]["ms"])
    mx: int | None = None
    for r in ep:
        if int(r["ms"]) - t0 > window_ms:
            break
        fo0, fo1, in_slot = row_span(r, slot_lba0, slot_bytes)
        if not in_slot:
            continue
        for v in (fo0, fo1):
            if v is None:
                continue
            end = v + (int(r["bytes"]) if v == fo0 else SECTOR) - 1
            mx = end if mx is None else max(mx, end)
    return mx


def classify_r10(segs: list[Segment], head_bytes: int = SELECT_HEAD) -> dict[str, Any]:
    slot_segs = [s for s in segs if s.in_slot and s.file_off0 is not None]
    if not slot_segs:
        return {"verdict": "no_slot_reads", "note": "keine Reads im Slot"}

    # first contiguous forward from 0?
    first = slot_segs[0]
    head_like = (
        first.direction == "forward"
        and first.file_off0 == 0
        and first.bytes >= head_bytes - READ_N
        and first.bytes <= head_bytes + READ_N
    )

    # after head: how far do fragment offs jump?
    after = slot_segs[1:] if head_like else slot_segs
    max_off = max((s.file_off0 or 0) for s in slot_segs)
    max_jump = 0
    near = True
    for s in after:
        o = s.file_off0 or 0
        if o > head_bytes + 1024 * 1024:
            near = False
            max_jump = max(max_jump, o - head_bytes)

    total_slot = sum(s.bytes for s in slot_segs)
    # R16: activity around P=958464, or first ~2 MiB resume chunk
    p_pos = 958464
    near_p = any(
        s.file_off0 is not None and abs(s.file_off0 - p_pos) < 64 * 1024 for s in slot_segs[:8]
    )
    early_bytes = 0
    for s in slot_segs:
        early_bytes += s.bytes
        if early_bytes >= R16_RESUME_BYTES - 8192:
            break
    r16_like = (not head_like) and (
        near_p
        or abs(early_bytes - R16_RESUME_BYTES) < 16384
        or abs(total_slot - R16_RESUME_BYTES) < 8192
    )

    if r16_like:
        verdict = "r16_resume_like"
        stall = "Startposition ≠ 0 — R16-Muster; P-Quelle klären"
    elif near and head_like:
        verdict = "fragments_near"
        stall = "Feste Zuordnung + stallAhead ≈ Fragmentbereich (Plan A)"
    elif head_like and not near:
        verdict = "fragments_far"
        stall = "Vorauslesen weit — Stall allein evtl. nicht genug; Slot klein oder Dateikette"
    elif not head_like and near:
        verdict = "unclear"
        stall = "kein Kopf-Lauf 360 KiB; Segmente manuell prüfen"
    else:
        verdict = "unclear"
        stall = "manuell prüfen"

    return {
        "verdict": verdict,
        "stall_implication": stall,
        "head_like": head_like,
        "first_seg_bytes": first.bytes,
        "max_file_off": max_off,
        "max_jump_past_head": max_jump,
        "slot_bytes_total": total_slot,
        "n_slot_segments": len(slot_segs),
    }


def analyze_episode(
    ep: list[dict],
    *,
    slot_lba0: int,
    slot_bytes: int,
    label: str,
) -> dict[str, Any]:
    segs = segments_from_episode(ep, slot_lba0, slot_bytes)
    touched = covered_blocks(ep, slot_lba0, slot_bytes)
    nblocks = slot_bytes // READ_N
    unread = sorted(set(range(nblocks)) - touched)
    unread_bytes = len(unread) * READ_N
    r10 = classify_r10(segs)
    ov0 = int(ep[0].get("ov") or 0)
    ov1 = int(ep[-1].get("ov") or 0)
    return {
        "label": label,
        "ms_from": int(ep[0]["ms"]),
        "ms_to": int(ep[-1]["ms"]),
        "span_s": round((int(ep[-1]["ms"]) - int(ep[0]["ms"])) / 1000.0, 3),
        "n_rows": len(ep),
        "bytes_total": sum(int(r["bytes"]) for r in ep),
        "ov_first_last": [ov0, ov1],
        "ov_delta": ov1 - ov0,
        "max_off_first_2s": max_off_first_s(ep, slot_lba0, slot_bytes),
        "segments": [asdict(s) for s in segs],
        "unread_4k_blocks": len(unread),
        "unread_bytes": unread_bytes,
        "unread_block_indices_head": unread[:40],
        "unread_block_indices_tail": unread[-20:] if len(unread) > 40 else [],
        "r10": r10,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reads", default="", help="msc_reads.jsonl oder Bridge-Log")
    ap.add_argument("--ms-from", type=int, default=None)
    ap.add_argument("--ms-to", type=int, default=None)
    ap.add_argument("--lba0", type=int, default=DEFAULT_LBA0, help="Slot-Start-LBA (L3 fav0=81)")
    ap.add_argument("--slot-bytes", type=int, default=DEFAULT_SLOT)
    ap.add_argument("--pause-ms", type=int, default=2000, help="Episode-Schnitt bei Pause")
    ap.add_argument("--out-dir", default="", help="schreibt REPORT.json + segments.csv")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.reads:
        ap.error("--reads required (unless --self-test)")

    rows = load_msc_reads(Path(args.reads), args.ms_from, args.ms_to)
    if not rows:
        print("no rows", file=sys.stderr)
        return 2

    if args.ms_from is not None or args.ms_to is not None:
        episodes = [rows]
        labels = [f"window_{args.ms_from}-{args.ms_to}"]
    else:
        episodes = coalesce_bursts(rows, args.pause_ms)
        labels = [f"ep{i}" for i in range(len(episodes))]

    reports = [
        analyze_episode(ep, slot_lba0=args.lba0, slot_bytes=args.slot_bytes, label=lab)
        for ep, lab in zip(episodes, labels)
        if ep
    ]
    out = {
        "reads": str(args.reads),
        "lba0": args.lba0,
        "slot_bytes": args.slot_bytes,
        "pause_ms": args.pause_ms,
        "n_episodes": len(reports),
        "episodes": reports,
    }

    # stdout summary
    for ep in reports:
        r10 = ep["r10"]
        print(
            f"{ep['label']}: ms {ep['ms_from']}–{ep['ms_to']} ({ep['span_s']}s) "
            f"rows={ep['n_rows']} bytes={ep['bytes_total']} ovΔ={ep['ov_delta']} "
            f"unread_4k={ep['unread_4k_blocks']} ({ep['unread_bytes']} B) "
            f"max_off_2s={ep['max_off_first_2s']} → {r10['verdict']}"
        )
        print(f"  stall: {r10['stall_implication']}")
        for s in ep["segments"][:12]:
            if s["direction"] == "meta":
                print(f"  seg{s['i']}: META lba={s['lba0']}…{s['lba1']} B={s['bytes']}")
            else:
                print(
                    f"  seg{s['i']}: {s['direction']:8} off={s['file_off0']}… "
                    f"B={s['bytes']} lba={s['lba0']}…{s['lba1']}"
                )
        if len(ep["segments"]) > 12:
            print(f"  … +{len(ep['segments']) - 12} Segmente")

    if args.out_dir:
        od = Path(args.out_dir)
        od.mkdir(parents=True, exist_ok=True)
        (od / "Q8-REPORT.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        with (od / "Q8-SEGMENTS.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "episode",
                    "seg",
                    "ms0",
                    "ms1",
                    "direction",
                    "file_off0",
                    "bytes",
                    "lba0",
                    "lba1",
                    "in_slot",
                ]
            )
            for ep in reports:
                for s in ep["segments"]:
                    w.writerow(
                        [
                            ep["label"],
                            s["i"],
                            s["ms0"],
                            s["ms1"],
                            s["direction"],
                            s["file_off0"],
                            s["bytes"],
                            s["lba0"],
                            s["lba1"],
                            s["in_slot"],
                        ]
                    )
        print(f"wrote {od / 'Q8-REPORT.json'}")

    return 0


def self_test() -> int:
    # synthetic: head 360 KiB then near fragment then final
    lba0 = 81
    rows = []
    ms = 1000
    # head 368640 @ 4k
    off = 0
    while off < SELECT_HEAD:
        lba = lba0 + off // SECTOR
        rows.append({"ms": ms, "gap": 4, "lba0": lba, "lba1": lba, "bytes": READ_N, "n": 1, "ov": 0})
        off += READ_N
        ms += 5
    ms += 3000  # pause → new episode if coalesced; keep same ep via low gap in analyze single
    # near fragment at 400 KiB
    frag_off = 400 * 1024
    lba = lba0 + frag_off // SECTOR
    rows.append({"ms": ms, "gap": 4, "lba0": lba, "lba1": lba, "bytes": READ_N, "n": 1, "ov": 0})
    rep = analyze_episode(rows, slot_lba0=lba0, slot_bytes=DEFAULT_SLOT, label="syn")
    assert rep["r10"]["head_like"], rep["r10"]
    assert rep["r10"]["verdict"] == "fragments_near", rep["r10"]
    # far fragment
    rows2 = rows[:-1] + [
        {
            "ms": ms,
            "gap": 4,
            "lba0": lba0 + (5 * 1024 * 1024) // SECTOR,
            "lba1": lba0 + (5 * 1024 * 1024) // SECTOR,
            "bytes": READ_N,
            "n": 1,
            "ov": 0,
        }
    ]
    rep2 = analyze_episode(rows2, slot_lba0=lba0, slot_bytes=DEFAULT_SLOT, label="far")
    assert rep2["r10"]["verdict"] == "fragments_far", rep2["r10"]
    print("self-test PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
