#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes_fmtx.py — FM-Sender API (docs/planung/KONZEPT-FM-TX.md)

Der Sender läuft als root-Dienst pidrive-fmtx.service. Die Web-UI schreibt
nur Settings (fm_tx) und Kommandos (/tmp/pidrive_fmtx_cmd) und liest den
Zustand aus /tmp/pidrive_fmtx_state.json.
"""

import os
import sys
BASE_DIR_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR_API)

from flask import Blueprint, jsonify, request
from web.shared import *  # noqa: F401,F403

fmtx_bp = Blueprint("fmtx_bp", __name__)


def _mods():
    _base = str(BASE_DIR)
    if _base not in sys.path:
        sys.path.insert(0, _base)
    from settings import load_settings, save_settings
    from modules.tx import tx_manager, freq_plan
    return load_settings, save_settings, tx_manager, freq_plan


def _state_payload(tm):
    st = tm.read_state()
    st["service_alive"] = tm.service_alive(st)
    return st


@fmtx_bp.route("/api/fmtx/config", methods=["GET", "POST"])
def api_fmtx_config():
    try:
        load_settings, save_settings, tm, fp = _mods()
        settings = load_settings()
        cfg = tm.get_cfg(settings)
        if request.method == "POST":
            patch = request.get_json(silent=True) or {}
            errs, new_cfg = tm.apply_patch(cfg, patch)
            if errs:
                return jsonify({"ok": False, "error": "; ".join(errs), "errors": errs}), 400
            tm.save_cfg(settings, new_cfg, save_settings)
            cfg = new_cfg
            st = tm.read_state()
            if st.get("state") in ("starting", "on") and tm.service_alive(st):
                tm.send_command("reload")
        consent_ok, consent_why = tm.consent_check(cfg)
        return jsonify({
            "ok": True,
            "config": cfg,
            "consent_ok": consent_ok,
            "consent_why": consent_why,
            "capabilities": tm.all_capabilities(),
            "pmr_channels": fp.pmr_channels(),
            "limits": {
                "ukw_min": fp.UKW_MIN_MHZ, "ukw_max": fp.UKW_MAX_MHZ,
                "ukw_step": fp.UKW_STEP_MHZ, "pi4_max": fp.PI4_RECOMMENDED_MAX_MHZ,
            },
            "pi_model": fp.read_pi_model(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@fmtx_bp.route("/api/fmtx/start", methods=["POST"])
def api_fmtx_start():
    return _checked_command("start")


@fmtx_bp.route("/api/fmtx/announce", methods=["POST"])
def api_fmtx_announce():
    """Boot-Ansage manuell testen; der Sender geht danach immer aus."""
    return _checked_command("announce")


def _checked_command(cmd):
    try:
        load_settings, save_settings, tm, _fp = _mods()
        settings = load_settings()
        cfg = tm.get_cfg(settings)
        if not cfg.get("enabled"):
            cfg["enabled"] = True
            tm.save_cfg(settings, cfg, save_settings)
            settings = load_settings()
        try:
            caps = tm.get_backend(cfg.get("backend")).capabilities()
        except Exception as e:
            caps = {"available": False, "why": str(e)}
        chk = tm.check_start(cfg, caps, tm.gather_context(settings))
        if not chk["ok"]:
            return jsonify({"ok": False, "error": "; ".join(chk["errors"]),
                            "errors": chk["errors"], "warnings": chk["warnings"]}), 409
        st = tm.read_state()
        if not tm.service_alive(st):
            return jsonify({"ok": False, "error": "pidrive-fmtx.service läuft nicht "
                            "(sudo systemctl start pidrive-fmtx)",
                            "warnings": chk["warnings"]}), 503
        tm.send_command(cmd)
        return jsonify({"ok": True, "warnings": chk["warnings"], "plan": chk["plan"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@fmtx_bp.route("/api/fmtx/stop", methods=["POST"])
def api_fmtx_stop():
    try:
        _ls, _ss, tm, _fp = _mods()
        ok = tm.send_command("stop")
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@fmtx_bp.route("/api/fmtx/state")
def api_fmtx_state():
    try:
        _ls, _ss, tm, _fp = _mods()
        return jsonify({"ok": True, "state": _state_payload(tm)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@fmtx_bp.route("/api/fmtx/rds", methods=["POST"])
def api_fmtx_rds():
    """Body: {ps, rt, rt_mode, enabled, pi, ps_rotate} — persistiert + live (reload)."""
    try:
        load_settings, save_settings, tm, _fp = _mods()
        body = request.get_json(silent=True) or {}
        settings = load_settings()
        cfg = tm.get_cfg(settings)
        rds_patch = {k: body[k] for k in ("ps", "rt", "rt_mode", "enabled", "pi", "ps_rotate") if k in body}
        if "rt" in rds_patch and "rt_mode" not in rds_patch:
            rds_patch["rt_mode"] = "fixed"
        errs, new_cfg = tm.apply_patch(cfg, {"rds": rds_patch})
        if errs:
            return jsonify({"ok": False, "error": "; ".join(errs), "errors": errs}), 400
        tm.save_cfg(settings, new_cfg, save_settings)
        tm.send_command("reload")
        return jsonify({"ok": True, "rds": new_cfg["rds"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _parse_peaks(raw):
    peaks = []
    for item in (raw or "").split(","):
        f, _, db = item.partition(":")
        try:
            peaks.append({"freq_mhz": float(f), "db": float(db or 0)})
        except ValueError:
            continue
    return peaks


@fmtx_bp.route("/api/fmtx/plan")
def api_fmtx_plan():
    """?band=ukw&f=88.4 | ?band=pmr446&ch=8 — Konflikte.
    ?suggest=1&start=87.5&stop=93&peaks=88.0:-30,90.1:-25 — freie Frequenzen
    (Peaks aus /api/spectrum/capture mode=range)."""
    try:
        load_settings, _ss, tm, fp = _mods()
        settings = load_settings()
        cfg = tm.get_cfg(settings)
        ctx = tm.gather_context(settings)
        band = (request.args.get("band") or cfg.get("band") or "ukw").lower()
        f = request.args.get("f", cfg.get("freq_mhz"))
        ch = request.args.get("ch", cfg.get("pmr_channel"))
        res = fp.plan(band, f, ch, pi_model=ctx.get("pi_model", ""),
                      active_dab_channel=ctx.get("dab_channel", ""),
                      rtl_rx_mhz=ctx.get("rtl_rx_mhz"),
                      block_on_dab=cfg.get("block_on_dab", True))
        out = {"ok": True, "plan": res, "context": ctx}
        if request.args.get("suggest") in ("1", "true", "yes"):
            start = float(request.args.get("start", fp.UKW_MIN_MHZ))
            stop = float(request.args.get("stop", fp.UKW_MAX_MHZ))
            prefer = fp.PI4_RECOMMENDED_MAX_MHZ if "Raspberry Pi 4" in ctx.get("pi_model", "") else None
            out["free"] = fp.suggest_free(
                _parse_peaks(request.args.get("peaks")), start, stop,
                top_n=int(request.args.get("n", 5)),
                active_dab_channel=ctx.get("dab_channel", ""),
                prefer_below_mhz=prefer,
            )
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
