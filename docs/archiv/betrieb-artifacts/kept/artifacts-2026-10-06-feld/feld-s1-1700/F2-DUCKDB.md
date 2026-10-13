# DuckDB-Queries: F2-Teil s1-1700

**Ingest:** `.venv-ingest/bin/python tools/ingest/ingest.py --run docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700`  
**DB:** `data/pidrive.duckdb` (gitignored) · `t_wall` = UTC (= Lokal − 2 h)

Abgleich mit [`F2-TEIL-s1-1700.md`](F2-TEIL-s1-1700.md).

## Muster B (Lokal 17:23 / UTC 15:23)

```sql
SELECT t_wall, playingUid, readCount, hostAbs, underruns
FROM status
WHERE run_id='feld-s1-1700' AND source='status-poll.jsonl'
  AND t_wall BETWEEN TIMESTAMP '2026-10-06 15:23:30' AND TIMESTAMP '2026-10-06 15:23:45'
ORDER BY t_wall;
```

**Ergebnis:** `readCount` 2156→2160→**2284** (+124 ≈ 512 KiB), dann flat; ab 15:23:35 `hostAbs=0`, `underruns=0`.

## Post-RST (Lokal 17:26 / UTC 15:26)

```sql
SELECT t_wall, playingUid, readCount, hostAbs, underruns
FROM status
WHERE run_id='feld-s1-1700' AND source='status-poll.jsonl'
  AND t_wall BETWEEN TIMESTAMP '2026-10-06 15:25:55' AND TIMESTAMP '2026-10-06 15:26:20'
ORDER BY t_wall;
```

**Ergebnis:** 15:26:04 `readCount` 2284→**259** (ESP-Reset); dann 272→339 Scan; `playingUid` leer.

## readCount-Sprünge ≥ 50

```sql
WITH p AS (
  SELECT t_wall, playingUid, readCount,
         lag(readCount) OVER (ORDER BY t_wall) AS prev_rc
  FROM status
  WHERE run_id='feld-s1-1700' AND source='status-poll.jsonl'
)
SELECT t_wall, playingUid, readCount, readCount - prev_rc AS d_rc
FROM p
WHERE prev_rc IS NOT NULL AND readCount - prev_rc >= 50
ORDER BY t_wall;
```

Wichtige Sprünge: +124 (BOB cold), +67 (post-RST scan), danach ~250/s Eager Rock (15:28).

## CLI

```bash
.venv-ingest/bin/python -c "import duckdb; c=duckdb.connect('data/pidrive.duckdb',read_only=True); print(c.execute('''…''').fetchall())"
```
