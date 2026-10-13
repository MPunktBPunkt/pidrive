# Artefakt-Archiv — Policy

Ziel: Arbeitsbaum schlank halten, ohne Erkenntnis zu verlieren.

## Drei Stufen

| Stufe | Was | Wo |
|-------|-----|-----|
| **Hot** | Aktuelle Lab/Feld-Kampagne, Übergaben, Specs | `docs/betrieb/artifacts-YYYY-MM-DD-*`, `docs/planung/` |
| **Warm (kept)** | Nur Berichte / Summaries (`.md`, kleine `*REPORT.json` / `summary.json`) | `docs/archiv/betrieb-artifacts/kept/<dir>/` |
| **Cold (roh)** | Traces, polls, reads.jsonl, Logs, MP3, Binaries | `docs/archiv/betrieb-artifacts/roh/<dir>.tar.gz` |

Zusätzlich: **Index** `docs/archiv/betrieb-artifacts/index.sqlite` — maschinenlesbare Metadaten (PASS/FAIL, FW, Pfade), **keine** Volltraces.

## Wann was

1. **Nach kanonischer Übergabe** und wenn neuere Läufe die Mechanik ablösen → Tag von Hot nach Warm+Cold archivieren.
2. **Roh-Tar** behalten, solange eine Re-Analyse denkbar ist (F0/D-Leiter, Regression).
3. **Löschen** erst nach bewusstem Go: Index-Zeile behalten, Tar entfernen (oder nur das Tar löschen, kept behalten).

## Was nicht in Git LFS gehört

- Tausende kleine JSON/JSONL → **packen**, nicht LFS.
- Einzelne große Binaries (MP3 ≫ 50 MB) → im Roh-Tar oder später Release/LFS; nicht lose im Hot-Tree.

## Tool

```bash
python3 tools/archive_artifacts_day.py --day docs/betrieb/artifacts-2026-10-07-feld
python3 tools/archive_artifacts_day.py --before 2026-10-08 --apply
```

`--apply` ersetzt das Hot-Verzeichnis durch einen Stub-README mit Link auf kept + roh.
