"""Q-L: Menüvorrang-Zeitfenster (offline)."""
from __future__ import annotations

from modules.menu_priority import MenuPriorityState, decide_view, note_event


def test_nav_starts_menu_window():
    st = MenuPriorityState()
    view, st2, push = decide_view(now=100.0, menu_rev=1, state=st, window_s=3.5, event="nav")
    assert view == "menu"
    assert push is True
    assert st2.until == 103.5


def test_window_holds_without_push():
    st = MenuPriorityState(until=103.5, last_rev=1)
    view, st2, push = decide_view(now=101.0, menu_rev=1, state=st, window_s=3.5, event="none")
    assert view == "menu"
    assert push is False
    assert st2.until == 103.5


def test_window_expires_to_auto_with_push():
    st = MenuPriorityState(until=103.5, last_rev=1)
    view, st2, push = decide_view(now=104.0, menu_rev=1, state=st, window_s=3.5, event="none")
    assert view == "auto"
    assert push is True
    assert st2.until == 0.0


def test_leaf_ends_window_immediately():
    st = MenuPriorityState(until=200.0, last_rev=5)
    view, st2, push = decide_view(now=100.0, menu_rev=6, state=st, window_s=3.5, event="leaf")
    assert view == "auto"
    assert push is True
    assert st2.until == 0.0


def test_nav_extends_window():
    st = MenuPriorityState(until=102.0, last_rev=1)
    view, st2, push = decide_view(now=101.0, menu_rev=2, state=st, window_s=3.5, event="nav")
    assert view == "menu"
    assert push is True
    assert st2.until == 104.5


def test_pending_event_from_note():
    st = note_event(MenuPriorityState(), "nav")
    view, st2, push = decide_view(now=50.0, menu_rev=1, state=st, window_s=3.5, event="none")
    assert view == "menu"
    assert push is True
    assert st2.pending_event == "none"


def test_idle_stays_auto():
    st = MenuPriorityState()
    view, st2, push = decide_view(now=10.0, menu_rev=0, state=st, window_s=3.5, event="none")
    assert view == "auto"
    assert push is False


def test_rev_change_without_event_is_nav():
    """EQ5: WebUI/goto hebt rev → Menüfenster."""
    st = MenuPriorityState(last_rev=1, until=0.0)
    view, st2, push = decide_view(now=50.0, menu_rev=2, state=st, window_s=3.5, event="none")
    assert view == "menu"
    assert push is True
    assert st2.until == 53.5


def test_boot_rev_init_no_window():
    st = MenuPriorityState()  # last_rev=-1
    view, st2, push = decide_view(now=1.0, menu_rev=7, state=st, window_s=3.5, event="none")
    assert view == "auto"
    assert push is False
    assert st2.last_rev == 7
