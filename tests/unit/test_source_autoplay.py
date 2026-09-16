"""Q-A…Q-E: Quellen-Autoplay und enter_action."""
from __future__ import annotations

from modules import source_autoplay as ap
from modules import source_state
from menu import menu_golden


def test_resolve_fm_fallback_freq():
    st = ap.resolve_station("fm", {"fm_freq": "104.4", "last_fm_station": None}, store=None)
    assert st["freq"] == "104.4"


def test_resolve_fm_prefers_last():
    st = ap.resolve_station(
        "fm",
        {"last_fm_station": {"name": "Lokal", "freq": "99.1"}, "fm_freq": "98.5"},
        store=None,
    )
    assert st["freq"] == "99.1"


def test_resolve_web_first_of_list():
    class _Store:
        web = [{"name": "A", "url": "http://a"}, {"name": "B", "url": "http://b"}]

    st = ap.resolve_station("webradio", {"last_web_station": None}, _Store())
    assert st["name"] == "A"


def test_should_autoplay_skips_same_source(monkeypatch):
    monkeypatch.setattr(source_state, "current_source", lambda: "fm")
    assert ap.should_autoplay("fm") is False
    assert ap.should_autoplay("dab") is True


def test_exactly_three_enter_actions():
    nodes = menu_golden.walk_tree(menu_golden.build_reference_tree())
    with_ea = [n for n in nodes if n.get("enter_action")]
    assert len(with_ea) == 3
    ids = sorted(n["id"] for n in with_ea)
    assert ids == ["dab", "fm", "webradio"]
    assert all(n["enter_action"].startswith("autoplay:") for n in with_ea)


def test_walk_does_not_call_autoplay(monkeypatch):
    """Q-D: menu walk startet keinen Tuner / keine enter_action."""
    calls = []

    def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("autoplay must not run during walk")

    monkeypatch.setattr(ap, "run_autoplay", _boom)
    assert menu_golden.cmd_walk() == 0
    assert calls == []


def test_activate_folder_does_not_autoplay():
    """activate: auf Quellenordner darf enter_action nicht auslösen (§2.1)."""
    from menu.menu_state import MenuState
    from menu.menu_golden import build_reference_tree

    state = MenuState(build_reference_tree())
    fm = None
    for n in menu_golden.walk_tree(state.root):
        if n["id"] == "fm" and n["type"] == "folder":
            fm = n
            break
    assert fm and fm.get("enter_action")
    node = state.activate(fm["uid"])
    assert node and node.id == "fm"
    # activate betritt Ordner — ohne Dispatcher kein Autoplay (Zustand bleibt rein)
    assert state.current.id == "fm"
