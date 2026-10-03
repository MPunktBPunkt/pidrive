# MSC Counter- und Status-Semantik (0.4.42)

**Zweck:** Felder nicht vermischen. Stand Code `esp32.pidrive` `UsbMscGadget.cpp` / `MenuStore`.

| Feld | Bedeutung (C) | Nicht bedeuten |
|------|----------------|----------------|
| `readCount` | Anzahl SCSI-Read-Aufrufe (Sektor-Gruppen); Reset nur **USB-Plug** | Wiedergabe, Cursor |
| `readsEmit` | Exportierte Burst-Events | vollständige Read-Anzahl bei leerem Export |
| `readOverflow` | verlorene Trace-Slots | „keine Reads“ |
| `bytesFile` | **kumulierte** Byte-Summe aller `Region::File`-Reads seit Plug | eindeutige Dateiabdeckung |
| `slotMap[].bytes` | **kumulierte** File-Read-Bytes in diesen Slot (inkl. Wiederholungen) | `unique covered`; kann **> Dateigröße** sein |
| `slotMap[].maxSeq` | Maximum von `seqBytes_` — längste **zusammenhängende** LBA-Kette (Reset bei Dateiwechsel oder LBA-Sprung > 16) | eindeutige Abdeckung bis EOF |
| `slotMap[].midFile` | Zähler Reads mit `lba > lbaStart+headLbaSlop` | Position |
| `playingUid` / `playingName` | `MenuStore` nach erfolgreichem **play.guess** (`evaluatePlay` OK) | HU-UI-Auswahl; leer ≠ „nichts spielt“ |
| `msc.quiet` `file=NB` | `bytesFile_` zum Zeitpunkt der Quiet-Detection | eindeutige Cache-Menge |

**Bilanz:** `ΔreadCount = Σ(burst.n) + Δoverflow` innerhalb einer Session.

**Trace-Coverage:** `tools/m3_trace_coverage.py` — Intervallvereinigung aus JSONL `kind=2`; immer gegen `bytesFile`/`slot.bytes` prüfen (Export kann unvollständig sein).
