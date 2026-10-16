#!/usr/bin/env python3
"""Safe F0 soft-cycle matrix orchestrator.

The orchestrator uses only ESP software operations.  A physical replug can be
recorded as an operator marker, but is never initiated or required by this tool.
Use ``--dry-run`` to exercise the complete artifact/report path without hardware.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from feld_status_poll import row_from_status
from lab_d_campaign import identity_diffs, identity_values, next_volume_label, slim_status

SCHEMA_VERSION = 1
IDENTITY_FIELDS = ("usbSerial", "productRevision", "bpbVolumeId", "bpbLabel", "rootLabel")
EXPECTED_IDENTITY_CHANGES = {
    "soft-usb": [],
    "media-hide": [],
    "serial": ["productRevision", "usbSerial"],
    "label": ["bpbLabel", "rootLabel"],
    "volume-id": ["bpbVolumeId"],
}
MATRIX = tuple(EXPECTED_IDENTITY_CHANGES)
HARD_STOP_REASONS = {
    "panic",
    "uptime-rollback",
    "freeze-violation",
    "not-quiet",
    "identity-drift",
    "preflight-failed",
    "operation-failed",
    "capture-incomplete",
}
CAPTURE_MODES = ("ram_local", "ram_wifi_off")
PROFILES = {
    "auto": {"settle_s": 0.5, "poll_interval_s": 0.25, "polls": 3, "cycle_ms": 600},
    "lab": {"settle_s": 2.0, "poll_interval_s": 0.5, "polls": 8, "cycle_ms": 900},
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def stream_from(status: dict) -> dict:
    msc = status.get("msc") or {}
    return msc.get("stream") or status.get("stream") or {}


def stall_enabled(status: dict) -> bool:
    """Conservative Freeze gate: any explicitly enabled stall representation is unsafe."""
    msc = status.get("msc") or {}
    candidates = (
        status.get("stallEnable"),
        (status.get("config") or {}).get("stallEnable"),
        (msc.get("stall") or {}).get("enabled"),
        (msc.get("stall") or {}).get("enable"),
    )
    return any(value is True or str(value).lower() in {"1", "true", "on", "enabled"} for value in candidates)


def panic_reason(status: dict) -> str | None:
    reason = str(status.get("resetReason") or "").lower()
    if "panic" in reason or "brownout" in reason or "watchdog" in reason or "wdt" in reason:
        return reason
    return None


def uptime_ms(status: dict) -> int | None:
    value = status.get("uptimeMs")
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def panic_gate(before: dict, after: dict) -> dict[str, Any]:
    before_up, after_up = uptime_ms(before), uptime_ms(after)
    reason = panic_reason(after)
    rollback = before_up is not None and after_up is not None and after_up < before_up
    reset_changed = (
        before.get("resetReasonCode") is not None
        and after.get("resetReasonCode") is not None
        and before.get("resetReasonCode") != after.get("resetReasonCode")
    )
    ok = not reason and not rollback and not reset_changed
    return {
        "ok": ok,
        "panic_reason": reason,
        "uptime_rollback": rollback,
        "reset_reason_changed": reset_changed,
        "before_uptime_ms": before_up,
        "after_uptime_ms": after_up,
    }


def quiet_gate(status: dict) -> dict[str, Any]:
    stream = stream_from(status)
    phase = str((status.get("msc") or {}).get("phase") or "").lower()
    active = bool(stream.get("active"))
    # Lab hosts often re-index after soft-usb/remount and leave phase=play|scan
    # without an armed stream — that is still "quiet" for the next cell.
    ok_phases = {"", "quiet", "idle", "index", "settle", "scan", "play"}
    return {
        "ok": not active and phase in ok_phases,
        "stream_active": active,
        "phase": phase or "unspecified",
    }


def preflight_gate(status: dict, expected_version: str = "") -> dict[str, Any]:
    version = str(status.get("version") or "")
    return {
        "ok": bool(status) and bool(status.get("otgUp")) and not stall_enabled(status)
        and (not expected_version or expected_version in version),
        "otg_up": bool(status.get("otgUp")),
        "stall_frozen": not stall_enabled(status),
        "version": version,
        "version_matches": not expected_version or expected_version in version,
        "panic_at_start": panic_reason(status),
    }


def slot_counters(status: dict) -> tuple[int, int]:
    slots = (status.get("msc") or {}).get("slotMap") or status.get("slotMap") or []
    body_bytes = sum(int(item.get("bytes") or item.get("b") or 0) for item in slots if isinstance(item, dict))
    max_seq = max(
        (int(item.get("maxSeq") or 0) for item in slots if isinstance(item, dict)),
        default=0,
    )
    return body_bytes, max_seq


def classify_outcome(before: dict, after: dict, panic: dict | None = None) -> dict[str, Any]:
    """Classify A-E independently from the A/B episode labels.

    A = Head/LIVE, B = Mid/body read, C = no relevant new read/cache,
    D = transport reset/panic, E = ambiguous/incomplete evidence.
    """
    panic = panic or panic_gate(before, after)
    if not panic.get("ok"):
        return {"code": "D", "name": "transport-reset", "evidence": panic}
    bm, bx = slot_counters(before)
    am, ax = slot_counters(after)
    msc_before, msc_after = before.get("msc") or {}, after.get("msc") or {}
    read_delta = int(msc_after.get("readCount") or 0) - int(msc_before.get("readCount") or 0)
    stream = stream_from(after)
    playing = after.get("playingUid") or stream.get("uid")
    live = bool(stream.get("active") and playing) or int(stream.get("absEnd") or 0) > int(
        stream.get("absBase") or 0
    )
    head = ax > bx and ax <= 12 * 512
    evidence = {
        "read_delta": read_delta,
        "slot_bytes_delta": am - bm,
        "max_seq_before": bx,
        "max_seq_after": ax,
        "playing_uid": playing,
        "stream_active": bool(stream.get("active")),
        "live": live,
    }
    if live and (head or read_delta > 0 or am > bm):
        return {"code": "A", "name": "head-live", "evidence": evidence}
    if read_delta > 0 or am > bm:
        return {"code": "B", "name": "mid-body-read", "evidence": evidence}
    if read_delta == 0 and am == bm:
        return {"code": "C", "name": "cache-no-read", "evidence": evidence}
    return {"code": "E", "name": "indeterminate", "evidence": evidence}


def identity_gate(cell: str, before: dict, after: dict) -> dict[str, Any]:
    b, a = identity_values(before), identity_values(after)
    changed = identity_diffs(b, a)
    expected = EXPECTED_IDENTITY_CHANGES[cell]
    return {
        "ok": changed == expected,
        "before": b,
        "after": a,
        "changed_fields": changed,
        "expected_changed_fields": expected,
    }


def _capture_value(payloads: list[dict], key: str) -> Any:
    """Read a health field from the newest top-level or nested capture object."""
    for payload in reversed(payloads):
        if not isinstance(payload, dict):
            continue
        candidates = [
            payload,
            payload.get("capture"),
            payload.get("health"),
            payload.get("offline"),
            payload.get("mess"),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict) and key in candidate:
                return candidate[key]
    return None


def capture_health(payloads: list[dict], expected_mode: str) -> dict[str, Any]:
    complete = _capture_value(payloads, "complete")
    overflow = _capture_value(payloads, "overflow")
    cmd_capture = _capture_value(payloads, "cmdCapture")
    mode = _capture_value(payloads, "mode")
    try:
        overflow_n = int(overflow)
    except (TypeError, ValueError):
        overflow_n = None
    return {
        "ok": complete is True and overflow_n == 0 and cmd_capture is True
        and (mode in (None, expected_mode)),
        "complete": complete,
        "overflow": overflow_n,
        "cmdCapture": cmd_capture,
        "mode": mode,
        "expected_mode": expected_mode,
    }


def command_seq(command: dict) -> int | None:
    for key in ("seq", "sequence", "id"):
        try:
            if command.get(key) is not None:
                return int(command[key])
        except (TypeError, ValueError):
            pass
    return None


class HttpClient:
    def __init__(self, base: str, timeout: float = 8.0):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}

    def status(self) -> dict:
        return self.request("GET", "/api/status")


class DryRunClient:
    """Deterministic hardware-free ESP model used by tests and operator rehearsal."""

    def __init__(
        self,
        *,
        capture_complete: bool = True,
        capture_overflow: int = 0,
        capture_page_size: int = 2,
    ) -> None:
        self.serial_n = 100
        self.capture_complete = capture_complete
        self.capture_overflow = capture_overflow
        self.capture_page_size = max(1, capture_page_size)
        self.capture_active = False
        self.capture_mode = "ram_local"
        self.capture_commands: list[dict[str, Any]] = []
        self.request_log: list[dict[str, Any]] = []
        self._capture_seq = 0
        self.status_value: dict[str, Any] = {
            "ok": True,
            "version": "0.4.52-dry-run",
            "uptimeMs": 100_000,
            "uptime": 100,
            "resetReason": "poweron",
            "resetReasonCode": 1,
            "otgUp": True,
            "playingUid": "",
            "stallEnable": False,
            "msc": {
                "phase": "quiet",
                "usbSerial": "PD0100",
                "productRevision": "0100",
                "bpbVolumeId": 0x12345678,
                "bpbLabel": "PIDRIVE",
                "rootLabel": "PIDRIVE",
                "readCount": 0,
                "slotMap": [{"uid": "fav0", "bytes": 0, "maxSeq": 0, "lba0": 81}],
                "stream": {"active": False, "absBase": 0, "absEnd": 0, "hostAbsCursor": 0},
                "stall": {"enabled": False},
            },
            "ports": {"otg": {"softUsbAttached": True}},
        }

    def status(self) -> dict:
        self.status_value["uptimeMs"] += 50
        return json.loads(json.dumps(self.status_value))

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        body = body or {}
        self.request_log.append({"method": method, "path": path, "body": body})
        if method == "GET" and path.startswith("/api/lab/mess?"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            after = int((query.get("after") or ["0"])[0])
            remaining = [
                command for command in self.capture_commands
                if int(command.get("seq") or 0) > after
            ]
            page = remaining[: self.capture_page_size]
            next_seq = int(page[-1]["seq"]) if page else after
            return {
                "ok": True,
                "cmdCapture": True,
                "capture": {
                    "mode": self.capture_mode,
                    "complete": self.capture_complete and not self.capture_active,
                    "overflow": self.capture_overflow,
                },
                "cmds": json.loads(json.dumps(page)),
                "nextSeq": next_seq,
                "hasMore": len(remaining) > len(page),
            }
        if path == "/api/lab/mess":
            operation = body.get("capture") or body.get("action")
            if operation == "start":
                if body.get("reset", False):
                    self.capture_commands.clear()
                    self._capture_seq = 0
                self.capture_mode = str(body.get("mode") or "ram_local")
                self.capture_active = True
                return {
                    "ok": True,
                    "cmdCapture": True,
                    "capture": {
                        "active": True,
                        "mode": self.capture_mode,
                        "complete": False,
                        "overflow": 0,
                    },
                }
            if operation == "stop" or body.get("stop") is True:
                self.capture_active = False
                return {
                    "ok": True,
                    "cmdCapture": True,
                    "capture": {
                        "active": False,
                        "mode": self.capture_mode,
                        "complete": self.capture_complete,
                        "overflow": self.capture_overflow,
                    },
                }
        if path in {"/api/lab/stop", "/api/session/stop"}:
            self.status_value["msc"]["stream"]["active"] = False
            self.status_value["msc"]["phase"] = "quiet"
        elif path == "/api/config":
            self.status_value["msc"]["bpbLabel"] = str(body.get("volumeLabel"))[:11]
            self.status_value["msc"]["rootLabel"] = str(body.get("volumeLabel"))[:11]
            self.status_value["msc"]["bpbVolumeId"] = int(body.get("fatVolumeId"))
        elif path == "/api/lab/remount" and not body.get("keepIdentity", False):
            self.serial_n += 1
            self.status_value["msc"]["usbSerial"] = f"PD{self.serial_n:04d}"
            self.status_value["msc"]["productRevision"] = f"{self.serial_n:04d}"
        elif path == "/api/lab/usb":
            self.status_value["ports"]["otg"]["softUsbAttached"] = True
        if self.capture_active and path != "/api/lab/mess":
            self._capture_seq += 1
            self.capture_commands.append(
                {
                    "seq": self._capture_seq,
                    "op": 0x28,
                    "blocks": 8,
                    "bytes": 4096,
                    "endpoint": path,
                }
            )
        return {"ok": True}


@dataclass
class RunClock:
    wall_start: str
    mono_start: float
    uptime_start_ms: int | None

    @classmethod
    def start(cls, status: dict | None = None) -> "RunClock":
        return cls(utc_now(), time.monotonic(), uptime_ms(status or {}))

    def stamp(self, status: dict | None = None) -> dict[str, Any]:
        return {
            "wall": utc_now(),
            "mono_s": round(time.monotonic() - self.mono_start, 6),
            "esp_uptime_ms": uptime_ms(status or {}),
            "esp_uptime_start_ms": self.uptime_start_ms,
        }


class Orchestrator:
    def __init__(self, args: argparse.Namespace, client: HttpClient | DryRunClient):
        self.args = args
        self.client = client
        self.out: Path = args.out
        self.out.mkdir(parents=True, exist_ok=True)
        first = client.status()
        self.clock = RunClock.start(first)
        self.run_id = args.run_id or f"soft-cycle-{uuid.uuid4().hex[:10]}"
        self.events = self.out / "events.jsonl"
        self.marks = self.out / "marks.jsonl"
        self.polls = self.out / "status-poll.jsonl"
        for path in (self.events, self.marks, self.polls):
            path.touch()
        self.cells: list[dict[str, Any]] = []
        self.hard_stop: str | None = None
        self.first_status = first
        self.last_status = first

    def timed(self, status: dict | None = None) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "run_id": self.run_id, **self.clock.stamp(status)}

    def event(self, name: str, status: dict | None = None, **data: Any) -> None:
        append_jsonl(self.events, {**self.timed(status), "event": name, **data})

    def mark(self, label: str, kind: str = "operator") -> None:
        append_jsonl(self.marks, {**self.timed(), "kind": kind, "label": label})

    def poll(self, status: dict, episode: str, cell: str) -> None:
        row = row_from_status(
            status,
            self.clock.stamp(status)["wall"],
            self.clock.stamp(status)["mono_s"],
            self.run_id,
        )
        row.update({"episode": episode, "cell": cell, "esp_uptime_start_ms": self.clock.uptime_start_ms})
        append_jsonl(self.polls, row)

    def snapshot(self, cell_dir: Path, episode: str, status: dict) -> None:
        self.last_status = status
        payload = {**self.timed(status), "episode": episode, "status": status}
        write_json(cell_dir / f"{episode.lower()}-snapshot.json", payload)
        write_json(
            cell_dir / ("before-snapshot.json" if episode == "A" else "after-snapshot.json"),
            payload,
        )
        self.poll(status, episode, cell_dir.name)

    def stop(self, reason: str, **data: Any) -> None:
        self.hard_stop = reason
        self.event("hard-stop", reason=reason, **data)

    def ensure_quiet(self) -> tuple[dict, dict]:
        self.client.request("POST", "/api/lab/stop", {})
        deadline = time.monotonic() + max(0.1, self.args.quiet_timeout_s)
        status = self.client.status()
        gate = quiet_gate(status)
        while not gate["ok"] and time.monotonic() < deadline:
            time.sleep(0.1)
            status = self.client.status()
            gate = quiet_gate(status)
        return status, gate

    def action(self, cell: str, before: dict) -> dict[str, Any]:
        msc = before.get("msc") or {}
        label = str(msc.get("bpbLabel") or "PIDRIVE")[:11]
        volume_id = int(msc.get("bpbVolumeId") or 1)
        if cell == "soft-usb":
            body = {"cycleMs": self.args.cycle_ms}
            self.client.request("POST", "/api/lab/usb", body)
            return {"endpoint": "/api/lab/usb", "body": body, "hardware": False}
        if cell == "media-hide":
            body = {"keepIdentity": True, "volumeLabel": label, "fatVolumeId": volume_id}
            self.client.request("POST", "/api/lab/remount", body)
            return {"endpoint": "/api/lab/remount", "body": body, "hardware": False}
        target_label = next_volume_label(label) if cell == "label" else label
        target_id = ((volume_id ^ 1) or 1) if cell == "volume-id" else volume_id
        if cell in {"label", "volume-id"}:
            self.client.request(
                "POST", "/api/config", {"volumeLabel": target_label, "fatVolumeId": target_id}
            )
        body = {
            "keepIdentity": cell != "serial",
            "volumeLabel": target_label,
            "fatVolumeId": target_id,
        }
        self.client.request("POST", "/api/lab/remount", body)
        return {"endpoint": "/api/lab/remount", "body": body, "hardware": False}

    def start_capture(self, cell: str) -> dict[str, Any]:
        body = {
            "capture": "start",
            "enable": True,
            "mode": self.args.capture_mode,
            "reset": True,
            "mark": f"{self.run_id}:{cell}:before-soft-action",
        }
        response = self.client.request("POST", "/api/lab/mess", body)
        if response.get("ok") is False:
            raise RuntimeError(f"capture start rejected: {response}")
        self.event("capture.start", cell=cell, mode=self.args.capture_mode)
        return response

    def export_capture(self) -> tuple[list[dict], list[dict], list[dict]]:
        commands: list[dict] = []
        pages: list[dict] = []
        responses: list[dict] = []
        after = 0
        seen_cursors = {after}
        for page_number in range(1, self.args.capture_max_pages + 1):
            response = self.client.request("GET", f"/api/lab/mess?after={after}")
            if response.get("ok") is False:
                raise RuntimeError(f"capture page rejected after={after}: {response}")
            responses.append(response)
            page_commands = response.get("cmds")
            if page_commands is None:
                page_commands = response.get("commands") or []
            if not isinstance(page_commands, list):
                raise RuntimeError("capture page commands are not a list")
            commands.extend(command for command in page_commands if isinstance(command, dict))
            seqs = [seq for seq in (command_seq(command) for command in page_commands) if seq is not None]
            advertised = response.get(
                "nextAfter", response.get("nextSeq", response.get("next"))
            )
            try:
                next_after = int(advertised) if advertised is not None else (max(seqs) if seqs else after)
            except (TypeError, ValueError):
                next_after = max(seqs) if seqs else after
            has_more = response.get("hasMore", response.get("more"))
            if isinstance(has_more, str):
                has_more = has_more.lower() in {"1", "true", "yes"}
            pages.append(
                {
                    "page": page_number,
                    "after": after,
                    "commands": len(page_commands),
                    "next_after": next_after,
                    "has_more": has_more,
                }
            )
            if has_more is False or (not page_commands and not has_more):
                break
            if next_after <= after or next_after in seen_cursors:
                raise RuntimeError(f"capture pagination made no progress after={after}")
            after = next_after
            seen_cursors.add(after)
        else:
            raise RuntimeError(f"capture pagination exceeded {self.args.capture_max_pages} pages")
        return commands, pages, responses

    def finish_capture(
        self, cell: str, cell_dir: Path, start_response: dict
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payloads = [start_response]
        commands: list[dict] = []
        pages: list[dict] = []
        error: str | None = None
        try:
            stop_response = self.client.request(
                "POST",
                "/api/lab/mess",
                {
                    "stop": True,
                    "reason": "cell_end",
                    "mark": f"{self.run_id}:{cell}:after-window",
                },
            )
            payloads.append(stop_response)
            commands, pages, page_responses = self.export_capture()
            payloads.extend(page_responses)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        health = capture_health(payloads, self.args.capture_mode)
        if error:
            health["ok"] = False
            health["error"] = error
        seqs = [seq for seq in (command_seq(command) for command in commands) if seq is not None]
        trace = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "cell": cell,
            "capture_mode": self.args.capture_mode,
            "command_count": len(commands),
            "first_seq": min(seqs) if seqs else None,
            "last_seq": max(seqs) if seqs else None,
            "pages": pages,
            "commands": commands,
            "capture_health": health,
        }
        write_json(cell_dir / "offline-bot-trace.json", trace)
        self.event(
            "capture.stop",
            cell=cell,
            complete=health.get("complete"),
            overflow=health.get("overflow"),
            healthy=health["ok"],
            commands=len(commands),
        )
        return health, trace

    def run_cell(self, cell: str) -> dict[str, Any]:
        cell_dir = self.out / cell
        cell_dir.mkdir(exist_ok=True)
        self.event("cell.begin", cell=cell)
        before, quiet = self.ensure_quiet()
        self.snapshot(cell_dir, "A", before)
        if not quiet["ok"]:
            report = {"cell": cell, "episodes": {"A": {"status": before}, "B": None}, "quiet_gate": quiet}
            report.update({"valid": False, "hard_stop": "not-quiet", "outcome": {"code": "E", "name": "not-quiet"}})
            write_json(cell_dir / "CELL-REPORT.json", report)
            self.stop("not-quiet", cell=cell)
            return report
        if stall_enabled(before):
            self.stop("freeze-violation", cell=cell)
            report = {"cell": cell, "valid": False, "hard_stop": "freeze-violation"}
            write_json(cell_dir / "CELL-REPORT.json", report)
            return report
        capture_start = self.start_capture(cell)
        action: dict[str, Any] | None = None
        operation_error: str | None = None
        samples: list[dict] = []
        try:
            action = self.action(cell, before)
            self.event("cell.action", cell=cell, action=action)
            if not self.args.dry_run:
                time.sleep(self.args.settle_s)
            for _ in range(self.args.polls):
                status = self.client.status()
                samples.append(status)
                self.poll(status, "B", cell)
                if not self.args.dry_run:
                    time.sleep(self.args.poll_interval_s)
        except Exception as exc:
            operation_error = f"{type(exc).__name__}: {exc}"
        capture, trace = self.finish_capture(cell, cell_dir, capture_start)
        after = samples[-1] if samples else self.client.status()
        self.snapshot(cell_dir, "B", after)
        panic = panic_gate(before, after)
        identity = identity_gate(cell, before, after)
        outcome = classify_outcome(before, after, panic)
        valid = bool(
            capture["ok"]
            and operation_error is None
            and panic["ok"]
            and identity["ok"]
            and not stall_enabled(after)
        )
        reason = None
        if not capture["ok"]:
            reason = "capture-incomplete"
        elif operation_error:
            reason = "operation-failed"
        elif not panic["ok"]:
            reason = "panic" if panic.get("panic_reason") else "uptime-rollback"
        elif stall_enabled(after):
            reason = "freeze-violation"
        elif not identity["ok"]:
            reason = "identity-drift"
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "cell": cell,
            "operation": action,
            "operation_error": operation_error,
            "capture_mode": self.args.capture_mode,
            "capture_health": capture,
            "capture_artifact": "offline-bot-trace.json",
            "capture_commands": trace["command_count"],
            "capture_pages": len(trace["pages"]),
            "episodes": {
                "A": {"meaning": "before-soft-cycle", "identity": identity_values(before)},
                "B": {"meaning": "after-soft-cycle", "identity": identity_values(after)},
            },
            "quiet_gate": quiet,
            "panic_gate": panic,
            "freeze_gate": {"ok": not stall_enabled(after), "stall_enabled": stall_enabled(after)},
            "identity_gate": identity,
            "outcome": outcome,
            "valid": valid,
            "hard_stop": reason,
            "finished": self.clock.stamp(after),
        }
        write_json(cell_dir / "CELL-REPORT.json", report)
        self.event("cell.end", after, cell=cell, valid=valid, outcome=outcome["code"])
        if reason:
            self.stop(reason, cell=cell)
        return report

    def write_initial_artifacts(self, preflight: dict) -> None:
        repo = Path(__file__).resolve().parents[1]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "started": self.clock.stamp(self.first_status),
            "host": {"node": platform.node(), "platform": platform.platform(), "python": sys.version},
            "git_head": git_head(repo),
            "dry_run": self.args.dry_run,
            "profile": self.args.profile,
            "capture_mode": self.args.capture_mode,
            "live_audio": self.args.live_audio,
            "matrix": list(self.args.cells),
            "preflight": preflight,
            "physical_replug": "never automated; optional operator marker only",
        }
        write_json(self.out / "run-manifest.json", manifest)
        lines = [
            "# Generated by tools/soft_cycle_orchestrator.py",
            f"run_id: {json.dumps(self.run_id)}",
            f"profile: {self.args.profile}",
            f"dry_run: {str(self.args.dry_run).lower()}",
            f"capture_mode: {self.args.capture_mode}",
            f"live_audio: {str(self.args.live_audio).lower()}",
            f"started_wall: {json.dumps(self.clock.wall_start)}",
            f"started_mono: {self.clock.mono_start}",
            f"esp_uptime_start_ms: {json.dumps(self.clock.uptime_start_ms)}",
            "hardware:",
            "  extra: false",
            "  physical_replug: false",
            "matrix:",
            *[f"  - {cell}" for cell in self.args.cells],
            "",
        ]
        (self.out / "run.yaml").write_text("\n".join(lines), encoding="utf-8")

    def finish(self) -> int:
        outcomes = {cell["cell"]: cell.get("outcome", {}).get("code") for cell in self.cells}
        valid = all(cell.get("valid") for cell in self.cells) and len(self.cells) == len(self.args.cells)
        summary = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "pass": valid and self.hard_stop is None,
            "hard_stop": self.hard_stop,
            "cells_completed": len(self.cells),
            "cells_requested": list(self.args.cells),
            "outcomes": outcomes,
            "dry_run": self.args.dry_run,
            "finished": self.clock.stamp(self.last_status),
        }
        write_json(self.out / "CELL-REPORT.json", {"run_id": self.run_id, "cells": self.cells})
        write_json(self.out / "SUMMARY.json", summary)
        rows = [
            "# Soft-Cycle-Orchestrator Ergebnis",
            "",
            f"- Run: `{self.run_id}`",
            f"- Profil: `{self.args.profile}` · Dry-run: `{self.args.dry_run}`",
            f"- Ergebnis: **{'PASS' if summary['pass'] else 'HARD STOP / FAIL'}**",
            f"- Hard stop: `{self.hard_stop or 'none'}`",
            "",
            "## Zellen",
            "",
        ]
        for report in self.cells:
            rows.append(
                f"- `{report['cell']}`: valid={report.get('valid')} · "
                f"Outcome {report.get('outcome', {}).get('code', 'E')} "
                f"({report.get('outcome', {}).get('name', 'incomplete')})"
            )
        rows.extend(
            [
                "",
                "Episode A (vor Aktion) und Episode B (danach) sind getrennt gespeichert.",
                "Outcome A–E ist die davon unabhängige Beobachtungsklassifikation.",
                "Kein physischer Replug und keine Zusatzhardware wurden automatisiert.",
                "",
            ]
        )
        (self.out / "ERGEBNIS.md").write_text("\n".join(rows), encoding="utf-8")
        return 0 if summary["pass"] else 2

    def run(self) -> int:
        preflight = preflight_gate(self.first_status, self.args.require_version)
        self.write_initial_artifacts(preflight)
        self.event("run.begin", self.first_status, profile=self.args.profile, dry_run=self.args.dry_run)
        if self.args.physical_replug_marker:
            self.mark(self.args.physical_replug_marker, "manual-physical-replug")
        if not preflight["ok"] or preflight["panic_at_start"]:
            self.stop("preflight-failed", gate=preflight)
            return self.finish()
        for cell in self.args.cells:
            try:
                report = self.run_cell(cell)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                report = {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": self.run_id,
                    "cell": cell,
                    "valid": False,
                    "hard_stop": "operation-failed",
                    "error": error,
                    "outcome": {"code": "E", "name": "operation-failed"},
                }
                cell_dir = self.out / cell
                cell_dir.mkdir(exist_ok=True)
                write_json(cell_dir / "CELL-REPORT.json", report)
                self.stop("operation-failed", cell=cell, error=error)
            self.cells.append(report)
            if self.hard_stop:
                break
        self.event("run.end", hard_stop=self.hard_stop)
        return self.finish()


def parse_cells(value: str) -> tuple[str, ...]:
    cells = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    unknown = sorted(set(cells) - set(MATRIX))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown cells: {', '.join(unknown)}")
    if len(set(cells)) != len(cells):
        raise argparse.ArgumentTypeError("duplicate matrix cell")
    return cells


def default_out() -> Path:
    return Path("artifacts") / f"soft-cycle-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esp", default="http://192.168.178.89")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="auto")
    parser.add_argument("--cells", type=parse_cells, default=MATRIX)
    parser.add_argument("--dry-run", action="store_true", help="complete hardware-free rehearsal")
    parser.add_argument(
        "--capture-mode",
        choices=CAPTURE_MODES,
        default="ram_local",
        help="ram_local is the live-audio-safe default; ram_wifi_off is lab baseline only",
    )
    parser.add_argument(
        "--live-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="declare TCP live-audio use; required to reject incompatible ram_wifi_off",
    )
    parser.add_argument("--capture-max-pages", type=int, default=10000)
    parser.add_argument("--require-version", default="")
    parser.add_argument("--quiet-timeout-s", type=float, default=8.0)
    parser.add_argument(
        "--physical-replug-marker",
        default="",
        help="record a manual operator observation only; never controls hardware",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.capture_mode == "ram_wifi_off":
        if args.profile != "lab":
            parser.error("--capture-mode ram_wifi_off requires --profile lab")
        if args.live_audio:
            parser.error("--capture-mode ram_wifi_off requires --no-live-audio")
    if args.capture_max_pages < 1:
        parser.error("--capture-max-pages must be positive")
    args.out = args.out or default_out()
    profile = PROFILES[args.profile]
    for key, value in profile.items():
        setattr(args, key, value)
    client: HttpClient | DryRunClient = DryRunClient() if args.dry_run else HttpClient(args.esp)
    try:
        return Orchestrator(args, client).run()
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"soft-cycle error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
