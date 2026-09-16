"""WebUI-Routen-Inventar darf nicht still schrumpfen / fehlen."""
from __future__ import annotations

import json
from pathlib import Path

from web.webui_check import collect_routes


def test_routes_json_covers_collected(repo_root: Path):
    inv_path = repo_root / "tests" / "webui" / "routes.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8"))
    inv_paths = {r["path"] for r in inv["routes"]}
    current = {r["path"] for r in collect_routes()}
    assert current, "keine Routen gefunden"
    lost = current - inv_paths
    assert not lost, (
        "Routen im Code fehlen in tests/webui/routes.json:\n  "
        + "\n  ".join(sorted(lost))
        + "\n→ In pidrive/: python3 -c \"from web.webui_check import write_routes_json; write_routes_json()\""
    )


def test_routes_inventory_not_empty(repo_root: Path):
    inv = json.loads((repo_root / "tests" / "webui" / "routes.json").read_text())
    assert len(inv["routes"]) >= 40
    assert len(inv["allowed_commands"]) >= 30
