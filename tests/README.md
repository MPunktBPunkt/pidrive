# Tests

| Bereich | Wo | Läuft |
|---------|-----|--------|
| Offline-CI | `bash tools/ci_offline.sh` / GitHub Actions | ohne Hardware |
| Unit + Verträge | `tests/unit/` (pytest) | CI |
| Golden Menü | `tests/golden/menu_tree.json` | CI + `pidrivectl menu verify` |
| WebUI-Inventar | `tests/webui/routes.json` | CI + `pidrivectl webui check` |
| iDrive-Skripte | `tests/idrive/*.txt` | CI offline / Pi live |
| HW-Suite | `pidrivectl test all` | **nur Pi** (RTL/BT/Audio) |

CI schlägt fehl bei: Doc-Link-Brüchen, Import-Fehlern, Menü-Verlusten,
WebUI-Vertragsbrüchen, fehlenden Statusfeldern, VERSION-Drift,
Routen die nicht im Inventar stehen.
