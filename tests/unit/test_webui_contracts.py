"""webui check / selftest als pytest."""
from __future__ import annotations

from web.webui_check import run_check, run_selftest


def test_webui_check_clean():
    # write_inventory=False: CI soll routes.json nicht still überschreiben
    assert run_check(write_inventory=False) == 0


def test_webui_selftest_clean():
    assert run_selftest() == 0
