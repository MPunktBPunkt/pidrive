# Analyse: Wie der Ton als Stream auf die HU kommen kann · 2026-10-08

Grundlage: [`ANALYSE-S3-TONFENSTER-2026-10-08.md`](ANALYSE-S3-TONFENSTER-2026-10-08.md) (Teil 2: M1/M2), [`HU-Technical-Facts.md`](../../fahrzeug/HU-Technical-Facts.md), [SPIKE-TINYUSB-READ10](../artifacts-2026-10-06-lab/SPIKE-TINYUSB-READ10-2026-10-06.md), [Lab C1–C7](../artifacts-2026-10-07-lab/C1-C7-ERGEBNIS.md).
Folgedokumente: [`AUFTRAG-LAB-REALITAET-2026-10-08.md`](AUFTRAG-LAB-REALITAET-2026-10-08.md) · [`STALL-BUILD-SPEC-2026-10-08.md`](../../planung/STALL-BUILD-SPEC-2026-10-08.md)

## 1. Prüfung der zweiten GPT-Zusammenfassung

| # | GPT-Aussage | Bewertung | Beleg / Korrektur |
|---|---|---|---|
| 1 | Faktor ~132 (800 000 / 6000) | richtig | M1: 788–805 KB/s |
| 2 | M2 als Erhaltungsgleichung, 1 511 044 − 471 640 = 1 039 404 = `absEnd` beim Überholen | richtig | M2 |
| 3 | „ID3 ~3,1–3,5 KB + Ring 49 152 B = **Live** ~52,3 KB“ | **falsch beschriftet** | 52,6 KB = ID3 **+** Live. Live allein = 49,2–49,6 KB |
| 4 | Cursor braucht 52 648 / 800 000 ≈ 65,8 ms, „passt zu ~75 ms“ | **ungenau** | Die 65,8 ms unterschlagen die 19-ms-Kopfpause. Gemessen: 13 Callbacks = Callback 1 + 19 ms + 12 × 5 ms ≈ 75 ms |
| 5 | 128 × 4 KiB Callback ≠ 1 × READ10 512 KiB; Q10 offen | richtig | Lab C3 (Puffer 4096 B) |
| 6 | 0,683 s (4 KiB) gegen 10,9 s (64 KiB) je Kommando | richtig | 4096 / 6000, 65 536 / 6000 |
| 7 | Teilantwort ist ein eigener Test | richtig, **wichtige Ergänzung** | dazu Punkt 15 |
| 8 | 19 ms per Sniffer klären (CSW → nächstes CBW) | richtig | — |
| 9 | id3Len exakt messen, dann Live direkt aus drei Messgrößen | richtig | Poll schreibt `id3Len` seit heute mit; Lab-Simulator liest die ID3-Länge direkt aus dem Dump |
| 10 | Marker 00 … 10 statt Piep alle 10 s | richtig | Bridge `--marker-period 1` (Zählton, neu) |
| 11 | PSRAM: 1 Slot = 512 KiB, mehrere Slots vervielfachen | richtig | — |
| 12 | Busy-Retry → kein DATA-IN → NAK → HU wartet → erneuter Callback | richtig | Spike (TinyUSB `proc_read10_cmd`); auf dem Bus NAKt der Controller IN-Token, solange kein Transfer anliegt |
| 13 | Beweisstatus-Tabelle | im Wesentlichen richtig | Zeile „Producer läuft kontinuierlich“: in s3 bewiesen, nicht generell (Tap-Fall B5) |
| 14 | E2 Kommandomix, R8, R16–R22 als Facts | richtig wiedergegeben | **aber nicht neu**: R16 steht seit 07.10. auf [B], R17–R22 seit s1-morgen |
| 15 | „Wenn die HU nach 1 s abbricht: 4 KiB PASS, 64 KiB FAIL“ | **nur bei Gesamtdauer-Limit** | Misst die HU **Inaktivität** (Zeit ohne Datenpaket), setzen 512-B-Teilantworten (alle 85 ms) das Limit ständig zurück → auch 64-KiB-Kommandos gingen. Gesamt- oder Inaktivitäts-Limit ist eine eigene Unbekannte (E7) |
| 16 | E5 „4-KiB-Transfers dominieren [B], stützt 4-KiB-Kommandos“ | **sagt nichts über Kommandos** | `xfer` zählt Callbacks; `n8kPlus` ist bauartbedingt immer 0 (Puffer 4096 B). Neu ablesbar: `n512=3` → es gibt 512-B-Kommandos; `n2k=0` → größere Kommandos wären Vielfache von 4 KiB |
| 17 | E6 „Queue-Tiefe 1 [S], wichtig für Backpressure“ | **protokollbedingt, [B]** | Bulk-Only Transport kennt kein Pipelining: CBW → Daten → CSW, erst dann das nächste CBW. Folge fürs Bremsen: Während ein READ wartet, kann die HU kein TEST UNIT READY (E3) schicken |
| 18 | R25 „Underrun-Bilanz korreliert quantitativ mit dem gehörten Fenster“ | **falsch** | Bytes ↔ 8,2 s passt; Gehör 5–6 s passt **nicht** (offen) |
| 19 | R27-Vorschlag: Host-Bytes = vorhandene Live + früher Zuwachs + „später erzeugte Daten, die zu spät kommen“ | **Idee gut, Zerlegung falsch** | Spät erzeugte Daten sind **kein** Teil der Host-Bytes. Richtig: Host-Bytes = ID3 + (Ring + Zuwachs bis zum Überholen) + Stille. R27 übernommen |
| 20 | F9: Hub geht nicht → „Sniffer nötig“, Full-Speed erzwingen entfällt | **präzisieren** | Passive Analyzer (Cynthion, Beagle 12) sind keine Hubs und damit nicht von F9 betroffen. Full-Speed erzwingen ist für den ESP32-S3 irrelevant (kann nur Full-Speed) |
| 21 | „Wir wissen zu wenig über die HU als MSC-Host“ | richtig | Abschnitt 4 |

## 2. Konzept „Vorsprung + Bremsen“ (Replug-Pfad)

Der Replug-Pfad ist der günstigste Fall: Die HU liest den aktuellen Titel **sequentiell ab 0** (R24), ohne Rückwärts-Segmente (anders als beim Tap, R16).

```mermaid
flowchart LR
  head["Kopf-Read: ID3 sofort"] --> lead["Vorsprung: Ring 48 KiB = 8 s sofort"]
  lead --> pace["Bremsen: Busy-Retry, Teilantworten 512 B"]
  pace --> eof["Datei-Ende nach 87 s Echtzeit"]
  eof --> nextTrack["Track-Ende R6, Autoplay F8, nächster Slot"]
```

1. **Kopf:** ID3 (Cover) liegt sticky vor → sofort.
2. **Vorsprung:** Der volle Ring (8,2 s bei 48k) wird sofort geliefert. Er ist zugleich der **Jitter-Puffer** zwischen Lese- und Abspielposition der HU: WLAN-Aussetzer bis ~8 s bleiben unhörbar.
3. **Bremsen:** Danach beantwortet der ESP jeden Callback erst, wenn neue Bytes da sind (`return 0` + 2 ms Pause, Teilantworten in 512-B-Schritten). Die HU liest jetzt mit 6000 B/s statt 800 KB/s.
4. **Ende:** 512 KiB sind nach 87 s gelesen und gespielt → Track-Ende (R6) → ~6 s Pause (R7) → Autoplay des nächsten Slots (F8). Für echten Dauerstrom braucht es größere Slots (z. B. 8 MiB = 23 min, Geometrie FW) oder eine Dateikette.

**Was dafür an der HU stimmen muss:** Q10 Kommandogröße + E7 Zeitlimit (Abschnitt 4). Zusätzlich muss sie **während** des langsamen Reads spielen (R12: [S] inkrementell, Stick F1).

## 3. Neu erkannte Hürden

### 3.1 P-Problem (Abspielposition nach Replug)

Nach Replug spielt die HU bei der gemerkten Position P (R23), liest aber ab 0 (R24). Heute ist das harmlos (alles in 0,66 s gelesen). **Mit Bremsen** existieren die Daten an Stelle P erst nach P Sekunden:

| P | Wartezeit bis Ton (gebremst) |
|---|---|
| 0 s | ~0 (Vorsprung) |
| 30 s | ~22 s (30 s − 8 s Vorsprung) |
| 80 s | ~72 s |

Was die HU in dieser Zeit tut (warten, überspringen, Fehler), ist unbekannt.

**Gegenmittel ohne Firmware:** P hängt an einer Titel-Identität (R23: nicht die Serial; Name/Größe/Kombi offen). Die Dateinamen kommen per `menu_set` vom Pi (`UsbMscGadget::applyMenuSlots` übernimmt `name`). → **Test:** Stationsnamen je Sitzung mit Suffix ändern (z. B. „Radio BOB 1007“) und prüfen, ob die HU danach bei 0 beginnt. Dafür liest die Bridge jetzt `--name-override-file`; `feld-s4-prep/rename.sh` ändert einen Namen atomar, während OTG abgesteckt ist. Das grenzt den P-Schlüssel ein und wäre zugleich die Lösung.

### 3.2 Tap-Pfad (Henne-Ei, B5)

Beim Tap startet der Producer erst durch den Read. Mit Bremsen wartet das **erste** Kommando auf: Play-Detect (2 Callbacks) → `play_uid` → Bridge → ffmpeg + HTTPS-Verbindung → ID3 (0,35 s) → erste Audio-Bytes. Realistisch **1–2 s**, plus kein Vorsprung (Ring leer).

- Risiko gegenüber E7 deutlich höher als beim Replug.
- Gegenmittel: (a) vorgewärmte Producer für alle Slots (ESP hat nur einen Ring → FW + PSRAM), (b) Tap nur auslösen lassen und Ton über den Replug-Pfad liefern (Bedienung umständlich), (c) beim Tap kurzen Vorsprung aus Stille-Frames im **Live-Format** geben (FW, `silenceMatchLive`).
- Dazu kommt beim Tap das Lesen außer der Reihe um P (R16) → feste Zuordnung Dateioffset → Strom (Stufenplan 3.2) nötig.

### 3.3 Zielkonflikt Bitrate

Höhere Bitrate = kürzere Wartezeit je Kommando, aber kürzerer Vorsprung aus demselben 48-KiB-Ring:

| Bitrate | B/s | Wartezeit je 4 KiB | je 512 B | Vorsprung (48 KiB) | Fenster heute |
|---|---|---|---|---|---|
| 128k | 16 000 | 0,26 s | 32 ms | 3,1 s | 3,1 s |
| 96k | 12 000 | 0,34 s | 43 ms | 4,1 s | 4,1 s |
| 64k | 8 000 | 0,51 s | 64 ms | 6,1 s | 6,1 s |
| **48k** | 6 000 | 0,68 s | 85 ms | 8,2 s | 8,2 s |
| 32k | 4 000 | 1,02 s | 128 ms | 12,3 s | 12,3 s |
| 24k | 3 000 | 1,37 s | 171 ms | 16,4 s | 16,4 s |

Folge: Für **heutige** Tests (Fenster messen) niedrige Bitrate; für **Bremsen** eher 64k–96k, sobald E7 bekannt ist. Mit PSRAM-Ring entfällt der Konflikt (Vorsprung unabhängig von der Bitrate).

## 4. Parameterlandkarte

### 4.1 Unbekannt (HU) — entscheidet über den Weg

| Parameter | Warum wichtig | Wie messen | FW-Go? |
|---|---|---|---|
| **Q10 Kommandogröße** | Wartezeit je Kommando 0,68 s oder 10,9 s | passiver USB-Sniffer; Lab-Referenz `--golden REPLUG --replug-cmd-kib 4/16/64` | nein (Sniffer) |
| **E7 Zeitlimit: Gesamtdauer oder Inaktivität** | bei Inaktivität retten Teilantworten auch große Kommandos | Stall-Build: Leiter `stallMaxMs`, mit/ohne Teilantworten | ja |
| Annahme von Teilantworten | Fluss alle 85 ms statt alle 0,68 s | Stall-Build `stallChunkBytes` 512 / 4096 | ja |
| Spielt die HU während des langsamen Reads? (R12) | sonst Ton erst nach 87 s | Stall-Build + Marker | ja |
| Verhalten, wenn der Decoder die Leseposition einholt | WLAN-Aussetzer > Vorsprung | Stall-Build + Producer-Lücke (`RealisticProducer` `gaps`) | ja |
| P-Schlüssel (R23) | P-Problem 3.1 | Namens-Suffix über `menu_set` | **nein** |
| Prefetch bei gebremstem Read (R21) | Dateikette | Stall-Build, 2 Slots | ja |
| Ursache 5–6 s statt 8,2 s | Formatwechsel? | s4 Marker + Lab-Dump am PC | nein |
| Herkunft der 19-ms-Kopfpause | HU prüft Kopf? | Sniffer | nein |
| Cache-Grenze Q4 | große Slots für Dauerstrom | Größenleiter (Katalog Q4) | Geometrie: ja |

### 4.2 Jetzt verstellbar (ohne FW)

| Stellschraube | Wo | Wirkung |
|---|---|---|
| `--bitrate` | Bridge | Fensterlänge (Tabelle 3.3) |
| `--target-bps` (**neu**) | Bridge | Producer-Rate = Feldrate erzwingen (Lab 6000 statt 9000 B/s) |
| `--re-local` (**neu**) | Bridge | lokale Dateien in Echtzeit statt 1,5× |
| `--marker` / `--marker-period S` (**neu**) | Bridge | Zählton zur Messung der Hördauer |
| Stationsnamen | Bridge `--name-override-file` → `menu_set` (bei OTG ab) | P-Schlüssel-Test ohne Pi-Menü-Umbau |
| Play-Detect (`playMinSeqBytes` …) | `/api/config` | wann `play_uid` feuert (Tap-Pfad) |
| Producer-Laufzeit vor Replug | Bedienung | Ring voll erst nach ≥ 8 s |
| Simulator: Kommandogröße, Takt, Kopfpause, SG-Zeitlimit, Producer-Burst (**neu**) | `nbt_hu_sim.py` | Lab-Referenz für Q10/E7 |

### 4.3 Nur mit FW-Go

Alle Stall-Stellschrauben, Ringgröße, Stille-Format, Cursor-Verhalten bei Underrun, Slot-Geometrie — als **Laufzeit-Felder** spezifiziert in [`STALL-BUILD-SPEC-2026-10-08.md`](../../planung/STALL-BUILD-SPEC-2026-10-08.md), damit ein einziger Flash viele Feldvarianten erlaubt.

## 5. Empfohlene Reihenfolge

1. **Lab-Abend-Gate** (ohne FW): Werkzeugregression, `--golden REPLUG` 4/16/64 KiB, echte Dumps 24–96k, Q12, 200 USB-Zyklen und Langlauf → [`AUFTRAG-LAB-ABEND`](AUFTRAG-LAB-ABEND-2026-10-08.md). M1/M2-Sollwerte: [`AUFTRAG-LAB-REALITAET`](AUFTRAG-LAB-REALITAET-2026-10-08.md).
2. **s4 im Auto, Kern 15–20 min** (ohne FW): nur HU-Hördauer mit Zählton, Bayern-Gegenprobe R28, Namens-Suffix/P-Schlüssel und passive Reboot-Rate → [`FELDPROTOKOLL-S4`](FELDPROTOKOLL-S4-TONFENSTER.md), Taschenkarte `feld-s4-prep/GO-S4.md`.
3. **Sniffer** (ohne FW): Q10 + 19 ms.
4. **FW-Go Stall-Build** mit Laufzeit-Stellschrauben: Lab-Leiter, dann Auto-Leiter (E7, Teilantworten, R12).
5. Entscheidung: Bremsen (bei E7 ≥ 0,7 s oder Inaktivitäts-Limit) oder PSRAM-Zeitversatz.
