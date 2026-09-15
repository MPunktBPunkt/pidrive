#!/usr/bin/env python3
"""menu_annotate.py — Post-Processing: path_id, uid, skip_on_nav (M1)."""

from typing import Dict, Set

from menu.menu_state import MenuNode


def fnv1a_64(s: str) -> int:
    h = 0xCBF29CE484222325
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def annotate_tree(root: MenuNode) -> MenuNode:
    """
    Rekursiv path_id / uid / skip_on_nav setzen.
    Kollidierende UIDs bekommen ein Suffix an der Hash-Eingabe.
    """
    used_uids: Set[int] = set()

    def _walk(node: MenuNode, parent_path: str):
        if parent_path:
            path_id = f"{parent_path}/{node.id}"
        else:
            path_id = node.id if node.id == "root" else f"root/{node.id}"
            if node.id == "root":
                path_id = "root"

        base = path_id
        uid = fnv1a_64(base)
        n = 0
        while uid in used_uids:
            n += 1
            uid = fnv1a_64(f"{base}#{n}")
        used_uids.add(uid)

        node.path_id = path_id if n == 0 else f"{base}#{n}"
        node.uid = uid
        node.skip_on_nav = node.type == "info"

        for child in node.children:
            _walk(child, node.path_id)

    _walk(root, "")
    return root


def collect_uid_set(root: MenuNode) -> Set[int]:
    uids: Set[int] = set()

    def _walk(node: MenuNode):
        uids.add(node.uid)
        for c in node.children:
            _walk(c)

    _walk(root)
    return uids


def export_node_tree(node: MenuNode) -> dict:
    return {
        "path_id": node.path_id,
        "uid": node.uid,
        "id": node.id,
        "label": node.label,
        "type": node.type,
        "action": node.action,
        "source": node.source,
        "playable": node.playable,
        "active": node.active,
        "skip_on_nav": node.skip_on_nav,
        "children": [export_node_tree(c) for c in node.children],
    }
