"""FM-Sender: TxManager-Zustandsmaschine mit Fake-Backend (ohne Hardware)."""
from __future__ import annotations

import json

import pytest

from modules.tx import tx_manager as tm


class FakeBackend:
    def __init__(self, fail_start=False):
        self.fail_start = fail_start
        self.running = False
        self.started = []
        self.rds = []
        self.stops = 0

    def capabilities(self):
        return {"available": True, "pins": [4], "bands": ["ukw"],
                "sources": ["mirror", "tone1k", "carrier", "silence", "announce"]}

    def start(self, cfg, audio_cmd):
        if self.fail_start:
            raise RuntimeError("kaputt")
        self.started.append((cfg, audio_cmd))
        self.running = True

    def stop(self):
        self.stops += 1
        self.running = False

    def set_rds(self, ps=None, rt=None):
        self.rds.append((ps, rt))
        return True

    def status(self):
        return {"running": self.running}


class FakeRds:
    def __init__(self):
        self.rt = "RT1"

    def compute(self, cfg, force=False):
        return cfg["rds"]["ps"], self.rt


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(tm, "CMD_FILE", str(tmp_path / "cmd"))
    monkeypatch.setattr(tm, "gather_context", lambda settings=None, status=None: {
        "pi_model": "Raspberry Pi 4 Model B", "dab_channel": "", "rtl_rx_mhz": None,
        "control_context": "idle"})
    cfg = tm.give_consent(tm.get_cfg({}), "lab_dummy", now=1)
    cfg["enabled"] = True
    settings = {"fm_tx": cfg}
    backends = []

    def factory(name):
        b = FakeBackend()
        backends.append(b)
        return b

    clock = Clock()
    mgr = tm.TxManager(lambda: settings, backend_factory=factory,
                       audio_cmd_factory=lambda c: ["fake-audio"],
                       rds_factory=FakeRds, clock=clock)
    return mgr, settings, backends, clock, tmp_path


def test_start_and_stop_writes_state(env):
    mgr, _s, backends, _c, tmp = env
    assert mgr.start() is True
    assert mgr.state == "on"
    cfg, audio = backends[-1].started[0]
    assert audio == ["fake-audio"]
    assert cfg["freq_effective_mhz"] == pytest.approx(91.0)
    st = json.loads((tmp / "state.json").read_text(encoding="utf-8"))
    assert st["state"] == "on" and st["rds_ps"] == "PIDRIVE"
    mgr.stop("user")
    assert mgr.state == "off" and backends[-1].stops >= 1


def test_start_blocked_without_consent(env):
    mgr, settings, _b, _c, _t = env
    settings["fm_tx"]["consent_ts"] = 0
    assert mgr.start() is False
    assert mgr.state == "error" and "Consent" in mgr.error


def test_start_blocked_when_disabled(env):
    mgr, settings, _b, _c, _t = env
    settings["fm_tx"]["enabled"] = False
    assert mgr.start() is False
    assert "enabled" in mgr.error


def test_backend_start_failure(env, monkeypatch):
    mgr, _s, _b, _c, _t = env
    mgr._backend_factory = lambda name: FakeBackend(fail_start=True)
    assert mgr.start() is False
    assert mgr.state == "error" and "kaputt" in mgr.error


def test_runtime_limit_stops(env):
    mgr, settings, _b, clock, _t = env
    settings["fm_tx"]["max_runtime_min"] = 1
    mgr.start()
    clock.t += 59
    mgr.tick()
    assert mgr.state == "on"
    clock.t += 2
    mgr.tick()
    assert mgr.state == "off"
    assert "Laufzeitlimit" in mgr.error


def test_watchdog_restarts_then_gives_up(env):
    mgr, _s, backends, clock, _t = env
    mgr.start()
    for _ in range(tm.MAX_RESTARTS):
        backends[-1].running = False
        clock.t += 1
        mgr.tick()
        assert mgr.state == "on"
    backends[-1].running = False
    clock.t += 1
    mgr.tick()
    assert mgr.state == "error"
    assert "kein Neustart" in mgr.error


def test_watchdog_keeps_original_start_time(env):
    mgr, _s, backends, clock, _t = env
    mgr.start()
    t0 = mgr.started_ts
    backends[-1].running = False
    clock.t += 5
    mgr.tick()
    assert mgr.started_ts == t0


def test_rds_auto_update_in_tick(env):
    mgr, _s, backends, _c, _t = env
    mgr.start()
    mgr.rds.rt = "Neuer Titel"
    mgr.tick()
    assert backends[-1].rds[-1] == (None, "Neuer Titel")
    assert mgr.rds_rt == "Neuer Titel"


def test_reload_rds_only_does_not_restart(env):
    mgr, settings, backends, _c, _t = env
    mgr.start()
    n_backends = len(backends)
    settings["fm_tx"]["rds"]["ps"] = "NEU"
    mgr.reload()
    assert len(backends) == n_backends
    assert backends[-1].rds[-1][0] == "NEU"


def test_reload_freq_restarts(env):
    mgr, settings, backends, _c, _t = env
    mgr.start()
    settings["fm_tx"]["freq_mhz"] = 89.0
    mgr.reload()
    assert mgr.state == "on"
    assert backends[-1].started[0][0]["freq_effective_mhz"] == pytest.approx(89.0)


def test_handle_commands(env):
    mgr, _s, _b, _c, _t = env
    mgr.handle("start")
    assert mgr.state == "on"
    mgr.handle("stop")
    assert mgr.state == "off"
    mgr.handle("")
    mgr.handle("unbekannt foo")


def test_send_command_and_needs_pulse(env, monkeypatch):
    _mgr, _s, _b, clock, tmp = env
    assert tm.send_command("start\nstop") is True
    assert (tmp / "cmd").read_text(encoding="utf-8") == "start stop\n"
    tm.write_state({"state": "on", "source": "mirror", "ts": int(__import__("time").time())})
    assert tm.needs_pulse_monitor() is True
    tm.write_state({"state": "on", "source": "tone1k", "ts": int(__import__("time").time())})
    assert tm.needs_pulse_monitor() is False
    tm.write_state({"state": "on", "source": "mirror", "ts": 0})
    assert tm.needs_pulse_monitor() is False


# ── Boot-Ansage / Autostart ──

def test_default_autostart_boot_only():
    assert tm.get_cfg({})["autostart"] == "boot_only"
    assert tm.get_cfg({})["freq_mhz"] == pytest.approx(91.0)


def test_announce_boot_only_stops_without_error(env):
    mgr, _s, backends, clock, _t = env
    assert mgr.announce(then="boot_only") is True
    run_cfg, _audio = backends[-1].started[0]
    assert run_cfg["source"] == "announce"
    assert mgr.rds_rt == tm.ANNOUNCE_RT
    snap = mgr.snapshot()
    assert snap["announcing"] is True and snap["source"] == "announce"
    clock.t += tm.ANNOUNCE_WINDOW_S - 1
    mgr.tick()
    assert mgr.state == "on"
    clock.t += 2
    mgr.tick()
    assert mgr.state == "off"
    assert mgr.error == ""
    assert mgr.snapshot()["announcing"] is False


def test_announce_always_switches_to_configured_source(env):
    mgr, settings, backends, clock, _t = env
    settings["fm_tx"]["source"] = "mirror"
    mgr.announce(then="always")
    clock.t += tm.ANNOUNCE_WINDOW_S + 0.5
    mgr.tick()
    assert mgr.state == "on"
    assert backends[-1].started[-1][0]["source"] == "mirror"
    assert mgr.rds_rt == "RT1"
    assert mgr.snapshot()["announcing"] is False


def test_announce_window_no_watchdog_restart(env):
    mgr, _s, backends, clock, _t = env
    mgr.announce(then="boot_only")
    n = len(backends)
    backends[-1].running = False
    clock.t += 2
    mgr.tick()
    assert len(backends) == n
    assert mgr.state == "on" and mgr.restarts == []


def test_announce_blocked_without_consent(env):
    mgr, settings, backends, _c, _t = env
    settings["fm_tx"]["consent_ts"] = 0
    assert mgr.announce(then="boot_only") is False
    assert not backends or not backends[-1].started
    assert mgr.announce_until == 0.0


def test_handle_announce_always_off_afterwards(env):
    mgr, settings, _b, clock, _t = env
    settings["fm_tx"]["autostart"] = "always"
    mgr.handle("announce")
    assert mgr.snapshot()["announcing"] is True
    clock.t += tm.ANNOUNCE_WINDOW_S + 1
    mgr.tick()
    assert mgr.state == "off" and mgr.error == ""


def test_reload_during_announce_keeps_announcing(env):
    mgr, settings, backends, _c, _t = env
    mgr.announce(then="boot_only")
    n = len(backends)
    settings["fm_tx"]["freq_mhz"] = 92.0
    mgr.reload()
    assert len(backends) == n and mgr.snapshot()["announcing"] is True
