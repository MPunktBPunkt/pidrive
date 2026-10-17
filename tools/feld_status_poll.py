#!/usr/bin/env python3
"""ESP status poll with wall-clock timestamps (Stufe 0 / Storm Q/S).

Schema v2 adds Prefetch-Livelock axes (M30/M31): prefetchHits, meta-byte
counters, midFile/fromHead per slot, plug/guess latencies. Older v1 rows
remain readable; classify tools tolerate missing axes.

Example:
  python3 tools/feld_status_poll.py --esp http://192.168.178.89 \\
      --out docs/betrieb/artifacts-2026-10-06-feld/feld-av-0723/status-poll.jsonl \\
      --seconds 90 --print
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2


def http_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def slot_progress(slots: list) -> list[dict]:
    out = []
    for s in slots or []:
        if not isinstance(s, dict):
            continue
        out.append(
            {
                "uid": s.get("uid"),
                "name": s.get("name"),
                "bytes": s.get("bytes"),
                "fileBytes": s.get("fileBytes"),
                "maxSeq": s.get("maxSeq"),
                "b": s.get("b"),
                "lba0": s.get("lba0"),
                "lba1": s.get("lba1"),
                "fromHead": s.get("fromHead"),
                "midFile": s.get("midFile"),
                "lastAgeMs": s.get("lastAgeMs"),
                "kind": s.get("kind"),
            }
        )
    return out


def row_from_status(st: dict, wall_iso: str, mono: float, run_id: str = "") -> dict:
    m = st.get("msc") or {}
    stream = m.get("stream") or st.get("stream") or {}
    slots = m.get("slotMap") or st.get("slotMap") or []
    sb = int(m.get("streamBytes") or 0)
    und = int(stream.get("underruns") or 0)
    reads = m.get("readCount")
    rej = m.get("playRejectCount")
    inv = None
    if isinstance(reads, (int, float)) and isinstance(rej, (int, float)):
        inv = int(reads) - int(rej)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id or None,
        "wall_iso": wall_iso,
        "mono_s": mono,
        "esp_uptime": st.get("uptime"),
        "esp_uptime_ms": st.get("uptimeMs"),
        "resetReason": st.get("resetReason"),
        "resetReasonCode": st.get("resetReasonCode"),
        "version": st.get("version"),
        "serial": m.get("usbSerial"),
        "otgUp": st.get("otgUp"),
        "plugged": m.get("plugged"),
        "plugCount": m.get("plugCount"),
        "unplugCount": m.get("unplugCount"),
        "playingUid": st.get("playingUid") or "",
        "playingName": st.get("playingName") or "",
        "phase": m.get("phase"),
        "readCount": reads,
        "transportEpoch": m.get("transportEpoch"),
        "botResetObservable": m.get("botResetObservable"),
        "bytesFile": m.get("bytesFile"),
        "bytesDir": m.get("bytesDir"),
        "bytesFat": m.get("bytesFat"),
        "bytesMeta": m.get("bytesMeta"),
        "bytesBoot": m.get("bytesBoot"),
        "bytesRead": m.get("bytesRead"),
        "prefetchHits": m.get("prefetchHits"),
        "msSincePlug": m.get("msSincePlug"),
        "msPlugToFirstRead": m.get("msPlugToFirstRead"),
        "msPlugToPlayGuess": m.get("msPlugToPlayGuess"),
        "streamBytes": sb,
        "underruns": und,
        "liveBytes": max(0, sb - und),
        "hostAbs": stream.get("hostAbsCursor"),
        "absBase": stream.get("absBase"),
        "absEnd": stream.get("absEnd"),
        "cursorArmed": stream.get("cursorArmed"),
        "stream_active": stream.get("active"),
        "stream_uid": stream.get("uid"),
        "stream_size": stream.get("size"),
        "id3Len": stream.get("id3Len"),
        "hasCover": stream.get("hasCover"),
        "headResyncs": stream.get("headResyncs"),
        "pumpTcpUp": st.get("pumpTcpUp"),
        "pumpTcpPeer": st.get("pumpTcpPeer") or "",
        "guess": m.get("playGuessCount"),
        "rej": rej,
        "reads_minus_rej": inv,
        "cold": m.get("coldBodyBurstCount"),
        "slotMap": slot_progress(slots),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="1 Hz ESP status poll (wall clock)")
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--out", required=True, help="output JSONL path")
    ap.add_argument("--run-id", default="", help="optional run_id for ingest")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument(
        "--append",
        action="store_true",
        help="append to existing JSONL instead of overwriting (field multi-segment)",
    )
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    t_end = time.monotonic() + max(0.0, args.seconds)
    n = 0
    mode = "a" if args.append else "w"
    with out.open(mode, encoding="utf-8") as f:
        while time.monotonic() < t_end:
            wall = datetime.now().astimezone().isoformat(timespec="milliseconds")
            mono = time.monotonic()
            try:
                st = http_json(f"{esp}/api/status")
                row = row_from_status(st, wall, mono, run_id=args.run_id)
            except Exception as e:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": args.run_id or None,
                    "wall_iso": wall,
                    "mono_s": mono,
                    "error": str(e),
                }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if args.do_print:
                if "error" in row:
                    print(row["wall_iso"], "ERR", row["error"], flush=True)
                else:
                    slots = row.get("slotMap") or []
                    mid = sum(int(s.get("midFile") or 0) for s in slots)
                    head = sum(int(s.get("fromHead") or 0) for s in slots)
                    print(
                        row["wall_iso"],
                        "play",
                        repr(row.get("playingName") or "-"),
                        "guess",
                        row.get("guess"),
                        "pref",
                        row.get("prefetchHits"),
                        "bf",
                        row.get("bytesFile"),
                        "mid",
                        mid,
                        "head",
                        head,
                        "rc",
                        row.get("readCount"),
                        "inv",
                        row.get("reads_minus_rej"),
                        flush=True,
                    )
            # pace
            sleep = args.interval - (time.monotonic() - mono)
            if sleep > 0:
                time.sleep(sleep)

    print(f"DONE n={n} out={out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
