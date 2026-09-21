"""usb_reset: sysfs-Pfad + _run()-dict (kein .splitlines auf dem dict)."""
from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

from modules.radio import rtlsdr


def test_find_rtl_sysfs_path_reads_vendor_product(tmp_path):
    d = tmp_path / "1-1.2"
    d.mkdir()
    (d / "idVendor").write_text("0bda\n")
    (d / "idProduct").write_text("2838\n")
    with patch("glob.glob", return_value=[str(d)]):
        assert rtlsdr._find_rtl_sysfs_path() == str(d)


def test_find_rtl_sysfs_path_skips_other(tmp_path):
    d = tmp_path / "1-1.3"
    d.mkdir()
    (d / "idVendor").write_text("1a86\n")
    (d / "idProduct").write_text("55d3\n")
    with patch("glob.glob", return_value=[str(d)]):
        assert rtlsdr._find_rtl_sysfs_path() is None


def test_usb_reset_uses_sysfs_not_dict_splitlines():
    """Regression: früher raw=_run(...); raw.splitlines() → AttributeError."""
    steps = []

    def fake_run(args, timeout=5):
        # dict wie echtes _run — darf nie .splitlines() bekommen
        return {"ok": True, "rc": 0, "out": "Bus 001 Device 005: ID 0bda:2838 Realtek\n",
                "err": "", "timeout": False}

    auth = {"v": "0"}

    def fake_set(path, value):
        steps.append(f"auth={value}")
        auth["v"] = value

    with patch.object(rtlsdr, "_run", side_effect=fake_run), \
         patch.object(rtlsdr, "_find_rtl_sysfs_path", return_value="/sys/bus/usb/devices/1-1.2"), \
         patch.object(rtlsdr, "_set_authorized", side_effect=fake_set), \
         patch.object(rtlsdr, "clear_stale_lock"), \
         patch.object(rtlsdr, "detect_usb", return_value={"present": True}), \
         patch.object(rtlsdr, "diagnose"), \
         patch("time.sleep"), \
         patch("builtins.open", mock_open(read_data="1\n")):
        r = rtlsdr.usb_reset()

    assert "usb path search error" not in " ".join(r["steps"])
    assert any("usb path:" in s for s in r["steps"])
    assert "authorized=0 (unbind)" in r["steps"]
    assert "authorized=1 (rebind)" in r["steps"]
    assert r["ok"] is True
    assert auth["v"] == "1"
