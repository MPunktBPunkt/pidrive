#!/usr/bin/env python3
"""Correlate PiDrive field artifacts for D/Resume/Identity analysis.

The report deliberately separates:
  * decoder/play state (playingUid),
  * physical MSC reads (LBA -> file offset), and
  * bytes already observed before a play transition.

It accepts an artifact directory and discovers status polls/snapshots, traces,
marks and event snapshots recursively.  No device connection is required.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HEAD_SLOP_SECTORS = 12
SECTOR = 512


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if isinstance(value, dict):
                yield value


def epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def first_number(obj: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = epoch(obj.get(key))
        if value is not None:
            return value
    return None


def msc_of(status: dict[str, Any]) -> dict[str, Any]:
    value = status.get("msc")
    return value if isinstance(value, dict) else {}


def stream_of(status: dict[str, Any]) -> dict[str, Any]:
    value = status.get("stream")
    if isinstance(value, dict):
        return value
    value = msc_of(status).get("stream")
    return value if isinstance(value, dict) else {}


def slots_of(status: dict[str, Any]) -> list[dict[str, Any]]:
    value = status.get("slotMap")
    if not isinstance(value, list):
        value = msc_of(status).get("slotMap")
    return [slot for slot in (value or []) if isinstance(slot, dict)]


@dataclass
class StatusSample:
    t: float | None
    source: str
    raw: dict[str, Any]

    @property
    def serial(self) -> str:
        return str(self.raw.get("serial") or msc_of(self.raw).get("usbSerial") or "")

    @property
    def playing(self) -> str:
        return str(self.raw.get("playingUid") or "")

    @property
    def stream_uid(self) -> str:
        return str(
            self.raw.get("stream_uid")
            or stream_of(self.raw).get("uid")
            or ""
        )


@dataclass
class TraceRead:
    t: float | None
    lba: int
    n: int
    source: str


def status_time(row: dict[str, Any]) -> float | None:
    return first_number(row, "wall", "wall_est", "wall_iso")


def load_statuses(root: Path) -> list[StatusSample]:
    rows: list[StatusSample] = []
    poll_paths = sorted(root.rglob("status-poll.jsonl"))
    for path in poll_paths:
        for row in read_jsonl(path):
            rows.append(StatusSample(status_time(row), str(path), row))

    # Snapshots add fields absent from old polls. Deduplicate identical files by
    # resolved path; duplicate copies in parent/child artifact folders are fine.
    for path in sorted(root.rglob("status*.json")):
        try:
            row = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict) or not (row.get("msc") or row.get("slotMap")):
            continue
        rows.append(StatusSample(status_time(row), str(path), row))
    rows.sort(key=lambda x: (x.t is None, x.t or 0.0, x.source))
    return rows


def load_trace(root: Path) -> list[TraceRead]:
    rows: list[TraceRead] = []
    for path in sorted(root.rglob("trace.jsonl")):
        for row in read_jsonl(path):
            if row.get("kind") != "file":
                continue
            try:
                lba = int(row["lba"])
                n = int(row.get("n") or 0)
            except (KeyError, TypeError, ValueError):
                continue
            rows.append(
                TraceRead(
                    first_number(row, "wall_est", "wall", "wall_iso"),
                    lba,
                    n,
                    str(path),
                )
            )
    rows.sort(key=lambda x: (x.t is None, x.t or 0.0))
    return rows


def nearest_status(statuses: list[StatusSample], when: float | None) -> StatusSample | None:
    candidates = [s for s in statuses if s.t is not None]
    if when is None or not candidates:
        return statuses[-1] if statuses else None
    return min(candidates, key=lambda s: abs(float(s.t) - when))


def slot_for_lba(status: StatusSample, lba: int) -> dict[str, Any] | None:
    for slot in slots_of(status.raw):
        try:
            if int(slot["lba0"]) <= lba <= int(slot.get("lba1") or slot["lba0"]):
                return slot
        except (KeyError, TypeError, ValueError):
            continue
    return None


def slot_size(slot: dict[str, Any]) -> int:
    try:
        return (int(slot["lba1"]) - int(slot["lba0"]) + 1) * SECTOR
    except (KeyError, TypeError, ValueError):
        return 0


def snapshot_rows(statuses: list[StatusSample]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for sample in statuses:
        msc = msc_of(sample.raw)
        for slot in slots_of(sample.raw):
            uid = str(slot.get("uid") or "")
            size = slot_size(slot)
            try:
                seen = int(slot.get("bytes") or 0)
            except (TypeError, ValueError):
                seen = 0
            output.append(
                {
                    "source": sample.source,
                    "time": sample.t,
                    "serial": sample.serial,
                    "volume_label": str(msc.get("volumeLabel") or ""),
                    "playing_uid": sample.playing,
                    "stream_uid": sample.stream_uid,
                    "stream_slot": msc.get("streamSlot"),
                    "uid": uid,
                    "name": slot.get("name"),
                    "slot_bytes": size,
                    "bytes_seen": seen,
                    "coverage_pct": round(100.0 * seen / size, 2) if size else None,
                    "from_head": slot.get("fromHead"),
                    "mid_file": slot.get("midFile"),
                    "max_seq": slot.get("maxSeq"),
                    "non_live_prefetch_candidate": bool(
                        size and seen >= size // 4 and sample.stream_uid and sample.stream_uid != uid
                    ),
                }
            )
    return output


def trace_rows(
    statuses: list[StatusSample], reads: list[TraceRead]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    first_seen: set[tuple[str, str]] = set()
    for read in reads:
        status = nearest_status(statuses, read.t)
        if status is None:
            continue
        slot = slot_for_lba(status, read.lba)
        if slot is None:
            continue
        uid = str(slot.get("uid") or "")
        lba0 = int(slot.get("lba0") or 0)
        file_off = (read.lba - lba0) * SECTOR
        key = (status.serial, uid)
        is_first = key not in first_seen
        first_seen.add(key)
        output.append(
            {
                "time": read.t,
                "serial": status.serial,
                "uid": uid,
                "lba": read.lba,
                "bytes": read.n,
                "file_offset": file_off,
                "head_like": file_off <= HEAD_SLOP_SECTORS * SECTOR,
                "first_body_read": is_first,
                "playing_uid": status.playing,
                "stream_uid": status.stream_uid,
                "live_slot": status.stream_uid == uid,
                "source": read.source,
            }
        )
    return output


def play_transitions(
    statuses: list[StatusSample], traces: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    previous = ""
    for sample in statuses:
        uid = sample.playing
        if not uid or uid == previous:
            previous = uid
            continue
        slot = next((s for s in slots_of(sample.raw) if s.get("uid") == uid), {})
        before_bytes = int(slot.get("bytes") or 0) if slot else 0
        nearby = []
        if sample.t is not None:
            nearby = [
                row
                for row in traces
                if row["uid"] == uid
                and row["time"] is not None
                and -2.0 <= float(row["time"]) - float(sample.t) <= 8.0
            ]
        output.append(
            {
                "time": sample.t,
                "serial": sample.serial,
                "uid": uid,
                "bytes_before_play": before_bytes,
                "reads_near_play": len(nearby),
                "first_body_offset_near_play": (
                    min(int(row["file_offset"]) for row in nearby) if nearby else None
                ),
                "cache_hit_like": not nearby,
                "source": sample.source,
            }
        )
        previous = uid
    return output


def load_events_and_marks(root: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"events": [], "marks": []}
    for path in sorted(root.rglob("events*.json")):
        try:
            value = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        events = value.get("events") if isinstance(value, dict) else None
        for event in events or []:
            if isinstance(event, dict):
                result["events"].append({"source": str(path), **event})
    for path in sorted(root.rglob("marks.jsonl")):
        for mark in read_jsonl(path):
            result["marks"].append({"source": str(path), **mark})
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_summary(report: dict[str, Any]) -> str:
    candidates = [
        row for row in report["snapshots"] if row["non_live_prefetch_candidate"]
    ]
    transitions = report["play_transitions"]
    lines = [
        "# D Resume/Identity Offline Report",
        "",
        f"- Status-/Slotzeilen: {len(report['snapshots'])}",
        f"- zugeordnete File-Reads: {len(report['trace_reads'])}",
        f"- Play-Transitions: {len(transitions)}",
        f"- Non-live-Prefetch-Kandidaten: {len(candidates)}",
        "",
        "## Auffällige Non-live-Prefetch-Snapshots",
        "",
        "| Serial | Slot | Abdeckung | Streamslot | Head/Mid | Quelle |",
        "|---|---|---:|---|---:|---|",
    ]
    for row in sorted(candidates, key=lambda x: float(x["coverage_pct"] or 0), reverse=True)[:30]:
        lines.append(
            f"| {row['serial']} | {row['uid']} | {row['coverage_pct']} % | "
            f"{row['stream_uid']} | {row['from_head']}/{row['mid_file']} | "
            f"`{Path(row['source']).name}` |"
        )
    lines.extend(
        [
            "",
            "## Play-Transitions",
            "",
            "| Serial | UID | Bytes vorher | Reads ±Fenster | erster Offset | Cache-hit-like |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in transitions[:50]:
        lines.append(
            f"| {row['serial']} | {row['uid']} | {row['bytes_before_play']} | "
            f"{row['reads_near_play']} | {row['first_body_offset_near_play']} | "
            f"{row['cache_hit_like']} |"
        )
    lines.extend(
        [
            "",
            "> `cache_hit_like` bedeutet nur: im verfügbaren Trace-Fenster wurde kein "
            "Read gefunden. Es ist kein Decoder-P-Beweis.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="artifact directory to analyze")
    parser.add_argument("--out", type=Path, help="output directory (default: RUN/d-resume-analysis)")
    args = parser.parse_args()

    root = args.run.resolve()
    out = (args.out or root / "d-resume-analysis").resolve()
    out.mkdir(parents=True, exist_ok=True)

    statuses = load_statuses(root)
    reads = load_trace(root)
    snapshots = snapshot_rows(statuses)
    traces = trace_rows(statuses, reads)
    context = load_events_and_marks(root)
    report = {
        "schema_version": 1,
        "run": str(root),
        "warnings": [
            "decoder P is not inferred from first_file_body_offset",
            "fromHead/midFile are ESP headLbaSlop classifications",
            "trace tag Rock Antenn is ambiguous; slot mapping uses LBA ranges",
        ],
        "snapshots": snapshots,
        "trace_reads": traces,
        "play_transitions": play_transitions(statuses, traces),
        **context,
    }
    (out / "RESUME-IDENTITY-REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_csv(out / "snapshots.csv", snapshots)
    write_csv(out / "trace-reads.csv", traces)
    write_csv(out / "play-transitions.csv", report["play_transitions"])
    (out / "REPORT.md").write_text(markdown_summary(report), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
