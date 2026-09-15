#!/usr/bin/env python3
"""webui_check.py — Statische WebUI-Prüfung und Shared-Selftest (W0/W1).

Befehle (via pidrivectl webui …):
  check     — sendCmd/fetch/Statusfelder gegen Whitelist und Routen
  selftest  — importiert web.shared.* und ruft öffentliche Funktionen
  routes    — listet Flask-Routen
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

WEB_DIR = Path(__file__).resolve().parent          # pidrive/web
PIDRIVE_DIR = WEB_DIR.parent                       # pidrive/
REPO_ROOT = PIDRIVE_DIR.parent                     # repo root
TEMPLATES = WEB_DIR / "templates"
STATIC_JS = WEB_DIR / "static" / "js"
ROUTES_JSON = REPO_ROOT / "tests" / "webui" / "routes.json"

# Prefixes müssen mit web.shared.constants.ALLOWED_COMMAND_PREFIXES übereinstimmen
def _cmd_prefixes():
    _ensure_path()
    from web.shared.constants import ALLOWED_COMMAND_PREFIXES
    return ALLOWED_COMMAND_PREFIXES


CMD_PREFIXES = None  # lazy; see _cmd_prefixes()

# Bekannte Defekte aus AUFTRAG V4 — check muss sie finden, solange unbehoben
EXPECTED_BAD_CMDS = {"prev_station", "next_station", "/api/ppm_calibrate"}


def _ensure_path():
    for p in (str(PIDRIVE_DIR), str(REPO_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _load_allowed() -> Set[str]:
    _ensure_path()
    from web.shared.constants import ALLOWED_COMMANDS
    return set(ALLOWED_COMMANDS)


def _cmd_allowed(cmd: str, allowed: Set[str]) -> bool:
    if cmd in allowed:
        return True
    return any(cmd.startswith(p) for p in _cmd_prefixes())


def collect_routes() -> List[Dict[str, Any]]:
    """Flask-Routen aus app.py und Blueprints per Regex (ohne App-Start)."""
    routes: List[Dict[str, Any]] = []
    files = [WEB_DIR / "app.py"] + sorted((WEB_DIR / "api").glob("routes_*.py"))
    pat = re.compile(
        r"""@(?:app|\w+_bp)\.route\(\s*['\"]([^'\"]+)['\"]"""
        r"""(?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?""",
        re.M,
    )
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # Blueprint-Präfix
        prefix = ""
        bpm = re.search(r"Blueprint\([^)]*url_prefix\s*=\s*['\"]([^'\"]+)['\"]", text)
        if bpm:
            prefix = bpm.group(1).rstrip("/")
        for m in pat.finditer(text):
            route_path = prefix + m.group(1)
            methods_raw = m.group(2) or "'GET'"
            methods = [x.strip().strip("'\"") for x in methods_raw.split(",") if x.strip()]
            routes.append({
                "path": route_path,
                "methods": methods,
                "file": str(path.relative_to(REPO_ROOT)),
            })
    return routes


def write_routes_json() -> Path:
    ROUTES_JSON.parent.mkdir(parents=True, exist_ok=True)
    allowed = sorted(_load_allowed())
    data = {
        "version": 1,
        "allowed_commands": allowed,
        "command_prefixes": list(_cmd_prefixes()),
        "routes": collect_routes(),
    }
    ROUTES_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return ROUTES_JSON


def _iter_template_sources() -> List[Tuple[Path, str]]:
    out = []
    for root in (TEMPLATES, STATIC_JS):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in (".html", ".js"):
                continue
            # Legacy-/Referenz-Templates: nicht als aktive Oberfläche prüfen
            if "legacy" in p.parts or "legacy" in p.name or p.name == "index_full.html":
                continue
            out.append((p, p.read_text(encoding="utf-8", errors="replace")))
    return out


_SENDCMD_RE = re.compile(
    r"""sendCmd\(\s*(?:['\"]([^'\"]+)['\"]|`([^`$]*)`)""",
    re.M,
)
_FETCH_RE = re.compile(
    r"""fetch\(\s*[`'\"](/[^`'\"?]*)""",
    re.M,
)
# Statusfelder: st.foo / j.status.foo / status.foo in Templates
_STATUS_FIELD_RE = re.compile(
    r"""(?:\bst|\bj\.status|status)\.([a-zA-Z_][a-zA-Z0-9_]*)"""
)


def _status_keys_written() -> Set[str]:
    """Schlüssel, die ipc.write_status schreibt (aus Quelltext)."""
    ipc_path = PIDRIVE_DIR / "ipc.py"
    text = ipc_path.read_text(encoding="utf-8", errors="replace")
    # Grobe Extraktion aus write_status dict-Literal
    m = re.search(r"def write_status\(.*?\n(.*?)(?=\ndef )", text, re.S)
    if not m:
        return set()
    body = m.group(1)
    return set(re.findall(r'''["']([a-zA-Z_][a-zA-Z0-9_]*)["']\s*:''', body))


def run_check(write_inventory: bool = True) -> int:
    """Statische Prüfung. Exit 0 = keine unerwarteten Treffer."""
    _ensure_path()
    if write_inventory:
        write_routes_json()

    allowed = _load_allowed()
    route_paths = {r["path"] for r in collect_routes()}
    # Parameter-Routen: /cover/<name> → Prefix-Match
    route_prefixes = [p.split("<")[0] for p in route_paths if "<" in p]
    status_written = _status_keys_written()

    bad_cmds: List[Tuple[str, str]] = []
    bad_fetches: List[Tuple[str, str]] = []
    bad_fields: List[Tuple[str, str]] = []
    found_expected: Set[str] = set()

    for path, text in _iter_template_sources():
        rel = str(path.relative_to(REPO_ROOT))
        for m in _SENDCMD_RE.finditer(text):
            cmd = (m.group(1) or m.group(2) or "").strip()
            if not cmd or "${" in cmd or "+" in cmd:
                # dynamisch gebaut — nur feste Literale prüfen
                if cmd and not any(c in cmd for c in "${+"):
                    pass
                else:
                    # Literal-Prefix vor ':' zählt als bekanntes Präfix-Muster
                    continue
            # Template-Literale mit Suffix: 'vol_set:'+v — sendCmd('vol_set:'+…)
            # oben schon gefiltert. Feste Strings:
            base = cmd.split(":")[0] + (":" if ":" in cmd else "")
            ok = _cmd_allowed(cmd, allowed)
            if not ok and ":" in cmd:
                ok = any(cmd.startswith(p) for p in _cmd_prefixes())
            if not ok:
                bad_cmds.append((rel, cmd))
                if cmd in EXPECTED_BAD_CMDS:
                    found_expected.add(cmd)

        for m in _FETCH_RE.finditer(text):
            url = m.group(1)
            if url.startswith("/static/"):
                continue
            hit = url in route_paths or any(url.startswith(rp) for rp in route_prefixes)
            # Query-freie Variante
            if not hit and "?" in url:
                hit = url.split("?", 1)[0] in route_paths
            if not hit:
                # /api/favorites existiert laut V4 nicht
                bad_fetches.append((rel, url))

        for field in _STATUS_FIELD_RE.findall(text):
            # Häufige JS-Hilfsnamen überspringen
            if field in ("length", "ok", "error", "then", "catch", "json", "status"):
                continue
            if status_written and field not in status_written:
                # Nur Felder melden, die klar Status sind und fehlen
                if field in ("processes", "lines", "log", "text", "output",
                             "disk_total", "throttled", "bt_on"):
                    bad_fields.append((rel, field))

    # Dedup
    bad_cmds = sorted(set(bad_cmds))
    bad_fetches = sorted(set(bad_fetches))
    bad_fields = sorted(set(bad_fields))

    print("PiDrive webui check")
    print(f"  Routen: {len(route_paths)}  ALLOWED_COMMANDS: {len(allowed)}")
    print(f"  sendCmd-Treffer (nicht erlaubt): {len(bad_cmds)}")
    for rel, cmd in bad_cmds:
        mark = " [erwartet V4]" if cmd in EXPECTED_BAD_CMDS else ""
        print(f"    ✗ {rel}: sendCmd({cmd!r}){mark}")
    print(f"  fetch-URLs ohne Route: {len(bad_fetches)}")
    for rel, url in bad_fetches:
        print(f"    ✗ {rel}: fetch({url!r})")
    print(f"  Statusfelder gelesen, nicht geschrieben: {len(bad_fields)}")
    for rel, field in bad_fields:
        print(f"    ✗ {rel}: status.{field}")

    missing_expected = EXPECTED_BAD_CMDS - found_expected
    if missing_expected:
        print(f"  ⚠ Erwartete V4-Treffer nicht gefunden: {sorted(missing_expected)}")
        print("    (Check unvollständig — bekannte Fehler müssen sichtbar sein)")
        return 2

    # Solange bekannte Bugs offen: Exit 1 (gefunden), aber W0-Abnahme ok
    if bad_cmds or bad_fetches or bad_fields:
        print("  Ergebnis: Treffer vorhanden (W0: bekannte Defekte sichtbar)")
        return 1
    print("  Ergebnis: 0 Treffer")
    return 0


def _public_functions(mod) -> List[str]:
    names = []
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        if getattr(obj, "__module__", None) != mod.__name__:
            continue
        names.append(name)
    return names


def run_selftest() -> int:
    """Importiert web.shared.* und ruft öffentliche Funktionen einmal."""
    _ensure_path()
    modules = [
        "web.shared.constants",
        "web.shared.files",
        "web.shared.system",
        "web.shared.audio",
        "web.shared.view_model",
        "web.shared",
    ]
    errors: List[str] = []
    print("PiDrive webui selftest")

    for name in modules:
        try:
            mod = importlib.import_module(name)
            print(f"  ✓ import {name}")
        except Exception as e:
            errors.append(f"import {name}: {type(e).__name__}: {e}")
            print(f"  ✗ import {name}: {type(e).__name__}: {e}")
            continue

        for fname in _public_functions(mod):
            fn = getattr(mod, fname)
            try:
                sig = inspect.signature(fn)
                kwargs = {}
                args = []
                for p in sig.parameters.values():
                    if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                        continue
                    if p.default is not inspect.Parameter.empty:
                        continue
                    # Pflichtargumente mit harmlosen Defaults füllen
                    if p.name in ("path", "cmd"):
                        args.append("/tmp/pidrive_webui_selftest_missing.json" if p.name == "path" else "noop")
                    else:
                        args.append(None)
                result = fn(*args, **kwargs)
                # NameError in geschluckten except → oft als error-Feld
                if isinstance(result, dict) and "error" in result:
                    err = str(result.get("error", ""))
                    if "is not defined" in err or "NameError" in err:
                        errors.append(f"{name}.{fname}: returned error {err!r}")
                        print(f"  ✗ {name}.{fname}: {err}")
                        continue
                print(f"  ✓ call {name}.{fname}")
            except (NameError, ImportError, AttributeError) as e:
                errors.append(f"{name}.{fname}: {type(e).__name__}: {e}")
                print(f"  ✗ {name}.{fname}: {type(e).__name__}: {e}")
            except Exception as e:
                # Andere Exceptions (fehlende HW etc.) sind kein Selftest-Fail
                print(f"  · {name}.{fname}: {type(e).__name__}: {e} (ignoriert)")

    # Shadowing-Check: lokaler Import == Modulimport (C16-Regel)
    hw = PIDRIVE_DIR / "trigger" / "td_hardware.py"
    if hw.exists():
        tree = ast.parse(hw.read_text(encoding="utf-8"))
        module_imports: Set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "modules":
                for alias in node.names:
                    module_imports.add(alias.asname or alias.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("modules"):
                        module_imports.add(alias.asname or alias.name.split(".")[-1])
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.ImportFrom) and sub.module == "modules":
                        for alias in sub.names:
                            bound = alias.asname or alias.name
                            if bound in module_imports and alias.asname is None:
                                msg = (f"td_hardware.py:{sub.lineno}: lokaler Import "
                                       f"'{bound}' kollidiert mit Modulimport (C16)")
                                errors.append(msg)
                                print(f"  ✗ {msg}")

    if errors:
        print(f"  Ergebnis: {len(errors)} Fehler")
        return 1
    print("  Ergebnis: 0 Fehler")
    return 0


def cmd_routes() -> int:
    routes = collect_routes()
    for r in sorted(routes, key=lambda x: x["path"]):
        methods = ",".join(r["methods"])
        print(f"{methods:12} {r['path']:40}  ({r['file']})")
    print(f"# {len(routes)} Routen")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: webui_check.py check|selftest|routes")
        return 2
    cmd = argv[0]
    if cmd == "check":
        return run_check()
    if cmd == "selftest":
        return run_selftest()
    if cmd == "routes":
        return cmd_routes()
    print(f"unbekannt: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
