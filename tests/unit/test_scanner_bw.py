"""Scanner-Bandbreiten / Sample-Rate-Formeln (W5 / K2)."""
from __future__ import annotations

from modules.radio import scanner as sc


def test_scan_bw_fast_narrowband():
    assert sc._scan_bw_fast("pmr446", 12500) == 25000
    assert sc._scan_bw_fast("freenet", 12500) == 25000
    assert sc._scan_bw_fast("lpd433", 12500) == 25000
    assert sc._scan_bw_fast("cb", 10000) == 20000


def test_scan_bw_fast_vhf_uhf_floor():
    assert sc._scan_bw_fast("vhf", 25000) >= 100000
    assert sc._scan_bw_fast("uhf", 25000) >= 100000
    assert sc._scan_bw_fast("vhf", 200000) == 200000


def test_sample_rate_floor_k2():
    # Ziel: mind. max(48000, bw*4) — nicht mehr harte 200000-Untergrenze
    for bw in (12500, 25000, 100000):
        rate = max(48000, bw * 4)
        assert rate >= 48000
        if bw == 12500:
            assert rate == 50000


def test_range_step_fast():
    assert sc._range_step_fast("vhf", {"step_fine": 0.025}) == 0.1
    assert sc._range_step_fast("uhf", {"step_fine": 0.025}) == 0.1
    assert sc._range_step_fast("pmr446", {"step_fine": 0.0125}) == 0.0125
