"""Reine Label-Helfer für MPRIS Menü-/Wiedergabezeilen (ohne D-Bus)."""

from __future__ import annotations


def menu_fields(menu: dict) -> tuple[str, str]:
    """Gewählter Menüeintrag → (title, artist) für AVRCP."""
    path = menu.get("path") or []
    if not isinstance(path, list):
        path = []
    cursor = int(menu.get("cursor", 0) or 0)
    nodes = menu.get("nodes") or []
    selected = ""
    if isinstance(nodes, list) and nodes and 0 <= cursor < len(nodes):
        try:
            selected = nodes[cursor].get("label", "") or ""
        except Exception:
            selected = ""
    title = selected or (path[-1] if path else "PiDrive")
    artist = " › ".join(path[1:]) if len(path) > 1 else "PiDrive"
    return title, artist


def now_playing_label(status: dict) -> str:
    """Laufender Sender für Album-Zeile während Menünavigation."""
    name = (status.get("radio_name") or status.get("radio_station")
            or status.get("track") or status.get("library_track") or "")
    name = str(name).strip()
    if name:
        return name[:64]
    if status.get("spotify"):
        return "Spotify"
    rt = (status.get("radio_type") or "").upper()
    if rt:
        return rt
    return "PiDrive"
