#!/usr/bin/env python3
"""menu_golden.py — Golden-Master, Lint und Verify für den Menübaum (M0)."""

import copy
import json
import os
import re
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BASE_DIR)
GOLDEN_DIR = os.path.join(REPO_ROOT, "tests", "golden")
GOLDEN_FILE = os.path.join(GOLDEN_DIR, "menu_tree.json")
CHANGES_FILE = os.path.join(GOLDEN_DIR, "CHANGES.md")

sys.path.insert(0, BASE_DIR)

from menu.menu_builder import build_tree
from menu.menu_state import MenuNode
from menu.station_store import StationStore
from settings import CONFIG_DIR, load_settings
import status


def build_reference_tree() -> MenuNode:
    """Offline-Baum wie main_core, ohne laufenden Core."""
    S = copy.deepcopy(status.S)
    settings = load_settings()
    store = StationStore(CONFIG_DIR)
    store.load_all()
    return build_tree(store, S, settings)


def mask_label(label: str) -> str:
    """Dynamische Label-Anteile maskieren (tests/golden/README.md)."""
    if label.startswith("IP: "):
        return "IP: <IP>"
    if label.startswith("Ausgang: "):
        return "Ausgang: <OUTPUT>"
    if label.startswith("Bluetooth: ") or label.startswith("Status: "):
        if label.startswith("Bluetooth: "):
            return "Bluetooth: <BT_STATE>"
        return "Status: <SPOTIFY_STATE>"
    if label.startswith("> ") or label.startswith("* "):
        return "<BT_PREFIX>" + label[2:]
    if label.startswith("Geraet: "):
        return "Geraet: <BT_DEVICE>"
    if label.startswith("Letztes: "):
        return "Letztes: <BT_LAST>"
    if label.startswith("SSID: "):
        return "SSID: <WIFI_SSID>"
    if label.startswith("Ordner: "):
        return "Ordner: <LIB_FOLDER>"
    if label.startswith("Alle: "):
        return "Alle: <LIB_NAME>"
    if re.match(r"^★ ", label) or re.match(r"^\* ", label):
        return "<FAV_PREFIX>" + label.split(" ", 1)[-1]
    return label


def node_to_dict(node: MenuNode, path: str) -> dict:
    return {
        "path": path,
        "id": node.id,
        "type": node.type,
        "action": node.action,
        "label": mask_label(node.label),
    }


def walk_tree(root: MenuNode) -> List[dict]:
    out: List[dict] = []

    def _walk(node: MenuNode, path: str):
        out.append(node_to_dict(node, path))
        for child in node.children:
            child_path = f"{path}/{child.id}" if path else child.id
            _walk(child, child_path)

    _walk(root, "root")
    return out


def lint_tree(nodes: List[dict]) -> Tuple[List[str], List[str]]:
    """Statische Prüfungen. Returns (errors, warnings)."""
    from trigger.trigger_dispatcher import would_handle

    errors: List[str] = []
    warnings: List[str] = []
    ids_seen: Dict[str, str] = {}
    by_path = {n["path"]: n for n in nodes}

    for n in nodes:
        nid = n["id"]
        if nid in ids_seen:
            # B3: baumweite Eindeutigkeit — bis M1 als Warnung (nicht blockierend)
            warnings.append(f"ID doppelt: {nid!r} ({ids_seen[nid]} und {n['path']})")
        else:
            ids_seen[nid] = n["path"]

        action = n.get("action")
        if action and not would_handle(action):
            errors.append(f"Action nicht behandelt: {action!r} ({n['path']})")

        if n["type"] == "folder":
            child_prefix = n["path"] + "/"
            direct_children = [
                p for p in by_path
                if p.startswith(child_prefix) and "/" not in p[len(child_prefix):]
            ]
            if n["path"] != "root" and not direct_children:
                errors.append(f"Leerer Ordner: {n['path']}")
            if n["path"] != "root" and direct_children and not _folder_has_back_from_nodes(n, by_path):
                errors.append(f"Kein Rückweg: {n['path']}")

        if n["type"] == "info":
            warnings.append(f"Info-Knoten (skip_on_nav fehlt): {n['path']}")

        label = n.get("label") or ""
        if len(label) > 64:
            errors.append(f"Label > 64 Zeichen: {n['path']} ({len(label)})")

    return errors, warnings


def _folder_has_back_from_nodes(folder: dict, by_path: dict) -> bool:
    prefix = folder["path"] + "/"
    for path, n in by_path.items():
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        if "/" in rest:
            continue
        if n.get("action") == "back" or n["id"].endswith("_back"):
            return True
        if n.get("label") == "Abbrechen" and n.get("action") == "back":
            return True
    return False


def verify_against_golden(current: List[dict], golden: List[dict]) -> Tuple[List, List, List]:
    g_map = {n["path"]: n for n in golden}
    c_map = {n["path"]: n for n in current}

    losses = [p for p in g_map if p not in c_map]
    gains = [p for p in c_map if p not in g_map]
    changes = []
    for p in g_map:
        if p not in c_map:
            continue
        g, c = g_map[p], c_map[p]
        if g.get("type") != c.get("type") or g.get("action") != c.get("action"):
            changes.append({"path": p, "was": g, "now": c})

    return losses, gains, changes


def write_snapshot(accept: bool = False, who: str = "pidrivectl") -> str:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    nodes = walk_tree(build_reference_tree())
    if not accept and os.path.exists(GOLDEN_FILE):
        raise SystemExit("Snapshot existiert — --accept zum Aktualisieren")

    with open(GOLDEN_FILE, "w", encoding="utf-8") as f:
        json.dump(nodes, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if accept:
        entry = (
            f"\n## {date.today().isoformat()} · v{open(os.path.join(REPO_ROOT, 'VERSION')).read().strip()}\n"
            f"- Golden Master aktualisiert von {who}\n"
        )
        with open(CHANGES_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    return GOLDEN_FILE


def cmd_snapshot(accept: bool = False) -> int:
    path = write_snapshot(accept=accept)
    print(f"Snapshot geschrieben: {path} ({len(walk_tree(build_reference_tree()))} Knoten)")
    return 0


def cmd_verify() -> int:
    if not os.path.exists(GOLDEN_FILE):
        print(f"FEHLER: Kein Golden Master unter {GOLDEN_FILE}")
        return 1
    with open(GOLDEN_FILE, encoding="utf-8") as f:
        golden = json.load(f)
    current = walk_tree(build_reference_tree())
    losses, gains, changes = verify_against_golden(current, golden)

    if losses:
        print("VERLUSTE:")
        for p in losses:
            print(f"  - {p}")
    if gains:
        print("ZUGÄNGE:")
        for p in gains:
            print(f"  + {p}")
    if changes:
        print("ÄNDERUNGEN (type/action):")
        for ch in changes:
            print(f"  ~ {ch['path']}: {ch['was'].get('type')}/{ch['was'].get('action')} → "
                  f"{ch['now'].get('type')}/{ch['now'].get('action')}")

    if losses or changes:
        return 1
    print(f"OK: {len(current)} Knoten, keine Verluste, keine Action-Änderungen")
    if gains:
        print(f"  ({len(gains)} neue Knoten)")
    return 0


def cmd_lint() -> int:
    nodes = walk_tree(build_reference_tree())
    errors, warnings = lint_tree(nodes)
    for w in warnings:
        print(f"WARNUNG: {w}")
    for e in errors:
        print(f"FEHLER: {e}")
    if errors:
        print(f"--- {len(errors)} Fehler, {len(warnings)} Warnungen")
        return 1
    print(f"OK: {len(nodes)} Knoten, {len(warnings)} Warnungen")
    return 0
