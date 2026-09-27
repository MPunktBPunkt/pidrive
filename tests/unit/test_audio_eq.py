"""Unit tests for modules.audio_eq (Tone + NR lavfi chain)."""
from __future__ import annotations

from modules import audio_eq as eq


def test_presets_exist():
    assert "flat" in eq.PRESETS
    assert "voice" in eq.PRESETS
    assert "airband" in eq.PRESETS


def test_flat_no_af():
    s = {"audio_eq_preset": "flat", "audio_eq_bass": 0, "audio_eq_mid": 0,
         "audio_eq_treble": 0, "audio_nr": False}
    assert eq.build_eq_filters(s) == []
    assert eq.mpv_af_arg(s) is None


def test_bass_preset_builds_filter():
    s = {}
    eq.apply_preset(s, "bass+")
    filters = eq.build_eq_filters(s)
    assert any(f.startswith("bass=g=") for f in filters)
    af = eq.mpv_af_arg(s, source="webradio")
    assert af and af.startswith("--af=lavfi=[")
    assert "bass=g=4" in af


def test_nr_adds_afftdn():
    s = {}
    eq.apply_preset(s, "voice")
    assert s["audio_nr"] is True
    filters = eq.build_eq_filters(s, source="voice")
    assert any(f.startswith("afftdn=") for f in filters)


def test_compose_with_base():
    s = {}
    eq.apply_preset(s, "noisy-fm")
    chain = eq.compose_lavfi(
        ["highpass=f=60", "lowpass=f=12000"],
        eq.build_eq_filters(s, source="fm"),
    )
    assert chain.startswith("lavfi=[")
    assert "highpass=f=60" in chain
    assert "afftdn=" in chain


def test_ensure_af_replaces_existing():
    s = {}
    eq.apply_preset(s, "flat")
    s["audio_eq_bass"] = 3
    args = ["PULSE_SERVER=unix:/var/run/pulse/native", "--ao=pulse", "--af=lavfi=[volume=1dB]"]
    out = eq.ensure_af_on_args(args, s, source="dab")
    afs = [a for a in out if a.startswith("--af=")]
    assert len(afs) == 1
    assert "bass=g=3" in afs[0]
    assert "volume=1dB" not in afs[0]


def test_clamp_bands():
    s = {}
    st = eq.set_bands(s, bass=99, mid=-99, treble=2, preset="custom")
    assert st["bass"] == 6
    assert st["mid"] == -6
    assert st["treble"] == 2
