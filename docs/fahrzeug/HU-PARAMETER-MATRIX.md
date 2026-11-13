# HU-Parametermatrix — BMW NBT Evo für den PiDrive-Betrieb

**Stand:** 2026-11-13 (neu §2.7 Bluetooth aus dem ersten BT-Feld-Capture, Facts §10.5); davor 2026-11-11 (Nachrechnung aller hu-probe-BMW-Sessions → Facts R53–R60, I8–I13; A15 widerlegt, A17–A24 neu) · **Basis:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md), Media-Leiter **0.3.17**, Heimfahrt **0.3.17**, Identity **0.3.19**, Größenleiter-Versuch **0.3.21**, Analyzer-Feld **0.0.52**, Abend-Offline 18.10., PiDrive s1–s6/F0.  
**Maßnahmen:** [`../planung/MASSNAHMEN-MSC-FULLMENU.md`](../planung/MASSNAHMEN-MSC-FULLMENU.md) · [`MASSNAHMEN-HU-PROBE-2026-10-22.md`](../archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) · Profil [`../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json`](../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json)
**Status:** [B] bewiesen · [S] stark belegt · [A] **abgeleitet** · [D] Desk · [H] Hypothese · [?] offen.

Device-Stack-Messungen sind keine Wire-Messungen. Lab-Werte (Debian-Host) sind keine NBT-Werte.  
**Lab-MSC-Wahrheit (17.10.):** nur SG_IO/O_DIRECT + ESP-Capture — siehe [`METHODIK-MSC-WAHRHEIT.md`](../betrieb/artifacts-2026-10-17-lab/METHODIK-MSC-WAHRHEIT.md).  
**hu-probe Abend-Offline (18.10.):** Track-Atom **[B]** — Audit [`hu-probe-bmw-s2-abend-offline-2026-10-18`](../../../hu-probe/audits/hu-probe-bmw-s2-abend-offline-2026-10-18/).  
**hu-probe Media-Leiter (22.10.):** Head-Scan **32+128=160** (~80 KiB), TUR idle **2238,78 ms**, Elevator STRONG, PiDrive-Vertrag **Struktur+Head** — Report [`2026-10-22-hu-probe-media-ladder`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md).  
**REJECTED (22.10.):** „nur Ordnerstruktur“; Prefetch-Lead **15 s** auf demo_v1; TUR≈1 Hz als Idle-Konstante; Lead=8 s als Profil-Konstante.
**Nachrechnung 11.11.:** Heimfahrt `#22`–`#24` Instrument-gültig (Facts §9.1) → ganze Datei wird gelesen (bis 7,2 MB), Kopf-Vorlauf 7–8 s vor Ende, Resume 0–3840 ∥ P→EOF, Ketten-Prefetch, Cache minutenlang. **REJECTED (11.11.):** R51 „1,6 s BUSY“ (Tool-Artefakt), Q18 „395xxx-Probe“ (`post_finalize`), Lesefenster 512 Blöcke (A15). Größenleiter-Läufe 27.10./11.11. ungültig.  

---

## 1. Neu abgeleitete Parameter (Querauswertung 16.10. + Abend 18.10. + Media-Leiter 22.10.)

| # | Ableitung | Status | Rechnung / Beleg | Folge für PiDrive |
|---|-----------|--------|------------------|-------------------|
| A1 | Track-Atom = **`(head,240)+(head+240,69)` = 309 LBA = 158 208 B**; „39“ = 30+9 Callback-Chunks (38×4096 + 2560), keine HU-Konstante und keine Meta-Blöcke im Burst | **[B]** | Demo-FAT `TRACK1..3.MP3` je 158 208 B. Abend-Offline PASS `175203`/`212136`/`212635`: je `read_bytes_sum=158208`, CBW-Paare exakt Atom. T3 covered **627–935** (nicht 938). **REJECTED:** 312 LBA / „3 Meta“ / „39×4 KiB als Byteformel“ (Callbacks ≠ CBWs). Quellen: `session-summaries.json`, Feldbericht Abend | Eager-EOF (R2) auf zweitem Medium + CBW-Grammatik wie PiDrive-MessCapture. Prefetch/R21 in **Atom-Einheiten** planen; Auswerte-Standard = CBW-Paar + covered + Morphologie, nicht Event-Count allein |
| A2 | Maximale READ10-Transferlänge der NBT = **240 Blöcke (120 KiB)** | **[S]**→**[B]** Atom | hu-probe S2 + Feld 16.10. MessCapture + Abend-Offline: Atom-Head immer **240**, nie >240 | Lese-, Resume- und Prefetch-Muster in **CBW-Einheiten zu 120 KiB** planen und auswerten, nicht in 4-KiB-Callbacks |
| A3 | Stall kann Menü sichtbar blockieren; **Ursache = genau ein 240-CBW @48 kbit/s ≈20,5 s** ist Inference | Phänomen [B] / Ursache **[A]** | Rechnung 120 KiB×8/48 kbit/s ≈ **20,5 s** stimmt. R35/E6 stützen BOT-QD=1. **Direktmessung** der Freeze-Dauer vs. Stall-Leiter steht aus (`lab_stall_phase_ladder.py`) | Stall-Leiter Menü-Phase; Abhilfe weiter: Vorlauf ≥ 1 CBW, höhere Bitrate, BUSY nur bei Vorlauf < CBW |
| A4 | Untere Grenze NBT-Timeout **pro READ10 ≥ ~20 s** | [A] bedingt | E7/s6: ~65 s **kumuliert** bis EOF ≠ Timeout eines einzelnen READ10. Feld 16.10.: 240-CBW bestätigt; Einzel-Timeout nicht gemessen | Stall-Leiter Audio-Phase 0…15 s (FW-Limit), danach Feld |
| A7 | Full-File-Read eines **512 KiB**-Slots = **`240,240,32,240,240,32`** (Summe 1024), **nicht** `8+4×240+56` | **[S]** | Feld MessCapture 16.10. mehrfach: BOB LED, Gelb, Tip Bayern (`mess-cmds-*-{bob-led,gelb,TIP-BAYERN}.json`). Vorhersage `8+56` widerlegt | Prefetch/EOF-Planung an 240/32-Muster; keine Annahme eines 8er-Intros für diesen Slot |
| A5 | Prefetch-Vorlauf ~15 s | **REJECTED** auf demo_v1 · Lead auf größerem Medium **VARIABLE** | free Offline 0.2.40: `prefetch_lead_demo_v1=0` FACT. Media-Leiter: Tail-Prefetch-**Struktur** 160@off160 FACT; ~8 s Lead nur VARIABLE (≠ Konstante). Alte 15‑s-Rechnung (Trackdauer−Pause) war Hypothese | R21 demote; Audible-Tap / Marker + `capture_t_us`; kein Lead=8/15 in Profilen. **11.11.:** natürlicher Autoplay-Wechsel 7,2–8 s (n=6, A18) — Normalfall, keine Profil-Konstante |
| A12 | Scan-Head = **READ10 32+128 = 160 Blöcke ≈ 80 KiB** | **[B]** | Media-Leiter `id3_cover`/`bitrate_mix`; Browse≠Player (Dir vs ID3-Head) | Producer: Dateikopf ≥ ~80 KiB gültig/konsistent (Vertrag) |
| A13 | Idle = nur TUR **2238,78 ms** (phase-locked), 0 File-Reads | **[B]** | free Offline + Live-Leiter | Stall/Idle-Modelle an 2239 ms, nicht an Session-Mittel ~1 Hz |
| A14 | Elevator / `tail_then_head` = Nearest-LBA-first | **[S]** STRONG | Media-Leiter `cache_place`; Re-Entry REJECTED | Prefetch/Resume-Auswertung: Reihenfolge ≠ zweites Atom |
| A15 | ~~HU liest in **Fenstern bis 512 Blöcke (256 KiB)**~~ | **widerlegt** (11.11.) für reale Dateien | Heimfahrt: 24 Dateien 2,0–7,2 MB je 100 % in einem Zug (A17). A7 (`240,240,32`×2) bleibt als Zerlegung eines 512-KiB-Slots gültig, ist aber kein Fenster | Keine Fenster-Annahme im Live-Pfad; ganze Slot-Länge einplanen |
| A16 | Medienwechsel nur am **TUR-Tick**; Blindfenster bis **~2,24 s** | [S] | hu-probe 20.10.: TUR freilaufend; `media_hide` → erste Fail-TUR auf altem Raster. Passt zu Soft-Remount wirkungslos (R37), solange Hide zwischen Ticks | Hide/Show nur gezielt; Risiko veralteter Cache |
| A17 | Spielende/gewählte Datei wird **vollständig** mit 0,9–1,05 MB/s gelesen, ohne Grenze bis **7,2 MB** | **[B]** | Facts R53: 24 Instanzen `#22`–`#24`, z. B. H01 7,20 MB in 9,6–10,9 s, R04 6,80 MB in 7,66 s | Live-Slot muss über die **ganze** Länge gepaced werden; geliefertes „Noch-nicht“ wird als Stille gecacht |
| A18 | Natürlicher Autoplay-Wechsel: **Kopf** des Folgetitels 7,2–8 s vor Ende (768 KiB bei bekanntem Medium, Block 160–2848 ≈ 1,31 MiB nach Fresh-Scan), **Rest beim Wechsel** | **[S]** n=6 | Facts R54 | Kopf jeder Nachbardatei ≥ ~1,4 MiB jederzeit gültig; Live-Wechsel ~8 s vor Ende vorbereiten |
| A19 | Resume nach Mount: Kopf **0–3840 Blöcke (1,875 MiB)** ∥ **P → EOF**; Mitte erst beim Abspielen | **[B]** n=3 | Facts R55 (`#22` J01, `#23` R04 ×2) | Live-Slot muss beliebige Resume-Position P bedienen; ab P bis EOF wird sofort angefordert |
| A20 | **Ketten-Prefetch:** mehrere Folgetitel komplett, Abstand ~4 ms, ≈31 MB in 70 s, auch in Unterordner | **[S]** | Facts R57 (`#23`, `#22` PODCAST); Auslöser [?] (Q19) | Nachbarn eines Live-/Steuer-Slots können ohne Tap vollständig gelesen werden |
| A21 | Body-Cache hält Daten **≥ 400–655 s**, auch über 10 MB Fremd-Reads; Teil-Eviction (Mitte zuerst) | **[S]** | Facts R56 | Inhalt eines einmal gelesenen Slots ändert sich für die HU nicht ohne neue Datei/LBA oder Cycle |
| A22 | Fresh-Scan je Datei = 160 Blöcke + EOF-Probe, **größenunabhängig** (59 KB … 11 MB) | **[S]** | Facts R58; erweitert A12 | Dateien ≤ 160 Blöcke sind nach dem Scan komplett im Cache |
| A23 | Steuerdateien (Tap = Befehl): ≤ 160 Blöcke → Tap erzeugt **keinen** Read; Prefetch/Kette/Ordner-Loop lesen sie auch **ohne** Tap; nach erstem Lesen wirkt sie bis zum Cycle nicht erneut | **[A]** | A20–A22, R9, R45, R50 | Steuerdatei > 80 KiB, Befehl an Reads jenseits Block 160 erkennen, Read ≠ Absicht; Steuerdateien nicht als Nachbarn eines Live-Slots |
| A24 | Kumulierte BUSY-Dauer pro Live-Slot ≈ **Spieldauer des Slots**: 4 MiB @48 kbit/s ≈ 699 s, @128 kbit/s ≈ 262 s; 8 MiB @48k ≈ 1398 s | **[A]** | A17 × Bitrate; belegt sind nur ~65 s kumuliert für 512 KiB (E7/R29) | Hauptrisiko Variante B: Pacing über eine ganze Datei ist ~4–20× länger als bisher gemessen → P0-Test |
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
| Längste reale Haltezeit eines Kommandos ohne BUSY-Stimulus (Heimfahrt) | < 0,3 s | **[B]** | Facts §9.1; R51 REJECTED | L | — | — |
| BUSY über eine ganze Datei (≥ 4 MiB) | unbekannt; nötig ≈ Spieldauer | [?] / [A] | A24, Q1 | L | **P0** | Live-Slot 4 MiB mit Pacing auf Echtzeit + Ohr, dann 8 MiB |
| Timeout je READ10 | ≥ ~20 s (bedingt) | [A] | A4 | L | **P0** | Lab-Leiter 0/1/2/5/10/15 s (`lab_stall_phase_ladder.py`), dann NBT; nicht E7-65 s kumuliert verwechseln |
| Timeout ohne Datenfluss (Inaktivität) | unbekannt | [?] | Q1 | L | P1 | Retry-Pausen ohne Daten |
| Reaktion bei Timeout | unbekannt (Reset? Skip? Remount?) | [?] | — | S | P1 | gezielt überschreiten, Status + Ohr |
| Menülatenz unter Stall | ~20 s beobachtet; Ursache 240-CBW Inference | [B] Phänomen / [A] Ursache | R35, A3 | U | P1 | Stall-Leiter Menü-Phase + Vorlauf ≥ 120 KiB A/B |
| Benötigter Live-Vorlauf ohne UI-Freeze | ≥ 1 CBW = 120 KiB (≈ 20 s @48k, 7,7 s @128k) | [A] | A2, A3 | L, U | **P0** | PSRAM **an** ab esp32.pidrive 0.4.54 (Ring 160 KiB) — [`ESP32-S3-BOARD`](../referenz/ESP32-S3-BOARD.md); Option-b Zeitversatz noch offen |
| Scan-Head (alle Dateigrößen) | **32+128 = 160 Blöcke ≈ 80 KiB** + EOF-Probe, größenunabhängig | **[B]** / [S] | A12, A22 | L, C | **P0** | Vertrag: Dateikopf gültig; „nur Struktur“ REJECTED |

### 2.3 Dateisystem und Medium

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| FAT12 / FAT16 / LFN | funktioniert | [B] | F1 | S | — | — |
| FAT32 / exFAT | ungetestet | [?] | — | S | P2 | Geometrie-Varianten |
| Fehlerhafte FAT/Root | leere Liste | [B] | F2 | S | — | — |
| Listenreihenfolge | ≠ Slot-Reihenfolge; ASCII mit Groß/Klein passt | [S]/[H] | F5 | U | P2 | Namen-/Cluster-Permutation |
| Autoplay-Reihenfolge | fav2 → fav1 → fav0 | [B] | F8 | U | — | — |
| Autoplay-Loop | im Ordner (M03 → M01); über Ordner [?] | [S] | R60 | U, L | P1 | Q19 |
| Autoplay-Takt / Bitraten | Wechsel ≈ Dateidauer; 32–320 kbit/s und VBR gelesen | [S] | R59 | L | — | — |
| Max. Dateigröße für Eager-Read (Q4a) | **≥ 7,2 MB vollständig**, keine Grenze sichtbar (A17); 8-MiB-Stille-Slots 98,9 % (R32) | [B] / [?] ≥ 8 MiB | R2, R32, R53 | L | **P0** | Einzeldatei 8/16 MiB mit hörbaren Markern — nicht die ganze Leiter |
| Verhalten bei sehr großer Datei („Radio ohne Ende“) | unbekannt | [?] | D-Leiter | L | **P0** | D1–D3 erst nach stabilem LIVE |
| Persistente Medium-Identity der HU | SQLite-Felder Serial, identifier, mountpath, lastseen | [D] | F10–F13 | L | — | — |

### 2.4 Cache, Prefetch, Resume

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| Gewählte Datei wird bis EOF gelesen | ja, **100 %**, 0,9–1,05 MB/s, bis 7,2 MB belegt; Demo = ein Track-Atom | **[B]** | R2, A1, A17 | L | — | — |
| Abwahl bricht Lesen ab | ja | [S] | R3 | L | — | — |
| Nächste Datei vorlesen | natürlicher Wechsel: Kopf 768 KiB–1,31 MiB **7,2–8 s vor Ende**, Rest beim Wechsel; demo_v1 Lead **0**; Kette möglich | [S] n=6 · 15 s **REJECTED** | R4, R54, A18, A20 | L | P1 | Q19: Kette vs. Kopf-Vorlauf |
| Cache-Hit ohne Reads | ja | [B] | R9 | L | — | — |
| Cache-Retention | ≥ 400–655 s, Teil-Eviction | [S] | R56, A21 | L | P1 | Q4c |
| Ketten-Prefetch | ≈31 MB in 70 s, Unterordner eingeschlossen | [S] | R57, A20 | L | P1 | Q19 |
| Non-live-Slots werden vorab gecacht (Stille) | ja, 98,9 % von 8 MiB | [B] | R32 | L | — | — |
| Cache überlebt ESP-RST | nein | [B] | R13 | L | — | — |
| Cache-Gesamtgröße (Q4b) | unbekannt; ≥ ~31 MB am Stück gelesen (R57), Haltung offen | [?] | Q4b | L | P1 | N × 512 KiB, Re-Select Hit/Miss |
| Eviction-Strategie (Q4c) | unbekannt; M01: Kopf/Ende gehalten, Mitte verdrängt (R56) | [?] | Q4c | L | P1 | Sequenz, dann frühe Datei |
| Wiedergabeposition P persistiert | ja, auch über Medienwechsel | [S] | R23 | L | — | — |
| P bricht bei Serial + Root-Label + Name | nein | [S] | R34 (`HU-Technical-Facts`, S3/S4/F1 — nicht Feld 16.10.) | L | — | — |
| Soft-Remount (NOT READY) als HU-Reset | wirkungslos | **[B]** | R37, E17; A16 Blindfenster | L | — | Menü-Reread = D+-Cycle (FW ≥0.4.55); Soft-Hide nur Lab |
| Remount = Cold Start | nein | **[S]** | R46 (nur `#23`) | L | — | 395xxx-Probe war Artefakt (Q18 geschlossen) |
| Eager Body = Play Intent | nein | **[S]** | R50 | L | P0 | Audible-GATE |
| Prefetch-Lead Konstante 8/15 s | REJECTED | **[B]** | R49, A5 | L | — | Lead VARIABLE |
| Analyzer-MSC ohne FAT → Media-UI | nein (silent mount) | **[B]** | E18/F15 | U | — | Content-Image nötig |
| P/Cache-Bruch durch BPB-Volume-ID | unbekannt | [?] | Q3/Q14, F0 B3 | L | P1 | Serial/Label/Vol REJECTED (R34); Rest niedrige Prio |
| P/Cache-Bruch durch BPB+Root-Label | unbekannt | [?] | F0 B2 | L | **P0** | F0 B2 isoliert |
| P/Cache-Bruch durch Serial + Product-Revision allein | unbekannt | [?] | F0 B1 | L | **P0** | F0 B1 isoliert |
| P/Cache-Bruch durch Größe, Pfad, Startcluster | unbekannt | [?] | Q14 | L | P1 | eigene Builds nach F0 |
| Resume-Lesemuster | 16-Block-Kopf, dann 120-KiB-Segmente vor/zurück, Pause 5,1 s | [B]/[A] | R16, A2 | L | — | — |
| Resume nach Mount (große Datei) | Kopf 0–3840 ∥ P → EOF; Mitte beim Abspielen | **[B]** | R55, A19 | L | — | — |
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
| Höhere Bitrate (96/128 kbit/s) | HU liest 32–320 kbit/s (R59); hörbar [?]; PiDrive-Live nur 48k getestet | [S] Read / [?] Live | D5, R59 | L, U | **P1** | verkürzt CBW-Wartezeit (A3) und BUSY-Summe (A24) |
| Formatwechsel Live ↔ Stille in einer Datei | ungetestet | [?] | D4 | L | P1 | Lab-AV, dann Feld |
| Wiedergabe beginnt während des Lesens | ja | [S] | R12 | L | P2 | Video Tap → Ton |
| Pause zwischen Tracks | ~6 s | [S] | R7 | L | — | — |
| Hörbare Tondauer vs. gelieferte Live-Bytes | 5–6 s gehört bei 8,2 s Ring | [B]/[?] | R25 | L | P1 | Marker-Audio, Decoder-Anlauf |
| Startverzögerung Tap → Ton | unbekannt | [?] | — | L, U | P2 | Video |

### 2.6 Identität und Betrieb

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| Angezeigter Gerätename | aus USB-iProduct | **[B]** | F16 | U | — | iProduct „PiDrive“ |
| Vendor-only / phone-like Identität | „nicht unterstützt“ | **[B]** | Facts §10 C-F1/C-F2 | S | — | — |
| `18D1:2D00` direkt | Zubehör-UI + Reconnect-Loop | **[B]** | Facts §10 C-F3 | S | — | — |
| hu-probe-Profil im Auto | `bmw`; `lab_debian` startet soft-detached | **[B]** | I12 | S | — | — |
| Preset `cache_place` am 10.11. ohne Dateien | Ursache offen | [?] | F17 | U | P1 | Preset-Diff 0.3.17 ↔ 0.3.36 |

### 2.7 Bluetooth (Variante A: A2DP/AVRCP/HFP, SDP)

Ein Feld-Capture 13.11. (A6, BlueZ/PipeWire auf `.108` als Phone, HU ohne Phone-App) — Facts §10.5. Prio bezogen auf Variante A bzw. Control Plane.

| Parameter | Wert | Status | Quelle | Benötigt für | Prio | Wie ermitteln |
|-----------|------|--------|--------|--------------|------|---------------|
| HU-Adresse / Class | `D4:36:39:CF:E1:B5`, `0x340408`, Name „BMW 38304“, Modul ALPS | **[B]** | C-BT1 | S | — | — |
| Pairing | Numeric Comparison (SSP), Agent bestätigt | **[B]** | C-BT3 | S | — | — |
| Profile der HU | A2DP-Sink 1.3 · AVRCP-CT 1.5 (kein TG) · HFP-HF 1.6 · MAP-MNS 1.2 · OPP · PnP | **[B]** | C-BT1 | L, U | — | — |
| RFCOMM-Kanäle der HU | 1 MAP-MNS · 2 HFP · 5 `deca-fade` · 6–10 SPP `0x1101` · 11 OPP | **[B]** | C-BT1 | S (Control) | — | — |
| RFCOMM-Initiative der HU (Leerlauf) | nur HFP; keine Daten-Kanäle | [S] | C-BT8 | S (Control) | **P0** | B2-B Hold 300 s mit MyBMW OFF/ON |
| Ziel-Kanal Android-SPP-Client | ch 6 (erster `0x1101`-Record) | [H] | C-BT2 | S (Control) | **P0** | B2-A: `.87` → ch 6 und ch 5 |
| SBC-Fähigkeiten | alle Modi, 44,1 + 48 kHz, Blöcke 4–16, Subbänder 4/8, Bitpool 2..53 | **[B]** | C-BT4 | L | — | — |
| AAC | MPEG-2/4 LC, 44,1 + 48 kHz, mono/stereo, VBR | **[B]** angeboten / [?] hörbar | C-BT4 | L | P1 | AAC-Source auf PiDrive, Ohr + Coex |
| Content Protection / Delay Report | SCMS-T + Delay Reporting an jeder SEP | **[B]** | C-BT4 | L | P2 | Wirkung von Delay Report auf Lippen-/UI-Sync |
| Gewählte Konfiguration BlueZ-Default | SBC 48 kHz Joint Stereo 16/8, Bitpool 53 | **[B]** | C-BT5 | L | P1 | Sample-Rate fest 44,1 kHz konfigurieren und vergleichen |
| Bitrate SBC-53 | ≈ 357 kbit/s @48 kHz / ≈ 328 kbit/s @44,1 kHz | Rechnung | C-BT5 | L | **P1** | gegen Coex-Budget ESP (~41–45 kB/s HCI) prüfen |
| AVRCP-Events, die die HU anfragt | `01 02 03 04 05(1 s) 06 07 09 0a 0b 0c`; abgelehnte 6× neu, dann Aufgabe | **[B]** | C-BT6 | U | P1 | TG mit allen Events anbieten |
| Metadaten-Abfrage | GetElementAttributes je Attribut einzeln, IDs 1–7 | **[B]** | C-BT6 | U | — | — |
| Browsing | genutzt (GetFolderItems Media-Player-Liste, ERTM) | **[B]** | C-BT6 | U | P1 | Antwort mit gültigem Player + Now-Playing |
| Pass-through | PLAY, FORWARD, BACKWARD (Lenkrad/iDrive) | **[B]** | C-BT6 | U | — | weitere Tasten (PAUSE/STOP) bei Bedarf |
| Absolute Volume | nicht beobachtet | [?] | C-BT6 | U | P2 | mit TG-Feature „Volume“ und Lautstärke am iDrive |
| HFP mit AG ohne Telefonie | SLC bricht an `AT+CHLD=?` ab, Reconnect alle 20–35 s | **[B]** | C-BT7 | S | **P1** | HFP-AG aus (`lab_hfp_stack.py hfp-off`) oder `+CHLD` beantworten |
| Wer nutzt ch 5 (`deca-fade`) | unbekannt | [?] | C-BT9 | S (Control) | P1 | Phone-HCI-Snoop mit MyBMW; B2-A ch 5 |

---

## 3. Was für Live-Ton zuerst fehlt

Die P0-Zeilen hängen zusammen:

1. **Stabile Episoden:** Panic/Brownout beim OTG-Stecken beseitigen, sonst ist jede Identity-Messung ungültig.
2. **Identity Serial/Label/Vol:** als Resume-Key **REJECTED** (23.10., Facts R34). Weitere Serien gestoppt.
3. **Timeout pro READ10 + nötiger Vorlauf:** entscheidet, wie lange BUSY pro 240-Block-CBW gehalten werden darf und ob ein Ring ≥ 120 KiB oder eine höhere Bitrate nötig ist.
4. **Pacing über eine ganze Datei (A24):** Die HU liest beim Spielstart die ganze Datei (A17). Erster Feldtest: ein 4-MiB-Live-Slot mit BUSY-Pacing auf Echtzeit, Ohr + Capture (hu-probe ≥ 0.3.40 oder PiDrive-MessCapture); danach 8 MiB. Die kleine Größenleiter (512 KiB…4 MiB) ist durch A17 überholt.
5. **Nachbarn und Steuerdateien (A18–A23):** Live-Slot ohne ungültige Nachbarn; Steuerdateien > 80 KiB und nicht neben Live-Slots. Q19 (Kette vs. Kopf-Vorlauf) mit markierten Nachbarn und Operator-Log klären.

A1 (Track-Atom 240+69) und A2 (240-Max) sind **[B]**; A12 (Head-160) und A13 (TUR 2238,78 ms) seit Media-Leiter/free **[B]**. A5 (15 s Lead) auf demo_v1 **REJECTED**; A15 (512-Block-Fenster) **widerlegt**; A17/A19 **[B]**, A18/A20–A22 **[S]**, A23/A24 abgeleitet. A7 bleibt MessCapture-**[S]**. A3/A4/A6 abgeleitet; A11/Audible und Cache-Key F0 offen — hu-probe Identity-Plan vor weiteren PiDrive-Cache-Hebeln.  
**FW:** esp32.pidrive **0.4.54** — PSRAM an, StreamBuffer-Mutex (R13), PanicTail/PhaseGate/DiagLog/HwInfo.

---

## 4. Messgültigkeit

Nur Instrument-gültige Sessions zählen (Facts §9.1): Heimfahrt `#22`–`#24`, Media-Leiter 22.10. außer `081410` (Ringverlust, I11), 20.10. free, S0/S2, 11.11. free (Ops). **Ungültig:** Größenleiter 27.10. und 11.11., Lab `065150` (I7/I8). Auswertungen nach `origin` filtern (`post_finalize` ≠ Trip, I9); `analyze_session.py` ist seit 11.11. gegen Tag-Wiederverwendung nach Remount korrigiert (I10).
