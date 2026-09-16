"""Q-K: MPRIS Menü-/Wiedergabelabel (ohne D-Bus)."""
from __future__ import annotations

from modules.mpris_labels import menu_fields, now_playing_label


def test_menu_fields_selected():
    menu = {
        "path": ["PiDrive", "Quellen", "FM Radio"],
        "cursor": 1,
        "nodes": [
            {"label": "Zurueck"},
            {"label": "Naechster Sender"},
        ],
    }
    title, artist = menu_fields(menu)
    assert title == "Naechster Sender"
    assert artist == "Quellen › FM Radio"


def test_now_playing_label_prefers_radio_name():
    assert now_playing_label({"radio_name": "ROCK FM", "radio_type": "DAB"}) == "ROCK FM"
    assert now_playing_label({"spotify": True}) == "Spotify"
    assert now_playing_label({}) == "PiDrive"
