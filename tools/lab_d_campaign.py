#!/usr/bin/env python3
"""D-Startgate lab campaign: preflight, S6/HU-A1 replay and identity gates.

The tool is intentionally Linux-hosted. It runs on the Proxmox/Debian machine
that owns the ESP OTG SG device; the Pi remains the TCP producer path.

Examples:
  python3 tools/lab_d_campaign.py preflight --sg /dev/sg0 --uart /dev/ttyACM0
  python3 tools/lab_d_campaign.py replay --selection head --sg /dev/sg0
  python3 tools/lab_d_campaign.py identity --dimension volume-id --device /dev/sdb
  python3 tools/lab_d_campaign.py --self-test

No command flashes firmware or transmits RF. Identity runs change exactly one
declared identity dimension and save the presented FAT sectors for verification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from lab_k3_volume_label import inspect_device
from nbt_hu_sim import (
    HuSim,
    PumpTcp,
    RealisticProducer,
    VirtualEar,
    arm_uid,
    load_profile,
    prep_lab,
    read_sg,
    snap_retry,
    wait_esp,
)

SCHEMA = 1
HEAD_SLOP_BYTES = 12 * 512
DEFAULT_PREFETCH_BYTES = 8_294_400  # S6 fav0: 98.88 % of 8 MiB


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 12) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode()) if raw else {}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def slim_status(status: dict) -> dict:
    msc = status.get("msc") or {}
    stream = msc.get("stream") or status.get("stream") or {}
    return {
        "version": status.get("version"),
        "uptime": status.get("uptime"),
        "uptimeMs": status.get("uptimeMs"),
        "resetReason": status.get("resetReason"),
        "resetReasonCode": status.get("resetReasonCode"),
        "mac": status.get("mac"),
        "otgUp": status.get("otgUp"),
        "uartUp": status.get("uartUp"),
        "uartState": status.get("uartState"),
        "pumpTcpUp": status.get("pumpTcpUp"),
        "pumpTcpPeer": status.get("pumpTcpPeer"),
        "playingUid": status.get("playingUid"),
        "usbSerial": msc.get("usbSerial"),
        "productRevision": msc.get("productRevision"),
        "remountGen": msc.get("remountGen"),
        "bpbVolumeId": msc.get("bpbVolumeId"),
        "bpbLabel": msc.get("bpbLabel"),
        "rootLabel": msc.get("rootLabel"),
        "readCount": msc.get("readCount"),
        "readOverflow": msc.get("readOverflow"),
        "readsEmit": msc.get("readsEmit"),
        "transportEpoch": msc.get("transportEpoch"),
        "botResetObservable": msc.get("botResetObservable"),
        "xfer": msc.get("xfer"),
        "stall": msc.get("stall"),
        "stream": {
            "uid": stream.get("uid"),
            "active": stream.get("active"),
            "cursorArmed": stream.get("cursorArmed"),
            "absBase": stream.get("absBase"),
            "absEnd": stream.get("absEnd"),
            "hostAbsCursor": stream.get("hostAbsCursor"),
            "underruns": stream.get("underruns"),
        },
        "slotMap": msc.get("slotMap") or [],
    }


def device_metadata(path: str) -> dict:
    p = Path(path)
    result: dict[str, Any] = {"path": path, "exists": p.exists()}
    if not p.exists():
        return result
    st = p.stat()
    result.update(
        {
            "mode": oct(st.st_mode),
            "major": os.major(st.st_rdev) if st.st_rdev else None,
            "minor": os.minor(st.st_rdev) if st.st_rdev else None,
            "resolved": str(p.resolve()),
        }
    )
    return result


def default_out(kind: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"docs/betrieb/artifacts-{dt.date.today().isoformat()}-lab/lab-d-{kind}-{stamp}")


class StatusPoller(threading.Thread):
    """Append-only status timeline with one monotonic origin for the entire run."""

    def __init__(self, esp: str, path: Path, run_id: str, t0: float, interval: float = 0.5):
        super().__init__(daemon=True)
        self.esp = esp.rstrip("/")
        self.path = path
        self.run_id = run_id
        self.t0 = t0
        self.interval = max(0.1, interval)
        self.stop_event = threading.Event()
        self.samples = 0
        self.errors = 0

    def run(self) -> None:
        with self.path.open("a", encoding="utf-8") as out:
            while not self.stop_event.is_set():
                started = time.monotonic()
                row: dict[str, Any] = {
                    "schema": SCHEMA,
                    "run_id": self.run_id,
                    "wall": utc_now(),
                    "mono_s": round(started - self.t0, 6),
                }
                try:
                    row["status"] = slim_status(http_json(f"{self.esp}/api/status", timeout=4))
                    self.samples += 1
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    self.errors += 1
                out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                out.flush()
                self.stop_event.wait(max(0.0, self.interval - (time.monotonic() - started)))

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=5)


class RunArtifacts:
    def __init__(self, out: Path, command: str, args: argparse.Namespace):
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.t0 = time.monotonic()
        self.run_id = f"{command}-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}"
        self.events_path = self.out / "events.jsonl"
        repo = Path(__file__).resolve().parents[1]
        self.manifest: dict[str, Any] = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "command": command,
            "started_utc": utc_now(),
            "host": {
                "node": platform.node(),
                "platform": platform.platform(),
                "python": sys.version,
            },
            "git_head": git_head(repo),
            "argv": sys.argv,
            "inputs": {
                key: str(value) if isinstance(value, Path) else value
                for key, value in vars(args).items()
                if key not in {"func"}
            },
        }
        self.write_manifest()
        self.write_run_yaml()

    def mark(self, event: str, **data: Any) -> None:
        row = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "wall": utc_now(),
            "mono_s": round(time.monotonic() - self.t0, 6),
            "event": event,
            **data,
        }
        with self.events_path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    def write_manifest(self) -> None:
        (self.out / "run-manifest.json").write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _yaml(value: Any) -> str:
        if value is None:
            return '""'
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=False)

    def write_run_yaml(self) -> None:
        """Write the canonical, ingest-friendly lab run manifest without PyYAML."""
        inputs = self.manifest.get("inputs") or {}
        result = self.manifest.get("result") or {}
        status = (
            result.get("status_initial")
            or result.get("status_before")
            or result.get("before")
            or {}
        )
        if isinstance(status, dict) and "msc" in status:
            status = slim_status(status)
        fw = status.get("version") if isinstance(status, dict) else None
        uptime_ms = status.get("uptimeMs") if isinstance(status, dict) else None
        has_status_poll = self.manifest.get("command") == "replay"
        lines = [
            "# Generated by tools/lab_d_campaign.py",
            f"run_id: {self._yaml(self.run_id)}",
            'stufe: "D-startgate"',
            "env: lab",
            f"fw: {self._yaml(fw)}",
            f"fw_commit: {self._yaml(self.manifest.get('git_head'))}",
            'build_env: "pidrive-s3-l3"',
            "geometry: L3",
            "counter_semantics: v3",
            f"command: {self._yaml(self.manifest.get('command'))}",
            f"started_utc: {self._yaml(self.manifest.get('started_utc'))}",
            f"finished_utc: {self._yaml(self.manifest.get('finished_utc'))}",
            "topology:",
            '  otg_host: "proxmox-debian"',
            '  producer: "pi-tcp"',
            f"  sg_device: {self._yaml(inputs.get('sg'))}",
            f"  block_device: {self._yaml(inputs.get('device'))}",
            f"  uart_device: {self._yaml(inputs.get('uart'))}",
            "  dtr_rts: false",
            "clock_sync:",
            f"  esp_uptime_ms: {self._yaml(uptime_ms)}",
            f"  wall: {self._yaml(self.manifest.get('started_utc'))}",
            "actions: []",
            "observations: []",
            'heard: "none"',
            "status_poll:",
            f"  interval_s: {self._yaml(inputs.get('poll_interval'))}",
            f"  out: {self._yaml('status-poll.jsonl' if has_status_poll else '')}",
            f"result_pass: {self._yaml(result.get('pass'))}",
            "",
        ]
        (self.out / "run.yaml").write_text("\n".join(lines), encoding="utf-8")

    def finish(self, result: dict) -> None:
        self.manifest["finished_utc"] = utc_now()
        self.manifest["duration_s"] = round(time.monotonic() - self.t0, 3)
        self.manifest["result"] = result
        self.write_manifest()
        self.write_run_yaml()


def capture_media(device: str, out: Path, prefix: str) -> dict:
    media, boot, root = inspect_device(device)
    (out / f"{prefix}-boot-sector.bin").write_bytes(boot)
    (out / f"{prefix}-root-directory.bin").write_bytes(root)
    report = {
        **media,
        "bootSha256": sha256(boot),
        "rootSha256": sha256(root),
    }
    (out / f"{prefix}-media.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def classify_selection(events: list[dict], uid: str, head_slop: int = HEAD_SLOP_BYTES) -> dict:
    reads = [event for event in events if event.get("op") == "read" and event.get("uid") == uid]
    if not reads:
        return {"class": "no-read", "reads": 0, "bytes": 0, "first_off": None, "classes": {}}
    offsets = [int(event["off"]) for event in reads if event.get("off") is not None]
    first_off = offsets[0] if offsets else None
    klasses: dict[str, int] = {}
    for event in reads:
        key = str(event.get("klass") or "UNKNOWN")
        klasses[key] = klasses.get(key, 0) + 1
    return {
        "class": "head" if first_off is not None and first_off <= head_slop else "mid",
        "reads": len(reads),
        "bytes": sum(int(event.get("n") or 0) for event in reads),
        "first_off": first_off,
        "min_off": min(offsets) if offsets else None,
        "max_off": max(offsets) if offsets else None,
        "classes": klasses,
    }


def run_preflight(args: argparse.Namespace) -> int:
    art = RunArtifacts(args.out or default_out("preflight"), "preflight", args)
    esp = args.esp.rstrip("/")
    result: dict[str, Any] = {
        "sg": device_metadata(args.sg),
        "uart": device_metadata(args.uart) if args.uart else {"path": None, "skipped": True},
        "warnings": [],
    }
    try:
        before = slim_status(http_json(f"{esp}/api/status"))
        result["status_before"] = before
        sg_fd = os.open(args.sg, os.O_RDONLY)
        try:
            _data, bot = read_sg(sg_fd, 0, 512, args.cmd_timeout_ms)
        finally:
            os.close(sg_fd)
        result["sg_read10"] = bot
        time.sleep(args.observe_s)
        after = slim_status(http_json(f"{esp}/api/status"))
        result["status_after"] = after
        result["same_usb_identity"] = before.get("usbSerial") == after.get("usbSerial")
        result["otg_stable"] = bool(before.get("otgUp") and after.get("otgUp"))
        up_before = before.get("uptimeMs")
        up_after = after.get("uptimeMs")
        result["no_reboot_observed"] = bool(
            up_before is not None and up_after is not None and int(up_after) >= int(up_before)
        )
        result["uart_reported_up"] = after.get("uartUp")
        if args.uart:
            result["warnings"].append(
                "TTY absichtlich nicht geöffnet: viele Serial-Clients toggeln DTR/RTS. "
                "Logger mit --noreset/ohne HUPCL separat starten."
            )
        result["pass"] = bool(
            result["same_usb_identity"] and result["otg_stable"] and result["no_reboot_observed"]
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["pass"] = False
    (art.out / "preflight-report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    art.finish(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"OUT {art.out}")
    return 0 if result["pass"] else 1


def run_replay(args: argparse.Namespace) -> int:
    out = args.out or default_out(f"a1-{args.selection}")
    art = RunArtifacts(out, "replay", args)
    esp = args.esp.rstrip("/")
    poller = StatusPoller(esp, out / "status-poll.jsonl", art.run_id, art.t0, args.poll_interval)
    poller.start()
    hu = HuSim(
        args.sg,
        load_profile(args.profile),
        period_ms=args.period_ms,
        cmd_timeout_ms=args.cmd_timeout_ms,
        reads_jsonl=out / "reads.jsonl",
    )
    pump: PumpTcp | None = None
    producer: RealisticProducer | None = None
    stop = threading.Event()
    result: dict[str, Any] = {"selection_requested": args.selection}
    try:
        art.mark("prepare.begin")
        pump = prep_lab(esp, args.esp_ip, None, remount=not args.no_remount)
        hu.open()
        hu.refresh_slots(esp)
        # Touch a short head then wait for msc.quiet so indexSettled becomes true.
        # evaluatePlay rejects with plug_window until that happens (S7 gate).
        try:
            hu.read_segment("fav2", 0, min(8192, hu.slots["fav2"].size))
        except Exception:
            pass
        art.mark("index.settle.wait")
        settle_t0 = time.time()
        settled_phase = None
        while time.time() - settle_t0 < 8.0:
            settled_phase = (http_json(f"{esp}/api/status").get("msc") or {}).get("phase")
            if settled_phase == "quiet":
                break
            time.sleep(0.5)
        result["index_settle"] = {
            "phase": settled_phase,
            "waited_s": round(time.time() - settle_t0, 3),
        }
        result["status_initial"] = snap_retry(esp)
        result["slots_initial"] = {
            uid: {"lba0": slot.lba0, "lba1": slot.lba1, "size": slot.size}
            for uid, slot in hu.slots.items()
        }
        if args.device:
            result["media_initial"] = capture_media(args.device, out, "initial")

        art.mark("fav1.live.begin")
        arm_uid(pump, "fav1", args.id3_bytes)
        hu.mark_armed()
        producer = RealisticProducer(
            pump, stop, start_delay_s=0.0, burst_factor=args.producer_burst
        )
        producer.start()
        time.sleep(args.live_prefill_s)
        hu.read_segment("fav1", 0, min(args.live_head_bytes, hu.slots["fav1"].size))
        result["status_fav1_live"] = snap_retry(esp)
        result["fav1_classes"] = dict(hu.class_counts)

        # End fav1 producer before the long non-live prefetch. Silence fill for
        # non-live slots does not need TCP audio, and MSC bursts starve Wi-Fi.
        stop.set()
        producer.join(timeout=3)
        result["producer_fav1"] = dict(producer.stats)
        try:
            pump.close()
        except Exception:
            pass
        pump = None

        art.mark("fav0.non_live_prefetch.begin", bytes=args.prefetch_bytes)
        hu._armed = False
        hu.class_counts.clear()
        hu.ear = VirtualEar()
        prefetch_n = hu.read_segment(
            "fav0", 0, min(args.prefetch_bytes, hu.slots["fav0"].size)
        )
        result["prefetch"] = {
            "bytes": prefetch_n,
            "slot_size": hu.slots["fav0"].size,
            "coverage_pct": round(100.0 * prefetch_n / hu.slots["fav0"].size, 3),
            "classes": dict(hu.class_counts),
        }
        wait_esp(esp, 60.0)
        result["status_after_prefetch"] = snap_retry(esp, retries=10, delay_s=2.0)

        selection_event_index = len(hu.events)
        hu.class_counts.clear()
        hu.ear = VirtualEar()
        wait_esp(esp, 60.0)
        pump = PumpTcp(args.esp_ip)
        pump.send_json({"t": "hello", "ver": 1})
        time.sleep(0.35)
        try:
            pump.drain(0.35)
        except Exception:
            pass
        stop = threading.Event()
        art.mark("fav0.select", selection=args.selection)
        arm_uid(pump, "fav0", args.id3_bytes)
        producer = RealisticProducer(
            pump, stop, start_delay_s=0.0, burst_factor=args.producer_burst
        )
        producer.start()
        hu.mark_armed()
        time.sleep(args.select_prefill_s)
        # S7-B: clear playingUid before the Head-Tip so play.guess can arm stall.
        # Stream overlay stays; already_playing would skip re-arm.
        if args.selection == "head":
            try:
                http_json(f"{esp}/api/lab/stop", "POST", {})
            except Exception:
                pass
            time.sleep(0.2)
            hu.read_segment("fav0", 0, min(args.select_read_bytes, hu.slots["fav0"].size))
        elif args.selection == "mid":
            off = min(args.mid_offset, max(0, hu.slots["fav0"].size - args.select_read_bytes))
            hu.read_segment("fav0", off, args.select_read_bytes)
        else:
            time.sleep(args.no_read_wait_s)

        time.sleep(args.settle_s)
        post = snap_retry(esp)
        selected = classify_selection(hu.events[selection_event_index:], "fav0")
        stall = post.get("stall") or {}
        selected["stall_armed"] = stall.get("armed")
        selected["playing_uid"] = post.get("play")
        selected["live_seen"] = int(selected["classes"].get("LIVE") or 0) > 0
        selected["matches_requested"] = selected["class"] == args.selection
        selected["gate_green"] = bool(
            selected["class"] == "head"
            and selected["stall_armed"] is True
            and selected["live_seen"]
        )
        result["selection"] = selected
        result["status_final"] = post
        result["timing"] = hu.timing_report()
        result["producer_fav0"] = dict(producer.stats)
        result["poll"] = {"samples": poller.samples, "errors": poller.errors}
        result["pass"] = bool(
            selected["matches_requested"]
            and not result["producer_fav1"].get("err")
            and not producer.stats.get("err")
        )
        art.mark("replay.end", gate_green=selected["gate_green"], observed=selected["class"])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["pass"] = False
    finally:
        stop.set()
        if producer is not None:
            producer.join(timeout=3)
        hu.close()
        if pump is not None:
            try:
                pump.send_json({"t": "audio_stop"})
            except Exception:
                pass
            pump.close()
        poller.stop()

    (out / "A1-REPORT.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    art.finish(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"OUT {out}")
    return 0 if result["pass"] else 1


def identity_values(status: dict) -> dict:
    msc = status.get("msc") or {}
    return {
        "usbSerial": msc.get("usbSerial"),
        "productRevision": msc.get("productRevision"),
        "bpbVolumeId": msc.get("bpbVolumeId"),
        "bpbLabel": msc.get("bpbLabel"),
        "rootLabel": msc.get("rootLabel"),
    }


def identity_diffs(before: dict, after: dict) -> list[str]:
    return sorted(key for key in before if before.get(key) != after.get(key))


def next_volume_label(current: str, explicit: str = "") -> str:
    """FAT volume label ≤11 chars. Overnight loops must never stall on equal label.

    Append-X works until length 11; then rotate the last character (A–Z / 0–9).
    """
    if explicit:
        out = explicit[:11]
        if out == (current or "")[:11]:
            raise ValueError("explicit --label equals current label")
        return out
    cur = (current or "").strip()[:11]
    if len(cur) < 11:
        return (cur + "X")[:11]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    last = cur[-1].upper()
    idx = alphabet.find(last)
    start = idx if idx >= 0 else -1
    for step in range(1, len(alphabet) + 1):
        nxt = alphabet[(start + step) % len(alphabet)]
        cand = cur[:-1] + nxt
        if cand != cur:
            return cand
    flip = "Q" if not cur.startswith("Q") else "Z"
    return (flip + cur[1:])[:11]


def stream_active(status: dict) -> bool:
    msc = status.get("msc") or {}
    stream = msc.get("stream") or status.get("stream") or {}
    return bool(stream.get("active"))


def ensure_stream_quiet(esp: str, timeout_s: float = 8.0) -> dict[str, Any]:
    """Remount is skipped while stream.active (msc.remount_skip). Stop first."""
    try:
        http_json(f"{esp}/api/lab/stop", "POST", {})
    except Exception:
        pass
    # Best-effort pump audio_stop (same pattern as nbt_hu_sim.prep_lab)
    try:
        import socket

        host = esp.split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]
        with socket.create_connection((host, 9090), timeout=1.5) as sock:
            sock.sendall(b'{"t":"audio_stop"}\n')
            time.sleep(0.2)
    except Exception:
        pass
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = http_json(f"{esp}/api/status")
        if not stream_active(last):
            phase = str((last.get("msc") or {}).get("phase") or "")
            if phase in ("", "quiet", "idle", "index", "settle"):
                return {"ok": True, "phase": phase or "quiet"}
            return {"ok": True, "phase": phase}
        time.sleep(0.25)
    return {
        "ok": False,
        "phase": (last.get("msc") or {}).get("phase"),
        "stream_active": stream_active(last) if last else None,
        "error": "stream still active — remount would remount_skip",
    }


def run_identity(args: argparse.Namespace) -> int:
    out = args.out or default_out(f"identity-{args.dimension}")
    art = RunArtifacts(out, "identity", args)
    esp = args.esp.rstrip("/")
    result: dict[str, Any] = {"dimension": args.dimension}
    try:
        quiet = ensure_stream_quiet(esp)
        result["quiet"] = quiet
        if not quiet.get("ok"):
            raise RuntimeError(quiet.get("error") or "stream not quiet")

        before_status = http_json(f"{esp}/api/status")
        before = identity_values(before_status)
        media_before = capture_media(args.device, out, "before")
        fixed_label = str(before.get("bpbLabel") or "")[:11]
        fixed_id = int(before.get("bpbVolumeId") or 0)

        if args.dimension == "volume-id":
            target_id = args.volume_id if args.volume_id is not None else (fixed_id ^ 1)
            if target_id == 0:
                target_id = 1
            target_label = fixed_label
            bump = False
        elif args.dimension == "label":
            target_id = fixed_id
            target_label = next_volume_label(fixed_label, args.label or "")
            bump = False
        else:
            target_id = fixed_id
            target_label = fixed_label
            bump = True

        art.mark(
            "identity.change",
            dimension=args.dimension,
            target_id=target_id,
            target_label=target_label,
            bump=bump,
        )
        http_json(
            f"{esp}/api/config",
            "POST",
            {"volumeLabel": target_label, "fatVolumeId": target_id},
        )
        http_json(
            f"{esp}/api/lab/remount",
            "POST",
            {
                "keepIdentity": not bump,
                "volumeLabel": target_label,
                "fatVolumeId": target_id,
            },
        )
        time.sleep(args.settle_s)
        after_status = http_json(f"{esp}/api/status")
        after = identity_values(after_status)
        media_after = capture_media(args.device, out, "after")
        diffs = identity_diffs(before, after)
        expected = {
            "volume-id": ["bpbVolumeId"],
            "label": ["bpbLabel", "rootLabel"],
            "serial": ["productRevision", "usbSerial"],
        }[args.dimension]
        result.update(
            {
                "before": before,
                "after": after,
                "changed_fields": diffs,
                "expected_changed_fields": expected,
                "media_before": media_before,
                "media_after": media_after,
                "one_dimension_only": diffs == expected,
                "device_matches_status": bool(
                    media_after["volumeId"] == after["bpbVolumeId"]
                    and media_after["bpbLabel"] == after["bpbLabel"]
                    and media_after["rootLabel"] == after["rootLabel"]
                ),
            }
        )
        result["pass"] = bool(result["one_dimension_only"] and result["device_matches_status"])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["pass"] = False
    (out / "IDENTITY-REPORT.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    art.finish(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"OUT {out}")
    return 0 if result["pass"] else 1


def write_identity_plan(args: argparse.Namespace) -> int:
    out = args.out or default_out("identity-plan")
    out.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema": SCHEMA,
        "rule": "one dimension per run; never combine identity rotation and head-force",
        "runnable_now": [
            {"dimension": "volume-id", "command": "identity --dimension volume-id"},
            {"dimension": "label", "command": "identity --dimension label"},
            {"dimension": "serial", "command": "identity --dimension serial"},
        ],
        "compile_or_geometry_variants": [
            {
                "dimension": "size",
                "status": "build-variant-required",
                "evidence": "msc.slotMap[].fileBytes + root directory file size",
            },
            {
                "dimension": "path",
                "status": "firmware/menu-layout-variant-required",
                "evidence": "msc.slotMap[].path + directory sector",
            },
            {
                "dimension": "startcluster",
                "status": "geometry-build-variant-required",
                "evidence": "msc.slotMap[].startCluster + FAT chain",
            },
        ],
    }
    (out / "identity-matrix-plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"OUT {out}")
    return 0


def self_test() -> int:
    assert classify_selection([], "fav0")["class"] == "no-read"
    head = [{"op": "read", "uid": "fav0", "off": 0, "n": 4096, "klass": "LIVE"}]
    mid = [{"op": "read", "uid": "fav0", "off": 1024 * 1024, "n": 4096, "klass": "SILENCE"}]
    assert classify_selection(head, "fav0") == {
        "class": "head",
        "reads": 1,
        "bytes": 4096,
        "first_off": 0,
        "min_off": 0,
        "max_off": 0,
        "classes": {"LIVE": 1},
    }
    assert classify_selection(mid, "fav0")["class"] == "mid"
    assert identity_diffs(
        {"usbSerial": "A", "bpbLabel": "X"}, {"usbSerial": "B", "bpbLabel": "X"}
    ) == ["usbSerial"]
    assert next_volume_label("PD0461") == "PD0461X"
    assert next_volume_label("PD0461XXXXX") == "PD0461XXXXY"
    assert next_volume_label("PD0461XXXX9") == "PD0461XXXXA"
    lab = "PD0461XXXXX"
    for _ in range(40):
        nxt = next_volume_label(lab)
        assert nxt != lab and len(nxt) <= 11
        lab = nxt
    print("self-test PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="command")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--esp", default="http://192.168.178.88")
    common.add_argument("--out", type=Path)

    preflight = sub.add_parser("preflight", parents=[common])
    preflight.add_argument("--sg", default="/dev/sg0")
    preflight.add_argument("--uart", default="/dev/ttyACM0")
    preflight.add_argument("--observe-s", type=float, default=2.0)
    preflight.add_argument("--cmd-timeout-ms", type=int, default=5000)
    preflight.set_defaults(func=run_preflight)

    replay = sub.add_parser("replay", parents=[common])
    replay.add_argument("--esp-ip", default="192.168.178.88")
    replay.add_argument("--sg", default="/dev/sg0")
    replay.add_argument("--device", default="", help="optional block device for sector capture")
    replay.add_argument(
        "--profile", type=Path, default=Path("tools/profiles/nbt_evo_2026-10-06.json")
    )
    replay.add_argument("--selection", choices=("no-read", "mid", "head"), required=True)
    replay.add_argument("--prefetch-bytes", type=int, default=DEFAULT_PREFETCH_BYTES)
    replay.add_argument("--live-head-bytes", type=int, default=64 * 1024)
    replay.add_argument("--select-read-bytes", type=int, default=64 * 1024)
    replay.add_argument("--mid-offset", type=int, default=1024 * 1024)
    replay.add_argument("--live-prefill-s", type=float, default=8.5)
    replay.add_argument("--select-prefill-s", type=float, default=8.5)
    replay.add_argument("--no-read-wait-s", type=float, default=3.0)
    replay.add_argument("--settle-s", type=float, default=1.0)
    replay.add_argument("--poll-interval", type=float, default=0.5)
    replay.add_argument("--period-ms", type=float, default=5.1)
    replay.add_argument("--cmd-timeout-ms", type=int, default=5000)
    replay.add_argument("--producer-burst", type=float, default=1.0)
    replay.add_argument("--id3-bytes", type=int, default=3300)
    replay.add_argument("--no-remount", action="store_true")
    replay.set_defaults(func=run_replay)

    identity = sub.add_parser("identity", parents=[common])
    identity.add_argument("--dimension", choices=("volume-id", "label", "serial"), required=True)
    identity.add_argument("--device", required=True, help="whole MSC block device, e.g. /dev/sdb")
    identity.add_argument("--volume-id", type=lambda value: int(value, 0))
    identity.add_argument("--label", default="")
    identity.add_argument("--settle-s", type=float, default=2.0)
    identity.set_defaults(func=run_identity)

    identity_plan = sub.add_parser("identity-plan", parents=[common])
    identity_plan.set_defaults(func=write_identity_plan)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.command:
        parser.error("choose preflight, replay, identity or identity-plan")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
