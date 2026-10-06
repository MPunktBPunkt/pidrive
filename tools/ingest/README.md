# Artefakt-Ingest (maschinenlesbar)

Review-Quelle: `artifacts-2026-10-06-feld/summary-2026-10-06.txt` (Parquet + DuckDB).

## Layout

```text
docs/betrieb/artifacts-*/**/run.yaml   ← Manifest (eingecheckt)
data/                                  ← generiert, gitignored
  runs.parquet
  status.parquet
  slots.parquet
  msc_reads.parquet
  bridge_events.parquet
  observations.parquet
  pidrive.duckdb
  manifest.json
```

## Setup + Lauf

```bash
python3 -m venv .venv-ingest
.venv-ingest/bin/pip install -r tools/ingest/requirements.txt
.venv-ingest/bin/python tools/ingest/ingest.py --root docs/betrieb
```

Beispiel-Abfrage:

```bash
.venv-ingest/bin/python -c "
import duckdb
c=duckdb.connect('data/pidrive.duckdb')
print(c.execute('''
  SELECT r.run_id, r.heard, max(s.hostAbs) AS max_host, max(s.underruns) AS und
  FROM status s JOIN runs r USING (run_id)
  GROUP BY ALL ORDER BY 1
''').fetchdf())
"
```

## Zukunft

- Neue Polls: `feld_status_poll.py` schreibt JSONL mit `wall_iso` + flachen Feldern (ingest-kompatibel).
- Sim-Reports: `REPORT.json` wird beim Ingest als Status/Observations gelesen.
- Rohdaten unter `artifacts-*` nicht editieren — nur `run.yaml` ergänzen und Ingest neu bauen.
