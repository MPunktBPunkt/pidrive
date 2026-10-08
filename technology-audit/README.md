# technology-audit

Systematische **Technologie-Inventare** und **Technology Sheets** für Hobby-Repos — wiederverwendbar für Folgeprojekte.

## Projekte

| Projekt | Inventar | Sheets |
|---------|----------|--------|
| [esp32.heartrate](projects/esp32.heartrate/) | [INVENTORY.md](projects/esp32.heartrate/INVENTORY.md) | [sheets/](projects/esp32.heartrate/sheets/) |
| PiDrive (geplant) | — | — |

## CI

```bash
bash tools/audit_validate.sh
# Optional: Repo klonen und Inventar-Signale prüfen
bash tools/audit_scan.sh /path/to/repo projects/esp32.heartrate/signals.json
```

GitHub: [`.github/workflows/audit.yml`](.github/workflows/audit.yml) — validiert dieses Repo; optional Scan gegen externes Ziel-Repo (`workflow_dispatch`).

## Docs

- [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
- [docs/TAXONOMY.md](docs/TAXONOMY.md)
