# GitHub Actions — Überblick & Einbindung

## Bereits definiert (Ziel-Repos)

| Repo | Workflow | Zweck |
|------|----------|--------|
| **pidrive** | `.github/workflows/ci.yml` | Python Offline-CI: `tools/ci_offline.sh` (Docs, Shell, compileall, pytest) — **kein HW** |
| **esp32.heartrate** | `.github/workflows/build.yml` | PlatformIO Matrix `heartrate` + `heartrate-s3`, Firmware-Artifacts |
| **technology-audit** | `.github/workflows/audit.yml` | Struktur-Validate + optional Signal-Scan gegen externes Repo |

## Einbindung empfohlen

### 1. technology-audit (dieses Repo)

- Jeder Push/PR: `audit_validate.sh` (Sheets, INVENTORY, SCOPE).
- Manuell / nach Push: Job **scan** klont z. B. `esp32.heartrate` und schreibt `scan-output.json` als Artifact.

### 2. esp32.heartrate (optionaler Companion-Workflow)

Datei `.github/workflows/technology-audit-scan.yml` (Pilot auf Branch):

- Checkout **dieses** Repo + Checkout **technology-audit** @ main
- `audit_scan.sh` auf esp32.heartrate → Artifact (Drift-Signale vs. manuelles INVENTORY)

Voraussetzung: `technology-audit` für `GITHUB_TOKEN` lesbar (private Repos: Repo-Zugriff für Actions).

### 3. pidrive

- **Nicht** in bestehende `ci.yml` mischen (Laufzeit).
- Stattdessen: periodisch `workflow_dispatch` in **technology-audit** mit `target_repo=pidrive`, oder separater PR der `projects/pidrive/` pflegt.

## Lokal (wie PiDrive CI)

```bash
bash tools/audit_validate.sh
bash tools/audit_scan.sh ../esp32.heartrate
```
