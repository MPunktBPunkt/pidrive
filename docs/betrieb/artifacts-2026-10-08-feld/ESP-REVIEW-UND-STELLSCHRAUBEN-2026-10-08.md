# ESP-Code-Review (Live-Pfad) und Stellschrauben · 2026-10-08

Stand: `esp32.pidrive-main` FW 0.4.46-dev, Fokus `StreamBuffer.h`, `PumpServer.cpp`, `UsbMscGadget.cpp`, `App.cpp`, `ConfigStore.*`. Keine Codeänderung (Freeze).

## Teil 1 — Review: Was ist falsch oder riskant?

Schwere: **H** = erklärt Feldverhalten / blockiert Dauerstrom, **M** = kann Ton stören, **N** = kosmetisch/Lab.

| # | Schwere | Stelle | Befund | Wirkung im Feld |
|---|---|---|---|---|
| 1 | **H** | `UsbMscGadget::onRead` Play-Detect → `PumpServer` `audio_start` → `StreamBuffer::start()` + `clearId3()` | Der Stream eines Senders wird **erst durch den HU-Read gestartet, der die Daten schon bräuchte**. `start()` leert Ring und ID3. | Tap liefert nie Bild/Ton (s3 Bayern/Rock). Nur der zuvor laufende Sender hat beim nächsten Replug Inhalt. |
| 2 | **H** | `readAt`, Zweig `else { underruns_++; … hostAbsCursor_++ }` | Der Host-Cursor läuft auch in der Stille weiter (1 Byte pro gelesenem Byte, ~800 KB/s), der Producer nur mit 6 KB/s. Nach einem 512-KiB-Read steht der Cursor ~470 KB **vor** `absEnd` (s3: `hostAbs` 822 195 bei `absEnd` ≈ 350 000). | Kein Fehler im engeren Sinn (Design ohne Stall), aber genau der Grund, warum nur ~8 s ankommen. Ein späterer sequentieller Read bekäme ~78 s lang nur Stille. Abhilfe = Stall (Option a). |
| 3 | **M** | `readAt` `kSil[aoff % kSilLen]` / Ring-Grenzen | Live = MPEG-2 L3 22,05 kHz mono; Stille = MPEG-1 L3 44,1 kHz joint stereo. Die Stille-Phase hängt an `aoff`, nicht an einer Frame-Grenze → erster Stille-Frame ist angeschnitten; ebenso endet der Live-Teil mitten im Frame (`absEnd`), und `absBase` beginnt nach Byte-Überschreiben mitten im Frame. | Decoder muss resyncen und bekommt einen Formatwechsel (Samplerate/Kanäle). Kandidat für die fehlenden 2–3 s (8,2 s gerechnet, 5–6 s gehört) — Stufenplan R7. |
| 4 | **M** | `StreamBuffer::push` (loop-Task, aus `PumpServer::drainTcp`) ↔ `readAt` (TinyUSB-Task) | Kein Mutex/Critical Section. `head_`, `size_`, `absBase_`, `absEnd_` werden einzeln geändert; `start()`/`clear()` kann mitten in einem `readAt` laufen. | Selten falsche/verschobene Bytes, kurze Knackser. Nicht Ursache des 8-s-Fensters. Abhilfe: Snapshot (base/end/head) unter `portENTER_CRITICAL` am Read-Anfang. |
| 5 | **M** | `PumpServer` `audio_start` | `start()` leert auch dann, wenn derselbe uid schon läuft (z. B. `play_replay` nach Reconnect, erneuter Tap). | Ein voller Ring kann ohne Not verworfen werden. Prüfen, ob die Bridge bei gleichem uid neu startet. |
| 6 | **M** | `PumpServer::acceptTcp` (sticky Link) | Zweiter Bridge-Host wird sofort geschlossen — gewollt, aber ohne Event/Log beim Abweisen. | s3: Capture-Bridge starb unbemerkt (BrokenPipe), `msc_reads` leer. Jetzt im Wrapper abgefangen (Pi-seitig). |
| 7 | N | `appendId3` | ID3 > 12 KiB wird still abgeschnitten; Tag-Header verspricht dann mehr Bytes → HU würde Audio als Tag überspringen. | Aktuell kein Problem: Bridge skaliert Cover auf ≤ 2500 B (`resize_jpeg`), ID3 ≈ 3,5 KB. |
| 8 | N | `/api/lab/overlay_read` | Ruft `readAt` auf → verschiebt `hostAbsCursor_`/`hostExpectFileOff_` und zählt Underruns. | Lab-Messung kann den HU-Pfad verfälschen; nie parallel zur HU/Simulator. |
| 9 | N | `remountMedia` | Wird übersprungen, solange ein Stream aktiv ist (`msc.remount_skip streaming`). | `/api/lab/remount` taugt nicht als „Software-Replug mit vollem Ring“; erst `audio_stop` → Ring weg. |
| 10 | N | `ConfigStore` `bufferTargetMs`, `timingProfile` | Werden gespeichert und angezeigt, aber **nirgends verwendet**. | „Buffer Ziel (ms)“ in der WebUI ist ein Placebo-Regler. |
| 11 | N | `UiPages.h` `cfg-play-plug` | Fallback in der UI 2500 ms, FW-Default 500 ms. | Nur relevant, wenn das Feld im JSON fehlt. |

**Fazit Review:** Kein einzelner „Tippfehler-Bug“, der den Dauerstrom verhindert. Das 8-s-Fenster ist die direkte Folge von #2 (kein Stall) plus Ringgröße; „nur BOB“ ist #1. #3 ist der beste Kandidat für 5–6 s statt 8 s, #4 sollte beim nächsten FW-Go mitgefixt werden.

## Teil 2 — Stellschrauben: Was kann man ohne Neu-Flashen verändern?

**Kurz: GPT lag teilweise richtig.** Für Ring, Timings des Live-Pfads und Samplerate gibt es **keine** Laufzeit-Regler im ESP. Es gibt aber Regler für die Play-Erkennung (ESP, sofort wirksam) und für Format/Bitrate auf dem Pi.

### 2.1 ESP zur Laufzeit (`/api/config`, NVS „pidrive“, WebUI-Seite Einstellungen)

Setzen über WebUI (SoftAP/STA, Abschnitt Einstellungen) oder per curl. Teil-JSON ist erlaubt, Werte werden in NVS gespeichert und die Play-Erkennung sofort neu gesetzt (`applyPlayDetectFromConfig`):

```bash
curl -s http://192.168.178.89/api/config                       # lesen
curl -s -X POST http://192.168.178.89/api/config \
  -H 'Content-Type: application/json' \
  -d '{"playMinSeqBytes":8192,"playCooldownMs":3000}'           # ändern
```

| Feld (NVS-Key) | Default | Grenzen | Wirkung |
|---|---|---|---|
| `playPlugWindowMs` (`play_plug`) | 500 | — | Reads so kurz nach Plug zählen nicht als Play |
| `playMinSeqBytes` (`play_seq`) | 6000 | ≥ 512 | sequentielle Bytes bis „Play erkannt“ |
| `playNavMinSeqBytes` (`play_nav`) | 4096 | ≥ 512 | dasselbe für Navigations-Stubs |
| `playHeadLbaSlop` (`play_head`) | 12 | ≤ 64 | wie nah am Dateikopf ein Read „Kopf“ ist |
| `playCooldownMs` (`play_cd`) | 5000 | — | Sperre gegen Nachbar-Stubs nach einem Play |
| `playPrefetchLbaSlop` (`play_pf`) | 2 | ≤ 32 | Mitte-Datei-Reads als Prefetch verwerfen |
| `labMode` (`lab`) | true | — | schaltet `/api/lab/*` frei |
| `enablePumpTcp`, `pumpTcpPort` | 1, 9090 | — | Pump-Link |
| `bufferTargetMs`, `timingProfile` | 5000, 0 | — | **wirkungslos** (Review #10) |

Für das Tonfenster sind diese Regler zweitrangig; sie beeinflussen, **wann** `play_uid` an den Pi geht (Befund #1), nicht wie viel Audio in der Datei steht.

### 2.2 Pi/Bridge (kein FW-Freeze)

| Regler | Wo | Wirkung aufs Fenster |
|---|---|---|
| `--bitrate` (48k Default) | `pump_bridge.py` CLI / Service-Unit | Fenster = 49 152 B / (Bitrate/8): 48k 8,2 s · 32k 12,3 s · 24k 16,4 s · 96k 4,1 s |
| `--marker` | CLI | 1-kHz-Piep alle 10 s, Zeitmarke im Ton |
| Samplerate 22 050 / mono | fest im ffmpeg-Aufruf | nur per Code-Änderung am Pi (erlaubt, kein ESP-Flash) — z. B. für ein Format-A/B gegen die 44,1-kHz-Stille (Review #3) |
| `AUDIO_TARGET_BPS_MIN` 9000 | Konstante in `pump_bridge.py` | Burst-Obergrenze, ändert das Fenster nicht |

### 2.3 Nur mit FW-Go (Compile-Zeit)

| Konstante | Datei | Wert | Bedeutung |
|---|---|---|---|
| `kCapacity` | `StreamBuffer.h` | 48 KiB | Ring = Fensterlänge |
| `kId3Max` | `StreamBuffer.h` | 12 KiB | Sticky-ID3 |
| `kHeadResyncFileBytes`, `kSeqSlop` | `StreamBuffer.h` | 8192 | Cursor-Snap/Sequenzerkennung |
| `kOverlayWarmupBytes` | `PumpServer.h` | 0 | Vorlauf vor Overlay-Arm |
| Slot-Geometrie L3 | `MscGeo` | 512 KiB/Slot | Dateigröße = 87 s @48k |
| Stille-Format | `Mp3Silence.h`, `kSil` | MPEG-1 44,1 k 48k | Formatwechsel |

**Empfehlung:** Für s4 nur `--bitrate` variieren (Modelltest, FELDPROTOKOLL-S4). ESP-Regler unverändert lassen, damit Läufe vergleichbar bleiben. Beim nächsten FW-Go wäre ein Laufzeit-Regler für `kCapacity` (bis SRAM-Grenze) und eine Stall-Zeit `stall_ms` der sinnvollste Ausbau.
