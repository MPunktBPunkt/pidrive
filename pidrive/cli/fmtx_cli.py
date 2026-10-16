"""fmtx_cli.py — pidrivectl fmtx … (FM-Sender, docs/planung/KONZEPT-FM-TX.md)

Schreibt Settings (fm_tx) und Kommandos an pidrive-fmtx.service,
liest /tmp/pidrive_fmtx_state.json. Senden selbst macht nur der Dienst.
"""
from __future__ import annotations

import json
import re
import time

from cli import format as fmt
from cli.service import EXIT_OK, EXIT_ERROR, EXIT_NOTFOUND, EXIT_OFFLINE, EXIT_BUSY

SELFTEST_FILE = "/tmp/pidrive_fmtx_selftest.json"
_MODE_ALIAS = {"lab": "lab_dummy", "lab_dummy": "lab_dummy", "dummy": "lab_dummy",
               "cable": "cable", "kabel": "cable", "antenna": "antenna", "antenne": "antenna"}


def _mods():
    from settings import load_settings, save_settings
    from modules.tx import tx_manager, freq_plan
    return load_settings, save_settings, tx_manager, freq_plan


def _patch(patch: dict, use_json: bool) -> int:
    load_settings, save_settings, tm, _fp = _mods()
    settings = load_settings()
    cfg = tm.get_cfg(settings)
    errs, new_cfg = tm.apply_patch(cfg, patch)
    if errs:
        for e in errs:
            fmt.err(e)
        return EXIT_NOTFOUND
    tm.save_cfg(settings, new_cfg, save_settings)
    st = tm.read_state()
    if st.get("state") in ("starting", "on") and tm.service_alive(st):
        tm.send_command("reload")
    if use_json:
        fmt.print_json({"ok": True, "config": new_cfg})
    else:
        f = tm.effective_freq(new_cfg)
        fmt.out(f"OK  band={new_cfg['band']} f={f} MHz backend={new_cfg['backend']} "
                f"pin=GPIO{new_cfg['pin']} source={new_cfg['source']} mode={new_cfg['mode']} "
                f"autostart={new_cfg.get('autostart')}")
        ok_c, why_c = tm.consent_check(new_cfg)
        if not ok_c:
            fmt.out(f"Hinweis: {why_c}")
    return EXIT_OK


def _print_status(use_json: bool) -> int:
    load_settings, _ss, tm, _fp = _mods()
    st = tm.read_state()
    alive = tm.service_alive(st)
    cfg = tm.get_cfg(load_settings())
    if use_json:
        fmt.print_json({"state": st, "service_alive": alive, "config": cfg})
        return EXIT_OK
    if not alive:
        fmt.out("Dienst: pidrive-fmtx.service antwortet nicht (sudo systemctl start pidrive-fmtx)")
    fmt.out(f"Zustand: {st.get('state', 'off')}" + (f"  Fehler: {st['error']}" if st.get("error") else ""))
    f = st.get("freq_mhz") if st.get("state") in ("on", "starting") else tm.effective_freq(cfg)
    fmt.out(f"Frequenz: {f} MHz ({st.get('band') or cfg['band']})  Backend: {st.get('backend') or cfg['backend']}  "
            f"Pin: GPIO{st.get('pin') or cfg['pin']}")
    fmt.out(f"Quelle: {cfg['source']}  Stereo: {cfg['stereo']}  Betriebsart: {cfg['mode']}  "
            f"Laufzeit max: {cfg['max_runtime_min']} min"
            + (f"  Rest: {int(st['runtime_left_s']) // 60} min" if st.get("runtime_left_s") is not None else ""))
    r = cfg["rds"]
    fmt.out(f"RDS: {'an' if r['enabled'] else 'aus'}  PI={r['pi']}  PS='{st.get('rds_ps') or r['ps']}'  "
            f"RT({r['rt_mode']})='{st.get('rds_rt') or r['rt']}'")
    ok_c, why_c = tm.consent_check(cfg)
    fmt.out("Consent: " + ("ok" if ok_c else why_c))
    fmt.out(f"Autostart: {cfg.get('autostart', 'off')}" + ("  (Ansage läuft)" if st.get("announcing") else ""))
    for w in st.get("warnings") or []:
        fmt.out(f"⚠ {w}")
    if st.get("throttled"):
        fmt.out(f"Throttling: {st['throttled']}")
    return EXIT_OK


def _start(use_json: bool, cmd: str = "start") -> int:
    load_settings, save_settings, tm, _fp = _mods()
    settings = load_settings()
    cfg = tm.get_cfg(settings)
    if not cfg.get("enabled"):
        cfg["enabled"] = True
        tm.save_cfg(settings, cfg, save_settings)
        settings = load_settings()
    try:
        caps = tm.get_backend(cfg["backend"]).capabilities()
    except Exception as e:
        caps = {"available": False, "why": str(e)}
    chk = tm.check_start(cfg, caps, tm.gather_context(settings))
    for w in chk["warnings"]:
        if not use_json:
            fmt.out(f"⚠ {w}")
    if not chk["ok"]:
        if use_json:
            fmt.print_json({"ok": False, "errors": chk["errors"], "warnings": chk["warnings"]})
        for e in chk["errors"]:
            fmt.err(e)
        return EXIT_BUSY
    if not tm.service_alive():
        fmt.err("pidrive-fmtx.service läuft nicht (sudo systemctl start pidrive-fmtx)")
        return EXIT_OFFLINE
    tm.send_command(cmd)
    for _ in range(20):
        time.sleep(0.25)
        st = tm.read_state()
        if st.get("state") in ("on", "error"):
            break
    st = tm.read_state()
    if use_json:
        fmt.print_json({"ok": st.get("state") == "on", "state": st})
    else:
        fmt.out(f"Zustand: {st.get('state')}" + ("  (Ansage läuft)" if st.get("announcing") else "")
                + (f"  Fehler: {st['error']}" if st.get("error") else ""))
    return EXIT_OK if st.get("state") == "on" else EXIT_ERROR


def _parse_range(text, default=(87.5, 108.0)):
    if not text:
        return default
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[-:]\s*([0-9]+(?:\.[0-9]+)?)\s*$", text)
    if not m:
        raise ValueError("Range ungültig — erwartet z.B. 87.5-93")
    return float(m.group(1)), float(m.group(2))


def _rtl_gate() -> str:
    try:
        from modules import source_state as _ss_gate
        ok_gate, why = _ss_gate.rtl_capture_gate()
        return "" if ok_gate else why
    except Exception:
        return ""


def _scan_free(args, use_json: bool) -> int:
    load_settings, _ss, tm, fp = _mods()
    try:
        start, stop = _parse_range(getattr(args, "range", None), (87.5, 93.0))
    except ValueError as e:
        fmt.err(str(e))
        return EXIT_NOTFOUND
    why = _rtl_gate()
    if why:
        fmt.err(f"Abbruch: {why}")
        return EXIT_BUSY
    settings = load_settings()
    from modules.radio import spectrum as _spmod
    ppm = int(settings.get("ppm_correction", 0) or 0)
    if not use_json:
        fmt.out(f"Scan {start}–{stop} MHz (ppm={ppm}) …")
    r = _spmod.scan_fm_channels(start_mhz=start, stop_mhz=stop, top_n=50, ppm=ppm,
                                gain=25, avg_frames=int(settings.get("spectrum_avg", 2)))
    if not r.get("ok"):
        fmt.err("Scan-Fehler: " + str(r.get("error")))
        return EXIT_ERROR
    ctx = tm.gather_context(settings)
    prefer = fp.PI4_RECOMMENDED_MAX_MHZ if "Raspberry Pi 4" in ctx.get("pi_model", "") else None
    free = fp.suggest_free(r.get("peaks") or [], start, stop, top_n=int(args.n or 5),
                           active_dab_channel=ctx.get("dab_channel", ""), prefer_below_mhz=prefer)
    if use_json:
        fmt.print_json({"ok": True, "occupied": r.get("peaks"), "free": free})
        return EXIT_OK
    fmt.out(f"Belegt: {len(r.get('peaks') or [])} Kanäle (Schwelle {r.get('thresh_db')} dB)")
    for i, x in enumerate(free, 1):
        dab = f"  2f→{','.join(x['dab_hits'])}" if x["dab_hits"] else ""
        fmt.out(f"  {i}. {x['freq_mhz']:.2f} MHz  Abstand {x['nearest_occupied_mhz']} MHz  "
                f"Score {x['score']}{dab}")
    if free:
        fmt.out(f"Übernehmen: pidrivectl fmtx freq {free[0]['freq_mhz']:.2f}")
    return EXIT_OK


def _selftest(args, use_json: bool) -> int:
    """TX an (falls aus), RTL-SDR peek auf f, 2f, 3f, Report, TX wieder aus."""
    load_settings, _ss, tm, _fp = _mods()
    cfg = tm.get_cfg(load_settings())
    if cfg["band"] != "ukw":
        fmt.err("selftest nur für UKW (PMR446: Laboraufbau manuell messen)")
        return EXIT_NOTFOUND
    why = _rtl_gate()
    if why:
        fmt.err(f"Abbruch: {why}")
        return EXIT_BUSY
    f = tm.effective_freq(cfg)
    st0 = tm.read_state()
    started_here = False
    if st0.get("state") != "on":
        rc = _start(use_json=False)
        if rc != EXIT_OK:
            return rc
        started_here = True
    time.sleep(float(args.settle or 3))
    from modules.radio import spectrum as _spmod
    ppm = int(load_settings().get("ppm_correction", 0) or 0)
    report = {"ts": int(time.time()), "freq_mhz": f, "mode": cfg["mode"], "pin": cfg["pin"],
              "backend": cfg["backend"], "source": cfg["source"], "measurements": []}
    for order in (1, 2, 3):
        fo = round(f * order, 3)
        r = _spmod.peek_fm_channel(fo, ppm=ppm, gain=int(args.gain), avg_frames=2)
        report["measurements"].append({
            "order": order, "freq_mhz": fo, "ok": r.get("ok"),
            "detected": r.get("detected"), "snr_db": r.get("snr_db"),
            "peak_db": (r.get("energy") or {}).get("peak_db"), "error": r.get("error"),
        })
        if not use_json:
            fmt.out(f"  {order}×  {fo:8.3f} MHz  detected={r.get('detected')}  snr={r.get('snr_db')} dB  "
                    f"peak={(r.get('energy') or {}).get('peak_db')} dB" +
                    (f"  Fehler: {r.get('error')}" if not r.get("ok") else ""))
    if started_here:
        tm.send_command("stop")
    m = report["measurements"]
    carrier_ok = bool(m and m[0].get("detected"))
    h2 = m[1].get("peak_db") if len(m) > 1 else None
    h1 = m[0].get("peak_db") if m else None
    report["carrier_detected"] = carrier_ok
    report["h2_rel_db"] = round(h2 - h1, 1) if (h1 is not None and h2 is not None) else None
    report["note"] = ("RTL-Pegel sind relativ (dBFS, Gain fest) — kein kalibrierter Leistungswert. "
                      "Für Lab-Gate E-1 mit Dämpfungsglied messen.")
    try:
        with open(SELFTEST_FILE, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    except Exception:
        pass
    if use_json:
        fmt.print_json(report)
    else:
        fmt.out(f"Träger erkannt: {'JA' if carrier_ok else 'NEIN'}  "
                f"2. Harmonische relativ: {report['h2_rel_db']} dB")
        fmt.out(f"Report: {SELFTEST_FILE}")
    return EXIT_OK if carrier_ok else EXIT_ERROR


def run(args, use_json: bool = False) -> int:
    c = getattr(args, "fmtx_cmd", None)
    if not c or c == "status":
        return _print_status(use_json)
    if c == "start":
        return _start(use_json)
    if c == "stop":
        _ls, _ss, tm, _fp = _mods()
        ok = tm.send_command("stop")
        if use_json:
            fmt.print_json({"ok": ok})
        else:
            fmt.out("Stopp gesendet" if ok else "Stopp fehlgeschlagen")
        return EXIT_OK if ok else EXIT_ERROR
    if c == "freq":
        return _patch({"band": "ukw", "freq_mhz": args.mhz}, use_json)
    if c == "band":
        p = {"band": args.band}
        if args.channel is not None:
            p["pmr_channel"] = args.channel
        return _patch(p, use_json)
    if c == "source":
        return _patch({"source": "tone1k" if args.source == "tone" else args.source}, use_json)
    if c == "pin":
        return _patch({"pin": args.gpio}, use_json)
    if c == "backend":
        return _patch({"backend": args.name}, use_json)
    if c == "runtime":
        return _patch({"max_runtime_min": args.minutes}, use_json)
    if c == "autostart":
        return _patch({"autostart": args.autostart.replace("-", "_")}, use_json)
    if c == "announce":
        return _start(use_json, cmd="announce")
    if c == "mode":
        mode = _MODE_ALIAS.get(args.mode.lower())
        if not mode:
            fmt.err("mode: lab | cable | antenna")
            return EXIT_NOTFOUND
        if not args.confirm:
            fmt.out("Betriebsart nur mit --confirm (Verantwortung für Aufbau, Leistung, Rechtslage).")
            if mode == "antenna":
                fmt.out("Antenne: Tiefpass am Pin ist Pflicht, SRD-Grenzwert (~50 nW ERP) beachten.")
            return EXIT_NOTFOUND
        return _patch({"mode": mode, "confirm": True}, use_json)
    if c == "rds":
        what = args.what
        val = " ".join(args.value or [])
        if what == "ps":
            return _patch({"rds": {"ps": val}}, use_json)
        if what == "rt":
            return _patch({"rds": {"rt": val, "rt_mode": "fixed"}}, use_json)
        if what == "pi":
            return _patch({"rds": {"pi": val}}, use_json)
        if what == "auto":
            on = val.lower() in ("on", "an", "1", "true", "")
            return _patch({"rds": {"rt_mode": "auto" if on else "fixed"}}, use_json)
        if what == "rotate":
            return _patch({"rds": {"ps_rotate": val.lower() in ("on", "an", "1", "true")}}, use_json)
        if what in ("on", "off"):
            return _patch({"rds": {"enabled": what == "on"}}, use_json)
        fmt.err("rds: ps <text> | rt <text> | pi <hex> | auto on|off | rotate on|off | on | off")
        return EXIT_NOTFOUND
    if c == "plan":
        load_settings, _ss, tm, fp = _mods()
        settings = load_settings()
        cfg = tm.get_cfg(settings)
        ctx = tm.gather_context(settings)
        f = args.mhz if args.mhz is not None else cfg.get("freq_mhz")
        band = "ukw" if args.mhz is not None else cfg["band"]
        p = fp.plan(band, f, cfg.get("pmr_channel"), pi_model=ctx["pi_model"],
                    active_dab_channel=ctx["dab_channel"], rtl_rx_mhz=ctx["rtl_rx_mhz"],
                    block_on_dab=cfg.get("block_on_dab", True))
        if use_json:
            fmt.print_json(p)
        else:
            fmt.out(f"f={p['freq_mhz']} MHz  ok={p['ok']}")
            for h in p["harmonics"]:
                fmt.out(f"  {h['order']}×  {h['freq_mhz']:.3f} MHz")
            for d in p["dab"]:
                fmt.out(f"  DAB {d['dab_channel']} ({d['dab_center_mhz']} MHz) ← {d['order']}. Harmonische"
                        + ("  [aktiv]" if d["active"] else ""))
            for e in p["errors"]:
                fmt.out(f"✗ {e}")
            for w in p["warnings"]:
                fmt.out(f"⚠ {w}")
        return EXIT_OK
    if c == "scan-free":
        return _scan_free(args, use_json)
    if c == "selftest":
        return _selftest(args, use_json)
    fmt.err(f"Unbekanntes fmtx-Subkommando: {c}")
    return EXIT_NOTFOUND
