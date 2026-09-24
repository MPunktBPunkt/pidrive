"""DAB welle programme selector — unique -p token on shared mux."""

from modules.radio.dab_play import _unique_welle_programme


def test_rock_antenne_bay_not_bayern():
    stations = [
        {"name": "BAYERN 1 Schw", "channel": "10A"},
        {"name": "BAYERN 1 Main", "channel": "10A"},
        {"name": "ROCK ANTENNE BAY", "channel": "10A"},
        {"name": "ARABELLA BAYERN", "channel": "10A"},
        {"name": "chillout antenne", "channel": "10A"},
        {"name": "ANTENNE BAYERN", "channel": "11D"},
    ]
    sel = _unique_welle_programme("ROCK ANTENNE BAY", "10A", stations)
    assert sel == "ROCK"
    assert "BAY" not in sel.split()  # alone would hit BAYERN


def test_antenne_bayern_on_11d():
    stations = [
        {"name": "ANTENNE BAYERN", "channel": "11D"},
        {"name": "BAYERN 3", "channel": "11D"},
        {"name": "BAYERN 1 Obb", "channel": "11D"},
    ]
    sel = _unique_welle_programme("ANTENNE BAYERN", "11D", stations)
    assert sel.upper().startswith("ANTENNE")
