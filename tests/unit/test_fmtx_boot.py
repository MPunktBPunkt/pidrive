"""FM-Sender: Boot-Ansage-Trigger (BootWatch) ohne Hardware."""
from __future__ import annotations

import json

import pytest

from modules.tx import service
from modules.tx import tx_manager as tm


class FakeMgr:
    def __init__(self, fm_tx, ok=True):
        self.settings = {"fm_tx": fm_tx}
        self.ok = ok
        self.state = "off"
        self.error = ""
        self.warnings = []
        self.calls = []

    def _load(self):
        return self.settings

    def announce(self, then="off"):
        self.calls.append(then)
        if not self.ok:
            self.state, self.error = "error", "Consent fehlt"
            return False
        self.state = "on"
        return True

    def publish(self):
        pass


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def boot(tmp_path, monkeypatch):
    src = tmp_path / "source_state.json"
    monkeypatch.setattr(service, "SOURCE_STATE_FILE", str(src))
    monkeypatch.setattr(service, "BOOT_MARKER", str(tmp_path / "boot_done"))

    def phase(p):
        src.write_text(json.dumps({"boot_phase": p}), encoding="utf-8")

    clock = Clock()
    return phase, clock, tmp_path


def _fm(**kw):
    c = tm.get_cfg({})
    c.update(enabled=True, **kw)
    return c


def test_triggers_once_after_steady_settle(boot):
    phase, clock, tmp = boot
    mgr = FakeMgr(_fm(autostart="boot_only"))
    w = service.BootWatch(clock=clock, boot_ts=0.0)
    phase("restore_source")
    assert w.poll(mgr) is None
    phase("steady")
    assert w.poll(mgr) is None
    clock.t += service.BOOT_SETTLE_S - 0.5
    assert w.poll(mgr) is None
    clock.t += 1
    msg = w.poll(mgr)
    assert "gestartet" in msg and mgr.calls == ["boot_only"]
    assert (tmp / "boot_done").exists()
    clock.t += 10
    assert w.poll(mgr) is None
    assert service.BootWatch(clock=clock, boot_ts=0.0).poll(mgr) is None
    assert mgr.calls == ["boot_only"]


def test_autostart_off_skips_but_marks(boot):
    phase, clock, tmp = boot
    mgr = FakeMgr(_fm(autostart="off"))
    w = service.BootWatch(clock=clock, boot_ts=0.0)
    phase("steady")
    w.poll(mgr)
    clock.t += service.BOOT_SETTLE_S + 0.1
    assert "aus" in w.poll(mgr)
    assert mgr.calls == [] and (tmp / "boot_done").exists()


def test_disabled_skips(boot):
    phase, clock, _tmp = boot
    fm = _fm(autostart="always")
    fm["enabled"] = False
    mgr = FakeMgr(fm)
    w = service.BootWatch(clock=clock, boot_ts=0.0)
    phase("steady")
    w.poll(mgr)
    clock.t += service.BOOT_SETTLE_S + 0.1
    assert "enabled" in w.poll(mgr)
    assert mgr.calls == []


def test_failed_announce_becomes_warning_not_error(boot):
    phase, clock, _tmp = boot
    mgr = FakeMgr(_fm(autostart="boot_only"), ok=False)
    w = service.BootWatch(clock=clock, boot_ts=0.0)
    phase("steady")
    w.poll(mgr)
    clock.t += service.BOOT_SETTLE_S + 0.1
    assert "Consent" in w.poll(mgr)
    assert mgr.state == "off" and mgr.error == ""
    assert any("Boot-Ansage" in x for x in mgr.warnings)


def test_stale_state_file_from_previous_boot_ignored(boot):
    phase, _clock, _tmp = boot
    phase("steady")
    assert service.read_boot_phase(boot_ts=4_000_000_000.0) == ""
    assert service.read_boot_phase(boot_ts=0.0) == "steady"
