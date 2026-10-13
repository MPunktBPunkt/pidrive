"""Offline contracts for the D-startgate lab campaign."""
from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


def load_tool(repo_root: Path):
    tools = repo_root / "tools"
    sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("lab_d_campaign", tools / "lab_d_campaign.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selection_classification_is_offset_based(repo_root: Path):
    tool = load_tool(repo_root)
    assert tool.classify_selection([], "fav0")["class"] == "no-read"
    assert (
        tool.classify_selection(
            [{"op": "read", "uid": "fav0", "off": 0, "n": 4096, "klass": "LIVE"}],
            "fav0",
        )["class"]
        == "head"
    )
    assert (
        tool.classify_selection(
            [{"op": "read", "uid": "fav0", "off": 1_048_576, "n": 4096, "klass": "SILENCE"}],
            "fav0",
        )["class"]
        == "mid"
    )


def test_identity_diff_reports_only_changed_fields(repo_root: Path):
    tool = load_tool(repo_root)
    before = {"usbSerial": "PD0001", "bpbVolumeId": 1, "bpbLabel": "PIDRIVE"}
    after = {"usbSerial": "PD0002", "bpbVolumeId": 1, "bpbLabel": "PIDRIVE"}
    assert tool.identity_diffs(before, after) == ["usbSerial"]


def test_replay_requires_explicit_selection(repo_root: Path):
    tool = load_tool(repo_root)
    parser = tool.build_parser()
    args = parser.parse_args(["replay", "--selection", "head"])
    assert args.selection == "head"
    assert args.prefetch_bytes == 8_294_400
    assert args.period_ms == 5.1


def test_run_artifacts_write_canonical_yaml(repo_root: Path, tmp_path: Path):
    tool = load_tool(repo_root)
    args = Namespace(sg="/dev/sg0", device="/dev/sdb", uart="/dev/ttyACM0", func=None)
    artifacts = tool.RunArtifacts(tmp_path, "replay", args)
    artifacts.finish({"pass": True, "status_initial": {"version": "test", "uptimeMs": 42}})
    text = (tmp_path / "run.yaml").read_text(encoding="utf-8")
    assert "env: lab" in text
    assert 'sg_device: "/dev/sg0"' in text
    assert "dtr_rts: false" in text
    assert 'out: "status-poll.jsonl"' in text


def test_uart_reset_classifier(repo_root: Path):
    path = repo_root / "tools" / "lab_uart_reset_log.py"
    spec = importlib.util.spec_from_file_location("lab_uart_reset_log", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classes = module.classify_boot_text("Brownout detector was triggered\nrst:0xc")
    assert classes == ["rom_reset", "brownout"]
    assert module.uptime_rollback([{"uptimeMs": 100}, {"uptimeMs": 5}])
