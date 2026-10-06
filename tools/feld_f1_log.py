#!/usr/bin/env python3
"""F1 field helper: poll slot progress + log t_sel / t_timer / t_eof with wall clock.

Keys (stdin, single char + Enter, or raw if tty):
  s  = t_sel   (track selected)
  t  = t_timer (HU playtime shows 0:01)
  e  = t_eof   (slot bytes stopped rising / EOF)
  n  = note    (prompt for free text)
  q  = quit

Example:
  python3 tools/feld_f1_log.py --esp http://192.168.178.89 \\
      --out docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/f1-events.jsonl --uid fav0
"""
from __future__ import annotations

import argparse
import json
import select
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def http_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wall_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def slot_b(st: dict, uid: str) -> tuple[int | None, int | None, int | None]:
    m = st.get("msc") or {}
    for s in m.get("slotMap") or []:
        if isinstance(s, dict) and s.get("uid") == uid:
            b = s.get("b")
            if b is None:
                b = s.get("bytes")
            return (
                int(b) if b is not None else None,
                int(s["maxSeq"]) if s.get("maxSeq") is not None else None,
                int(s["lba0"]) if s.get("lba0") is not None else None,
            )
    return None, None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="F1 timer event logger + slot poll")
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--out", required=True)
    ap.add_argument("--uid", default="fav0", help="slot to watch (fav0=8MiB Silence)")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--expect-bytes", type=int, default=8 * 1024 * 1024, help="EOF hint threshold")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    esp = args.esp.rstrip("/")
    events: list[dict] = []
    marks: dict[str, str] = {}

    print(
        f"F1 log → {out}\n"
        f"Watch uid={args.uid} expect≥{args.expect_bytes} B\n"
        "Keys: s=t_sel  t=t_timer  e=t_eof  n=note  q=quit\n"
        "Bridge für F1 stoppen. Video auf Spielzeit-Zähler.\n",
        flush=True,
    )

    def emit(kind: str, **extra: object) -> None:
        row = {"wall_iso": wall_now(), "kind": kind, "uid": args.uid, **extra}
        events.append(row)
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("EVENT", row, flush=True)
        if kind in ("t_sel", "t_timer", "t_eof"):
            marks[kind] = row["wall_iso"]

    last_b: int | None = None
    flat = 0
    try:
        while True:
            wall = wall_now()
            try:
                st = http_json(f"{esp}/api/status")
                b, mx, _ = slot_b(st, args.uid)
                m = st.get("msc") or {}
                rc = m.get("readCount")
                play = st.get("playingUid") or ""
                line = (
                    f"{wall} play={play!r} {args.uid}.b={b} maxSeq={mx} "
                    f"rc={rc} host={ (m.get('stream') or {}).get('hostAbsCursor') }"
                )
                if b is not None and last_b is not None:
                    if b == last_b:
                        flat += 1
                    else:
                        flat = 0
                    if b >= args.expect_bytes and flat >= 2 and "t_eof" not in marks:
                        print("HINT: bytes flat at/above expect — press e for t_eof?", flush=True)
                last_b = b
                print(line, flush=True)
            except Exception as e:
                print(wall, "ERR", e, flush=True)

            # non-blocking key
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                raw = sys.stdin.readline().strip().lower()
                if not raw:
                    continue
                cmd = raw[0]
                if cmd == "s":
                    emit("t_sel", slot_b=last_b)
                elif cmd == "t":
                    emit("t_timer", slot_b=last_b)
                elif cmd == "e":
                    emit("t_eof", slot_b=last_b)
                elif cmd == "n":
                    note = raw[1:].strip() or input("note> ").strip()
                    emit("note", text=note, slot_b=last_b)
                elif cmd == "q":
                    break
                else:
                    print("unknown key", raw, flush=True)

            # verdict if all three present
            if {"t_sel", "t_timer", "t_eof"} <= set(marks.keys()):
                # parse rough seconds from iso is messy; store mono deltas via wall strings only
                summary = {
                    "wall_iso": wall_now(),
                    "kind": "f1_summary",
                    "uid": args.uid,
                    "t_sel": marks["t_sel"],
                    "t_timer": marks["t_timer"],
                    "t_eof": marks["t_eof"],
                    "hint": "inkrementell if t_timer << t_eof; after_eof if t_timer ≈ t_eof",
                }
                with out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(summary, ensure_ascii=False) + "\n")
                print("SUMMARY", summary, flush=True)
                print("Paste observations into run.yaml; then continue F2 or quit (q).", flush=True)
                marks.clear()  # allow repeat

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)

    # yaml snippet for operator
    snippet = out.with_suffix(".yaml-snippet")
    lines = ["# paste into run.yaml observations/actions:", "observations:"]
    for ev in events:
        if ev["kind"] in ("t_sel", "t_timer", "t_eof", "note"):
            lines.append(
                f'  - {{t: "{ev["wall_iso"]}", what: "{ev["kind"]}", '
                f'uid: "{args.uid}", note: "{ev.get("text") or ev.get("slot_b")}"}}'
            )
    snippet.write_text("\n".join(lines) + "\n")
    print(f"Wrote {snippet}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
