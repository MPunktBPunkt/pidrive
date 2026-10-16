"""FM-Sender: RDS-Texte/Gruppen, AudioTap-Kommandos, Backend-Argumente, NBFM (ohne Hardware)."""
from __future__ import annotations

import math
import struct

import pytest

from modules.tx import audio_tap, backend_chip, nbfm_mod, rds
from modules.tx.backend_pifmrds import PiFmRdsBackend, CTL_FIFO
from modules.tx.backend_rpitx import RpitxBackend


def test_rds_ascii_transliterates_and_trims():
    assert rds.rds_ascii("Bayern 3 – Grüße", 64) == "Bayern 3 - Gruesse"
    assert rds.rds_ascii("ABCDEFGHIJ", 8) == "ABCDEFGH"
    assert rds.rds_ascii("a\nb\tc", 64) == "a b c"


def test_now_playing_radio_and_music():
    name, rt = rds.now_playing_text({"control_context": "radio_fm",
                                     "radio_name": "FM: Bayern 3 (99.4 MHz)", "dls_text": ""})
    assert name == "Bayern 3" and rt == "Bayern 3"
    _n, rt = rds.now_playing_text({"control_context": "radio_dab", "radio_name": "ROCK FM",
                                   "dls_text": "AC/DC - Thunderstruck"})
    assert rt == "ROCK FM - AC/DC - Thunderstruck"
    _n, rt = rds.now_playing_text({"control_context": "spotify", "artist": "A", "track": "T"})
    assert rt == "A - T"
    assert rds.now_playing_text({}) == ("", "")


def test_rds_auto_rate_limit():
    t = [0.0]
    status = {"control_context": "spotify", "artist": "A", "track": "T1"}
    r = rds.RdsAuto(status_reader=lambda: status, clock=lambda: t[0], rt_min_interval_s=10)
    cfg = {"rds": {"ps": "PIDRIVE", "rt_mode": "auto", "rt": ""}}
    assert r.compute(cfg, force=True) == ("PIDRIVE", "A - T1")
    status["track"] = "T2"
    t[0] = 5
    assert r.compute(cfg)[1] == "A - T1"
    t[0] = 11
    assert r.compute(cfg)[1] == "A - T2"


def test_rds_fixed_mode():
    r = rds.RdsAuto(status_reader=lambda: {"artist": "x", "track": "y"})
    ps, rt = r.compute({"rds": {"ps": "Mein", "rt_mode": "fixed", "rt": "Fest"}}, force=True)
    assert (ps, rt) == ("Mein", "Fest")


def test_rds_ps_rotation():
    t = [0.0]
    r = rds.RdsAuto(status_reader=lambda: {"control_context": "radio_dab",
                                           "radio_name": "ANTENNE BAYERN"},
                    clock=lambda: t[0])
    cfg = {"rds": {"ps": "PIDRIVE", "rt_mode": "auto", "ps_rotate": True}}
    seen = set()
    for i in range(6):
        t[0] = i * (rds.PS_ROTATE_S + 0.1)
        seen.add(r.compute(cfg)[0])
    assert {"PIDRIVE", "ANTENNE ", "BAYERN"} <= seen


def test_groups_0a_ps():
    g = rds.groups_0a(0xD3A2, "PIDRIVE")
    assert len(g) == 4
    assert all(x[0] == 0xD3A2 and x[2] == 0xE0CD for x in g)
    assert [x[1] & 0x3 for x in g] == [0, 1, 2, 3]
    assert g[0][3] == (ord("P") << 8) | ord("I")
    assert (g[0][1] >> 12) == 0


def test_groups_2a_rt_terminated():
    g = rds.groups_2a(0x1234, "Hallo", ab=1)
    assert (g[0][1] >> 12) == 2
    assert (g[0][1] >> 4) & 1 == 1
    text = "".join(chr(x[2] >> 8) + chr(x[2] & 0xFF) + chr(x[3] >> 8) + chr(x[3] & 0xFF) for x in g)
    assert text.startswith("Hallo\r")
    assert len(rds.groups_2a(0x1, "x" * 64)) == 16


def test_audio_tap_commands():
    assert audio_tap.build_cmd("carrier") is None
    tone = audio_tap.build_cmd("tone1k", stereo=False)
    assert any("sine=frequency=1000" in a for a in tone.argv)
    assert tone.argv[-2:] == ["wav", "-"]
    assert "-ac" in tone.argv and tone.argv[tone.argv.index("-ac") + 1] == "1"
    mir = audio_tap.build_cmd("mirror", stereo=True, monitor="alsa_output.x.monitor")
    assert "pulse" in mir.argv and "alsa_output.x.monitor" in mir.argv
    assert mir.env["PULSE_SERVER"].startswith("unix:")
    sil = audio_tap.build_cmd("silence", stereo=True)
    assert any("anullsrc" in a for a in sil.argv)
    raw = audio_tap.build_cmd("tone1k", raw_rate=48000, narrowband=True)
    assert raw.argv[-7:] == ["-ac", "1", "-ar", "48000", "-f", "s16le", "-"]
    with pytest.raises(ValueError):
        audio_tap.build_cmd("radio")


def test_audio_tap_announce_wav(tmp_path):
    wav = tmp_path / "ann.wav"
    wav.write_bytes(b"RIFF")
    cmd = audio_tap.build_cmd("announce", stereo=True, announce_wav=str(wav))
    assert str(wav) in cmd.argv
    assert any(a.startswith("adelay=500") for a in cmd.argv)
    assert cmd.argv[cmd.argv.index("-t") + 1] == "5"
    assert cmd.argv[-2:] == ["wav", "-"]


def test_audio_tap_announce_beep_fallback(tmp_path):
    cmd = audio_tap.build_cmd("announce", raw_rate=48000, announce_wav=str(tmp_path / "fehlt.wav"))
    assert any("sine=frequency=1000" in a and "duration=1" in a for a in cmd.argv)
    assert cmd.argv[-7:] == ["-ac", "1", "-ar", "48000", "-f", "s16le", "-"]


def test_pifmrds_args():
    b = PiFmRdsBackend()
    cfg = {"freq_effective_mhz": 88.4, "rds": {"enabled": True, "pi": "D3A2"},
           "rds_ps": "PIDRIVE", "rds_rt": "Hallo"}
    argv = b.build_tx_cmd(cfg, with_audio=True)
    assert argv[1:3] == ["-freq", "88.40"]
    assert ["-audio", "-"] == argv[3:5]
    assert "-ctl" in argv and CTL_FIFO in argv
    argv2 = b.build_tx_cmd(dict(cfg, rds={"enabled": False}), with_audio=False)
    assert "-audio" not in argv2 and "-ps" not in argv2
    caps = b.capabilities()
    assert caps["pins"] == [4] and caps["bands"] == ["ukw"] and caps["rds"] is True


def test_rpitx_args_and_pmr_gate():
    b = RpitxBackend()
    cfg = {"freq_effective_mhz": 446.00625, "band": "pmr446", "source": "carrier", "mode": "cable"}
    assert b.build_tx_cmd(cfg, with_audio=False)[1:] == ["-f", "446006250"]
    argv = b.build_tx_cmd(cfg, with_audio=True)
    assert "-t" in argv and "i16" in argv and "446006250" in argv
    with pytest.raises(RuntimeError):
        b.start(cfg, None)
    a = b.build_audio(dict(cfg, source="tone1k"))
    assert "nbfm_mod" in a.argv[-1] and "--dev 2500" in a.argv[-1]
    assert b.build_audio(cfg) is None
    assert "pmr446" in b.capabilities()["bands"]


def test_chip_frequency_helpers():
    assert backend_chip.qn8027_channel(88.0) == 240
    assert backend_chip.qn8027_channel(108.0) == 640
    assert backend_chip.si4713_freq_units(88.4) == 8840
    with pytest.raises(ValueError):
        backend_chip.si4713_freq_units(120.0)


def test_nbfm_modulator_constant_envelope():
    k = 2 * math.pi * 2500 / 48000
    iq, phase = nbfm_mod.modulate_py([0, 16384, -16384, 32767], 0.0, k)
    assert len(iq) == 16
    vals = struct.unpack("<8h", iq)
    for i in range(0, 8, 2):
        mag = math.hypot(vals[i], vals[i + 1])
        assert mag == pytest.approx(nbfm_mod.AMP, rel=0.01)
    assert -math.pi <= phase <= math.pi
