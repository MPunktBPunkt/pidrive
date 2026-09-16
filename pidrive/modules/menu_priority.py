"""
modules/menu_priority.py — Menüvorrang mit Zeitablauf (Q-L)
Aufrufer: main_core.py, td_nav.py
Rein prüfbar ohne D-Bus/Hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

View = Literal["auto", "menu"]
Event = Literal["nav", "leaf", "none"]


@dataclass
class MenuPriorityState:
    until: float = 0.0
    last_rev: int = -1
    pending_event: Event = "none"


def decide_view(
    *,
    now: float,
    menu_rev: int,
    state: MenuPriorityState,
    window_s: float = 3.5,
    event: Event = "none",
) -> Tuple[View, MenuPriorityState, bool]:
    """
    Eingabe: Zeit, Menü-Revision, optional Event (nav|leaf).
    Ausgabe: (view, neuer State, push_needed).

    - nav / Rev-Änderung: Zeitfenster starten/verlängern → view=menu, push
    - leaf: Fenster sofort beenden → view=auto, push
    - Zeitablauf: einmal auf auto zurück, push
    - sonst: aktueller view ohne Push
    """
    st = MenuPriorityState(
        until=state.until,
        last_rev=state.last_rev,
        pending_event=state.pending_event,
    )
    ev: Event = event if event != "none" else st.pending_event
    st.pending_event = "none"

    # Erster Tick: Rev nur merken, kein Menüfenster (Boot)
    if st.last_rev < 0:
        st.last_rev = menu_rev
        if ev == "none":
            return "auto", st, False

    # EQ5: WebUI goto/activate hebt rev — gilt als Navigation
    if ev == "none" and menu_rev != st.last_rev:
        ev = "nav"

    if ev == "leaf":
        st.until = 0.0
        st.last_rev = menu_rev
        return "auto", st, True

    if ev == "nav":
        st.until = now + max(0.1, float(window_s))
        st.last_rev = menu_rev
        return "menu", st, True

    if st.until > 0.0:
        if now < st.until:
            st.last_rev = menu_rev
            return "menu", st, False
        st.until = 0.0
        st.last_rev = menu_rev
        return "auto", st, True

    st.last_rev = menu_rev
    return "auto", st, False


def note_event(state: MenuPriorityState, event: Event) -> MenuPriorityState:
    """Event aus dem Trigger-Pfad vormerken (vor dem nächsten Tick)."""
    return MenuPriorityState(
        until=state.until,
        last_rev=state.last_rev,
        pending_event=event,
    )
