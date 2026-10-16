"""tx_manager.py — FM-Sender: Konfiguration, Consent, Zustandsmaschine, IPC.

Zustände: off → starting → on → (off | error)
Boot-Ansage: announce() sendet ANNOUNCE_WINDOW_S lang die Quelle „announce“,
danach je nach fm_tx.autostart aus (boot_only) oder konfigurierte Quelle (always).
Läuft im root-Dienst pidrive-fmtx.service (modules/tx/service.py).
Web und CLI nutzen nur die Hilfsfunktionen (Settings, State lesen, Kommando senden).
"""
from __future__ import annotations

import copy
import json
import os
import re
import time

from modules.tx import freq_plan

STATE_FILE = "/tmp/pidrive_fmtx_state.json"
CMD_FILE = "/tmp/pidrive_fmtx_cmd"
STATUS_FILE = "/tmp/pidrive_status.json"

SOURCES = ("mirror", "tone1k", "carrier", "silence")
MODES = ("lab_dummy", "cable", "antenna")
BACKENDS = ("pifmrds", "rpitx", "chip")
RT_MODES = ("auto", "fixed")
AUTOSTART_MODES = ("off", "boot_only", "always")

ANNOUNCE_WINDOW_S = 6.0
ANNOUNCE_RT = "PiDrive is starting"

MAX_RESTARTS = 3
RESTART_WINDOW_S = 300

DEFAULTS = {
    "enabled": False,
    "band": "ukw",
    "freq_mhz": 91.0,
    "pmr_channel": 8,
    "pin": 4,
    "backend": "pifmrds",
    "source": "mirror",
    "stereo": True,
    "preemph_us": 50,
    "rds": {
        "enabled": True,
        "pi": "D3A2",
        "ps": "PIDRIVE",
        "rt_mode": "auto",
        "rt": "",
        "ps_rotate": False,
    },
    "mode": "lab_dummy",
    "consent_ts": 0,
    "consent_mode": "",
    "max_runtime_min": 60,
    "block_on_dab": True,
    "autostart": "boot_only",
    "chip": {
        "type": "qn8027",
        "bus": 1,
        "addr": "",
        "power": 0,
        "reset_gpio": None,
        "xtal_24mhz": False,
    },
}


# ── Konfiguration ────────────────────────────────────────────────────────────

def get_cfg(settings: dict | None) -> dict:
    """fm_tx aus Settings, tief mit DEFAULTS gemischt."""
    cfg = copy.deepcopy(DEFAULTS)
    raw = (settings or {}).get("fm_tx") or {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in ("rds", "chip") and isinstance(v, dict):
                cfg[k].update(v)
            elif k in cfg:
                cfg[k] = v
    return cfg


def _clean_text(s, maxlen: int) -> str:
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(s or ""))
    return s[:maxlen]


def validate_cfg(cfg: dict, caps: dict | None = None) -> tuple[list[str], dict]:
    """Prüft und normalisiert. Rückgabe (fehler, cfg_normalisiert)."""
    c = copy.deepcopy(cfg)
    errs: list[str] = []

    c["band"] = str(c.get("band") or "ukw").lower()
    if c["band"] not in freq_plan.BANDS:
        errs.append(f"band: nur {', '.join(freq_plan.BANDS)}")

    if c["band"] == "ukw":
        ok, err, f = freq_plan.validate_ukw(c.get("freq_mhz"))
        if not ok:
            errs.append(err)
        else:
            c["freq_mhz"] = f
    if c["band"] == "pmr446":
        try:
            freq_plan.pmr_channel_mhz(c.get("pmr_channel"))
            c["pmr_channel"] = int(c["pmr_channel"])
        except ValueError as e:
            errs.append(str(e))

    c["backend"] = str(c.get("backend") or "pifmrds").lower()
    if c["backend"] not in BACKENDS:
        errs.append(f"backend: nur {', '.join(BACKENDS)}")

    c["source"] = str(c.get("source") or "mirror").lower()
    if c["source"] == "tone":
        c["source"] = "tone1k"
    if c["source"] not in SOURCES:
        errs.append(f"source: nur {', '.join(SOURCES)}")

    c["mode"] = str(c.get("mode") or "lab_dummy").lower()
    if c["mode"] not in MODES:
        errs.append(f"mode: nur {', '.join(MODES)}")

    try:
        c["pin"] = int(c.get("pin"))
    except (TypeError, ValueError):
        errs.append(f"pin ungültig: {c.get('pin')!r}")
    if caps:
        pins = caps.get("pins") or []
        if pins and c.get("pin") not in pins:
            errs.append(f"Pin GPIO{c.get('pin')} vom Backend {c['backend']} nicht unterstützt (nur {pins})")
        bands = caps.get("bands") or []
        if bands and c["band"] not in bands:
            errs.append(f"Band {c['band']} vom Backend {c['backend']} nicht unterstützt")
        sources = caps.get("sources") or []
        if sources and c["source"] not in sources:
            errs.append(f"Quelle {c['source']} vom Backend {c['backend']} nicht unterstützt")

    try:
        c["preemph_us"] = int(c.get("preemph_us"))
        if c["preemph_us"] not in (50, 75):
            errs.append("preemph_us: nur 50 oder 75")
    except (TypeError, ValueError):
        errs.append("preemph_us ungültig")

    try:
        c["max_runtime_min"] = int(c.get("max_runtime_min"))
        if not 1 <= c["max_runtime_min"] <= 600:
            errs.append("max_runtime_min: 1–600")
    except (TypeError, ValueError):
        errs.append("max_runtime_min ungültig")

    c["stereo"] = bool(c.get("stereo"))
    c["enabled"] = bool(c.get("enabled"))
    c["block_on_dab"] = bool(c.get("block_on_dab", True))

    c["autostart"] = str(c.get("autostart") or "off").lower().replace("-", "_")
    if c["autostart"] not in AUTOSTART_MODES:
        errs.append(f"autostart: nur {', '.join(AUTOSTART_MODES)}")

    rds = c.get("rds") or {}
    pi = str(rds.get("pi") or "D3A2").upper()
    if not re.fullmatch(r"[0-9A-F]{4}", pi):
        errs.append(f"RDS PI: 4 Hex-Zeichen (war {pi!r})")
    rt_mode = str(rds.get("rt_mode") or "auto").lower()
    if rt_mode not in RT_MODES:
        errs.append("RDS rt_mode: auto oder fixed")
    c["rds"] = {
        "enabled": bool(rds.get("enabled", True)),
        "pi": pi,
        "ps": _clean_text(rds.get("ps") or "PIDRIVE", 8),
        "rt_mode": rt_mode,
        "rt": _clean_text(rds.get("rt"), 64),
        "ps_rotate": bool(rds.get("ps_rotate", False)),
    }
    chip = c.get("chip") or {}
    if str(chip.get("type") or "qn8027").lower() not in ("qn8027", "si4713"):
        errs.append("chip.type: qn8027 oder si4713")
    return errs, c


def consent_check(cfg: dict) -> tuple[bool, str]:
    """Consent und Betriebsart. PMR446 nur mit lab_dummy."""
    if cfg.get("band") == "pmr446":
        if cfg.get("mode") != "lab_dummy":
            return False, "PMR446 nur in Betriebsart Labor/Dummy-Load"
        if cfg.get("backend") != "rpitx":
            return False, "PMR446 nur mit Backend rpitx"
    try:
        ts = float(cfg.get("consent_ts") or 0)
    except (TypeError, ValueError):
        ts = 0
    if ts <= 0:
        return False, "Kein Consent gespeichert (Web-Dialog oder pidrivectl fmtx mode … --confirm)"
    if (cfg.get("consent_mode") or "") != cfg.get("mode"):
        return False, f"Consent gilt nicht für Betriebsart {cfg.get('mode')} — neu bestätigen"
    return True, ""


def give_consent(cfg: dict, mode: str, now: float | None = None) -> dict:
    c = copy.deepcopy(cfg)
    c["mode"] = mode
    c["consent_mode"] = mode
    c["consent_ts"] = int(now if now is not None else time.time())
    return c


_PATCH_KEYS = ("enabled", "band", "freq_mhz", "pmr_channel", "pin", "backend", "source",
               "stereo", "preemph_us", "mode", "max_runtime_min", "block_on_dab", "autostart")
_RDS_KEYS = ("enabled", "pi", "ps", "rt_mode", "rt", "ps_rotate")


def apply_patch(cfg: dict, patch: dict, now: float | None = None) -> tuple[list[str], dict]:
    """Teil-Update aus Web/CLI. confirm=true bestätigt die (neue) Betriebsart.

    Rückgabe (fehler, cfg). Bei Fehlern bleibt cfg unverändert.
    """
    c = copy.deepcopy(cfg)
    patch = patch or {}
    for k in _PATCH_KEYS:
        if k in patch:
            c[k] = patch[k]
    if isinstance(patch.get("rds"), dict):
        for k in _RDS_KEYS:
            if k in patch["rds"]:
                c["rds"][k] = patch["rds"][k]
    if isinstance(patch.get("chip"), dict):
        for k in DEFAULTS["chip"]:
            if k in patch["chip"]:
                c["chip"][k] = patch["chip"][k]
    if c.get("band") == "pmr446" and "backend" not in patch:
        c["backend"] = "rpitx"
    if c.get("band") == "ukw" and "backend" not in patch and c.get("backend") == "rpitx" \
            and cfg.get("band") == "pmr446":
        c["backend"] = "pifmrds"
    caps = None
    try:
        caps = get_backend(c.get("backend")).capabilities()
    except Exception:
        caps = None
    errs, c = validate_cfg(c, caps)
    if errs:
        return errs, copy.deepcopy(cfg)
    if patch.get("confirm"):
        c = give_consent(c, c["mode"], now)
    return [], c


def save_cfg(settings: dict, cfg: dict, save_settings) -> dict:
    s = dict(settings or {})
    s["fm_tx"] = copy.deepcopy(cfg)
    save_settings(s)
    return s


def effective_freq(cfg: dict) -> float | None:
    try:
        return freq_plan.tx_freq_mhz(cfg.get("band"), cfg.get("freq_mhz"), cfg.get("pmr_channel"))
    except ValueError:
        return None


# ── Kontext (Status anderer Module) ──────────────────────────────────────────

def _read_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


_FM_FREQ_RE = re.compile(r"\((\d{2,3}(?:\.\d+)?)\s*MHz\)")


def gather_context(settings: dict | None = None, status: dict | None = None) -> dict:
    """Pi-Modell, aktiver DAB-Block, RTL-Empfangsfrequenz."""
    status = status if status is not None else (_read_json(STATUS_FILE, {}) or {})
    settings = settings or {}
    ctx_name = str(status.get("control_context") or "idle")
    dab_channel = ""
    rtl_rx = None
    if ctx_name == "radio_dab":
        dab_channel = str((settings.get("last_dab_station") or {}).get("channel") or "")
    elif ctx_name in ("radio_fm", "scanner"):
        m = _FM_FREQ_RE.search(str(status.get("radio_name") or ""))
        if m:
            rtl_rx = float(m.group(1))
    return {
        "pi_model": freq_plan.read_pi_model(),
        "control_context": ctx_name,
        "dab_channel": dab_channel,
        "rtl_rx_mhz": rtl_rx,
    }


def check_start(cfg: dict, caps: dict | None, ctx: dict) -> dict:
    """Alle Startbedingungen. {"ok", "errors", "warnings", "plan", "cfg"}."""
    errs, c = validate_cfg(cfg, caps)
    warnings: list[str] = []
    if caps is not None and not caps.get("available", True):
        errs.append(f"Backend {c['backend']} nicht verfügbar: {caps.get('why') or '?'}")
    ok_c, why_c = consent_check(c)
    if not ok_c:
        errs.append(why_c)
    p = freq_plan.plan(
        c["band"], c.get("freq_mhz"), c.get("pmr_channel"),
        pi_model=ctx.get("pi_model", ""),
        active_dab_channel=ctx.get("dab_channel", ""),
        rtl_rx_mhz=ctx.get("rtl_rx_mhz"),
        block_on_dab=c.get("block_on_dab", True),
    )
    errs.extend(p["errors"])
    warnings.extend(p["warnings"])
    if c["mode"] == "antenna":
        warnings.append("Antennenbetrieb: Tiefpass am Pin ist Pflicht, SRD-Grenzwert beachten")
    if c["source"] == "mirror":
        warnings.append("Analoge Klinke (PWM) kann beim Senden gestört sein (Lab-Gate E-1)")
        if ctx.get("control_context") == "radio_dab":
            warnings.append("DAB lief vor dem Senderstart ALSA-direkt — DAB-Sender einmal neu "
                            "wählen, dann läuft der Ton über Pulse und wird gespiegelt")
    return {"ok": not errs, "errors": errs, "warnings": warnings, "plan": p, "cfg": c}


# ── IPC ──────────────────────────────────────────────────────────────────────

def read_state() -> dict:
    st = _read_json(STATE_FILE, None)
    if not isinstance(st, dict):
        return {"state": "off", "service": False}
    return st


def write_state(st: dict) -> None:
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
        try:
            os.chmod(STATE_FILE, 0o644)
        except Exception:
            pass
    except Exception:
        pass


def send_command(cmd: str) -> bool:
    """Eine Zeile an den Dienst (gleiches Append-Muster wie /tmp/pidrive_cmd)."""
    line = re.sub(r"[\r\n]", " ", str(cmd or "")).strip()
    if not line:
        return False
    try:
        with open(CMD_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception:
        return False


def service_alive(st: dict | None = None, max_age_s: float = 10.0) -> bool:
    st = st if st is not None else read_state()
    try:
        return (time.time() - float(st.get("ts") or 0)) <= max_age_s
    except (TypeError, ValueError):
        return False


def needs_pulse_monitor() -> bool:
    """True, wenn der Sender die Wiedergabe spiegelt (DAB muss dann über Pulse laufen)."""
    st = read_state()
    return (
        st.get("state") in ("starting", "on")
        and st.get("source") == "mirror"
        and service_alive(st)
    )


# ── Backends ─────────────────────────────────────────────────────────────────

def get_backend(name: str):
    name = (name or "pifmrds").lower()
    if name == "pifmrds":
        from modules.tx.backend_pifmrds import PiFmRdsBackend
        return PiFmRdsBackend()
    if name == "rpitx":
        from modules.tx.backend_rpitx import RpitxBackend
        return RpitxBackend()
    if name == "chip":
        from modules.tx.backend_chip import ChipBackend
        return ChipBackend()
    raise ValueError(f"Backend unbekannt: {name!r}")


def all_capabilities() -> dict:
    out = {}
    for n in BACKENDS:
        try:
            out[n] = get_backend(n).capabilities()
        except Exception as e:
            out[n] = {"available": False, "why": str(e), "bands": [], "pins": []}
    return out


# ── Zustandsmaschine (nur im Dienst) ─────────────────────────────────────────

class TxManager:
    def __init__(self, load_settings, save_settings=None, backend_factory=get_backend,
                 audio_cmd_factory=None, rds_factory=None, clock=time.time):
        self._load = load_settings
        self._save = save_settings
        self._backend_factory = backend_factory
        self._audio_cmd_factory = audio_cmd_factory
        self._clock = clock
        self.backend = None
        self.cfg = get_cfg(self._load())
        self.state = "off"
        self.error = ""
        self.warnings: list[str] = []
        self.started_ts = 0.0
        self.restarts: list[float] = []
        self.rds_ps = ""
        self.rds_rt = ""
        self.throttled = ""
        self.announce_until = 0.0
        self.announce_then = "off"
        if rds_factory is None:
            from modules.tx.rds import RdsAuto
            rds_factory = RdsAuto
        self.rds = rds_factory()

    # ── Status ──
    def snapshot(self) -> dict:
        now = self._clock()
        left = None
        if self.state in ("starting", "on") and self.started_ts:
            left = max(0, int(self.started_ts + self.cfg["max_runtime_min"] * 60 - now))
        bst = {}
        if self.backend is not None:
            try:
                bst = self.backend.status()
            except Exception as e:
                bst = {"err": str(e)}
        return {
            "ts": int(now),
            "service": True,
            "state": self.state,
            "error": self.error,
            "warnings": list(self.warnings),
            "backend": self.cfg.get("backend"),
            "band": self.cfg.get("band"),
            "freq_mhz": effective_freq(self.cfg),
            "pmr_channel": self.cfg.get("pmr_channel") if self.cfg.get("band") == "pmr446" else None,
            "pin": self.cfg.get("pin"),
            "source": "announce" if self.announce_until else self.cfg.get("source"),
            "announcing": bool(self.announce_until),
            "autostart": self.cfg.get("autostart"),
            "stereo": self.cfg.get("stereo"),
            "mode": self.cfg.get("mode"),
            "rds_enabled": self.cfg["rds"]["enabled"],
            "rds_pi": self.cfg["rds"]["pi"],
            "rds_ps": self.rds_ps,
            "rds_rt": self.rds_rt,
            "started_ts": int(self.started_ts) if self.started_ts else 0,
            "runtime_left_s": left,
            "restarts": len(self.restarts),
            "throttled": self.throttled,
            "proc": bst,
        }

    def publish(self) -> None:
        write_state(self.snapshot())

    # ── Aktionen ──
    def start(self, source_override: str | None = None, rt_override: str | None = None) -> bool:
        if self.state in ("starting", "on"):
            self.stop("restart")
        settings = self._load() or {}
        self.cfg = get_cfg(settings)
        try:
            backend = self._backend_factory(self.cfg.get("backend"))
            caps = backend.capabilities()
        except Exception as e:
            self._fail(f"Backend: {e}")
            return False
        chk = check_start(self.cfg, caps, gather_context(settings))
        self.warnings = chk["warnings"]
        if not chk["ok"]:
            self._fail("; ".join(chk["errors"]))
            return False
        self.cfg = chk["cfg"]
        if not self.cfg.get("enabled"):
            self._fail("fm_tx.enabled ist aus")
            return False
        self.state = "starting"
        self.error = ""
        self.publish()
        source = source_override or self.cfg.get("source")
        audio_cfg = dict(self.cfg, source=source)
        audio_cmd = None
        if self._audio_cmd_factory is not None:
            audio_cmd = self._audio_cmd_factory(audio_cfg)
        else:
            from modules.tx import audio_tap
            audio_cmd = audio_tap.build_cmd(source, self.cfg.get("stereo"))
        ps, rt = self.rds.compute(self.cfg, force=True)
        if rt_override is not None:
            rt = _clean_text(rt_override, 64)
        self.rds_ps, self.rds_rt = ps, rt
        run_cfg = dict(audio_cfg, freq_effective_mhz=effective_freq(self.cfg),
                       rds_ps=ps, rds_rt=rt)
        try:
            backend.start(run_cfg, audio_cmd)
        except Exception as e:
            self.backend = backend
            self._safe_backend_stop()
            self.backend = None
            self._fail(f"Start fehlgeschlagen: {e}")
            return False
        self.backend = backend
        self.started_ts = self._clock()
        self.state = "on"
        self.publish()
        return True

    def announce(self, then: str = "off") -> bool:
        """Boot-Ansage senden. then=always: danach mit konfigurierter Quelle weiter, sonst aus."""
        self.restarts = []
        ok = self.start(source_override="announce", rt_override=ANNOUNCE_RT)
        if ok:
            self.announce_until = self._clock() + ANNOUNCE_WINDOW_S
            self.announce_then = then if then in AUTOSTART_MODES else "off"
            self.publish()
        return ok

    def stop(self, reason: str = "user") -> None:
        self._safe_backend_stop()
        self.backend = None
        self.announce_until = 0.0
        quiet = reason in ("user", "announce_done")
        if reason != "restart":
            self.started_ts = 0.0
        if self.state != "error" or quiet:
            self.state = "off"
            if quiet:
                self.error = ""
        if not quiet and reason != "restart":
            self.error = self.error or f"gestoppt: {reason}"
        self.publish()

    def set_rds(self, ps: str | None = None, rt: str | None = None) -> bool:
        if ps is not None:
            self.rds_ps = _clean_text(ps, 8)
        if rt is not None:
            self.rds_rt = _clean_text(rt, 64)
        if self.backend is None or self.state != "on" or not self.cfg["rds"]["enabled"]:
            return False
        try:
            return bool(self.backend.set_rds(ps=self.rds_ps if ps is not None else None,
                                             rt=self.rds_rt if rt is not None else None))
        except Exception:
            return False

    def reload(self) -> None:
        """Settings neu lesen; läuft der Sender, mit neuer Konfiguration neu starten."""
        was_on = self.state in ("starting", "on")
        new_cfg = get_cfg(self._load() or {})
        if self.announce_until:
            # laufende Ansage nicht unterbrechen; die neue Konfiguration greift danach
            _errs, self.cfg = validate_cfg(new_cfg)
            self.publish()
            return
        if not was_on:
            self.cfg = new_cfg
            self.publish()
            return
        _errs, new_cfg = validate_cfg(new_cfg)
        only_rds = {k: v for k, v in new_cfg.items() if k != "rds"} == \
                   {k: v for k, v in self.cfg.items() if k != "rds"}
        if only_rds and new_cfg["rds"].get("pi") == self.cfg["rds"].get("pi"):
            self.cfg = new_cfg
            ps, rt = self.rds.compute(self.cfg, force=True)
            self.set_rds(ps=ps, rt=rt)
            self.publish()
            return
        self.start()

    def handle(self, line: str) -> None:
        line = (line or "").strip()
        if not line:
            return
        cmd, _, arg = line.partition(" ")
        cmd = cmd.lower()
        if cmd == "start":
            self.restarts = []
            self.start()
        elif cmd == "stop":
            self.stop("user")
        elif cmd == "reload":
            self.reload()
        elif cmd == "announce":
            self.announce("off")
        elif cmd == "rds_ps":
            self.set_rds(ps=arg)
            self.publish()
        elif cmd == "rds_rt":
            self.set_rds(rt=arg)
            self.publish()

    def tick(self) -> None:
        """Watchdog, Laufzeitlimit, RDS-Auto. Aufruf ca. 1×/s."""
        now = self._clock()
        if self.state == "on" and self.announce_until:
            # Ansagefenster: Prozessende ist hier normal, kein Watchdog-Neustart
            if now < self.announce_until:
                return
            then = self.announce_then
            self.announce_until = 0.0
            if then == "always":
                self.restarts = []
                self.start()
            else:
                self.stop("announce_done")
            return
        if self.state == "on":
            limit = self.cfg["max_runtime_min"] * 60
            if self.started_ts and now - self.started_ts >= limit:
                self.stop(f"Laufzeitlimit {self.cfg['max_runtime_min']} min erreicht")
                return
            alive = True
            try:
                alive = bool(self.backend and self.backend.status().get("running"))
            except Exception:
                alive = False
            if not alive:
                self.restarts = [t for t in self.restarts if now - t < RESTART_WINDOW_S]
                if len(self.restarts) >= MAX_RESTARTS:
                    self._safe_backend_stop()
                    self.backend = None
                    self._fail(f"Backend {MAX_RESTARTS}× in {RESTART_WINDOW_S // 60} min beendet — kein Neustart")
                    return
                self.restarts.append(now)
                started = self.started_ts
                self.start()
                if self.state == "on" and started:
                    self.started_ts = started
                return
            if self.cfg["rds"]["enabled"]:
                ps, rt = self.rds.compute(self.cfg)
                upd_ps = ps if ps != self.rds_ps else None
                upd_rt = rt if rt != self.rds_rt else None
                if upd_ps is not None or upd_rt is not None:
                    self.set_rds(ps=upd_ps, rt=upd_rt)

    # ── intern ──
    def _safe_backend_stop(self) -> None:
        if self.backend is None:
            return
        try:
            self.backend.stop()
        except Exception:
            pass

    def _fail(self, msg: str) -> None:
        self.state = "error"
        self.error = msg
        self.started_ts = 0.0
        self.publish()
