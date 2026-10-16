"""Offline contracts for the safe F0 soft-cycle orchestrator."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def load_tool(repo_root: Path):
    tools = repo_root / "tools"
    sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location(
        "soft_cycle_orchestrator", tools / "soft_cycle_orchestrator.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def status(
    *,
    read_count: int = 0,
    body_bytes: int = 0,
    max_seq: int = 0,
    active: bool = False,
    playing: str = "",
    uptime: int = 1000,
    reason: str = "poweron",
) -> dict:
    return {
        "ok": True,
        "version": "0.4.52-test",
        "uptimeMs": uptime,
        "resetReason": reason,
        "resetReasonCode": 1,
        "otgUp": True,
        "playingUid": playing,
        "stallEnable": False,
        "msc": {
            "phase": "quiet",
            "usbSerial": "PD0100",
            "productRevision": "0100",
            "bpbVolumeId": 1,
            "bpbLabel": "PIDRIVE",
            "rootLabel": "PIDRIVE",
            "readCount": read_count,
            "slotMap": [{"uid": "fav0", "bytes": body_bytes, "maxSeq": max_seq}],
            "stream": {
                "active": active,
                "uid": playing,
                "absBase": 0,
                "absEnd": 4096 if active else 0,
            },
            "stall": {"enabled": False},
        },
    }


def test_outcome_classification_a_to_e(repo_root: Path):
    tool = load_tool(repo_root)
    before = status()
    assert tool.classify_outcome(before, status(read_count=1, body_bytes=4096, max_seq=4096,
                                                active=True, playing="fav0"))["code"] == "A"
    assert tool.classify_outcome(before, status(read_count=2, body_bytes=8192,
                                                max_seq=500_000))["code"] == "B"
    assert tool.classify_outcome(before, status())["code"] == "C"
    assert tool.classify_outcome(before, status(uptime=1, reason="panic"))["code"] == "D"
    ambiguous = status(read_count=-1)
    assert tool.classify_outcome(before, ambiguous)["code"] == "E"


def test_matrix_isolated_dimensions(repo_root: Path):
    tool = load_tool(repo_root)
    assert tool.MATRIX == ("soft-usb", "media-hide", "serial", "label", "volume-id")
    assert tool.EXPECTED_IDENTITY_CHANGES["soft-usb"] == []
    assert tool.EXPECTED_IDENTITY_CHANGES["media-hide"] == []
    assert tool.EXPECTED_IDENTITY_CHANGES["serial"] == ["productRevision", "usbSerial"]
    assert tool.EXPECTED_IDENTITY_CHANGES["label"] == ["bpbLabel", "rootLabel"]
    assert tool.EXPECTED_IDENTITY_CHANGES["volume-id"] == ["bpbVolumeId"]


def test_panic_and_uptime_rollback_are_hard_failures(repo_root: Path):
    tool = load_tool(repo_root)
    before = status(uptime=5000)
    panic = tool.panic_gate(before, status(uptime=5100, reason="panic"))
    assert panic["ok"] is False and panic["panic_reason"] == "panic"
    rollback = tool.panic_gate(before, status(uptime=100))
    assert rollback["ok"] is False and rollback["uptime_rollback"] is True


def test_identity_drift_invalidates_cell(repo_root: Path):
    tool = load_tool(repo_root)
    before = status()
    after = status()
    after["msc"]["usbSerial"] = "PD0101"
    assert tool.identity_gate("soft-usb", before, after)["ok"] is False
    after["msc"]["productRevision"] = "0101"
    serial = tool.identity_gate("serial", before, after)
    assert serial["ok"] is True
    assert serial["changed_fields"] == ["productRevision", "usbSerial"]


def test_report_and_dry_run_have_complete_artifacts(repo_root: Path, tmp_path: Path):
    tool = load_tool(repo_root)
    rc = tool.main(["--dry-run", "--profile", "auto", "--out", str(tmp_path)])
    assert rc == 0
    required = {
        "run.yaml",
        "run-manifest.json",
        "events.jsonl",
        "marks.jsonl",
        "status-poll.jsonl",
        "CELL-REPORT.json",
        "SUMMARY.json",
        "ERGEBNIS.md",
    }
    # marks.jsonl is required even when no optional manual marker was supplied.
    assert required <= {path.name for path in tmp_path.iterdir()}
    summary = json.loads((tmp_path / "SUMMARY.json").read_text(encoding="utf-8"))
    assert summary["pass"] is True and summary["dry_run"] is True
    assert summary["cells_completed"] == 5
    for cell in tool.MATRIX:
        cell_dir = tmp_path / cell
        assert (cell_dir / "a-snapshot.json").exists()
        assert (cell_dir / "b-snapshot.json").exists()
        report = json.loads((cell_dir / "CELL-REPORT.json").read_text(encoding="utf-8"))
        assert set(report["episodes"]) == {"A", "B"}
        assert report["valid"] is True
        assert report["capture_health"]["ok"] is True
        assert report["capture_health"]["complete"] is True
        assert report["capture_health"]["overflow"] == 0
        assert report["capture_health"]["cmdCapture"] is True
        trace = json.loads((cell_dir / "offline-bot-trace.json").read_text(encoding="utf-8"))
        assert trace["capture_mode"] == "ram_local"
        assert trace["capture_health"]["ok"] is True


def test_profiles_and_physical_replug_are_safe(repo_root: Path, tmp_path: Path):
    tool = load_tool(repo_root)
    assert tool.PROFILES["auto"]["polls"] < tool.PROFILES["lab"]["polls"]
    rc = tool.main(
        [
            "--dry-run",
            "--out",
            str(tmp_path),
            "--cells",
            "soft-usb",
            "--physical-replug-marker",
            "operator pulled cable",
        ]
    )
    assert rc == 0
    marks = (tmp_path / "marks.jsonl").read_text(encoding="utf-8")
    assert "manual-physical-replug" in marks
    manifest = json.loads((tmp_path / "run-manifest.json").read_text(encoding="utf-8"))
    assert "never automated" in manifest["physical_replug"]


def configured_args(tool, out: Path, *argv: str):
    args = tool.build_parser().parse_args(["--dry-run", "--out", str(out), *argv])
    for key, value in tool.PROFILES[args.profile].items():
        setattr(args, key, value)
    return args


def test_capture_pagination_exports_every_command(repo_root: Path, tmp_path: Path):
    tool = load_tool(repo_root)
    args = configured_args(tool, tmp_path, "--cells", "label")
    client = tool.DryRunClient(capture_page_size=1)
    rc = tool.Orchestrator(args, client).run()
    assert rc == 0
    trace = json.loads(
        (tmp_path / "label" / "offline-bot-trace.json").read_text(encoding="utf-8")
    )
    assert trace["command_count"] == 2
    assert [command["seq"] for command in trace["commands"]] == [1, 2]
    assert len(trace["pages"]) == 2
    page_gets = [
        request["path"]
        for request in client.request_log
        if request["method"] == "GET" and request["path"].startswith("/api/lab/mess?after=")
    ]
    assert page_gets[:2] == ["/api/lab/mess?after=0", "/api/lab/mess?after=1"]


@pytest.mark.parametrize(
    ("complete", "overflow"),
    [(False, 0), (True, 1)],
)
def test_incomplete_capture_is_hard_stop(
    repo_root: Path, tmp_path: Path, complete: bool, overflow: int
):
    tool = load_tool(repo_root)
    args = configured_args(tool, tmp_path, "--cells", "soft-usb")
    client = tool.DryRunClient(capture_complete=complete, capture_overflow=overflow)
    rc = tool.Orchestrator(args, client).run()
    assert rc == 2
    report = json.loads(
        (tmp_path / "soft-usb" / "CELL-REPORT.json").read_text(encoding="utf-8")
    )
    assert report["capture_health"]["ok"] is False
    assert report["hard_stop"] == "capture-incomplete"
    summary = json.loads((tmp_path / "SUMMARY.json").read_text(encoding="utf-8"))
    assert summary["hard_stop"] == "capture-incomplete"


def test_ram_wifi_off_is_lab_baseline_only(repo_root: Path, tmp_path: Path):
    tool = load_tool(repo_root)
    good = tmp_path / "good"
    rc = tool.main(
        [
            "--dry-run",
            "--profile",
            "lab",
            "--capture-mode",
            "ram_wifi_off",
            "--no-live-audio",
            "--cells",
            "soft-usb",
            "--out",
            str(good),
        ]
    )
    assert rc == 0
    report = json.loads(
        (good / "soft-usb" / "CELL-REPORT.json").read_text(encoding="utf-8")
    )
    assert report["capture_mode"] == "ram_wifi_off"
    assert report["capture_health"]["mode"] == "ram_wifi_off"

    with pytest.raises(SystemExit):
        tool.main(
            [
                "--dry-run",
                "--profile",
                "auto",
                "--capture-mode",
                "ram_wifi_off",
                "--no-live-audio",
            ]
        )
    with pytest.raises(SystemExit):
        tool.main(["--dry-run", "--profile", "lab", "--capture-mode", "ram_wifi_off"])
