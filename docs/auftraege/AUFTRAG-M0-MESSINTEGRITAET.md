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

1. Wo schreibt Bridge `/tmp/pidrive_msc_reads.jsonl`? Wann startet Handler?  
2. Warum B7-A-Datei 0 Bytes trotz `readCount`? (Handler down, Offset-Slice, OTA, Restart)  
3. Session-Ende: Zeilenzahl / `Σ n` vs. `readCount` als Checksumme ins Summary.

### 4. Trace-Inhalt

Zwei reproduzierbare Lab-Mount-Sweeps mit **nicht-leerem** Trace; LBA grob klassifizierbar (FAT/DIR/Head/Body).

## Abnahme

- [ ] Gleichung pro Session erfüllt (Batch-`n` korrekt einbezogen)  
- [ ] Zwei Mount-Sweeps repro; Trace-Dateien >0 und inhaltlich stimmig  
- [ ] Session-Grenze in Tools/Docs verankert (kein stiller Cross-Boot-Delta)  
- [ ] Leerer Export im Feld = Fail des Passes für Transporturteil (explizit markieren)

**Danach erst M3.**

## Nicht-Ziele

Firmware-Großumbau; Play-Detect; Live; Ring; „auf Verdacht“ neue Counter ohne Gleichung.
