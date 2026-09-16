"""Menü-Vertrag: tote Einträge, Walk, iDrive-Skripte."""
from __future__ import annotations

from pathlib import Path

from menu import idrive_sim, menu_golden
from menu.menu_state import MenuState
from trigger.trigger_dispatcher import would_handle


def test_menu_verify_no_losses():
    assert menu_golden.cmd_verify() == 0


def test_menu_lint_no_errors():
    assert menu_golden.cmd_lint() == 0


def test_menu_walk_all_reachable():
    assert menu_golden.cmd_walk() == 0


def test_menu_rebuild_keeps_cursor():
    assert menu_golden.cmd_rebuild_test() == 0


def test_no_duplicate_ids():
    nodes = menu_golden.walk_tree(menu_golden.build_reference_tree())
    seen = {}
    dups = []
    for n in nodes:
        if n["id"] in seen:
            dups.append((n["id"], seen[n["id"]], n["path"]))
        else:
            seen[n["id"]] = n["path"]
    assert not dups, f"Doppelte Menü-IDs (tote activate/goto):\n{dups}"


def test_no_collision_suffix_path_ids():
    nodes = menu_golden.walk_tree(menu_golden.build_reference_tree())
    bad = [n["path_id"] for n in nodes if "#" in (n.get("path_id") or "").split("/")[-1]]
    assert not bad, f"path_id Kollisions-Suffix:\n{bad}"


def test_action_toggle_have_handlers():
    nodes = menu_golden.walk_tree(menu_golden.build_reference_tree())
    dead = []
    for n in nodes:
        if n["type"] not in ("action", "toggle"):
            continue
        act = n.get("action")
        if not act:
            dead.append(f"leer: {n['path']}")
        elif not would_handle(act):
            dead.append(f"unbekannt {act!r}: {n['path']}")
    assert not dead, "Menüpunkte ohne Funktion:\n  " + "\n  ".join(dead)


def test_stations_playable_meta():
    nodes = menu_golden.walk_tree(menu_golden.build_reference_tree())
    bad = []
    for n in nodes:
        if n["type"] != "station":
            continue
        src = n.get("source") or ""
        meta = n.get("meta") or {}
        if not src:
            bad.append(f"{n['path']}: kein source")
        elif src == "fm" and not meta.get("freq"):
            bad.append(f"{n['path']}: fm ohne freq")
        elif src == "webradio" and not meta.get("url"):
            bad.append(f"{n['path']}: webradio ohne url")
        elif src == "dab" and not (meta.get("name") or meta.get("service_id")):
            bad.append(f"{n['path']}: dab ohne name/sid")
    assert not bad, "Sender ohne Abspiel-Meta:\n  " + "\n  ".join(bad)


def test_activate_all_actionable_leaves():
    root = menu_golden.build_reference_tree()
    state = MenuState(root)
    fails = []
    for n in menu_golden.walk_tree(root):
        if n["type"] not in ("station", "action", "toggle"):
            continue
        got = state.activate(n["uid"])
        if got is None or got.uid != n["uid"]:
            fails.append(n.get("path_id") or n["path"])
    assert not fails, f"activate tot ({len(fails)}):\n  " + "\n  ".join(fails[:20])


def test_folders_have_back_and_selectable():
    root = menu_golden.build_reference_tree()
    nodes = menu_golden.walk_tree(root)
    by_path = {n["path"]: n for n in nodes}
    bad = []
    for n in nodes:
        if n["type"] != "folder" or n["path"] == "root":
            continue
        prefix = n["path"] + "/"
        kids = [
            p for p in by_path
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]
        if not kids:
            bad.append(f"leer: {n['path']}")
            continue
        if not any(not by_path[p].get("skip_on_nav") for p in kids):
            bad.append(f"nur skip: {n['path']}")
        if not menu_golden._folder_has_back_from_nodes(n, by_path):
            bad.append(f"kein back: {n['path']}")
    assert not bad, "Ordner-Struktur:\n  " + "\n  ".join(bad)


def test_idrive_rockfm_offline(repo_root: Path):
    script = repo_root / "tests" / "idrive" / "rockfm.txt"
    assert script.is_file()
    assert idrive_sim.run_script(str(script), offline=True) == 0


def test_idrive_stop_offline(repo_root: Path):
    script = repo_root / "tests" / "idrive" / "stop.txt"
    assert script.is_file()
    assert idrive_sim.run_script(str(script), offline=True) == 0


def test_idrive_audio_klinke_offline(repo_root: Path):
    script = repo_root / "tests" / "idrive" / "audio-klinke.txt"
    assert script.is_file()
    assert idrive_sim.run_script(str(script), offline=True) == 0


def test_idrive_bt_scan_offline(repo_root: Path):
    script = repo_root / "tests" / "idrive" / "bt-scan.txt"
    assert script.is_file()
    assert idrive_sim.run_script(str(script), offline=True) == 0
