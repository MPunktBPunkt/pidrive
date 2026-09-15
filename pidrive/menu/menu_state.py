#!/usr/bin/env python3
"""menu_state.py — MenuNode + MenuState  v0.11.127
Ausgelagert aus menu_model.py."""

import log
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# ── MenuNode ──────────────────────────────────────────────────────────────────

@dataclass
class MenuNode:
    id:       str
    label:    str
    type:     str   # folder / station / action / toggle / info

    children:  List["MenuNode"] = field(default_factory=list)
    action:    Optional[str]    = None
    source:    Optional[str]    = None   # fm / dab / webradio / spotify
    playable:  bool = False
    active:    bool = False
    meta:      Dict[str, Any] = field(default_factory=dict)
    # M1: stabile Adressierung (nach annotate_tree gesetzt)
    path_id:   str = ""
    uid:       int = 0
    skip_on_nav: bool = False

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "label":    self.label,
            "type":     self.type,
            "action":   self.action,
            "source":   self.source,
            "playable": self.playable,
            "active":   self.active,
            "meta":     self.meta,
            "path_id":  self.path_id,
            "uid":      self.uid,
            "skip_on_nav": self.skip_on_nav,
            "has_children": len(self.children) > 0,
        }


# ── MenuState ─────────────────────────────────────────────────────────────────

class MenuState:
    """Stack-basierte Navigation — beliebig viele Ebenen."""

    def __init__(self, root: MenuNode):
        self._root: MenuNode = root
        self._stack:   List[MenuNode] = [root]
        self._cursors: List[int]      = [0]
        self.rev: int = 0
        self.uid_counter: int = 1
        self._last_uid_set: set = set()
        try:
            from menu.menu_annotate import collect_uid_set
            self._last_uid_set = collect_uid_set(root)
        except Exception:
            pass
        self._cursors[-1] = self._first_selectable(root.children)

    @property
    def root(self) -> MenuNode:
        return self._root

    @root.setter
    def root(self, _value: MenuNode):
        raise AttributeError("menu_state.root ist privat — MenuState.rebuild(new_root) verwenden")

    @property
    def current(self) -> MenuNode:
        return self._stack[-1]

    @property
    def cursor(self) -> int:
        return self._cursors[-1]

    @property
    def depth(self) -> int:
        return len(self._stack)

    @property
    def path(self) -> List[str]:
        return [n.label for n in self._stack]

    @property
    def path_ids(self) -> List[str]:
        return [n.path_id for n in self._stack]

    @property
    def current_nodes(self) -> List[MenuNode]:
        return self.current.children

    @property
    def selected(self) -> Optional[MenuNode]:
        nodes = self.current_nodes
        if not nodes:
            return None
        return nodes[min(self.cursor, len(nodes) - 1)]

    @property
    def selected_folder(self) -> Optional[MenuNode]:
        """Aktuell geöffneter Folder (letztes Element im Stack, v0.9.21)."""
        if len(self._stack) > 1:
            return self._stack[-1]
        return None

    @staticmethod
    def _first_selectable(nodes: List[MenuNode]) -> int:
        for i, n in enumerate(nodes):
            if not n.skip_on_nav:
                return i
        return 0

    def key_up(self):
        nodes = self.current_nodes
        before = self._cursors[-1]
        i = before - 1
        while i >= 0 and nodes[i].skip_on_nav:
            i -= 1
        if i >= 0:
            self._cursors[-1] = i
            self.rev += 1
        log.info(f"MENU_NAV up before={before} after={self._cursors[-1]} n={len(nodes)} rev={self.rev}")

    def key_down(self):
        nodes = self.current_nodes
        before = self._cursors[-1]
        n = len(nodes)
        i = before + 1
        while i < n and nodes[i].skip_on_nav:
            i += 1
        if i < n:
            self._cursors[-1] = i
            self.rev += 1
        log.info(f"MENU_NAV down before={before} after={self._cursors[-1]} n={n} rev={self.rev}")

    def key_enter(self):
        node = self.selected
        if node is None:
            return
        if node.type == "folder" and node.children:
            self._stack.append(node)
            self._cursors.append(self._first_selectable(node.children))
            self.rev += 1
            return node
        elif node.type in ("station", "action", "toggle"):
            self.rev += 1
            return node
        return None

    def key_back(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._cursors.pop()
            self.rev += 1

    def key_left(self):
        self.key_back()

    def key_right(self):
        return self.key_enter()

    def navigate_to(self, node_id: str):
        for i, node in enumerate(self.root.children):
            if node.id == node_id or node.label.lower() == node_id.lower():
                self._stack   = [self.root, node]
                self._cursors = [i, self._first_selectable(node.children)]
                self.rev += 1
                return True
        try:
            idx = int(node_id)
            if 0 <= idx < len(self.root.children):
                node = self.root.children[idx]
                self._stack   = [self.root, node]
                self._cursors = [idx, self._first_selectable(node.children)]
                self.rev += 1
                return True
        except (ValueError, TypeError):
            pass
        return False

    def goto(self, path_id: str) -> bool:
        """Navigiert zu beliebig tiefer path_id (M2). Cursor auf dem Zielknoten."""
        parts = [p for p in path_id.strip("/").split("/") if p]
        if parts and parts[0] == "root":
            parts = parts[1:]
        if not parts:
            self._stack = [self.root]
            self._cursors = [self._first_selectable(self.root.children)]
            self.rev += 1
            return True

        node = self.root
        stack: List[MenuNode] = [self.root]
        parent_cursors: List[int] = []

        for part in parts:
            found = None
            for i, child in enumerate(node.children):
                if child.id == part:
                    found = (child, i)
                    break
            if found is None:
                return False
            child, idx = found
            parent_cursors.append(idx)
            stack.append(child)
            node = child

        # Stack = Pfad bis Elternordner; Cursor zeigt auf Ziel
        self._stack = stack[:-1]
        self._cursors = list(parent_cursors)
        self.rev += 1
        return True

    def activate(self, uid: int) -> Optional[MenuNode]:
        """Findet Knoten per UID und liefert ihn (PlayItem-Äquivalent)."""
        node = self._find_node_by_uid(self.root, uid)
        if node is None:
            return None
        if not self.goto(node.path_id):
            return None
        if node.type == "folder" and node.children:
            self.key_enter()
            return node
        if node.type in ("station", "action", "toggle", "info"):
            self.rev += 1
            return node
        return node

    def _find_node_by_uid(self, node: MenuNode, uid: int) -> Optional[MenuNode]:
        if node.uid == uid:
            return node
        for child in node.children:
            hit = self._find_node_by_uid(child, uid)
            if hit is not None:
                return hit
        return None

    def rebuild(self, new_root: MenuNode) -> None:
        """Einziger erlaubter Baumtausch — rettet Pfad und Cursor über path_id/uid (M2)."""
        old_path_ids = list(self.path_ids)
        old_selected_uid = self.selected.uid if self.selected else None
        old_cursor = self.cursor

        self._root = new_root
        self._stack = [new_root]
        self._cursors = [self._first_selectable(new_root.children)]

        for want in old_path_ids[1:]:
            parent = self._stack[-1]
            idx = None
            for i, child in enumerate(parent.children):
                if child.path_id == want:
                    idx = i
                    break
            if idx is None:
                want_id = want.rsplit("/", 1)[-1]
                for i, child in enumerate(parent.children):
                    if child.id == want_id:
                        idx = i
                        break
            if idx is None:
                break
            self._cursors[-1] = idx
            child = parent.children[idx]
            self._stack.append(child)
            self._cursors.append(self._first_selectable(child.children))

        nodes = self.current_nodes
        if nodes and old_selected_uid is not None:
            hit = None
            for i, child in enumerate(nodes):
                if child.uid == old_selected_uid:
                    hit = i
                    break
            if hit is not None:
                self._cursors[-1] = hit
            else:
                i = min(old_cursor, len(nodes) - 1)
                if nodes[i].skip_on_nav:
                    i = self._first_selectable(nodes)
                self._cursors[-1] = i

        self.clamp_cursors()
        self.rev += 1
        try:
            from menu.menu_annotate import collect_uid_set
            return self.note_uid_set(collect_uid_set(new_root))
        except Exception:
            return False

    def clamp_cursors(self):
        for depth in range(len(self._stack)):
            if depth == 0:
                if len(self._stack) > 1:
                    try:
                        self._cursors[0] = self.root.children.index(self._stack[1])
                    except ValueError:
                        self._cursors[0] = 0
            else:
                parent   = self._stack[depth - 1]
                children = parent.children
                old_cur  = self._cursors[depth] if depth < len(self._cursors) else 0
                if not children:
                    self._cursors[depth] = 0
                else:
                    self._cursors[depth] = min(old_cur, len(children) - 1)

    def note_uid_set(self, uids: set) -> bool:
        """uid_counter erhöhen wenn sich die UID-Menge geändert hat."""
        if uids != self._last_uid_set:
            self.uid_counter += 1
            self._last_uid_set = set(uids)
            return True
        return False

    def export(self) -> dict:
        nodes = self.current_nodes
        cursor = min(self.cursor, max(0, len(nodes) - 1))
        return {
            "rev":       self.rev,
            "path":      self.path,
            "path_ids":  self.path_ids,
            "title":     " / ".join(self.path[-2:]) if len(self.path) > 1 else self.path[0],
            "cursor":    cursor,
            "can_back":  self.depth > 1,
            "nodes":     [n.to_dict() for n in nodes],
            # Compat (deprecated — entfernen nach WebUI-Umstellung)
            "cat":        0,
            "cat_label":  self._stack[1].label if len(self._stack) > 1 else self.root.label,
            "item":       cursor,
            "item_label": nodes[cursor].label if nodes else "",
            "categories": [c.label for c in self.root.children],
            "items":      [n.label for n in nodes],
        }

    def export_tree(self) -> dict:
        from menu.menu_annotate import export_node_tree
        return {
            "uid_counter": self.uid_counter,
            "rev": self.rev,
            "tree": export_node_tree(self.root),
        }
