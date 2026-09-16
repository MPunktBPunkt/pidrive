"""Statische WebUI-Oberfläche: Nav, sendCmd-Vertrag, onclick, Pflicht-Routen."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "pidrive" / "web"
TEMPLATES = WEB / "templates"
STATIC_JS = WEB / "static" / "js"
SURFACE = json.loads(
    (REPO / "tests" / "webui" / "required_surface.json").read_text(encoding="utf-8")
)

_SENDCMD_RE = re.compile(
    r"""sendCmd\(\s*(?:['\"]([^'\"]+)['\"]|`([^`$]*)`)"""
)
_ONCLICK_RE = re.compile(r"""onclick\s*=\s*['\"]\s*([a-zA-Z_$][\w$]*)\s*\(""")
_HREF_RE = re.compile(r"""href\s*=\s*['\"](/[^#'\"]*)['\"]""")
_SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src=['\"]([^'\"]+)['\"]""", re.I)
_FUNC_RE = re.compile(
    r"""(?:async\s+)?function\s+([a-zA-Z_$][\w$]*)\s*\(|"""
    r"""(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?\("""
)


def _active_templates() -> list[Path]:
    out = []
    for p in TEMPLATES.rglob("*.html"):
        if "legacy" in p.parts or p.name in ("index_full.html", "index_legacy.html"):
            continue
        out.append(p)
    return out


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _static_path(src: str) -> Path:
    """/static/js/foo.js → pidrive/web/static/js/foo.js"""
    assert src.startswith("/static/")
    return WEB / src[len("/"):]  # static/js/foo.js under web/


def _all_active_text() -> str:
    parts = [_read(p) for p in _active_templates()]
    for js in STATIC_JS.glob("*.js"):
        if js.name == "page-index.js":
            continue
        parts.append(_read(js))
    return "\n".join(parts)


def test_nav_hrefs_are_registered_routes():
    from web.webui_check import collect_routes

    routes = {r["path"] for r in collect_routes()}
    base = _read(TEMPLATES / "base.html")
    hrefs = {h for h in _HREF_RE.findall(base) if not h.startswith("/static")}
    missing = sorted(
        h for h in hrefs
        if h not in routes
        and not any(h.startswith(rp.split("<")[0]) for rp in routes if "<" in rp)
    )
    assert not missing, f"Nav-Links ohne Flask-Route: {missing}"
    required = set(SURFACE["pages"])
    assert required <= (hrefs | {"/"}), f"Nav fehlt Seiten: {sorted(required - hrefs)}"


def test_required_sendcmds_still_in_ui():
    text = _all_active_text()
    found: set[str] = set()
    for m in _SENDCMD_RE.finditer(text):
        cmd = (m.group(1) or m.group(2) or "").strip()
        if not cmd:
            continue
        found.add(cmd)
        found.add(cmd.split(":")[0])
    missing = [req for req in SURFACE["required_cmds"] if req not in found]
    assert not missing, (
        "Pflicht-sendCmd fehlen in aktiven Templates/JS "
        "(UI-Funktion entfernt?):\n  " + "\n  ".join(missing)
    )


def test_onclick_handlers_defined():
    base_funcs = set()
    for m in _FUNC_RE.finditer(_read(TEMPLATES / "base.html")):
        base_funcs.add(m.group(1) or m.group(2))
    known_global = base_funcs | {"sendCmd", "showToast", "setText", "el", "refreshBase"}

    errors = []
    for path in _active_templates():
        text = _read(path)
        local = set(known_global)
        for m in _FUNC_RE.finditer(text):
            local.add(m.group(1) or m.group(2))
        for src in _SCRIPT_SRC_RE.findall(text):
            if src.startswith("/static/"):
                js = _static_path(src)
                if js.is_file():
                    for m in _FUNC_RE.finditer(_read(js)):
                        local.add(m.group(1) or m.group(2))
        for m in _ONCLICK_RE.finditer(text):
            name = m.group(1)
            if name not in local:
                errors.append(f"{path.relative_to(REPO)}: onclick={name}() ohne function")
    assert not errors, "Tote onclick-Handler:\n  " + "\n  ".join(errors)


def test_forbidden_scripts_not_loaded():
    text = "\n".join(_read(p) for p in _active_templates())
    for bad in SURFACE["forbidden_script_srcs"]:
        assert bad not in text, f"{bad} darf nicht in aktiven Templates geladen werden (V1)"


def test_script_srcs_exist():
    missing = []
    for path in _active_templates():
        for src in _SCRIPT_SRC_RE.findall(_read(path)):
            if not src.startswith("/static/"):
                continue
            fs = _static_path(src)
            if not fs.is_file():
                missing.append(f"{path.name}: {src}")
    assert not missing, "script src fehlt:\n  " + "\n  ".join(missing)


def test_required_routes_present_in_code():
    from web.webui_check import collect_routes

    current = {r["path"] for r in collect_routes()}
    required = set(SURFACE["pages"]) | set(SURFACE["apis_get"])
    gone = sorted(p for p in required if p not in current)
    assert not gone, f"Pflicht-Routen fehlen im Code: {gone}"
