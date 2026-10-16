"""FM-Sender: Validierung, Consent, Patch-Logik (ohne Hardware)."""
from __future__ import annotations

from modules.tx import tx_manager as tm


def _cfg(**kw):
    c = tm.get_cfg({})
    c.update(kw)
    return c


def test_get_cfg_deep_merges_rds():
    c = tm.get_cfg({"fm_tx": {"freq_mhz": 90.0, "rds": {"ps": "TEST"}}})
    assert c["freq_mhz"] == 90.0
    assert c["rds"]["ps"] == "TEST"
    assert c["rds"]["pi"] == "D3A2"
    assert c["max_runtime_min"] == 60


def test_validate_defaults_ok():
    errs, c = tm.validate_cfg(tm.get_cfg({}))
    assert errs == []
    assert c["source"] == "mirror"


def test_validate_rejects_bad_values():
    errs, _ = tm.validate_cfg(_cfg(freq_mhz=120.0, source="radio", mode="moon",
                                   max_runtime_min=0, preemph_us=60))
    joined = " ".join(errs)
    assert "UKW" in joined and "source" in joined and "mode" in joined
    assert "max_runtime_min" in joined and "preemph_us" in joined


def test_validate_rds_texts_trimmed_and_pi_hex():
    c = _cfg()
    c["rds"] = {"ps": "123456789", "rt": "x" * 80, "pi": "zz12"}
    errs, out = tm.validate_cfg(c)
    assert any("PI" in e for e in errs)
    assert out["rds"]["ps"] == "12345678"
    assert len(out["rds"]["rt"]) == 64


def test_validate_pin_against_caps():
    errs, _ = tm.validate_cfg(_cfg(pin=17), caps={"pins": [4], "bands": ["ukw"]})
    assert any("GPIO17" in e for e in errs)


def test_validate_source_against_caps():
    errs, _ = tm.validate_cfg(_cfg(source="mirror"), caps={"sources": ["tone1k"]})
    assert any("Quelle" in e for e in errs)


def test_tone_alias():
    _errs, c = tm.validate_cfg(_cfg(source="tone"))
    assert c["source"] == "tone1k"


def test_consent_required():
    ok, why = tm.consent_check(_cfg())
    assert not ok and "Consent" in why


def test_consent_bound_to_mode():
    c = tm.give_consent(_cfg(), "cable", now=1000)
    assert tm.consent_check(c) == (True, "")
    c["mode"] = "antenna"
    ok, why = tm.consent_check(c)
    assert not ok and "antenna" in why


def test_pmr_only_lab_dummy_and_rpitx():
    c = tm.give_consent(_cfg(band="pmr446", backend="rpitx"), "cable", now=1)
    ok, why = tm.consent_check(c)
    assert not ok and "Labor" in why
    c = tm.give_consent(_cfg(band="pmr446", backend="pifmrds"), "lab_dummy", now=1)
    ok, why = tm.consent_check(c)
    assert not ok and "rpitx" in why
    c = tm.give_consent(_cfg(band="pmr446", backend="rpitx"), "lab_dummy", now=1)
    assert tm.consent_check(c)[0]


def test_apply_patch_confirm_sets_consent():
    errs, c = tm.apply_patch(_cfg(), {"mode": "antenna", "confirm": True}, now=42)
    assert errs == []
    assert c["mode"] == "antenna" and c["consent_mode"] == "antenna" and c["consent_ts"] == 42


def test_apply_patch_mode_without_confirm_invalidates():
    _e, c = tm.apply_patch(_cfg(), {"mode": "lab_dummy", "confirm": True}, now=1)
    _e, c2 = tm.apply_patch(c, {"mode": "antenna"})
    assert not tm.consent_check(c2)[0]


def test_apply_patch_pmr_switches_backend():
    errs, c = tm.apply_patch(_cfg(), {"band": "pmr446", "pmr_channel": 5})
    assert errs == []
    assert c["backend"] == "rpitx"
    errs, c2 = tm.apply_patch(c, {"band": "ukw"})
    assert errs == []
    assert c2["backend"] == "pifmrds"


def test_apply_patch_error_keeps_old():
    old = _cfg()
    errs, c = tm.apply_patch(old, {"freq_mhz": 200})
    assert errs
    assert c == old


def test_check_start_collects_errors_and_warnings():
    c = tm.give_consent(_cfg(enabled=True), "lab_dummy", now=1)
    caps = {"available": True, "pins": [4], "bands": ["ukw"]}
    ctx = {"pi_model": "Raspberry Pi 4 Model B", "dab_channel": "", "rtl_rx_mhz": None,
           "control_context": "radio_dab"}
    r = tm.check_start(c, caps, ctx)
    assert r["ok"], r["errors"]
    assert any("Klinke" in w for w in r["warnings"])
    assert any("DAB" in w for w in r["warnings"])
    r2 = tm.check_start(c, {"available": False, "why": "fehlt"}, ctx)
    assert not r2["ok"]
    assert any("fehlt" in e for e in r2["errors"])


def test_autostart_validation_and_patch():
    _e, c = tm.validate_cfg(_cfg(autostart="boot-only"))
    assert c["autostart"] == "boot_only"
    errs, _ = tm.validate_cfg(_cfg(autostart="sometimes"))
    assert any("autostart" in e for e in errs)
    errs, c2 = tm.apply_patch(_cfg(), {"autostart": "always"})
    assert errs == [] and c2["autostart"] == "always"


def test_default_freq_91_warns_dab_6a():
    c = tm.give_consent(_cfg(enabled=True), "lab_dummy", now=1)
    assert c["freq_mhz"] == 91.0
    ctx = {"pi_model": "Raspberry Pi 4 Model B", "dab_channel": "", "rtl_rx_mhz": None,
           "control_context": "idle"}
    r = tm.check_start(c, {"available": True, "pins": [4], "bands": ["ukw"]}, ctx)
    assert r["ok"], r["errors"]
    assert any("6A" in w for w in r["warnings"])


def test_gather_context_parses_status():
    ctx = tm.gather_context(
        {"last_dab_station": {"channel": "11D"}},
        {"control_context": "radio_fm", "radio_name": "FM: Bayern 3 (99.4 MHz)"},
    )
    assert ctx["rtl_rx_mhz"] == 99.4 and ctx["dab_channel"] == ""
    ctx2 = tm.gather_context({"last_dab_station": {"channel": "11D"}},
                             {"control_context": "radio_dab"})
    assert ctx2["dab_channel"] == "11D" and ctx2["rtl_rx_mhz"] is None
