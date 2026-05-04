#!/usr/bin/env python3
"""menu_state.py — MenuNode + MenuState  v0.10.21
Ausgelagert aus menu_model.py."""

import os
import json
import time
import log
import ipc
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from modules.scanner import BANDS, VHF_RANGE, UHF_RANGE
try:
    from modules import favorites as _fav_mod
except Exception:
    _fav_mod = None


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
            "has_children": len(self.children) > 0,
        }


# ── MenuState ─────────────────────────────────────────────────────────────────

class MenuState:
    """Stack-basierte Navigation — beliebig viele Ebenen."""

    def __init__(self, root: MenuNode):
        self.root          = root
        self._stack:   List[MenuNode] = [root]
        self._cursors: List[int]      = [0]
        self.rev: int = 0

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

    def key_up(self):
        before = self._cursors[-1]
        if self._cursors[-1] > 0:
            self._cursors[-1] -= 1
            self.rev += 1
        log.info(f"MENU_NAV up before={before} after={self._cursors[-1]} n={len(self.current_nodes)} rev={self.rev}")

    def key_down(self):
        before = self._cursors[-1]
        n = len(self.current_nodes)
        if n > 0 and self._cursors[-1] < n - 1:
            self._cursors[-1] += 1
            self.rev += 1
        log.info(f"MENU_NAV down before={before} after={self._cursors[-1]} n={n} rev={self.rev}")

    def key_enter(self):
        node = self.selected
        if node is None:
            return
        if node.type == "folder" and node.children:
            self._stack.append(node)
            self._cursors.append(0)
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
                self._cursors = [i, 0]
                self.rev += 1
                return True
        try:
            idx = int(node_id)
            if 0 <= idx < len(self.root.children):
                node = self.root.children[idx]
                self._stack   = [self.root, node]
                self._cursors = [idx, 0]
                self.rev += 1
                return True
        except (ValueError, TypeError):
            pass
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

    def export(self) -> dict:
        nodes = self.current_nodes
        cursor = min(self.cursor, max(0, len(nodes) - 1))
        return {
            "rev":       self.rev,
            "path":      self.path,
            "title":     " / ".join(self.path[-2:]) if len(self.path) > 1 else self.path[0],
            "cursor":    cursor,
            "can_back":  self.depth > 1,
            "nodes":     [n.to_dict() for n in nodes],
            # Compat
            "cat":        0,
            "cat_label":  self._stack[1].label if len(self._stack) > 1 else self.root.label,
            "item":       cursor,
            "item_label": nodes[cursor].label if nodes else "",
            "categories": [c.label for c in self.root.children],
            "items":      [n.label for n in nodes],
        }



