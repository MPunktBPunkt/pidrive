"""Flask-Smoke: Seiten + APIs antworten, Blueprints registriert (kein Hardware nötig)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

SURFACE = json.loads(
    (Path(__file__).resolve().parents[1] / "webui" / "required_surface.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def flask_app():
    from web.app import app

    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(flask_app):
    return flask_app.test_client()


def test_blueprints_registered(flask_app):
    err = flask_app.config.get("BLUEPRINT_IMPORT_ERROR")
    assert err is None, f"Blueprint-Import fehlgeschlagen: {err}"


def test_live_url_map_matches_collect_routes(flask_app):
    """Regex-Inventar vs echte Flask-Registrierung — fängt stille Blueprint-Verluste."""
    from web.webui_check import collect_routes

    collected = {r["path"] for r in collect_routes()}
    live = set()
    for rule in flask_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = rule.rule
        live.add(path)
        live.add(re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"<\1>", path))

    missing = []
    for p in collected:
        if p in live:
            continue
        base = p.split("<")[0]
        if any(str(r).startswith(base) for r in live):
            continue
        missing.append(p)
    assert not missing, (
        "collect_routes findet Routen, die Flask nicht registriert:\n  "
        + "\n  ".join(sorted(missing))
    )


@pytest.mark.parametrize("path", sorted(SURFACE["pages"]))
def test_pages_return_200_with_markers(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    body = r.get_data(as_text=True)
    for marker in SURFACE["pages"][path]["markers"]:
        assert marker in body, f"{path}: Marker {marker!r} fehlt im HTML"


def test_static_api_core_js(client):
    r = client.get("/static/js/api-core.js")
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert "PiDriveAPI" in text
    assert "sendCmd" in text


def test_api_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


def test_api_core_contract(client):
    r = client.get("/api/core")
    assert r.status_code == 200
    data = r.get_json()
    missing = [k for k in SURFACE["core_keys"] if k not in data]
    assert not missing, f"/api/core fehlt Keys: {missing}"
    assert isinstance(data["status"], dict)
    assert isinstance(data["nodes"], list)


@pytest.mark.parametrize("path", SURFACE["apis_get"])
def test_required_apis_get_ok(client, path, tmp_path, monkeypatch):
    if path.startswith("/api/music"):
        import modules.music_library as lib

        music_root = tmp_path / "Musik"
        music_root.mkdir()
        monkeypatch.setattr(
            lib, "get_music_root", lambda settings=None: str(music_root)
        )

    r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    ct = r.content_type or ""
    assert "json" in ct, f"{path} content-type={ct}"
    data = r.get_json(silent=True)
    assert data is not None, f"{path}: keine JSON-Antwort"
    if isinstance(data, dict) and data.get("error") == "Not Found":
        pytest.fail(f"{path}: Not Found — Blueprint/Route fehlt")


def test_api_cmd_allowed(client, tmp_path, monkeypatch):
    import web.app as webapp
    import web.shared.constants as const
    import web.shared.files as files

    cmd_file = tmp_path / "cmd"
    cmd_file.write_text("")
    monkeypatch.setattr(const, "CMD_FILE", str(cmd_file))
    monkeypatch.setattr(webapp, "CMD_FILE", str(cmd_file))
    monkeypatch.setattr(files, "CMD_FILE", str(cmd_file))

    r = client.post("/api/cmd", json={"cmd": "radio_stop"})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True
    assert "radio_stop" in cmd_file.read_text()


def test_api_cmd_rejects_unknown(client):
    r = client.post("/api/cmd", json={"cmd": "prev_station"})
    assert r.status_code == 400
    assert r.get_json().get("ok") is False
