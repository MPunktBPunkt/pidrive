# Artefakte M0 — Lab Messintegrität 2026-10-03

**ESP:** `.88` · Bridge Pi `.105` · Host Proxmox `.108`  
**Tool:** `tools/m0_lab_mount_sweep.py`  
**Auftrag:** [`../../auftraege/AUFTRAG-M0-MESSINTEGRITAET.md`](../../auftraege/AUFTRAG-M0-MESSINTEGRITAET.md)

## Ergebnis

| Pass | Ordner | FW | Verdict | ΔreadCount | Σ burst.n | emitΔ = lines |
|------|--------|-----|---------|------------|-----------|---------------|
| Lernlauf (falsche Absolut-Gleichung / leerer Export) | `lab88-140905/` | 0.4.37 | FAIL (lehrreich) | — | — | — |
| **M0 Abnahme** | **`lab88-141005/`** | 0.4.37 | **PASS ×2** | 296 / 295 | 296 / 295 | ja |
| **M0 Reconfirm L3** | **`lab88-l3-m0-1542/`** | **0.4.42** | **PASS ×2** | **457 / 457** | 457 / 457 | ja |

**Gleichung (normativ für Soft-Remount-Fenster):**

`ΔreadCount = Σ(burst.n) + Δdrops`

Zusätzlich bestätigt: `ΔreadsEmit = Anzahl JSONL-Burst-Zeilen`.

Streubreite: 296 vs 295 (0.4.37); unter L3/0.4.42 **457/457** (identisch).

## Code-/Betriebs-Hinweise aus dem Lauf

1. Soft-`remountMedia` **resettet `readCount` nicht** (Reset nur USB-Plug-Kante). Absolut-`readCount` ≠ Session-Fenster.  
2. `readsEmit` resettet ebenfalls nicht beim Remount.  
3. Ohne Bridge: `readsEmit=0` und leerer Export trotz Reads.  
4. B7-A 0-Byte-JSONL = Exportpfad/Bridge-Problem, kein Beweis für Telemetrieverlust.  
5. Stimulus hier: Host-`dd`-Nudge (Remount ggf. `skip` bei aktivem Stream) — Bilanz gilt trotzdem.

## Abnahme-Checkliste

- [x] Gleichung pro Fenster  
- [x] Zwei Sweeps, Trace >0, diag >0  
- [x] Session-Hinweis dokumentiert (Δ, nicht Absolut)  
- [x] Leerer Export = Fail (Lernlauf)

**M3 freigegeben** aus Messintegritäts-Sicht (Lab). Feld weiter Session-Δ + nicht-leeren Export verlangen.
