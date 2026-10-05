# StreamBuffer / Counter-Semantik · 2026-10-05

**Quelle:** `esp32.pidrive/src/core/StreamBuffer.h` (+ `UsbMscGadget.cpp` Live-Pfad)  
**Anlass:** GPT/Mistral-Review Feldabend — `underruns`/`streamBytes`/`liveBytes` absichern.

## Definitionen

| Feld | Bedeutung |
|------|-----------|
| `absBase` / `absEnd` | Absolute Byte-Koordinaten des Audio-Rings (ohne sticky ID3). Bei `push()` wächst `absEnd`; bei Ring-Voll läuft `absBase` mit (Scroll). |
| `size` / `cap` | Ring-Füllstand / Kapazität (`cap=49152` = 48 KiB). |
| `hostAbsCursor` | Cursor in **Ring-Koordinaten** (nicht fileOff). Bei Cursor-Mode wird er **pro ausgegebenem Byte** hochgezählt — auch bei Underrun. |
| `cursorArmed` | Nach erstem Live-Read (oder Head-Resync) true. |
| `underruns` | Bytes, die bei `active` **nicht** aus `[absBase, absEnd)` kamen → Silence-Frame-Fill. |
| `msc.streamBytes` | Summe `bufsize` aller MSC-Reads, die den **Live-Pfad** (`stream_->readAt`) genommen haben — **inkl.** Underrun-Silence. |
| `liveBytes` (Correlate) | `streamBytes - underruns` (abgeleitet; FW-Feld existiert nicht). |

## `readAt(fileOff)` (Kern)

1. Sticky ID3: `fileOff < id3Len` → ID3-Bytes, kein Underrun.  
2. Cursor-Arm: erster Read / Head-Nähe / Seek-Back → `hostAbsCursor = absBase`.  
3. Sequentiell + armed → weiter mit Cursor (`aoff = hostAbsCursor`).  
4. Treffer: `active && size>0 && absBase ≤ aoff < absEnd` → Ring-Byte, Cursor++.  
5. Miss: `underruns++`, Silence, **Cursor++ trotzdem**.  
6. `hostExpectFileOff_ = fileOff + n` für Sequenz-Erkennung (`kSeqSlop=8192`).

**Wichtig:** Einmal vor dem Fenster-Ende vorausgelaufen → weitere sequentielle Reads bleiben Outside, bis Head-Resync (`nearHead` + Seek-Back) den Cursor auf `absBase` snapt.

## Feld 15:41 (status-1541) im Licht dieser Semantik

| Beobachtung | Deutung |
|-------------|---------|
| `streamBytes == underruns == hostAbsCursor == 253952` | Jedes Live-Pfad-Byte war Outside/Underrun — Cursor hat nie (oder nie nachhaltig) im Fenster gelesen. |
| Snapshot `absBase=161944..absEnd=211096`, `size=49152` | Ring **später** voll; Cursor bereits **~42 KiB hinter absEnd**. |
| `cursorArmed=true` | Cursor-Mode aktiv (kein reiner fileOff-Pfad). |

→ Fehlerzustand **Fenster-Miss** ist code-kompatibel erklärt als: **Cursor outruns Ring / liest Outside und läuft weiter**. Ob der Host zu früh/mittig startete oder der Producer zu spät füllte, braucht Lab-Zeitreihe (nicht aus einem Snapshot).

## Was `liveBytes>0` bedeutet

Nur Bytes, die tatsächlich aus dem Ring kamen. Silence-Underruns erhöhen `streamBytes`, nicht den Hörinhalt. MPEG-Sync allein reicht nicht (Silence-Frames haben Syncs).
