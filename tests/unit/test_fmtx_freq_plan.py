"""FM-Sender: Bandgrenzen, PMR-Formel, Oberwellen, RTL-Konflikt, freie Frequenz (ohne Hardware)."""
from __future__ import annotations

import pytest

from modules.tx import freq_plan as fp


@pytest.mark.parametrize("n,mhz", [(1, 446.00625), (8, 446.09375), (16, 446.19375)])
def test_pmr_channel_formula(n, mhz):
    assert fp.pmr_channel_mhz(n) == pytest.approx(mhz, abs=1e-6)


@pytest.mark.parametrize("n", [0, 17, -1, "x", None])
def test_pmr_channel_invalid(n):
    with pytest.raises(ValueError):
        fp.pmr_channel_mhz(n)


def test_pmr_channels_list():
    ch = fp.pmr_channels()
    assert len(ch) == 16
    assert ch[0]["channel"] == 1 and ch[-1]["channel"] == 16


@pytest.mark.parametrize("f", [87.5, 88.4, 92.95, 108.0])
def test_validate_ukw_ok(f):
    ok, err, s = fp.validate_ukw(f)
    assert ok, err
    assert s == pytest.approx(f)


@pytest.mark.parametrize("f", [87.45, 108.05, 50, "abc", None, float("nan")])
def test_validate_ukw_out_of_range(f):
    ok, _err, _s = fp.validate_ukw(f)
    assert not ok


def test_validate_ukw_raster_suggests_snap():
    ok, err, s = fp.validate_ukw(88.43)
    assert not ok
    assert s == pytest.approx(88.45)
    assert "50 kHz" in err


def test_tx_freq_mhz_by_band():
    assert fp.tx_freq_mhz("ukw", 88.4) == pytest.approx(88.4)
    assert fp.tx_freq_mhz("pmr446", pmr_channel=1) == pytest.approx(446.00625)
    with pytest.raises(ValueError):
        fp.tx_freq_mhz("lw", 0.2)


def test_second_harmonic_in_dab_band3():
    hits = fp.harmonics_conflicts(88.0)
    chans = {h["dab_channel"] for h in hits if h["order"] == 2}
    assert "5B" in chans
    assert all(h["order"] == 2 for h in hits)


def test_third_harmonic_outside_band3():
    hits = fp.harmonics_conflicts(100.0, orders=(3,))
    assert hits == []


def test_active_dab_block_blocks_start():
    p = fp.plan("ukw", 104.45, active_dab_channel="10C")
    # 2 × 104.45 = 208.9 MHz → 9D (208.064) innerhalb Toleranz, 10C (213.360) nicht
    assert p["ok"]
    p2 = fp.plan("ukw", 104.45, active_dab_channel="9D")
    assert not p2["ok"]
    assert any("9D" in e for e in p2["errors"])
    p3 = fp.plan("ukw", 104.45, active_dab_channel="9D", block_on_dab=False)
    assert p3["ok"]
    assert any("9D" in w for w in p3["warnings"])


def test_rtl_conflict():
    assert fp.rtl_conflict(88.4, 88.9) == {"rx_mhz": 88.9, "delta_mhz": 0.5}
    assert fp.rtl_conflict(88.4, 90.0) is None
    assert fp.rtl_conflict(88.4, None) is None
    p = fp.plan("ukw", 88.4, rtl_rx_mhz=88.0)
    assert not p["ok"]


def test_pi5_blocked_pi4_hint():
    p5 = fp.plan("ukw", 88.4, pi_model="Raspberry Pi 5 Model B Rev 1.0")
    assert not p5["ok"]
    p4 = fp.plan("ukw", 95.0, pi_model="Raspberry Pi 4 Model B Rev 1.4")
    assert p4["ok"]
    assert any("93" in w for w in p4["warnings"])
    p4low = fp.plan("ukw", 88.0, pi_model="Raspberry Pi 4 Model B Rev 1.4")
    assert not any("93" in w for w in p4low["warnings"])


def test_pmr_plan_warns():
    p = fp.plan("pmr446", pmr_channel=3)
    assert p["freq_mhz"] == pytest.approx(446.03125)
    assert any("PMR446" in w for w in p["warnings"])


def test_suggest_free_avoids_occupied():
    peaks = [{"freq_mhz": 88.0, "mean_db": -20}, {"freq_mhz": 89.0, "db": -25}]
    free = fp.suggest_free(peaks, 87.5, 90.0, top_n=10)
    assert free
    for x in free:
        assert abs(x["freq_mhz"] - 88.0) >= fp.FREE_MIN_SPACING_MHZ - 1e-9
        assert abs(x["freq_mhz"] - 89.0) >= fp.FREE_MIN_SPACING_MHZ - 1e-9
    assert free[0]["score"] >= free[-1]["score"]


def test_suggest_free_prefers_below():
    free = fp.suggest_free([], 92.0, 94.0, top_n=3, prefer_below_mhz=93.0)
    assert all(x["freq_mhz"] < 93.0 for x in free)


def test_suggest_free_empty_range():
    assert fp.suggest_free([], 95.0, 90.0) == []
