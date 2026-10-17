# Richtlinie: Firmware-/OTA-Bins im pidrive-Repo

**Stand:** 2026-10-17 (Review B4)

| Regel | Inhalt |
|-------|--------|
| Kanon | OTA/USB-Bins leben in **`esp32.pidrive/dist/`** (Build-Repo) |
| Artefakt-Kopie | Im `pidrive`-Repo nur wenn für einen **Feld-Handoff** nötig und **≤ 3 MiB** |
| Verboten | Medien/MP3, Dump-Images, > 3 MiB Blindkopien |
| Nach Feld | Kopie darf bleiben als Trace zum Lauf; Duplikate nicht stapeln (eine Version pro Artefakt-Ordner) |
| Namensschema | `pidrive.<semver>.ota.esp32s3.bin` |

Aktuelles Beispiel: `favoriten-layout-01/pidrive.0.4.53-dev.ota.esp32s3.bin` (~1,4 MiB) — zulässig als einmaliger Lab/Feld-Handoff.
