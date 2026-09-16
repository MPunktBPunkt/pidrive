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
from menu.menu_annotate import annotate_tree
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
    return annotate_tree(build_tree(store, S, settings))


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
        "source": node.source,
        "meta": dict(node.meta or {}),
        "label": mask_label(node.label),
        "path_id": getattr(node, "path_id", "") or path,
        "uid": getattr(node, "uid", 0),
        "skip_on_nav": getattr(node, "skip_on_nav", False),
        "playable": bool(getattr(node, "playable", False)),
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
            # Doppelte IDs → goto/activate/iDrive bricht (B3) — Fehler, nicht Warnung
            errors.append(f"ID doppelt: {nid!r} ({ids_seen[nid]} und {n['path']})")
        else:
            ids_seen[nid] = n["path"]

        ntype = n["type"]
        action = n.get("action")

        # Action/Toggle ohne action = Enter tut nichts (td_nav silent return)
        if ntype in ("action", "toggle") and not action:
            errors.append(f"Action leer (ohne Funktion): {n['path']}")
        elif action and not would_handle(action):
            errors.append(f"Action nicht behandelt: {action!r} ({n['path']})")

        # Stationen brauchen source + Meta zum Abspielen
        if ntype == "station":
            src = (n.get("source") or "").strip()
            meta = n.get("meta") or {}
            if not src:
                errors.append(f"Station ohne source: {n['path']}")
            elif src == "fm" and not meta.get("freq"):
                errors.append(f"FM-Station ohne freq: {n['path']}")
            elif src == "webradio" and not (meta.get("url") or meta.get("id")):
                errors.append(f"Webradio-Station ohne url: {n['path']}")
            elif src == "dab" and not (
                meta.get("name") or meta.get("service_id") or (n.get("label") or "").strip()
            ):
                errors.append(f"DAB-Station ohne name/service_id: {n['path']}")

        if ntype == "folder":
            child_prefix = n["path"] + "/"
            direct_children = [
                p for p in by_path
                if p.startswith(child_prefix) and "/" not in p[len(child_prefix):]
            ]
            if n["path"] != "root" and not direct_children:
                errors.append(f"Leerer Ordner: {n['path']}")
            if n["path"] != "root" and direct_children and not _folder_has_back_from_nodes(n, by_path):
                errors.append(f"Kein Rückweg: {n['path']}")
            # Mindestens ein anwählbarer Eintrag (nicht nur Info/skip)
            if n["path"] != "root" and direct_children:
                selectable = [
                    p for p in direct_children
                    if not by_path[p].get("skip_on_nav")
                ]
                if not selectable:
                    errors.append(f"Ordner ohne anwählbaren Eintrag: {n['path']}")

        if ntype == "info" and not n.get("skip_on_nav"):
            errors.append(f"Info-Knoten ohne skip_on_nav (Enter blind): {n['path']}")

        # Annotate-Kollisions-Suffix bedeutet doppelte id im Elternordner
        path_id = n.get("path_id") or ""
        if "#" in path_id.split("/")[-1]:
            errors.append(f"path_id mit Kollisions-Suffix (ID-Konflikt): {path_id}")

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
    # UID-Eindeutigkeit (M1)
    root = build_reference_tree()
    uids = []
    def _u(n):
        uids.append(n.uid)
        for c in n.children:
            _u(c)
    _u(root)
    if len(uids) != len(set(uids)):
        errors.append(f"UID nicht eindeutig: {len(uids)} Knoten, {len(set(uids))} unique")
    for w in warnings:
        print(f"WARNUNG: {w}")
    for e in errors:
        print(f"FEHLER: {e}")
    if errors:
        print(f"--- {len(errors)} Fehler, {len(warnings)} Warnungen")
        return 1
    print(f"OK: {len(nodes)} Knoten, {len(warnings)} Warnungen, UIDs eindeutig")
    return 0


def cmd_tree(as_json: bool = False, depth: int = 0) -> int:
    from menu.menu_state import MenuState
    root = build_reference_tree()
    state = MenuState(root)
    data = state.export_tree()

    def _trim(node: dict, d: int):
        if depth and d >= depth:
            node = dict(node)
            node["children"] = []
            node["truncated"] = True
            return node
        out = dict(node)
        out["children"] = [_trim(c, d + 1) for c in node.get("children", [])]
        return out

    tree = data["tree"] if not depth else _trim(data["tree"], 0)
    payload = {"uid_counter": data["uid_counter"], "rev": data["rev"], "tree": tree}

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    def _print(node: dict, indent: int = 0):
        pad = "  " * indent
        skip = " [skip]" if node.get("skip_on_nav") else ""
        act = f" action={node.get('action')}" if node.get("action") else ""
        print(f"{pad}{node.get('type','?'):7} uid={node.get('uid')} {node.get('path_id')}  {node.get('label')!r}{skip}{act}")
        if node.get("truncated"):
            print(f"{pad}  …")
            return
        for c in node.get("children", []):
            _print(c, indent + 1)

    print(f"uid_counter={payload['uid_counter']}")
    _print(payload["tree"])
    return 0


def cmd_goto(path_id: str) -> int:
    from menu.menu_state import MenuState
    state = MenuState(build_reference_tree())
    if not state.goto(path_id):
        print(f"FEHLER: Pfad nicht gefunden: {path_id}")
        return 1
    sel = state.selected
    print(f"Pfad:   {' / '.join(state.path)}")
    print(f"path_ids: {' > '.join(state.path_ids)}")
    print(f"Cursor: {state.cursor}")
    if sel:
        print(f"Markiert: {sel.label!r} type={sel.type} uid={sel.uid} path_id={sel.path_id}")
    return 0


def cmd_activate(uid: int) -> int:
    from menu.menu_state import MenuState
    state = MenuState(build_reference_tree())
    node = state.activate(uid)
    if node is None:
        print(f"FEHLER: UID nicht gefunden: {uid}")
        return 1
    print(f"Aktiviert: {node.label!r} type={node.type} action={node.action} path_id={node.path_id}")
    print(f"Pfad jetzt: {' / '.join(state.path)}")
    return 0


def cmd_path() -> int:
    from menu.menu_state import MenuState
    state = MenuState(build_reference_tree())
    sel = state.selected
    print(f"Pfad: {' / '.join(state.path)}")
    if sel:
        print(f"Markiert: {sel.label!r} uid={sel.uid}")
    return 0


def cmd_rebuild_test() -> int:
    """Offline: goto tief, rebuild, prüfen ob Position hält."""
    from menu.menu_state import MenuState
    root = build_reference_tree()
    state = MenuState(root)
    target = "sources/dab/dab_stations"
    if not state.goto(target):
        # fallback first station list that exists
        print(f"FEHLER: {target} nicht erreichbar")
        return 1
    for _ in range(5):
        state.key_down()
    before_path = list(state.path_ids)
    before_uid = state.selected.uid if state.selected else None
    before_label = state.selected.label if state.selected else None
    # rebuild same tree (simulates menu_rev without content change)
    state.rebuild(build_reference_tree())
    after_uid = state.selected.uid if state.selected else None
    print(f"Vorher:  path={before_path} uid={before_uid} label={before_label!r}")
    print(f"Nachher: path={state.path_ids} uid={after_uid} label={(state.selected.label if state.selected else None)!r}")
    if before_path == state.path_ids and before_uid == after_uid:
        print("OK: Pfad und Cursor überstehen Rebuild")
        return 0
    print("FEHLER: Position nicht erhalten")
    return 1


def _normalize_path_id(path_id: str) -> List[str]:
    parts = [p for p in path_id.strip("/").split("/") if p]
    if parts and parts[0] == "root":
        parts = parts[1:]
    return parts


def find_node_by_path(root: MenuNode, path_id: str) -> Optional[Tuple[MenuNode, List[Tuple[MenuNode, int]]]]:
    """Findet Knoten; liefert (node, [(parent, index_in_parent), ...]) vom Root aus."""
    parts = _normalize_path_id(path_id)
    trail: List[Tuple[MenuNode, int]] = []
    node = root
    for part in parts:
        want = part.split("#", 1)[0]
        found = None
        for i, child in enumerate(node.children):
            if child.id == part or child.id == want:
                found = (child, i)
                break
            if child.path_id and child.path_id.split("/")[-1] == part:
                found = (child, i)
                break
        if found is None:
            return None
        child, idx = found
        trail.append((node, idx))
        node = child
    return node, trail


def cmd_walk() -> int:
    """
    R3: jeden Ordner per goto öffnen, Rückweg prüfen; jedes action/toggle/station
    per activate(uid) erreichbar — fängt tote Menüpunkte offline.
    """
    from menu.menu_state import MenuState

    root = build_reference_tree()
    nodes = walk_tree(root)
    errors: List[str] = []
    folders = 0
    leaves = 0

    for n in nodes:
        if n["type"] != "folder" or n["path"] == "root":
            continue
        folders += 1
        state = MenuState(root)
        pid = n.get("path_id") or n["path"]
        if not state.goto(pid):
            errors.append(f"Ordner nicht erreichbar: {pid}")
            continue
        if not _folder_has_back_from_nodes(n, {x["path"]: x for x in nodes}):
            errors.append(f"Ordner ohne Rückweg: {pid}")

    state = MenuState(root)
    for n in nodes:
        if n["type"] not in ("station", "action", "toggle"):
            continue
        leaves += 1
        got = state.activate(n["uid"])
        if got is None:
            errors.append(f"activate tot: {n.get('path_id') or n['path']} uid={n['uid']}")
        elif got.uid != n["uid"]:
            errors.append(f"activate falscher Knoten: {n['path']} → {got.path_id}")

    lint_errs, lint_warns = lint_tree(nodes)
    errors.extend(lint_errs)

    for w in lint_warns:
        print(f"WARNUNG: {w}")
    for e in errors:
        print(f"FEHLER: {e}")
    if errors:
        print(f"--- walk: {len(errors)} Fehler ({folders} Ordner, {leaves} Blätter)")
        return 1
    print(f"OK: walk {folders} Ordner + {leaves} Blätter, lint sauber")
    return 0


def skip_only_cost(root: MenuNode, path_id: str) -> Optional[dict]:
    """
    Minimale Tastendrücke bei Skip-Only (down/enter, kein back).
    Cursor startet auf Index 0 jeder Ebene. Kosten = Summe(index + 1 enter) je Ebene.
    """
    found = find_node_by_path(root, path_id)
    if found is None:
        return None
    node, trail = found
    cost = 0
    steps = []
    for parent, idx in trail:
        downs = idx  # Cursor startet bei 0
        cost += downs + 1  # + enter
        steps.append({"id": parent.children[idx].id, "downs": downs, "enter": 1})
    reachable = node.type != "info"  # Enter auf info tut nichts (B5)
    return {
        "path": "root/" + "/".join(_normalize_path_id(path_id)) if _normalize_path_id(path_id) else "root",
        "id": node.id,
        "type": node.type,
        "label": mask_label(node.label),
        "depth": len(trail),
        "cost": cost,
        "reachable": reachable,
        "steps": steps,
    }


def collect_leaf_costs(root: MenuNode) -> List[dict]:
    """
    Skip-Only-Ziele: Sender, Aktionen, Toggles, Info.
    Favoriten-Kinder unter Stationen (B6, im Auto unerreichbar) werden ausgelassen —
    gemessen wird der Enter auf dem Sender selbst.
    """
    targets = []

    def _walk(node: MenuNode, path: str, parent: Optional[MenuNode] = None):
        if node is not root and node.type in ("station", "action", "toggle", "info"):
            if parent is not None and parent.type == "station":
                pass  # B6: fav_toggle unter Station — Skip-Only erreicht das nicht
            else:
                info = skip_only_cost(root, path)
                if info:
                    targets.append(info)
        for child in node.children:
            child_path = f"{path}/{child.id}" if path else child.id
            _walk(child, child_path, parent=node)

    _walk(root, "root")
    return targets


def ergonomics_stats(leaves: List[dict]) -> dict:
    costs = [L["cost"] for L in leaves]
    if not costs:
        return {"count": 0}
    costs_sorted = sorted(costs)
    n = len(costs_sorted)
    median = costs_sorted[n // 2] if n % 2 else (costs_sorted[n // 2 - 1] + costs_sorted[n // 2]) / 2
    return {
        "count": n,
        "median": median,
        "max": max(costs),
        "min": min(costs),
        "over_20": sum(1 for c in costs if c > 20),
        "unreachable": sum(1 for L in leaves if not L["reachable"]),
        "mean": round(sum(costs) / n, 1),
    }


def cmd_cost(path_id: str) -> int:
    root = build_reference_tree()
    info = skip_only_cost(root, path_id)
    if info is None:
        print(f"FEHLER: Pfad nicht gefunden: {path_id}")
        return 1
    print(f"Pfad:      {info['path']}")
    print(f"Label:     {info['label']}")
    print(f"Typ:       {info['type']}")
    print(f"Tiefe:     {info['depth']}")
    print(f"Kosten:    {info['cost']} Tastendrücke (down+enter)")
    print(f"Erreichbar:{' ja' if info['reachable'] else ' NEIN (info-Knoten)'}")
    for i, s in enumerate(info["steps"], 1):
        print(f"  Schritt {i}: {s['downs']}× down + enter → {s['id']}")
    return 0


def cmd_report(write_doc: bool = False) -> int:
    root = build_reference_tree()
    leaves = collect_leaf_costs(root)
    stats = ergonomics_stats(leaves)
    leaves_sorted = sorted(leaves, key=lambda L: (-L["cost"], L["path"]))

    print(f"Blätter:       {stats['count']}")
    print(f"Median-Kosten: {stats['median']}")
    print(f"Max-Kosten:    {stats['max']}")
    print(f"Min-Kosten:    {stats['min']}")
    print(f"Mittel:        {stats['mean']}")
    print(f"Kosten > 20:   {stats['over_20']}")
    print(f"Unerreichbar:  {stats['unreachable']}")
    print()
    print(f"{'Kosten':>6}  {'Tiefe':>5}  {'OK':>3}  Pfad")
    for L in leaves_sorted[:40]:
        ok = "ja" if L["reachable"] else "nein"
        print(f"{L['cost']:6d}  {L['depth']:5d}  {ok:>3}  {L['path']}")
    if len(leaves_sorted) > 40:
        print(f"  … {len(leaves_sorted) - 40} weitere")

    if write_doc:
        _write_ergonomie_doc(leaves_sorted, stats)
    return 0


def _write_ergonomie_doc(leaves: List[dict], stats: dict) -> str:
    out_dir = os.path.join(REPO_ROOT, "docs", "menue")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "MENU-ERGONOMIE.md")
    ver = open(os.path.join(REPO_ROOT, "VERSION"), encoding="utf-8").read().strip()
    top10 = leaves[:10]
    over20 = [L for L in leaves if L["cost"] > 20]
    unreachable = [L for L in leaves if not L["reachable"]]

    lines = [
        "# Menü-Ergonomie (Skip-Only)",
        "",
        f"**Stand:** v{ver} · {date.today().isoformat()}",
        "",
        "Kennzahl: minimale Tastendrücke (`down`/`enter`, kein `back`) vom Wurzelmenü",
        "bis zum Ziel. „Zurueck“-Einträge zählen als normale Knoten.",
        "",
        "## Vorher-Stand (Baseline vor M4)",
        "",
        "| Kennzahl | Wert |",
        "|----------|------|",
        f"| Blätter | {stats['count']} |",
        f"| Median-Kosten | {stats['median']} |",
        f"| Mittel | {stats['mean']} |",
        f"| Max-Kosten | {stats['max']} |",
        f"| Min-Kosten | {stats['min']} |",
        f"| Blätter mit Kosten > 20 | {stats['over_20']} |",
        f"| Unerreichbar (info) | {stats['unreachable']} |",
        "",
        "### Top 10 teuerste Ziele",
        "",
        "| Kosten | Tiefe | Pfad | Label |",
        "|--------|-------|------|-------|",
    ]
    for L in top10:
        lines.append(f"| {L['cost']} | {L['depth']} | `{L['path']}` | {L['label']} |")

    lines += [
        "",
        "### Unerreichbare Info-Knoten (B5)",
        "",
    ]
    if unreachable:
        for L in unreachable:
            lines.append(f"- `{L['path']}` — {L['label']}")
    else:
        lines.append("- (keine)")

    lines += [
        "",
        f"### Blätter mit Kosten > 20 ({len(over20)})",
        "",
    ]
    for L in over20[:30]:
        lines.append(f"- {L['cost']}: `{L['path']}`")
    if len(over20) > 30:
        lines.append(f"- … und {len(over20) - 30} weitere")

    lines += [
        "",
        "## Messung wiederholen",
        "",
        "```bash",
        "pidrivectl menu report",
        "pidrivectl menu cost sources/dab/dab_stations/<id>",
        "```",
        "",
        "Nach M4 hier einen Abschnitt **Nachher** ergänzen (nicht überschreiben).",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nDokument geschrieben: {path}")
    return path
