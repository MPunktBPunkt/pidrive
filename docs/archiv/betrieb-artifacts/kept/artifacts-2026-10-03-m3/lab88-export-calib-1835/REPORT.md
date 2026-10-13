# Lab Export-Kalibrierung A+B — 2026-10-03 18:35

**FW:** `0.4.42-dev` · ESP `.88` · Bridge `.105 --no-audio` · Host `.108` `/dev/sda` 16 MiB  
**Tool:** `tools/m3_lab_export_calib.py`  
**Artefakte:** `report.json` · `EAR.txt` · `A1/A2/B-*.jsonl`

## Ergebnis

| Arm | Soll | Ist |
|-----|------|-----|
| **A1** Bridge-up Control | `Δrc = Σn`, Export vollständig | **PASS** `d_rc=64 = sum_n`, `ov=0`, 23 JSONL-Zeilen |
| **A2** Pre-Connect | Reads ohne Bridge → Export≪1, `ov` klein | **PASS** `tcp=false` während Blind; `blind_rc=256`; `export_frac=0.0`; `ov=0`; `ΔreadsEmit=0` |
| **B** Gaps 10/50/100 ms | je `Δrc=Σn`, vollständig | **PASS** alle drei `d_rc=48=sum_n`, `ov=0` |

**Operator-Regel (D):** Bridge-TCP **vor** Remount/Plug/Host-Stimulus für quantitative M3seq.

## Nebenbefunde (Messmethode)

1. **`mv` + neue Datei** während offenem Bridge-Append → Writes landen im Archive-Inode; Live-JSONL leer. Fix im Tool: `cp` + `truncate -s 0` (gleiche Inode).  
2. Bridge-Reconnect nach Kill ohne Warten auf `pumpTcpUp=false` → `BrokenPipe` / toter Bridge → B ohne Export. Fix: Kill verifizieren, Ensure mit Retry + TCP-Wait.  
3. Frühere Läufe `1822`/`1830` methodisch verworfen (leerer Export / Kill nicht verifiziert).

## Burst-Aggregation (B)

Bei festem Stimulus 48 Sektoren (6×8) entstehen **14–16** JSONL-Zeilen (`kBurstGapMs=50`) — Σ`n` bleibt 48. Gap 10 ms vs 100 ms ändert Vollständigkeit nicht; Aggregation nur Zeilenzahl.
