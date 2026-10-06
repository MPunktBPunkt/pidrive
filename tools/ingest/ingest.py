#!/usr/bin/env python3
"""Ingest heterogeneous field/lab artifacts into Parquet + DuckDB.

Review (summary-2026-10-06): Rohdaten bleiben; normalisierte Schicht in data/.

  .venv-ingest/bin/python tools/ingest/ingest.py --root docs/betrieb
  .venv-ingest/bin/python tools/ingest/ingest.py --run docs/betrieb/artifacts-2026-10-06-feld/feld-av-0723

Requires: duckdb, pyyaml (see tools/ingest/requirements.txt).
Generated files under data/ are gitignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import duckdb
except ImportError as e:
    raise SystemExit(
        "duckdb missing — create venv: python3 -m venv .venv-ingest && "
        ".venv-ingest/bin/pip install -r tools/ingest/requirements.txt"
    ) from e

try:
    import yaml
except ImportError as e:
    raise SystemExit("pyyaml missing — pip install pyyaml") from e

REPO = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1

UPTIME_RE = re.compile(
    r"(?:(?P<h>\d+)\s*h)?\s*(?:(?P<min>\d+)\s*min)?\s*(?:(?P<s>\d+)\s*s)?",
    re.I,
)


def parse_uptime_ms(s: Any) -> int | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    text = str(s).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    m = UPTIME_RE.fullmatch(text.replace(" ", ""))
    if not m:
        m = UPTIME_RE.search(text)
    if not m:
        return None
    h = int(m.group("h") or 0)
    mn = int(m.group("min") or 0)
    sec = int(m.group("s") or 0)
    if h == 0 and mn == 0 and sec == 0 and not any(m.groups()):
        return None
    return ((h * 60 + mn) * 60 + sec) * 1000


def parse_wall(s: Any) -> datetime | None:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc).astimezone()
    text = str(s).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.astimezone()
    except ValueError:
        return None


def wall_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat(timespec="milliseconds")


class ClockSync:
    """Map ESP uptime_ms → wall time via one anchor."""

    def __init__(self, esp_uptime_ms: int | None, wall: datetime | None):
        self.esp_uptime_ms = esp_uptime_ms
        self.wall = wall

    def from_uptime(self, uptime_ms: int | None) -> datetime | None:
        if self.wall is None or self.esp_uptime_ms is None or uptime_ms is None:
            return None
        delta = timedelta(milliseconds=uptime_ms - self.esp_uptime_ms)
        return self.wall + delta

    def from_epoch(self, ts: float | None) -> datetime | None:
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(float(ts)).astimezone()
        except (OSError, OverflowError, ValueError):
            return None


def load_run_yaml(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not doc.get("run_id"):
        raise SystemExit(f"run.yaml missing run_id: {path}")
    doc["_path"] = str(path)
    doc["_dir"] = str(path.parent)
    return doc


def discover_run_yamls(root: Path) -> list[Path]:
    return sorted(root.rglob("run.yaml"))


def flatten_status(st: dict, *, source: str, run_id: str, clock: ClockSync) -> dict:
    m = st.get("msc") or {}
    stream = m.get("stream") or st.get("stream") or {}
    sb = int(m.get("streamBytes") or st.get("streamBytes") or 0)
    und = int(stream.get("underruns") or st.get("underruns") or 0)
    up_ms = parse_uptime_ms(st.get("uptime") or st.get("esp_uptime"))
    # correlate / poll already flat
    if "hostAbsCursor" in st or "hostAbs" in st:
        host = st.get("hostAbsCursor", st.get("hostAbs"))
        und = int(st.get("underruns") or und)
        sb = int(st.get("streamBytes") or sb)
        abs_base = st.get("absBase")
        abs_end = st.get("absEnd")
        armed = st.get("cursorArmed")
        play = st.get("play") or st.get("playingUid") or ""
        up_ms = parse_uptime_ms(st.get("esp_uptime") or st.get("uptime")) or up_ms
    else:
        host = stream.get("hostAbsCursor")
        abs_base = stream.get("absBase")
        abs_end = stream.get("absEnd")
        armed = stream.get("cursorArmed")
        play = st.get("playingUid") or ""

    t_wall = None
    if st.get("wall_iso"):
        t_wall = parse_wall(st["wall_iso"])
    elif st.get("ts") is not None:
        t_wall = clock.from_epoch(st.get("ts"))
    else:
        t_wall = clock.from_uptime(up_ms)

    return {
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "t_wall": wall_iso(t_wall),
        "esp_uptime_ms": up_ms,
        "version": st.get("version"),
        "playingUid": play,
        "readCount": m.get("readCount") if "readCount" in m else st.get("readCount"),
        "bytesFile": m.get("bytesFile") if "bytesFile" in m else st.get("bytesFile"),
        "streamBytes": sb,
        "underruns": und,
        "liveBytes": max(0, sb - und) if sb or und else st.get("liveBytes"),
        "hostAbs": host,
        "absBase": abs_base,
        "absEnd": abs_end,
        "cursorArmed": armed,
        "stream_active": stream.get("active") if stream else st.get("stream_active"),
        "guess": m.get("playGuessCount") if m else st.get("playGuessCount"),
        "rej": m.get("playRejectCount") if m else st.get("playRejectCount"),
        "cold": m.get("coldBodyBurstCount") if m else st.get("coldBodyBurstCount"),
        "serial": m.get("usbSerial") if m else st.get("serial"),
    }


def iter_slots(st: dict, *, source: str, run_id: str, clock: ClockSync, status_row: dict) -> list[dict]:
    m = st.get("msc") or {}
    slots = m.get("slotMap") or st.get("slotMap") or st.get("slots") or []
    rows = []
    for s in slots:
        if not isinstance(s, dict):
            continue
        rows.append(
            {
                "run_id": run_id,
                "source": source,
                "t_wall": status_row.get("t_wall"),
                "esp_uptime_ms": status_row.get("esp_uptime_ms"),
                "uid": s.get("uid"),
                "name": s.get("name"),
                "bytes": s.get("bytes", s.get("b")),
                "maxSeq": s.get("maxSeq", s.get("mx")),
                "fromHead": s.get("fromHead", s.get("h")),
                "midFile": s.get("midFile", s.get("m")),
                "lba0": s.get("lba0"),
                "lba1": s.get("lba1"),
            }
        )
    return rows


def iter_msc_reads(st: dict, *, source: str, run_id: str, status_row: dict) -> list[dict]:
    m = st.get("msc") or {}
    trace = m.get("mscTrace") or st.get("mscTrace") or []
    rows = []
    for e in trace:
        if not isinstance(e, dict):
            continue
        rows.append(
            {
                "run_id": run_id,
                "source": source,
                "t_wall": status_row.get("t_wall"),
                "esp_uptime_ms": status_row.get("esp_uptime_ms"),
                "ms": e.get("ms"),
                "gap": e.get("gap"),
                "lba": e.get("lba"),
                "n": e.get("n"),
                "kind": e.get("kind"),
                "tag": e.get("tag"),
                "fileOff": e.get("fileOff") or e.get("fileOff0"),
            }
        )
    return rows


def dedupe_msc_reads(rows: list[dict]) -> list[dict]:
    """Ring of 96 overlaps across snapshots — keep unique (ms,lba,n,tag)."""
    seen: set[tuple] = set()
    out = []
    for r in rows:
        key = (r.get("run_id"), r.get("ms"), r.get("lba"), r.get("n"), r.get("tag"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


BRIDGE_PATTERNS = [
    (re.compile(r"audio_start.*?uid[=:\s]+(\S+)", re.I), "audio_start"),
    (re.compile(r"play_uid.*?uid[=:\s]+(\S+)", re.I), "play_uid"),
    (re.compile(r"switch.*?from[=:\s]+(\S+).*?to[=:\s]+(\S+).*?age[=:\s]+([\d.]+)", re.I), "switch"),
    (re.compile(r"hello_ack", re.I), "hello_ack"),
    (re.compile(r"BrokenPipe|broken pipe", re.I), "broken_pipe"),
    (re.compile(r"MSC_MAP_FROZEN", re.I), "msc_map_frozen"),
]


def parse_bridge_line(line: str, run_id: str, source: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    # leading wall time?
    t_wall = None
    mts = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*)\s+(.*)$", text)
    if mts:
        t_wall = wall_iso(parse_wall(mts.group(1).replace(" ", "T")))
        text = mts.group(2)
    for rx, ev in BRIDGE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        row = {
            "run_id": run_id,
            "source": source,
            "t_wall": t_wall,
            "event": ev,
            "raw": text[:500],
            "uid": None,
            "uid_to": None,
            "age_s": None,
        }
        if ev in ("audio_start", "play_uid"):
            row["uid"] = m.group(1).strip("\",'")
        elif ev == "switch":
            row["uid"] = m.group(1)
            row["uid_to"] = m.group(2)
            try:
                row["age_s"] = float(m.group(3))
            except ValueError:
                pass
        return row
    return None


def _bitrate_kbps(doc: dict) -> int | None:
    if doc.get("bitrate_kbps") is not None:
        try:
            return int(doc["bitrate_kbps"])
        except (TypeError, ValueError):
            pass
    br = (doc.get("bridge") or {}).get("bitrate") or ""
    m = re.match(r"(\d+)", str(br))
    return int(m.group(1)) if m else None


def observations_from_run(doc: dict) -> list[dict]:
    rows = []
    heard = doc.get("heard")
    if heard:
        rows.append(
            {
                "run_id": doc["run_id"],
                "t_wall": (doc.get("clock_sync") or {}).get("wall"),
                "what": "heard",
                "value": heard,
                "note": doc.get("notes") or "",
            }
        )
    for obs in doc.get("observations") or []:
        if isinstance(obs, dict):
            rows.append(
                {
                    "run_id": doc["run_id"],
                    "t_wall": wall_iso(parse_wall(obs.get("t") or obs.get("t_wall"))),
                    "what": obs.get("what") or obs.get("op") or "note",
                    "value": str(obs.get("value") or obs.get("uid") or ""),
                    "note": obs.get("note") or json.dumps(obs, ensure_ascii=False, default=str)[:300],
                }
            )
    return rows


def collect_run(doc: dict) -> dict[str, list[dict]]:
    root = Path(doc["_dir"])
    run_id = doc["run_id"]
    cs = doc.get("clock_sync") or {}
    clock = ClockSync(parse_uptime_ms(cs.get("esp_uptime_ms")), parse_wall(cs.get("wall")))

    status_rows: list[dict] = []
    slot_rows: list[dict] = []
    read_rows: list[dict] = []
    bridge_rows: list[dict] = []

    # Full ESP status JSON
    for p in sorted(root.rglob("status-*.json")) + sorted(root.rglob("st-*.json")):
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(st, dict):
            continue
        # skip nested REPORT wrappers
        if "pre" in st and "classification" in st:
            continue
        rel = str(p.relative_to(root))
        flat = flatten_status(st, source=rel, run_id=run_id, clock=clock)
        status_rows.append(flat)
        slot_rows.extend(iter_slots(st, source=rel, run_id=run_id, clock=clock, status_row=flat))
        read_rows.extend(iter_msc_reads(st, source=rel, run_id=run_id, status_row=flat))

    # Correlate / poll JSONL (already flat-ish)
    for p in sorted(root.rglob("*.jsonl")):
        rel = str(p.relative_to(root))
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            # sim events vs status
            if obj.get("op") == "read" or obj.get("klass"):
                continue
            flat = flatten_status(obj, source=rel, run_id=run_id, clock=clock)
            status_rows.append(flat)
            if obj.get("slotMap") or obj.get("slots"):
                slot_rows.extend(
                    iter_slots(obj, source=rel, run_id=run_id, clock=clock, status_row=flat)
                )

    # Lab REPORT.json snapshots (pre/after)
    for p in sorted(root.glob("status-*.json")):
        pass  # already in rglob

    for p in sorted(root.rglob("REPORT.json")):
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        rel = str(p.relative_to(root))
        for key in ("pre", "after_uid", "after_next", "snap_final"):
            st = rep.get(key)
            if isinstance(st, dict) and ("hostAbs" in st or "streamBytes" in st or "slots" in st):
                # lab snap shape
                wrapped = {
                    "uptime": st.get("uptime"),
                    "playingUid": st.get("play"),
                    "msc": {
                        "streamBytes": st.get("streamBytes"),
                        "readCount": st.get("readCount"),
                        "usbSerial": st.get("serial"),
                        "stream": {
                            "hostAbsCursor": st.get("hostAbs"),
                            "absBase": st.get("absBase"),
                            "absEnd": st.get("absEnd"),
                            "underruns": st.get("underruns"),
                            "cursorArmed": st.get("armed"),
                            "active": st.get("active"),
                        },
                        "slotMap": st.get("slots") or [],
                    },
                    "version": st.get("version"),
                }
                flat = flatten_status(wrapped, source=f"{rel}:{key}", run_id=run_id, clock=clock)
                status_rows.append(flat)
                slot_rows.extend(
                    iter_slots(wrapped, source=f"{rel}:{key}", run_id=run_id, clock=clock, status_row=flat)
                )
        # golden results as observations
        for gid, res in (rep.get("results") or {}).items():
            if isinstance(res, dict):
                bridge_rows.append(
                    {
                        "run_id": run_id,
                        "source": rel,
                        "t_wall": None,
                        "event": f"golden_{gid}",
                        "raw": json.dumps({"pass": res.get("pass")}, ensure_ascii=False),
                        "uid": None,
                        "uid_to": None,
                        "age_s": None,
                    }
                )

    for p in sorted(root.rglob("bridge*.txt")) + sorted(root.rglob("bridge*.log")):
        rel = str(p.relative_to(root))
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                row = parse_bridge_line(line, run_id, rel)
                if row:
                    bridge_rows.append(row)
        except Exception:
            continue

    read_rows = dedupe_msc_reads(read_rows)
    obs_rows = observations_from_run(doc)

    run_row = {
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "env": doc.get("env"),
        "stufe": doc.get("stufe"),
        "fw": doc.get("fw"),
        "fw_commit": doc.get("fw_commit"),
        "build_env": doc.get("build_env"),
        "geometry": doc.get("geometry"),
        "counter_semantics": doc.get("counter_semantics"),
        "station": doc.get("station"),
        "bitrate_kbps": doc.get("bitrate_kbps")
        if doc.get("bitrate_kbps") is not None
        else _bitrate_kbps(doc),
        "heard": doc.get("heard"),
        "notes": doc.get("notes"),
        "artifact_dir": doc["_dir"],
        "clock_esp_uptime_ms": parse_uptime_ms(cs.get("esp_uptime_ms")),
        "clock_wall": wall_iso(parse_wall(cs.get("wall"))),
    }

    return {
        "runs": [run_row],
        "status": status_rows,
        "slots": slot_rows,
        "msc_reads": read_rows,
        "bridge_events": bridge_rows,
        "observations": obs_rows,
    }


def write_tables(out_dir: Path, tables: dict[str, list[dict]], db_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))

    def _json_default(o: Any) -> Any:
        if isinstance(o, datetime):
            return wall_iso(o)
        raise TypeError(type(o))

    try:
        for name, rows in tables.items():
            parquet = out_dir / f"{name}.parquet"
            if not rows:
                # empty table with minimal schema
                con.execute(
                    f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM (SELECT 1 AS _empty) WHERE 0"
                )
                con.execute(f"COPY {name} TO '{parquet.as_posix()}' (FORMAT PARQUET)")
                continue
            # register via JSON
            tmp = out_dir / f"_{name}.json"
            tmp.write_text(json.dumps(rows, ensure_ascii=False, default=_json_default), encoding="utf-8")
            con.execute(
                f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_json_auto('{tmp.as_posix()}')"
            )
            con.execute(f"COPY {name} TO '{parquet.as_posix()}' (FORMAT PARQUET)")
            tmp.unlink(missing_ok=True)
            print(f"  {name}: {len(rows)} rows -> {parquet.resolve()}")
        # convenience views
        con.execute(
            """
            CREATE OR REPLACE VIEW v_feld_status AS
            SELECT * FROM status WHERE run_id LIKE '%feld%';
            """
        )
    finally:
        con.close()
    print(f"  duckdb: {Path(db_path).resolve()}")


def merge_tables(acc: dict[str, list[dict]], part: dict[str, list[dict]]) -> None:
    for k, rows in part.items():
        acc.setdefault(k, []).extend(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest artifacts → data/*.parquet + DuckDB")
    ap.add_argument("--root", default="docs/betrieb", help="scan for run.yaml under this tree")
    ap.add_argument("--run", action="append", default=[], help="single artifact dir (with run.yaml)")
    ap.add_argument("--out", default="data", help="output directory (gitignored)")
    ap.add_argument("--db", default="data/pidrive.duckdb")
    args = ap.parse_args()

    runs: list[Path] = []
    if args.run:
        for r in args.run:
            p = Path(r)
            y = p / "run.yaml" if p.is_dir() else p
            if not y.is_file():
                raise SystemExit(f"missing {y}")
            runs.append(y)
    else:
        runs = [p for p in discover_run_yamls(Path(args.root)) if "templates" not in p.parts]
        if not runs:
            raise SystemExit(f"no run.yaml under {args.root}")

    print(f"ingest {len(runs)} run(s)")
    acc: dict[str, list[dict]] = {}
    for y in runs:
        doc = load_run_yaml(y)
        print(f"- {doc['run_id']} ({y.parent})")
        part = collect_run(doc)
        merge_tables(acc, part)

    write_tables(Path(args.out), acc, Path(args.db))
    # also write a small manifest
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runs": [r["run_id"] for r in acc.get("runs", [])],
        "counts": {k: len(v) for k, v in acc.items()},
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
