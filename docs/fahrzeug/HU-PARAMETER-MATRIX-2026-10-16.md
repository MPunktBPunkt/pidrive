# HU-Parametermatrix — BMW NBT Evo für den PiDrive-Betrieb

**Stand:** 2026-10-16 · **Basis:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md) (Stand 15.10.), hu-probe S0 0.2.17 / S2 0.2.23, Offline-P0, PiDrive-Feld s1–s6 und F0, Lab 13.–16.10., technology-audit 0.7.1.
**Status:** [B] bewiesen · [S] stark belegt · [A] **abgeleitet** (projektübergreifende Rechnung aus vorhandenen Daten, noch nicht direkt gemessen) · [D] Desk · [H] Hypothese · [?] offen.

Device-Stack-Messungen sind keine Wire-Messungen. Lab-Werte (Debian-Host) sind keine NBT-Werte.

---

## 1. Neu abgeleitete Parameter (Querauswertung 16.10.)

| # | Ableitung | Status | Rechnung / Beleg | Folge für PiDrive |
|---|-----------|--------|------------------|-------------------|
| A1 | „Burst-39“ ist **eine komplette Datei**, keine HU-Konstante | [A] stark | `hu-probe/firmware/src/msc/demo_fat.bin`: `TRACK1..3.MP3` je **158 208 B**. Offline-P0: reine Bursts **158 208 B** in ~170 ms. 39 Events = READ10 **240** Blöcke (30 × 4096) + READ10 **69** Blöcke (8 × 4096 + 2560). Erklärt auch die seltenen `n=2560`-Events und `blocks=69` | Eager-EOF (R2) ist damit auf einem **zweiten, unabhängigen Medium** bestätigt. `eager_eof` in hu-probe kann von INFERENCE auf [S] steigen |
| A2 | Maximale READ10-Transferlänge der NBT = **240 Blöcke (120 KiB)** | **[S]** | hu-probe S2 + **Feld 16.10. MessCapture** (`feld-512kib-predict-01`): nie >240; häufig 240 | Lese-, Resume- und Prefetch-Muster in **CBW-Einheiten zu 120 KiB** planen und auswerten, nicht in 4-KiB-Callbacks |
| A3 | Die ~20 s Menüträgheit unter Stall (R35) entsteht durch **ein** gebremstes 240-Block-Kommando | [A] stark | BOT kennt nur ein offenes Kommando (E6). 122 880 B bei Live-Rate 6,0 KB/s (48 kbit/s) ≈ **20,5 s**; Lab-Pacing 734–1021 ms je 4 KiB ⇒ 22–31 s je CBW. FAT/DIR-Reads des Menüs warten so lange hinter dem offenen READ10 | Menü-Freeze ist kein HU-Fehler, sondern Folge von Stall-Länge pro CBW. Abhilfe: Vorlauf ≥ 1 CBW, höhere Bitrate oder BUSY nur, wenn Vorlauf < CBW-Länge |
| A4 | Untere Grenze NBT-Timeout **pro READ10 ≥ ~20 s** | [A] bedingt | E7/s6: ~65 s Audio bis EOF eines 512-KiB-Slots unter BUSY ohne Abbruch ≈ 3–4 gebremste 240-Block-CBWs à ~20 s. **Feld 16.10.:** 240-Block-CBWs im Play/Full-File bestätigt; Timeout-Grenze selbst nicht neu gemessen | Bei 48 kbit/s liegt ein CBW bereits an dieser Grenze. Gesamtgrenze bleibt Q1 |
| A7 | Full-File-Read eines **512 KiB**-Slots = **`240,240,32,240,240,32`** (Summe 1024), **nicht** `8+4×240+56` | **[S]** | Feld MessCapture 16.10. mehrfach: BOB LED, Gelb, Tip Bayern (`mess-cmds-*-{bob-led,gelb,TIP-BAYERN}.json`). Vorhersage `8+56` widerlegt | Prefetch/EOF-Planung an 240/32-Muster; keine Annahme eines 8er-Intros für diesen Slot |
| A5 | Prefetch-Vorlauf ~15 s ist mit hu-probe-Pausen vereinbar | [H] | Track 158 208 B bei 48 kbit/s = **26,4 s**. 26,4 s − 15 s = 11,4 s ≈ Inter-Burst-Pause p50 **10,2 s** (n=18, gemischte Sessions) | R21 nicht hochstufen; Bestätigung mit Markern und LBA-Folge |
| A6 | Ein Info/Xing-Header ist für Eager-Read nicht nötig | [A] schwach | Demo-Tracks ohne erkennbaren Info/Xing-Tag werden ebenso komplett gelesen wie PiDrive-Slots mit LAME-Info | Info-Tag weiter für Dauer/Fortschrittsbalken prüfen, nicht für das Leseverhalten |

**Feld-Ergebnis MessCapture 0.4.52 (16.10., NBT `.89`):** Ein Full-File-Read eines 512-KiB-Slots zerfällt in **`240 + 240 + 32 + 240 + 240 + 32`** (nicht `8 + 4×240 + 56`). LIVE-Ohr nur kurz (~5–6 s) nach Klasse-A-OTG; Panic/weiße LED bleibt Blocker. Details: `docs/betrieb/artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md`.  
**Offen:** R16-Resume (kleines Kommando → 240er) weiter bestätigen; Ton↔READ-Korrelation im ~5 s-Fenster.

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
| TUR-Rate | ~0,8–1/s idle; Session-weit ~2 Hz | [S] | E3 | S | P2 | Fensterraten je Phase |
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
| Callback-Chunk | 4096 B (Stack) | [B] | E5 | L | — | — |
| Häufige CBW-Längen | 8 und 240 Blöcke, Rest bis EOF (z. B. 69) | [B]/[A] | E11, A1 | L | — | — |
| Max. READ10-Transfer | 240 Blöcke = 120 KiB | [A] | A2 | L, U | P1 | `MessCapture`-Histogramm je Phase (Scan/Play/Prefetch) |
| Lesetakt ohne/mit ESP-Play | 3,74–3,78 ms / ~5 ms je 4 KiB | [B] | R15 | L | — | — |
| BUSY-Toleranz kumuliert | ≥ ~65 s bis EOF | [B] | E7, R29 | L | — | — |
| Timeout je READ10 | ≥ ~20 s (bedingt) | [A] | A4 | L | **P0** | Lab-Leiter Stall pro CBW 10/20/30/45 s am NBT, CBW-Länge mitloggen |
| Timeout ohne Datenfluss (Inaktivität) | unbekannt | [?] | Q1 | L | P1 | Retry-Pausen ohne Daten |
| Reaktion bei Timeout | unbekannt (Reset? Skip? Remount?) | [?] | — | S | P1 | gezielt überschreiten, Status + Ohr |
| Menülatenz unter Stall | ~20 s, erklärt durch ein offenes CBW | [B] Phänomen / [A] Ursache | R35, A3 | U | P1 | Stall mit Vorlauf ≥ 120 KiB vs. ohne vergleichen |
| Benötigter Live-Vorlauf ohne UI-Freeze | ≥ 1 CBW = 120 KiB (≈ 20 s @48k, 7,7 s @128k) | [A] | A2, A3 | L, U | **P0** | Ring-/PSRAM-Größe prüfen, Lab-Messung |

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
| Gewählte Datei wird bis EOF gelesen | ja, ~1 MB/s | [B] (+[A] A1) | R2 | L | — | — |
| Abwahl bricht Lesen ab | ja | [S] | R3 | L | — | — |
| Nächste Datei vorlesen | komplett, ~15 s vor Wiedergabeende | [B]/[S] | R4, R21 | L | P1 | Marker + LBA (A5) |
| Cache-Hit ohne Reads | ja | [B] | R9 | L | — | — |
| Non-live-Slots werden vorab gecacht (Stille) | ja, 98,9 % von 8 MiB | [B] | R32 | L | — | — |
| Cache überlebt ESP-RST | nein | [B] | R13 | L | — | — |
| Cache-Gesamtgröße (Q4b) | unbekannt | [?] | Q4b | L | P1 | N × 512 KiB, Re-Select Hit/Miss |
| Eviction-Strategie (Q4c) | unbekannt | [?] | Q4c | L | P1 | Sequenz, dann frühe Datei |
| Wiedergabeposition P persistiert | ja, auch über Medienwechsel | [S] | R23 | L | — | — |
| P bricht bei Serial + Root-Label + Name | nein | [S] | R34 | L | — | — |
| Soft-Remount mit gleicher Identity ändert Ton | nein | [S] | F0 16.10. | L | — | — |
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
| ID3v2 am Dateianfang + APIC JPEG | funktioniert | [B] | M1 | C | — | — |
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
2. **Identity-Achse F0 (B1–B3):** entscheidet, ob PiDrive den HU-Cache gezielt brechen kann.
3. **Timeout pro READ10 + nötiger Vorlauf:** entscheidet, wie lange BUSY pro 240-Block-CBW gehalten werden darf und ob ein Ring ≥ 120 KiB oder eine höhere Bitrate nötig ist.
4. **Große Datei (D1–D3):** erst danach, sonst läuft die Leiter in dieselben Cache-/Resume-Effekte.

A2 (240-Max) und A7 (512‑KiB Full-File `4×240+2×32`) sind am NBT mit MessCapture 16.10. bestätigt bzw. gegen die alte `8+56`-Vorhersage entschieden. A1/A3/A4/A5/A6 bleiben abgeleitet; Timeout- und Ton↔READ-Feinheiten offen.
