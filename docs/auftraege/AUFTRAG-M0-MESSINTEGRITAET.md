# Auftrag M0 — MSC-Messintegrität (klein, scharf)

**Stand:** 2026-10-03 · aktiv  
**Überordnung:** [`AUFTRAG-MSC-HOST-READ-NACHWEIS.md`](AUFTRAG-MSC-HOST-READ-NACHWEIS.md) Rev. 4  
**Repo FW:** `esp32.pidrive` · Bridge/Tools: `pidrive`  
**Kein:** Ring, Geometrie-Umbau, Play-Detect-Rewrite, Live-Overlay.

---

## Ziel

Sicherstellen, dass Host-Read-Zähler und exportierte Telemetrie **dieselbe Session** beschreiben und die Gleichung aufgeht — bevor M3 LBA-Muster interpretiert.

## Bekannte Befunde (Evidenz)

| Befund | Klasse | Hinweis |
|--------|--------|---------|
| Status L0: `readCount=806`, `readsEmit=218`, `readOverflow=0` | dokumentiert | Status JSON §11.12 Artefakte |
| `kBurstGapMs=50`, `kBurstMaxN=32`, Burst-Merge in `drainPendingReads` | **Code** | `UsbMscGadget.h/.cpp` — `readsEmit` = Burst-Flushes, nicht SCSI-Count |
| Hypothese 806/218 ≈ 3,7 Reads/Zeile | Interpretation | **erste** M0-Prüfhypothese (Mistral); gegen `Σ burst.n` verifizieren |
| B7-A `pidrive_msc_reads.jsonl` / `diag` = **0 Bytes** | dokumentiert | `artifacts-2026-10-03-b7/fav0-123818/` — Exportpfad tot trotz Counter |
| B7-A Polls: `rc` 421→0 bei t≈3,4 s | Rohdaten `replug-1231` / fav0 | Session-/Boot-Grenze; keine Cross-Session-Deltas |

## Arbeiten

### 1. Zählsemantik (Code + Lab)

1. Bestätigen: `readCount` = SCSI-/Host-Read-Ereignisse; `readsEmit` = `noteReadsEmitted` pro **Burst-Emit**.  
2. Lab-Mount-Sweep: `readCount == Σ(n über exportierte Bursts) + readOverflow` (bzw. explizite Drop-Zähler).  
3. Status-Felder dokumentieren (COUNTER-SEMANTICS ergänzen falls nötig).

### 2. Session-Identität

Jeder Poll / jedes Read-Event / Artefakt-Meta:

- Boot-/Session-ID (monoton oder bootMs + serial)  
- `uptime`, `msSincePlug`, `usbSerial`, FW-Version  
- Replug-Zeit, erster/letzter Read  

Polls vor Session-Marker **nicht** mit neuer Session verrechnen.

### 3. Exportpfad-Integrität

1. Wo schreibt Bridge `/tmp/pidrive_msc_reads.jsonl` **und** `/tmp/pidrive_msc_diag.jsonl`? (beide Handler — B7-A hatte **beide** 0 Bytes → gemeinsamer Ausfallpunkt prüfen)  
2. Warum B7-A leer trotz `readCount`? (`readsHandler_`/`Pump` down, Offset-Slice, OTA, Bridge nur auf anderem Host)  
3. Session-Ende: Zeilenzahl / `Σ n` vs. `readCount` als Checksumme ins Summary.  
4. Leerer Export = **Fail** des Passes für jedes Transporturteil (Tools müssen das markieren).

**Code-Hinweis:** `readsEmit` steigt nur über `noteReadsEmitted()` im Pump-Pfad — **ohne** verbundenen `pump_bridge` bleibt `readsEmit=0` trotz `readCount↑`. M0-Lab braucht Bridge→ESP **vor** dem Sweep.

### 4. Trace-Inhalt

Zwei reproduzierbare Lab-Mount-Sweeps mit **nicht-leerem** Trace; LBA grob klassifizierbar (FAT/DIR/Head/Body).  
Doppel-Lauf zusätzlich für **Streubreite**: gleiche `readCount`? (Auto-Replug oft deterministisch ~421 — Lab-Vergleich für M3-Übertragbarkeit.)

### 5. Session-ID (minimal)

`bootMs`/`uptime` + `usbSerial` (+ FW) reichen — **kein** neues NVS-Feld. Bilanz nur Pi-Tooling (`Σ burst.n` im Summary).

## Gleichung (normativ)

```
ΔreadCount = Σ(burst.n) + Δdrops   # Soft-Remount / Beobachtungsfenster
```

Absolut-`readCount` nur nach **USB-Plug-Reset** (Code: `onUsbPlugged`). Soft-`remountMedia` setzt Counter **nicht** zurück.

**nicht** `readCount = Anzahl JSONL-Zeilen + drops`.  
`readsEmit` = Burst-Flushes (`kBurstGapMs=50`); `ΔreadsEmit` sollte = JSONL-Zeilen im Fenster.  
`readOverflow=0` ≠ Vollständigkeitsbeweis ohne Σ-Bilanz.

## Lab-Ergebnis 2026-10-03

Siehe [`../betrieb/artifacts-2026-10-03-m0/`](../betrieb/artifacts-2026-10-03-m0/) — **PASS** (2×): Δrc 296/295 = Σn; emitΔ = Zeilen; diag>0.

## Abnahme

- [x] Gleichung pro Session/Fenster erfüllt (Batch-`n` korrekt einbezogen) — Lab 2026-10-03  
- [x] Zwei Mount-Sweeps repro; Trace-Dateien >0 und inhaltlich stimmig  
- [x] Session-Grenze / Δ-Semantik in Tools/Docs verankert  
- [x] Leerer Export = Fail (explizit; Lernlauf `lab88-140905`)  
- [x] `diag`-JSONL im Lab-Sweep >0  

**Danach erst M3.**

## Praxis-Hinweise (Mistral + Lab)

1. **reads + diag** prüfen (gemeinsamer Bridge-Ausfall).  
2. Doppel-Lauf → Streubreite notieren (hier 296 vs 295).  
3. Session-ID minimal: `uptime`/`usbSerial`/`remountGen`/`FW` — kein NVS.  
4. Tool: `tools/m0_lab_mount_sweep.py`.

## Nicht-Ziele

Firmware-Großumbau; Play-Detect; Live; Ring; „auf Verdacht“ neue Counter ohne Gleichung.
