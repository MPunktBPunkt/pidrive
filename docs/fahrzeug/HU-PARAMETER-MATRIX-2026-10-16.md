# HU-Parametermatrix — BMW NBT Evo für den PiDrive-Betrieb

**Stand:** 2026-10-23 (Identity/Detach in Facts R37–R45) · 2026-10-22 · **Basis:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md), hu-probe free Offline **0.2.40**, Media-Leiter **0.3.17**, PSRAM-Audit 21.10., Abend-Offline 18.10., PiDrive-Feld s1–s6/F0, technology-audit Media-Leiter + 0.7.1.  
**Maßnahmen:** [`../planung/MASSNAHMEN-HU-PROBE-2026-10-22.md`](../planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) · Profil [`../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json`](../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json)
**Status:** [B] bewiesen · [S] stark belegt · [A] **abgeleitet** · [D] Desk · [H] Hypothese · [?] offen.

Device-Stack-Messungen sind keine Wire-Messungen. Lab-Werte (Debian-Host) sind keine NBT-Werte.  
**Lab-MSC-Wahrheit (17.10.):** nur SG_IO/O_DIRECT + ESP-Capture — siehe [`METHODIK-MSC-WAHRHEIT.md`](../betrieb/artifacts-2026-10-17-lab/METHODIK-MSC-WAHRHEIT.md).  
**hu-probe Abend-Offline (18.10.):** Track-Atom **[B]** — Audit [`hu-probe-bmw-s2-abend-offline-2026-10-18`](../../../hu-probe/audits/hu-probe-bmw-s2-abend-offline-2026-10-18/).  
**hu-probe Media-Leiter (22.10.):** Head-Scan **32+128=160** (~80 KiB), TUR idle **2238,78 ms**, Elevator STRONG, PiDrive-Vertrag **Struktur+Head** — Report [`2026-10-22-hu-probe-media-ladder`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md).  
**REJECTED (22.10.):** „nur Ordnerstruktur“; Prefetch-Lead **15 s** auf demo_v1; TUR≈1 Hz als Idle-Konstante; Lead=8 s als Profil-Konstante.

---

## 1. Neu abgeleitete Parameter (Querauswertung 16.10. + Abend 18.10. + Media-Leiter 22.10.)

| # | Ableitung | Status | Rechnung / Beleg | Folge für PiDrive |
|---|-----------|--------|------------------|-------------------|
| A1 | Track-Atom = **`(head,240)+(head+240,69)` = 309 LBA = 158 208 B**; „39“ = 30+9 Callback-Chunks (38×4096 + 2560), keine HU-Konstante und keine Meta-Blöcke im Burst | **[B]** | Demo-FAT `TRACK1..3.MP3` je 158 208 B. Abend-Offline PASS `175203`/`212136`/`212635`: je `read_bytes_sum=158208`, CBW-Paare exakt Atom. T3 covered **627–935** (nicht 938). **REJECTED:** 312 LBA / „3 Meta“ / „39×4 KiB als Byteformel“ (Callbacks ≠ CBWs). Quellen: `session-summaries.json`, Feldbericht Abend | Eager-EOF (R2) auf zweitem Medium + CBW-Grammatik wie PiDrive-MessCapture. Prefetch/R21 in **Atom-Einheiten** planen; Auswerte-Standard = CBW-Paar + covered + Morphologie, nicht Event-Count allein |
| A2 | Maximale READ10-Transferlänge der NBT = **240 Blöcke (120 KiB)** | **[S]**→**[B]** Atom | hu-probe S2 + Feld 16.10. MessCapture + Abend-Offline: Atom-Head immer **240**, nie >240 | Lese-, Resume- und Prefetch-Muster in **CBW-Einheiten zu 120 KiB** planen und auswerten, nicht in 4-KiB-Callbacks |
| A3 | Stall kann Menü sichtbar blockieren; **Ursache = genau ein 240-CBW @48 kbit/s ≈20,5 s** ist Inference | Phänomen [B] / Ursache **[A]** | Rechnung 120 KiB×8/48 kbit/s ≈ **20,5 s** stimmt. R35/E6 stützen BOT-QD=1. **Direktmessung** der Freeze-Dauer vs. Stall-Leiter steht aus (`lab_stall_phase_ladder.py`) | Stall-Leiter Menü-Phase; Abhilfe weiter: Vorlauf ≥ 1 CBW, höhere Bitrate, BUSY nur bei Vorlauf < CBW |
| A4 | Untere Grenze NBT-Timeout **pro READ10 ≥ ~20 s** | [A] bedingt | E7/s6: ~65 s **kumuliert** bis EOF ≠ Timeout eines einzelnen READ10. Feld 16.10.: 240-CBW bestätigt; Einzel-Timeout nicht gemessen | Stall-Leiter Audio-Phase 0…15 s (FW-Limit), danach Feld |
| A7 | Full-File-Read eines **512 KiB**-Slots = **`240,240,32,240,240,32`** (Summe 1024), **nicht** `8+4×240+56` | **[S]** | Feld MessCapture 16.10. mehrfach: BOB LED, Gelb, Tip Bayern (`mess-cmds-*-{bob-led,gelb,TIP-BAYERN}.json`). Vorhersage `8+56` widerlegt | Prefetch/EOF-Planung an 240/32-Muster; keine Annahme eines 8er-Intros für diesen Slot |
| A5 | Prefetch-Vorlauf ~15 s | **REJECTED** auf demo_v1 · Lead auf größerem Medium **VARIABLE** | free Offline 0.2.40: `prefetch_lead_demo_v1=0` FACT. Media-Leiter: Tail-Prefetch-**Struktur** 160@off160 FACT; ~8 s Lead nur VARIABLE (≠ Konstante). Alte 15‑s-Rechnung (Trackdauer−Pause) war Hypothese | R21 demote; Audible-Tap / Marker + `capture_t_us`; kein Lead=8/15 in Profilen |
| A12 | Scan-Head = **READ10 32+128 = 160 Blöcke ≈ 80 KiB** | **[B]** | Media-Leiter `id3_cover`/`bitrate_mix`; Browse≠Player (Dir vs ID3-Head) | Producer: Dateikopf ≥ ~80 KiB gültig/konsistent (Vertrag) |
| A13 | Idle = nur TUR **2238,78 ms** (phase-locked), 0 File-Reads | **[B]** | free Offline + Live-Leiter | Stall/Idle-Modelle an 2239 ms, nicht an Session-Mittel ~1 Hz |
| A14 | Elevator / `tail_then_head` = Nearest-LBA-first | **[S]** STRONG | Media-Leiter `cache_place`; Re-Entry REJECTED | Prefetch/Resume-Auswertung: Reihenfolge ≠ zweites Atom |
| A15 | HU liest in **Fenstern bis 512 Blöcke (256 KiB)**, geteilt in CBWs bis 240 Blöcke | [H] | A7 = 2 × (240+240+32); demo_v1 309 = abgeschnittenes Fenster. 256 KiB @128 kbit/s ≈ 16,4 s. hu-probe 20.10. | Größenleiter/P0 prüft Fenster-Nachladen; nicht mit Scan-Head A12 verwechseln |
| A16 | Medienwechsel nur am **TUR-Tick**; Blindfenster bis **~2,24 s** | [S] | hu-probe 20.10.: TUR freilaufend; `media_hide` → erste Fail-TUR auf altem Raster. Passt zu Soft-Remount wirkungslos (R37), solange Hide zwischen Ticks | Hide/Show nur gezielt; Risiko veralteter Cache |
| A6 | Ein Info/Xing-Header ist für Eager-Read nicht nötig | [A] schwach | Demo-Tracks ohne erkennbaren Info/Xing-Tag werden ebenso komplett gelesen wie PiDrive-Slots mit LAME-Info | Info-Tag weiter für Dauer/Fortschrittsbalken prüfen, nicht für das Leseverhalten |
| A8 | Demo-Track-Bänder (Δ=309): **T1 9–317 · T2 318–626 · T3 627–935** | **[B]** T1/T3 offline · T2 live | Offline PASS: T3 `175203`/`212635` covered 627–935; T1 `212136` covered 9–317. Live `4028`/`2264`: T2 318–622. **T2 offline noch offen** | Band-Karte für Prefetch-/Hold-Auswertung; Frage umformulieren: *unter welcher Bedingung fordert die HU welches 309-LBA-Atom?* |
| A9 | Offline Integrity-PASS-Signatur = **genau ein 39er-Atom-Burst** pro Lauf (3×) | **[B]** | PASS `175203`, `212136`, `212635`: n_bursts=1, n_reads=39, overflow=0, upload=delivered. FAIL-Läufe reproduzieren oft die Burst-Form, Footer fehlt | Operatives Prüfkriterium für Offline-Captures; Multi-Burst ≠ PASS-Norm |
| A10 | Zwei Atom-Reihenfolgen: **head_then_tail** vs. **tail_then_head** (kein T1a/T1b-Split) | **[B]** Morphologie · Ursache [H] | T3: `(627,240)+(867,69)`. T1-Hold `212136`: `(249,69)+(9,240)` = dasselbe T1-Atom rückwärts + kind-Labels file34/dir4/fat1 **innerhalb** Band 9–317 (`read_bytes_sum` weiter 158 208) | Reihenfolge und kind-Labels getrennt von Band-Geometrie führen; T1a/T1b verwerfen |
| A11 | Hold-Anzeige ≠ USB-Traffic (`212635`): Operator Hold **2**, Buffer = **T3-Atom** | **[H]** stark (M3) | Kandidaten: Prefetch-Ahead über gehaltenen Track / Autoplay-Vorlauf / früherer Cache-Miss. Diskriminator: T2-Hold-Lauf mit Markern (`play_start` / Hold-Festigung / `audible_change`) — Checkliste `hu-probe/docs/feld/2026-10-18-t2-hold-checklist.md` | Direkt relevant für R21/Prefetch-Modelle; GATE-01 bleibt OPEN bis Marker + Capture-Timestamps |

**Feld-Ergebnis MessCapture 0.4.52 (16.10., NBT `.89`):** Ein Full-File-Read eines 512-KiB-Slots zerfällt in **`240 + 240 + 32 + 240 + 240 + 32`** (nicht `8 + 4×240 + 56`). LIVE-Ohr nur kurz (~5–6 s) nach Klasse-A-OTG; Panic/weiße LED bleibt Blocker. Details: `docs/betrieb/artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md`.  
**hu-probe Abend-Offline 0.2.30 (18.10.):** Atom-Modell geräteübergreifend **[B]**; T2 offline + Prefetch-Lead (GATE-01) + `capture_t_us`-Fix offen; Operator setzt hu-probe fort, bevor PiDrive hier anschließt.  
**Offen (PiDrive-relevant):** R16-Resume; Ton↔READ; A11-Diskriminierung; B16 kind=dir/fat im T1-Band (Medium-Layout vs. Label-Logik); Clustergrenzen-Check Split@head+240.

---

## 2. Parametertabelle

Spalte **Benötigt für**: L = Live-Ton, C = Cover/ID3, S = Stabilität, U = Bedienung/UI. **Prio:** P0 blockiert Live-Ton, P1 nötig für Dauerbetrieb, P2 Optimierung.

### 2.1 USB, Enumeration, Strom

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| Bus-Geschwindigkeit | Full-Speed (~1 MB/s Bulk) | [B] | R1, R15 | L | — | — |
| Plug → INQUIRY / erster READ | ~997 ms / ~1004–1046 ms | [B] | E1, Offline-P0 | S | — | — |
| SCSI-Kommandomix | TUR ≫ READ10, PREVENT, MODE_SENSE6, READ_CAPACITY, INQUIRY | [B] | E2 | S | — | — |
| MODE_SENSE6 je READ_CAPACITY | 2,0 | [B] | E2 | S | — | — |
| TUR idle Period | **2238,78 ms** (p10–p90 ≈ 2238–2239); Session-Mittel ~1–2 Hz ≠ Idle | **[B]** idle / [S] session | A13, E3, Media-Leiter | S | P2 | Idle-Fenster, nicht Uptime-Mittel |
| Schreibzugriffe | keine | [B] | E4 | S | — | — |
| Queue-Tiefe | 1 (BOT) | [B] | E6 | L, U | — | — |
| Physisches Detach → Attach | 2,3–6,0 s | [B] | E8 | S | — | — |
| Mindestverweildauer bis DATA-Reads | > ~4–7,5 s | [B] Muster | E9 | S | P1 | Dwell-Leiter mit Soft-Cycle-Orchestrator |
| USB-Hub | nicht unterstützt (getestete Hubs) | [B] | F9 | S | — | — |
| VBUS-Strombudget der HU | unbekannt | [?] | Q11 | S | P0 | USB-Messadapter Min/Max beim Stecken |
| Ursache ESP-Reset/Panic beim OTG-Stecken | Panic beobachtet (F0), Brownout möglich | [?] | Q11, F0 | S | **P0** | UART-Resetgrund + `resetReason`/Panic-Tail; Netzteil A/B |
| USB-Suspend/Standby der HU (Zündung aus) | ~20 min vermutet | [H] | hu-probe 15.10. | S | P2 | Zeitstempel bis Detach/Suspend |

### 2.2 READ10-Transport und Bremsen (BUSY)

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| Callback-Chunk | 4096 B (Stack); ≠ CBW-Länge | [B] | E5, A1 | L | — | — |
| Track-Atom (Demo 158 208 B) | `(240)+(69)` = 309 LBA; 39 Callbacks = 30+9 | **[B]** | A1 (Abend 18.10.) | L | — | — |
| Häufige CBW-Längen | 8 und 240 Blöcke, Rest bis EOF (z. B. 69) | **[B]** | E11, A1 | L | — | — |
| Max. READ10-Transfer | 240 Blöcke = 120 KiB | **[B]** | A2 | L, U | P1 | bestätigt; weitere Phasen optional |
| Lesetakt ohne/mit ESP-Play | 3,74–3,78 ms / ~5 ms je 4 KiB | [B] | R15 | L | — | — |
| BUSY-Toleranz kumuliert | ≥ ~65 s bis EOF | [B] | E7, R29 | L | — | — |
| Timeout je READ10 | ≥ ~20 s (bedingt) | [A] | A4 | L | **P0** | Lab-Leiter 0/1/2/5/10/15 s (`lab_stall_phase_ladder.py`), dann NBT; nicht E7-65 s kumuliert verwechseln |
| Timeout ohne Datenfluss (Inaktivität) | unbekannt | [?] | Q1 | L | P1 | Retry-Pausen ohne Daten |
| Reaktion bei Timeout | unbekannt (Reset? Skip? Remount?) | [?] | — | S | P1 | gezielt überschreiten, Status + Ohr |
| Menülatenz unter Stall | ~20 s beobachtet; Ursache 240-CBW Inference | [B] Phänomen / [A] Ursache | R35, A3 | U | P1 | Stall-Leiter Menü-Phase + Vorlauf ≥ 120 KiB A/B |
| Benötigter Live-Vorlauf ohne UI-Freeze | ≥ 1 CBW = 120 KiB (≈ 20 s @48k, 7,7 s @128k) | [A] | A2, A3 | L, U | **P0** | PSRAM **an** ab esp32.pidrive 0.4.54 (Ring 160 KiB) — [`ESP32-S3-BOARD`](../referenz/ESP32-S3-BOARD.md); Option-b Zeitversatz noch offen |
| Scan-Head (größere Medien) | **32+128 = 160 Blöcke ≈ 80 KiB** | **[B]** | A12 | L, C | **P0** | Vertrag: Dateikopf gültig; „nur Struktur“ REJECTED |

### 2.3 Dateisystem und Medium

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| FAT12 / FAT16 / LFN | funktioniert | [B] | F1 | S | — | — |
| FAT32 / exFAT | ungetestet | [?] | — | S | P2 | Geometrie-Varianten |
| Fehlerhafte FAT/Root | leere Liste | [B] | F2 | S | — | — |
| Listenreihenfolge | ≠ Slot-Reihenfolge; Regel unbekannt | [S]/[?] | F5 | U | P2 | Namen-/Cluster-Permutation |
| Autoplay-Reihenfolge | fav2 → fav1 → fav0 | [B] | F8 | U | — | — |
| Max. Dateigröße für Eager-Read (Q4a) | 8 MiB fast vollständig gelesen; Grenze unbekannt | [B]/[?] | R2, R32 | L | **P0** | Größenleiter 8…64 MiB (D1–D3) |
| Verhalten bei sehr großer Datei („Radio ohne Ende“) | unbekannt | [?] | D-Leiter | L | **P0** | D1–D3 erst nach stabilem LIVE |
| Persistente Medium-Identity der HU | SQLite-Felder Serial, identifier, mountpath, lastseen | [D] | F10–F13 | L | — | — |

### 2.4 Cache, Prefetch, Resume

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| Gewählte Datei wird bis EOF gelesen | ja, ~1 MB/s; Demo = ein Track-Atom | **[B]** | R2, A1 | L | — | — |
| Abwahl bricht Lesen ab | ja | [S] | R3 | L | — | — |
| Nächste Datei vorlesen | Struktur ja (Tail@160 / Full-Atom); Lead **0** auf demo_v1, sonst **VARIABLE** | [B] Struktur · Lead VARIABLE · 15 s **REJECTED** demo_v1 | R4, A5/A12, Media-Leiter | L | P1 | Marker + LBA + `capture_t_us`; kein festes Lead=8/15 s |
| Cache-Hit ohne Reads | ja | [B] | R9 | L | — | — |
| Non-live-Slots werden vorab gecacht (Stille) | ja, 98,9 % von 8 MiB | [B] | R32 | L | — | — |
| Cache überlebt ESP-RST | nein | [B] | R13 | L | — | — |
| Cache-Gesamtgröße (Q4b) | unbekannt | [?] | Q4b | L | P1 | N × 512 KiB, Re-Select Hit/Miss |
| Eviction-Strategie (Q4c) | unbekannt | [?] | Q4c | L | P1 | Sequenz, dann frühe Datei |
| Wiedergabeposition P persistiert | ja, auch über Medienwechsel | [S] | R23 | L | — | — |
| P bricht bei Serial + Root-Label + Name | nein | [S] | R34 (`HU-Technical-Facts`, S3/S4/F1 — nicht Feld 16.10.) | L | — | — |
| Soft-Remount (NOT READY) als HU-Reset | wirkungslos | **[B]** | R37, E17; A16 Blindfenster | L | — | echten USB-Cycle nutzen |
| P/Cache-Bruch durch BPB-Volume-ID | unbekannt | [?] | Q3/Q14, F0 B3 | L | **P0** | F0 B3 isoliert (Lab-Tooling 18/18 grün) |
| P/Cache-Bruch durch BPB+Root-Label | unbekannt | [?] | F0 B2 | L | **P0** | F0 B2 isoliert |
| P/Cache-Bruch durch Serial + Product-Revision allein | unbekannt | [?] | F0 B1 | L | **P0** | F0 B1 isoliert |
| P/Cache-Bruch durch Größe, Pfad, Startcluster | unbekannt | [?] | Q14 | L | P1 | eigene Builds nach F0 |
| Resume-Lesemuster | 16-Block-Kopf, dann 120-KiB-Segmente vor/zurück, Pause 5,1 s | [B]/[A] | R16, A2 | L | — | — |
| Frische Auswahl ohne P | 360 KiB = 3 CBW ab Kopf | [B]/[A] | R17, A2 | L | — | — |
| Replug liest aktuellen Titel ab 0 | ja, 0,65 s | [B] | R24, R26 | L, C | — | — |
| Pause nach Kopf-Read beim Replug | ~19 ms (nur mit laufendem Stream) | [B]/[?] Ursache | R26 | L | P2 | `MessCapture` mit Barrier an/aus |

### 2.5 Metadaten, Decoder, Hörbarkeit

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| ID3v2 am Dateianfang + APIC JPEG | funktioniert | [B] | M1; Lab 17.10. SG_IO: sticky **3200 B**, PDSQ@3204 (`id3-chain-…`) | C | — | — |
| Funktionierendes Cover | JPEG 320×320, ≤ 8 KiB | [B] | M2 | C | — | — |
| Maximale ID3-/Covergröße | unbekannt | [?] | — | C | P2 | 16/32/64 KiB APIC |
| Cover-Update ohne neuen Kopf-Read | nicht möglich (nur beim Kopf-Read) | [S] | R28 | C | P1 | Titelwechsel im Live-Strom messen |
| Live-Format | MPEG-2 L3 22,05 kHz mono 48 kbit/s | [B] | D1 | L | — | — |
| Höhere Bitrate (96/128 kbit/s) | ungetestet | [?] | D5 | L, U | **P1** | verkürzt CBW-Wartezeit (A3) |
| Formatwechsel Live ↔ Stille in einer Datei | ungetestet | [?] | D4 | L | P1 | Lab-AV, dann Feld |
| Wiedergabe beginnt während des Lesens | ja | [S] | R12 | L | P2 | Video Tap → Ton |
| Pause zwischen Tracks | ~6 s | [S] | R7 | L | — | — |
| Hörbare Tondauer vs. gelieferte Live-Bytes | 5–6 s gehört bei 8,2 s Ring | [B]/[?] | R25 | L | P1 | Marker-Audio, Decoder-Anlauf |
| Startverzögerung Tap → Ton | unbekannt | [?] | — | L, U | P2 | Video |

---

## 3. Was für Live-Ton zuerst fehlt

Die P0-Zeilen hängen zusammen:

1. **Stabile Episoden:** Panic/Brownout beim OTG-Stecken beseitigen, sonst ist jede Identity-Messung ungültig.
2. **Identity Serial/Label/Vol:** als Resume-Key **REJECTED** (23.10., Facts R34). Weitere Serien gestoppt; Fokus Größenleiter + Fresh-Trigger.
3. **Timeout pro READ10 + nötiger Vorlauf:** entscheidet, wie lange BUSY pro 240-Block-CBW gehalten werden darf und ob ein Ring ≥ 120 KiB oder eine höhere Bitrate nötig ist.
4. **Große Datei (D1–D3):** erst danach, sonst läuft die Leiter in dieselben Cache-/Resume-Effekte.

A1 (Track-Atom 240+69) und A2 (240-Max) sind **[B]**; A12 (Head-160) und A13 (TUR 2238,78 ms) seit Media-Leiter/free **[B]**. A5 (15 s Lead) auf demo_v1 **REJECTED**. A7 bleibt MessCapture-**[S]**. A3/A4/A6 abgeleitet; A11/Audible und Cache-Key F0 offen — hu-probe Identity-Plan vor weiteren PiDrive-Cache-Hebeln.  
**FW:** esp32.pidrive **0.4.54** — PSRAM an, StreamBuffer-Mutex (R13), PanicTail/PhaseGate/DiagLog/HwInfo.
