# Tests

| Bereich | Wo | Läuft |
|---------|-----|--------|
| Offline-CI | `bash tools/ci_offline.sh` / GitHub Actions | ohne Hardware |
| Unit + Verträge | `tests/unit/` (pytest) | CI |
| WebUI-Oberfläche | `tests/webui/required_surface.json` + Flask-Smoke | CI — Seiten/APIs/sendCmd |
| Menü tot/Walk | `pidrivectl menu lint\|walk` + iDrive-Skripte | CI — leere Actions, doppelte IDs, activate |
| Golden Menü | `tests/golden/menu_tree.json` | CI + `pidrivectl menu verify` |
| WebUI-Inventar | `tests/webui/routes.json` | CI + `pidrivectl webui check` |
| iDrive-Skripte | `tests/idrive/*.txt` | CI offline / Pi live |
| HW-Suite | `pidrivectl test all` | **nur Pi** (RTL/BT/Audio); inkl. WebUI Live-Smoke |
| WebUI Live-Smoke | `tools/webui_live_smoke.py` / `pidrivectl webui smoke` | Pi — Flows/Timings/State-Machine |

CI schlägt fehl bei: Doc-Link-Brüchen, Import-Fehlern, Menü-Verlusten,
WebUI-Vertragsbrüchen (Seiten/APIs/Buttons/onclick), fehlenden Statusfeldern,
VERSION-Drift, Routen die nicht im Inventar stehen.

**WebUI absichtlich erweitern?** Pflicht-Routen/Befehle in
`tests/webui/required_surface.json` ergänzen; Inventar mit
`pidrivectl webui check` aktualisieren.
