# HU Technical Facts — BMW NBT Evo als USB-Massenspeicher-Host

**Stand:** 2026-11-13 (BT: A6 FIELD PASS · Secondary NBT-AAD `4f70751` · F20 RFCOMM-Initiator **UNKNOWN** · B2-A/B2-B Two-Mode; davor 12.11.: Connected/BT Desk-Nachzug BimmerGestalt + Lab `NO_RFCOMM`; 11.11.: hu-probe R53–R60 / Narrative [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md); Facts-Körper 06.11. MSC/Connected Desk) · **Fahrzeug:** BMW 118d F20 LCI (2017), NBT Evo · **Gerät:** ESP32-S3 `esp32.pidrive` 0.4.60+ / `hu-probe` 0.3.38 (Feld), 0.3.40 (Code, ungetestet) / Analyzer-Gadget 0.0.52 / `esp32.bt-analyzer` hci-agent 0.3.19  
**Maßnahmen:** [`../planung/MASSNAHMEN-MSC-FULLMENU.md`](../planung/MASSNAHMEN-MSC-FULLMENU.md) · [`MASSNAHMEN-HU-PROBE-2026-10-22.md`](../archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) · hu-probe: [`heimfahrt`](../../../hu-probe/docs/feld/MSC-HEIMFAHRT.md) · [`identity-multireview`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/MSC-IDENTITY-REMOUNT.md) · [`wire-074319/455`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-074319-074455.md) · [`detach-browse`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) · [`Größenleiter GO`](../../../hu-probe/docs/feld/MSC-GROESSENLEITER-GO.md) · Analyzer: [`Feldmatrix 06.11.`](../../../usb-analyzer/docs/reports/2026-11-06-field-host-matrix.md) · [`Cross-Check 02.11.`](../archiv/betrieb/2026-11-02-esp-usb-analyzer-crosscheck.md)  
**Zweck:** Sammlung dessen, was über das Verhalten der Head Unit (HU) am USB-Port **bekannt und belegt** ist. Jede Aussage trägt einen Belegstatus und eine Quelle. Neue Feldtests sollen hier nachgetragen werden.  
**Narrative Lesefassung (TOC + Quellen + GPT-Abgleich):** [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md) — dieses Dokument bleibt die normative Claim-Tabelle.

**Scope:** Belegte Plattform = **diese** NBT Evo. Zwei getrennte Ebenen: **Storage Plane** (USB-MSC, §§1–9) und **Control Plane** (AOA/Connected, §10 + [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md)). Keine gemessenen Fakten zu CAN, MOST, CarPlay, Android Auto oder HU-WLAN/Ethernet-APIs. AOA/Connected: **Abgrenzung** Feld (E18/F15) + **Desk-[D]** in §10 — keine stillen MSC↔Connected-Transfers. Andere BMW-Generationen = kein stiller Transfer. Lab-AV ≠ Feld-Ohr. Analyzer-Host-Stimulus ≠ echte NBT.

| Status | Bedeutung |
|--------|-----------|
| **[B]** bewiesen | direkt in Rohdaten gemessen, mehrfach oder byte-genau nachgerechnet |
| **[S]** stark belegt | konsistent in mehreren Läufen, aber nicht unter allen Bedingungen geprüft |
| **[D]** Desk-Fakt | an gepinntem Fremdcode/-artefakt belegt; keine Messung an dieser HU |
| **[H]** Hypothese | plausibel, noch nicht gemessen |
| **[?]** offen | unbekannt, Test nötig |

Begleitdokumente: [`../betrieb/MSC-AKTUELL.md`](../betrieb/MSC-AKTUELL.md) · [`../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) · Audit-Reports: [`media-ladder`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md) · [`heimfahrt`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-heimfahrt.md) · [`abend-offline`](../../../technology-audit/docs/reports/2026-10-18-hu-probe-bmw-s2-abend-offline.md) · Audits: [`hu-probe-heimfahrt-2026-10-22`](../../../technology-audit/audits/hu-probe-heimfahrt-2026-10-22/) · [`hu-probe-media-ladder-2026-10-22`](../../../technology-audit/audits/hu-probe-media-ladder-2026-10-22/) · [`esp32-usb-analyzer-2026-field-host-matrix`](../../../technology-audit/audits/esp32-usb-analyzer-2026-field-host-matrix/) · [`pidrive-2026-bmw-hu`](../../../technology-audit/audits/pidrive-2026-bmw-hu/evidence.md) · Foreign-Desk: [`bmw-nbt-media-index`](../../../technology-audit/audits/bmw-nbt-media-index-2026-foreign/evidence.md) · [`usb-bot-observation`](../../../technology-audit/audits/usb-bot-observation-2026-foreign/evidence.md) · hu-probe Profil [`bmw_nbt_evo.json`](../../../hu-probe/profiles/bmw_nbt_evo.json)

---

## 1. Gesamtbild in einem Satz

**Zwei-Plane (Kurz):** Storage = aggressiver USB-MSC-Host mit ≥3 Zuständen (Navigator ≠ Browse ≠ Body), großen READ10 (CBW oft 8/240), hoher Stall-Toleranz (Feld stark belegt). Control = Connected Apps **G1–G4** (BCL→Etch→SAS; danach RHMI/CDS/AV — keine Gate-ID G5; Desk-[D], F20-Wire offen). Details: [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md).

**Storage Plane:** Die NBT-Evo-HU behandelt USB-Medien wie eine Festplatte mit fertigen Dateien, hält aber **mindestens drei getrennte Zustände**: (1) **Navigator/Playlist-Position**, (2) **Browse-/Titel-/Bibliotheks-Cache**, (3) **Audio-Body-Cache**. USB-Cycle, FS-Re-Enum und Resume sind **nicht dasselbe Ereignis**; Remount ist **kein** Cold Start (R46, Beleg nur `#23`). Fresh-Scan liest je Datei **160 Blöcke Kopf + EOF-Probe**, unabhängig von der Dateigröße (R58). Ein Titel, der zu spielen beginnt, wird **vollständig** mit Bus-Geschwindigkeit gelesen (R53: 24 Dateien 2,0–7,2 MB, je 100 %, 0,9–1,05 MB/s, **keine Obergrenze bis 7,2 MB**). Beim natürlichen Autoplay-Wechsel kommt ~7–8 s vor Titelende ein Kopf-Vorlauf des Folgetitels, der Rest beim Wechsel (R54). Resume nach Mount liest Kopf 0–3840 Blöcke verschränkt mit Resume-Position→EOF (R55). Die HU kann mehrere Folgetitel Rücken an Rücken vorlesen (R57, ≈31 MB in 70 s) und hält Body-Daten minutenlang (R56). Eager ≠ Play Intent (R50). Idle: **TUR ~2239 ms**. Callback-Reads oft 4 KiB (E5); CBW-`blocks` häufig **8 und 240** (E11). Das **512-Block-Fenster** (Matrix A15) ist für reale Dateien **widerlegt**. Größenleiter-Feldläufe 27.10./11.11. **ungültig** (Instrument, I7/I8); Q16 ist für 2–7,2 MB durch die nachgerechnete Heimfahrt beantwortet, für ≥ 8 MiB offen.

```mermaid
flowchart LR
  Plug["USB Plug / Cycle / Reconnect"] --> Enum["SCSI + FS-Enum"]
  Enum --> Path{Zustand bekannt?}
  Path -->|Fresh / Cold| Scan["Datei-Scan 160 Bloecke + EOF je File"]
  Path -->|Cycle/Remount + bekannt| Res["Kontextaufnahme / kein Bibliotheks-Fresh"]
  Scan --> Modes["Head / Eager Body / Neighbor-Interleave"]
  Res --> Atom["Resume-Atom oft tail70 then head240"]
  Modes --> Wait["Idle TUR 2238.78 ms"]
  Atom --> Wait
  Wait --> Sel["Nutzer / Autoplay"]
  Sel --> Nav["Navigator-Position"]
  Sel --> Browse{"Browse-Cache Hit?"}
  Browse -->|ja| UI["Liste ohne Neu-Read"]
  Browse -->|nein| DirRead["Dir/Heads erneut"]
  Nav --> Play{"Body-Cache / Intent?"}
  Play -->|Hit| PlayCache["Wiedergabe ohne Body-Read"]
  Play -->|Miss| Eager["Atom / Eager-Read ≠ Audible"]
```

**PiDrive-Vertrag:** stabiles Directory/FAT + gültiger Dateikopf (~80 KiB + konsistente Size/EOF); Body darf dynamisch entstehen; Neighbor-Eager/Partial erwarten. Browse-UI aus Dir (8.3), Player-ID3 aus Head (M5). **Live-Slot:** Die HU fordert die **ganze Datei** sofort an (R53). Ohne BUSY-Pacing über die gesamte Slot-Länge landet alles noch nicht Erzeugte als Stille im HU-Cache. Der Folgetitel wird ~7–8 s vor Ende angelesen (R54), Nachbarn können vollständig vorgelesen werden (R57). **Nicht annehmen:** Remount ⇒ Cold Start / Position weg; Serial/Label/Vol ⇒ Resume-Key; Soft-Remount (NOT READY) ⇒ HU-Reset; „länger weg“ ≤~99 s ⇒ Fresh; großer Read ⇒ hörbares Play; Prefetch-Lead = 15 s; Lesefenster 512 Blöcke.

---

## 2. Enumeration und SCSI-Verhalten

| # | Fakt | Status | Wert / Beleg |
|---|------|--------|--------------|
| E1 | INQUIRY ca. 1 s nach Plug | [B] | `msToInquiry=997`, `msPlugToFirstRead=1004` (`status-0758-bayern-1.json`); identisch 01.10. (`msToInquiry` ≈ 1000) |
| E2 | Kommandomix | [B] | PiDrive: `inquiry=1`, `capacity=3`, `prevent=7`, `startStop=0`, `otherScsi=0`; Firmware-Fingerprint `hint=hu-like`. **hu-probe:** `tur` ≫ `read10`, dazu `prevent_allow`, `mode_sense6`, `read_capacity10`, `inquiry`. **MODE_SENSE6 / READ_CAPACITY = 2,0** (S2 Kern 60/30; auch vor Stall-Fix) = Host-Muster, kein Stall-Indiz (`EVID-HUPROBE-2026-10-15-005`). [`bmw-s0-0.2.11`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-0.2.11-auswertung.md), Audit S0/S2 |
| E3 | TEST UNIT READY periodisch, **Leerlauf-Periode 2,239 s**, phasenstarr | **[B]** (korr. 19.10.) | hu-probe: alle TUR-Abstände außerhalb von Mount-Bursts, 19 BMW-Sessions, **n = 382**: p10/Median/p90 = **2238/2239/2239 ms**. Der Timer läuft über Reads hinweg weiter, unabhängig von der Leseaktivität. **REJECTED:** „~0,8/s“, „Golden ≈ 1/s“ (Mittel über Uptime inkl. Mount-Bursts und Pausen) und Session-TUR-Hz ~2,06 als Leerlauf-Rate (`EVID-HUPROBE-2026-10-15-012` war ein Fenstermittel). [`unabhängige Auswertung`](../../../hu-probe/docs/feld/MSC-TUR-MOUNT-FACTS.md) P-TUR |
| E4 | Keine Schreibzugriffe | [B] | `writeCount=0`, `writeReject=0` in allen Snapshots; Golden `writes_expected: false`; hu-probe S0/S2: keine Writes in ausgewerteten CBWs (`001`/`003`) |
| E5 | Transfergröße **Event-/Callback-Ebene** fast ausschließlich 4 KiB | [B] Event | `xfer: n512=3, n2k=0, n4k=1536, n8kPlus=0` (07:58); `n4k=2293` (st-55). hu-probe File-n=4096 dominant (S0/S2). **Callbacks ≠ CBW:** TinyUSB-Puffer 4096 B → `n8kPlus` bauartbedingt 0; ein READ(10) kann viele Re-Entries erzeugen. CDB-Größe = E11 / Q10. Ablesbar: `n512=3` → 512-B-Callbacks; größere Datenphasen werden in 4-KiB-Chunks zerlegt |
| E6 | Queue-Tiefe 1, ein Kommando nach dem anderen | **[B]** protokollbedingt | Bulk-Only Transport: CBW → Daten → CSW, erst danach das nächste CBW (kein Pipelining). `mscTrace`: Abstand 3–5 ms, keine überlappenden Kommandos. LBAs innerhalb eines Segments monoton, **zwischen Segmenten nicht** (R16). Folge fürs Bremsen: Während ein READ wartet, kommt **kein** TEST UNIT READY (E3). QD-max p50=1 hu-probe `INFERRED` (Wire `UNKNOWN`, `012`) |
| E7 | Toleranz gegenüber langsamen READ10 / BUSY | **[B] NBT** | Feld s6: Stall-on lieferte ungefähr **65 s Musik+ID3 bis EOF** eines 512-KiB-Slots; Stall-off fiel reproduzierbar auf etwa **6 s** Ringfenster zurück. NBT akzeptiert damit TinyUSB-BUSY-Retries über Minuten. Die Operator-Dauer ist nicht poll-genau; Gesamtdauer- vs. Inaktivitätslimit bleibt offen (Q1 / HU-A7) — bei `blocks=240` hängt ein Retry an ~122 KiB Datenphase, nicht an 4 KiB (E11). Annahme „kleiner Ring = harte Dauerstrom-Grenze“ **REJECTED** (`EVID-BMWHU-2026-10-12-005`). S7-B Lab: BUSY erst nach Head-`play.guess`; D0 auf 0.4.49 regressionsfrei. Evidence `EVID-BMWHU-2026-10-12-001`–`005`. [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md), [`S7-D-SPEC`](../archiv/planung/S7-D-LEITER-SPEC-2026-10-12.md) |
| E8 | Physisches OTG / Soft-Cycle detach→attach | **[B]** Timing · **[S]** Resume | BMW S0 0.2.2: Host detach→attach **2,294–6,011 s** (11 Paare). Soft-Lab ≈ **0,30 s** (nicht als NBT-Fakt). **23.10.:** Soft-Cycle (D+) und OTG ~30–99 s → Re-Enum + Resume (R38/R42/R43); Soft-Remount (NOT READY) ≠ Detach (R37). [`bmw-s0`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-auswertung.md) · [`detach-browse`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) |
| E9 | Kurze Verweildauer → kein DATA / keine Reads | **[B]** Muster / [?] Ursache | BMW S0 0.2.2: Fenster ~3,8 s → BOOT+FAT+ROOT ohne DATA; mehrere Plugs ~4,7–7,5 s ohne Read-Events. Inference: Dwell-Zeit für DATA/Playback nötig. Eager-EOF/Prefetch auf 256/512‑KiB-Demo **nicht** revalidiert |
| E10 | Replug-Scan-Grundmuster (kleines Medium) | **[B]** 256 KiB-Demo | 6/8 nicht-leerer Fenster: **22 Reads / 65 536 B** = BOOT+FAT+ROOT+DATA. Fenster 7 dichter Mehrfach-Scan (Instrument-/Drain-Artefakt in 0.2.2). Nicht auf große PiDrive-Slots übertragen |
| E11 | READ10-**CBW**-Blockzahl oft **8** und **240**; Demo-Track-Atom = **`(head,240)+(head+240,69)`** | **[B]** hu-probe S2 | Device-Stack CBW (nicht Wire): häufig `blocks=8` (=4096 B) und `blocks=240` (=122 880 B → typ. 30×4096 `read`-Events); Events/READ10 ≈ **5,29**. **Abend-Offline 18.10. (0.2.30):** drei PASS mit exakt Atom 240+69 = 309 LBA = 158 208 B; „39“ = 30+9 Callbacks (38×4096+2560), nicht 39×4 KiB. Covered T3 **627–935** (**REJECTED:** 627–938 / 312 LBA / „3 Meta“). Audit [`hu-probe-bmw-s2-abend-offline-2026-10-18`](../../../hu-probe/audits/hu-probe-bmw-s2-abend-offline-2026-10-18/). Event-n=4096 = Stack-Chunk — nicht blind „HU immer 4 KiB“. `EVID-HUPROBE-2026-10-15-004`. Gate **HU-A10** teilweise belegt |
| E12 | Mount-Signatur | **[B]** hu-probe | Jeder BMW-Mount: INQUIRY ×1, READ_CAPACITY10 ×3, MODE_SENSE6 ×6, PREVENT_ALLOW ×7, genau **32 TUR** (davon ≈ 15 als Burst in 0,05–0,29 s) und **11 READ10** in fester Folge `0/8, 0/8, 24/8, 0/8, 0/1, 1/3, 7/2, 1/1, 2/1, 3/5, 24/8` (LBAs auf dem hu-probe-Demo-Image: FAT 1–6, Root 7–8). Variante: `3/5` → `3/1 + 4/4` (Sessions 195657, 2363). P-MOUNT/P-MREAD. **Präzisierung 11.11.:** Struktur fest, LBAs layoutabhängig — drive_mix (`#22`–`#24`): `0/8,0/8,96/40,8/8,24/8,56/8,16/8,64/8,512/8,32/8,131072/8`; die Folge oben gilt nur für das Demo-Image |
| E13 | LBA 24/8 wird pro Mount zweimal gelesen | [S] Messung / [?] Zweck | Auf dem Demo-Image liegt LBA 24 mitten in TRACK1. Festes Probe-Offset oder Cache-Fenster ist offen; Test mit hu-probe-Medium `tail_probe` (Datenbereich verschoben). P-LBA24 |
| E14 | Resume-Read nach Mount | [S] | Der zuletzt gespielte Track wird **0,2–0,3 s** nach Ende der Mount-Signatur gelesen (S0/S2). Passt zu R24; **23.10.** Cycle+bekannt oft ohne Datei-Head-Scan, Atom am Resume-Track (R38/R41). P-RESUME |
| E15 | Auswahllatenz Marker → READ10 | [S] | Manuelle Wahl **1,7–1,9 s** (`171815`, `2280`), Autoplay-Sprung ≈ **0,2 s** (`200036`). Marker teils nachgezogen, daher [S]. P-SEL |
| E16 | tail_then_head | **[B]** Morphologie (R41) / Ursache [H] | T1 als Folgetrack oft Ende zuerst (`249/69`→`9/240`); Erst-Mounts head-first. **23.10.:** nach Cycle/Resume = Resume-Korrelat `tail70→head240` (R41), nicht „nach jedem Mount“. P-TAIL |
| E17 | Media-Loss-Reaktion | **[B]** | Nach `NOT READY / MEDIUM NOT PRESENT` (hu-probe `hideMedia`): `TUR status=1 → REQUEST_SENSE → PREVENT_ALLOW status=1` (`20261019-075344`, Tags 131–146). **23.10.:** Soft-Remount/NOT READY ≠ HU-Reset / Fresh (R37). P-LOSS |
| E18 | Analyzer-MSC-Gadget am NBT (zweites Instrument) | **[B]** Feld 06.11. | usb-analyzer Device `.89` **0.0.52**, Identity `303a:1001`, Pattern `lab_sector_v1` (512×512 B): HU **mountet** als Storage; Class-Hook CBW: TUR / MODE_SENSE6 / PREVENT_ALLOW / READ_CAPACITY10 / READ10 (`transfer_length` oft **8**); Soft-Reenum → Remount + mehr READs; `writeOps=0`; `aoa51/52/53=0` trotz AOA-respond. **Kein** Media-/Zubehör-UI ohne FAT/Media (F15). Unabhängig von hu-probe TinyUSB-Tap. [`Feldmatrix`](../../../usb-analyzer/docs/reports/2026-11-06-field-host-matrix.md) · Evidence [`bmw_hu/`](../../../usb-analyzer/docs/evidence/field_host_matrix_2026-11-06/bmw_hu/) |
| E19 | Hide-Poll ohne Aufgeben | **[B]** | 27.10. Größenleiter Schritt 1 (`20261027-080529_bmw_seq_size_ladder_1r1`; alle Events `post_finalize` = echte HU-Kommandos nach Capture-Ende, I9): **455× TUR (status=1) → REQUEST_SENSE** im 2,24-s-Takt über **1000,7 s (16,7 min)**, kein Reset, kein Aufgeben. NOT READY ist für die HU ein Dauer-Wartezustand (passt zu R37) |

Quelle E12–E17: [hu-probe unabhängige Auswertung 2026-10-19](../../../hu-probe/docs/feld/MSC-TUR-MOUNT-FACTS.md). Lab-Modell: `tools/nbt_hu_sim.py --hu-model nbt_evo_2026_10`, Profil `tools/profiles/nbt_evo_lab_2026-10-19.json`. E18: Analyzer-Feldmatrix 2026-11-06.

---

## 3. Dateisystem und Medienliste

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| F1 | FAT12 und FAT16 werden gelesen; Dateien mit LFN-Namen werden in der Medienliste angezeigt | [B] | Geometrien Legacy (FAT12 2 MiB), L0 (FAT12 4 MiB), L3 (FAT16 16 MiB) im Feld gelistet |
| F2 | Falsch gepatchte FAT/Root → leere Liste | [B] | Bug 0.4.19 (FELDTEST §4.2) |
| F3 | Dateien mit ungültigem Inhalt (0xFF) → Decoder überspringt, Playlist „rauscht durch“ | [B] | FELDTEST §4.3 |
| F4 | Volle Slot-Länge mit gültigen CBR-Stille-Frames + Xing → Datei bleibt stabil in der Liste | [S] | seit B2 (`Mp3Silence::fill`) |
| F5 | HU-Listenreihenfolge ≠ Slot-Reihenfolge des ESP | [S] | L0-Test 03.10.: BOB oben, Rock unten (Slots fav0=Rock, fav1=Bayern, fav2=BOB). **[H]** passt zu ASCII-Sortierung mit Groß/Klein (`BOB` < `Bayern` < `Rock`, da `O` < `a`) — Testmedium mit gezielten Namen nötig |
| F6 | USB-Serial und Root-Volume-Label (`PDnnnn`) wechseln bei Remount | [B] | PD0082 → PD0084 (06.10.), PD0004 → PD0005 (01.10.); über ESP-RST bleibt die Identity gleich (PD0089, 7 Boots s1-morgen). **Präzisierung 13.10.:** `patchBoot()` lässt FAT-BPB-Volume-ID und BPB-Label aus dem Demo-Image unverändert; `formatVolumeLabel()` ändert nur den Root-Directory-Volume-Eintrag. „Label geändert“ war daher bisher keine vollständige FAT-Volume-Identity-Rotation. |
| F7 | Diese HU zeigt beim Abspielen nur einen **Fortschrittsbalken**, keinen Sekundenzähler | [B] | s1-morgen `f1-events.jsonl` 07:46:43 |
| F8 | Autoplay-Reihenfolge BOB → Bayern → Rock (`fav2 → fav1 → fav0`) | [B] | s1-morgen, mehrfach |
| F9 | USB-Hub an dieser HU: weder Stick noch ESP über den getesteten Hub erkannt (Protokoll: USB-1.1 geplant; Abend: USB-2-Hub) | [B] | F1-Abend 07.10. [`F1-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md) — Full-Speed-Erzwingen über Hub entfällt als Werkzeug |
| F15 | Mount/SCSI ohne sichtbares Media-UI | **[B]** Operator+Wire | Analyzer `lab_sector_v1` / Pattern-Stick: P-MOUNT + READs, aber **kein** erkennbares Medium/Zubehör auf dem HU-Display. Sichtbare Medienliste braucht echtes **FAT + Mediendateien** (z. B. pidrive/hu-probe SynthFat). Abgrenzung: MSC-Identity `303a:1001` ≠ AOA/Connected-Pfad (E18). |
| F16 | Gerätename im HU-UI kommt aus USB-**iProduct**, nicht aus SCSI-INQUIRY oder Volume-Label | **[B]** Feld 10.11. | HU zeigte „Espressif ESP32-S3 DevKitC-1 …“ (Arduino-Default-iProduct) bei INQUIRY/Volume `HUPROBE`; Fix hu-probe 0.3.37. PiDrive: iProduct „PiDrive“ setzen. [`FELD-2026-11-10`](../../../hu-probe/docs/feld/FELD-2026-11-10-I303A-REVAL-MSC.md) |
| F17 | Preset `cache_place` zeigte am 10.11. **keine Dateien** („unbekannter Name/Interpret“); am 22.10. wurde dasselbe Preset normal gelesen | **[?]** Widerspruch | 10.11. hu-probe 0.3.36 vs. Media-Leiter 22.10. 0.3.17. Kandidaten: Preset-Inhalt zwischen den Versionen geändert, HU-Cache-Zustand, Soft-Detach-Falle (I12). `cache_a` am 10.11. ok |

### 3.1 Persistente NBT-Medienartefakte aus Foreign-Desk-Audits

Diese Punkte stammen aus gepinnten Fremdrepositories und sind **keine**
Messungen am Fahrzeug:

| # | Fakt | Status | Beleg / Grenze |
|---|------|--------|----------------|
| F10 | Ein NBT-Forensikmodul liest aus Offline-SQLite eine Tabelle `mediastores` mit unter anderem `msid`, `lastseen`, Anzeigename, `identifier` und `mountpath` | [D] | `BMW-IVI-NBT-ingest-module@127fb15c`; `EVID-BMWMEDIA-2026-10-13-015` |
| F11 | Dasselbe Modul liest `usbdevicedetails.deviceserialno/lastseen` sowie `folders.basepath/last_sync` | [D] | gepinnter Code; persistente USB-/Pfad-/Zeitfelder sind belegt |
| F12 | BMW-Musikbackups enthalten logische USB-Pfade wie `/USB1/...`; BR30 wird als Playlist- und BR67 als JPG-Typ behandelt | [D] | `idrivetools@08e0c43c`, `BMC@c22b27ed`; Offline-Backupformat |
| F13 | Keines der geprüften BMW-Repositories zeigt, wie NBT diese Felder live vergleicht, welcher Wert Resume-P oder Cache invalidiert oder wie Eviction funktioniert | [?] | Korpusgrenze des Audits; USB-Serial, `identifier`, Mount-/Basepath und Zeitfelder sind nur Kandidaten für Q3/Q4 |
| F14 | Ein BR67/JPG-Artefakt beweist weder ID3-APIC-Verarbeitung noch den Cover-Cache der HU | [D] Grenze | Die Repositories enthalten keinen APIC-/Live-USB-Nachweis; M1–M3 bleiben ausschließlich Feldbefunde |

---

## 4. Metadaten: ID3 und Cover

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| M1 | ID3v2-Tag am Dateianfang wird gelesen, Cover (APIC, JPEG) wird angezeigt | [B] | 01.10. Heimabend, 02.10. 60-s-Test: „Cover + kurze Sekunden Ton“ |
| M2 | Cover-Format, das funktioniert | [B] | JPEG 320×320, ≤ 8 KiB (`assets/usb-msc-covers`), sticky ID3 `id3Len=3044`/`3496` |
| M3 | Cover wird auch angezeigt, wenn danach nur Stille folgt | [S] | 02.10./03.10.: Cover ohne Ton in mehreren Fällen |
| M4 | Offline-BMW-Backups kennen einen separaten JPG-Typ (BR67); Zusammenhang zu APIC oder zum live angezeigten Cover | [D] Typ / [?] Zusammenhang | Foreign-Desk-Audit; nicht als Erklärung für Radio BOB aufwerten |
| M5 | Browse-Liste zeigt **8.3-Namen aus dem Directory**, Player zeigt **ID3-Titel aus dem Dateikopf** | **[B]** | Media-Leiter 22.10. `id3_cover` (`EVID-HUPROBE-2026-10-22-008`); bisher nur Fließtext. Folge: Menütexte im Browse über Dateinamen, Player-Text über ID3 |

---

## 5. Leseverhalten beim Abspielen (Kern)

### 5.1 Fakten

| # | Fakt | Status | Rechnung / Beleg |
|---|------|--------|------------------|
| R1 | Leserate ≈ USB-Full-Speed-Grenze | [B] | `mscTrace`: 4096 B alle 4 ms ≈ 1 MB/s; netto 665–816 KB/s (Runde 08:10), 774 KB/s (Replug 08:05) |
| R2 | Gewählte Datei wird bis EOF gelesen (oder bis zur Abwahl) | [B] | PiDrive: 86.016 + 438.272 = **524.288** (07:58); 163.840 + 360.448 = **524.288** (08:12:35); `fav0` 8 MiB: `bytes=8.421.376` (`status-pre-rst-0755`). **hu-probe Demo (Abend 18.10.):** Offline PASS = genau ein Track-Atom 158 208 B / 309 LBA (`175203` T3, `212136` T1, `212635` T3) — Eager-EOF auf zweitem Medium **[B]** |
| R3 | Bei Abwahl während des Reads bricht die HU ab | [S] | st-55: `fav0 maxSeq=5.971.968` von 8.388.608 nach Senderwechsel |
| R4 | Nächste Datei wird komplett vorgelesen | [B] | st-52 → st-55: `fav1` fertig, dann `fav2` +128 Reads = 524.288 B, während `fav1` spielt |
| R5 | Nach dem Vorlesen keine Reads während der Wiedergabe | [B] | `readCount=1539` konstant von 07:58:31 bis 07:59:34; B7-A (03.10.): ≥ 150 s keine Reads |
| R6 | Track-Ende = Datei-Ende, dann automatischer Wechsel | [B] | 512 KiB bei 48 kbit/s: (524.288 − 3.044) / 5.973 B/s = **87,3 s**; Wechsel nach **93,2 s** (`switch fav1 → fav2 (age=93.2s)`) |
| R7 | Pause zwischen Tracks | [S] | 93,2 − 87,3 ≈ **6 s** |
| R8 | Body-Reads können **vor** dem Head-Read kommen (Prefetch) | [B] | 08:04:00 `cold_body_burst … ev=not_from_head`, Head-Read erst 08:04:01 |
| R9 | Cache-Treffer erzeugt keine Reads (Muster B) | [B] | 08:00 BOB, 08:04 Bayern, 08:06 BOB: `hostAbs=0`, Datei vorher `bytes=524288` |
| R10 | Beim Scan nach Plug/RST wird groß vorgelesen | [B] | post-RST nach 5–14 s: `fav0` 3,8–5,6 MiB gelesen |
| R11 | Erneute Auswahl einer gecachten Datei spielt denselben Inhalt nochmal | [B] | 01.10.: „erneute Wahl = dieselben ~6 s“ |
| R12 | Ab wann die HU abspielt (sofort vs. nach Read-Ende) | **[S] inkrementell** / Formalgo offen | F1-Abend Stick: gesprochene Marker ab **0** sofort hörbar bei 5-MB- und 100-MB-Datei ([`F1-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md)). Formales Go: Video-Timing t(Tap→erster Marker) + 100-MB-Gegenprobe gegen Batch-then-Play |
| R13 | Überlebt der **Body-/Datei-Cache** einen ESP-RST (gleiche Serial)? | **[B] Body neu** · **[S] Position oft ja** | s1-morgen 07.10.: in **6/6** RSTs Datei im ersten Poll vollständig frisch gelesen (`maxSeq` = Größe) — Body-Cache weg. **hu-probe 23.10.:** ESP-RST bei T3/`cache_a_pin` → Operator **Resume bei T3** (Navigator bleibt). Trennung: Cache-Inhalt ≠ Playlist-Position (R37–R40). [`KORREKTUR-F2C`](../betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/KORREKTUR-F2C-RST-ARTEFAKT.md) · [`detach-browse`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) |
| R14 | LED-Blinken korreliert mit Cold-Body-/MSC-Aktivität | [S] | s1-1700: erster Autoplay (Bayern) ohne Blink; BOB/Rock cold mit Blink; frühere Läufe `cold_body_burst`. **Nicht** alleiniger Cache-Orakelzustand — operativ: Blink ≈ Body-Read/MSC-Aktivität |
| R15 | Lesetakt: **4,0 ms pro 4 KiB** (≈ 250 Reads/s, 1,02 MB/s) = Bulk-Grenze USB Full-Speed (~1,2 KB/ms + CBW/CSW). Mit ESP-Play-Erkennung **5,1 ms** (≈ 195/s, 0,80 MB/s) | [B] Takt-Messgröße / **[B] Ursache** ESP-Play; Scheduler-Pace nur [H] | Feld s1-morgen: 250/s ohne Play, 195/s nach `playingUid=fav0`. **Lab C2:** Idle sg p50 **4,0 ms** → Armed **5,0 ms**; Ursache = **ESP Live-/Play-Pfad** ([`C1-C7-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-lab/C1-C7-ERGEBNIS.md)). **hu-probe S0/S2 (Audit 15.10.):** File-Gap-p50 **~3739 µs** (S0 0.2.17) / **~3783 µs** (S2 0.2.23) ≈ FS-Bulk (`EVID-HUPROBE-2026-10-15-001`/`003`/`008`) — **Messgröße FACT**, als HU-Scheduler-Pace weiter `INFERRED`. Frühere 0.2.2/0.2.11-Gaps (3724 / 3586–3738 µs) konsistent. Eager-EOF/Prefetch auf Demo **nicht** revalidiert (`010`) |
| R16 | Lesen **außer der Reihe** bei Wiederaufnahme an Position P: vorwärts 8, rückwärts 120, rückwärts 120, vorwärts 360, rückwärts 360, vorwärts 968 KiB (Summe **1.982.464 B**), dann **5,1 s Pause**, dann sequenziell ab P + 1336 KiB bis EOF (6.057.984 B) | **[B]** Summen und Reihenfolge | `msc.reads` p1-run-a ms 364034–365907 und p1-run-b ms 171378–173250: beide exakt 1.982.464 B ab LBA 1953 (P = Dateioffset 958.464), danach Lauf ab LBA 4625 (= P + 1336 KiB). **Read-Ebene (p1-run-a):** LBA 1953–1961 (F8), 1713–1945 (B120), 1473–1705 (B120), 1969–2681 (F360), 753–1465 (B360), 2689–4617 (F968). Jedes Rückwärtssegment endet direkt unter dem bisher niedrigsten Block, innerhalb eines Segments wird aufsteigend gelesen. m3seq 03.10. Ep. 7 ab LBA 1953 größer (4.407.296 B) |
| R17 | Frische Auswahl **ohne gespeicherte Position P**: erster sequenzieller Lauf **368.640 B** (360 KiB) ab Kopf, danach 2–3 s Fragmente, dann Lauf bis EOF | [B] ohne P | s1-morgen 5/5 (`slotMap.fav0.maxSeq`); Endlauf 5.201.920 B in 3/4 angetippten Fällen. **Präzisierung 07.10. Abend:** gilt nur, wenn keine persistierte P vorliegt — sonst R16/Resume (R23, Q8 s2) |
| R23 | Wiedergabeposition **P** persistiert in der HU über Medienwechsel; Fortsetzung ≠ Offset 0 | **[S]** (+ s3/s4) | **F1-Abend:** Stick↔ESP, Weiterzählen. **S3:** P überlebt Remount mit neuer USB-Serial und gekoppeltem Root-Label. **S4/K3:** zusätzlich geänderter Dateiname bei unverändertem Pfad, Größe und Startcluster brach P ebenfalls nicht. FAT-BPB-Volume-ID und BPB-Label blieben in beiden Fällen aus dem Demo-Image konstant. Widerlegt ist daher nur die konkrete Kombination Serial+Root-Label+Name, nicht „vollständige Medium-Identity“. **Präzisierung:** P ist nur die *Abspielposition*; gelesen wird nach Remount trotzdem ab 0 (R24). [`Analyse 13.10.`](../betrieb/artifacts-2026-10-13-analyse/ANALYSE-D-RESUME-IDENTITY-2026-10-13.md) |
| R24 | Nach OTG-Remount (ohne ESP-Reboot) liest die HU den **aktuellen Titel komplett sequentiell ab Offset 0** (512 KiB, 128 × 4 KiB in 0,6–0,85 s) und spielt danach aus dem Cache an P weiter. **Abspielposition ≠ Lesereihenfolge.** Ein UI-Tap dagegen liest ab Umgebung von P (s3: 240 K) | **[B]** | Feld s3: 7 BOB-Replugs, LBA 17489→18512 lückenlos (`trace.jsonl`), `readCount` danach konstant. Passt zu R20 (Wiederanlauf liest Titel komplett). [`ANALYSE-S3-TONFENSTER`](../betrieb/artifacts-2026-10-08-feld/ANALYSE-S3-TONFENSTER-2026-10-08.md) |
| R25 | Hörbares Tonfenster nach Remount = **Ringinhalt** zum Read-Zeitpunkt: 48 KiB (`kCapacity`) ≈ **8,2 s @48k**, dahinter Stille. Gehört 5–6 s (Rest: Formatwechsel-Flush/Anlauf, R7 Stufenplan, offen) | **[B]** Bytes / [S] Hördauer | s3: `underruns Δ` 471 640 / 470 616 / 471 567 je Read → Live ≈ 49–50 KB; Ton nur, wenn Producer vor dem Replug ≥ 8 s lief (deshalb nur zuletzt getappter Sender BOB). Messung Hördauer mit Marker: s4. Mengenbilanz: R27. **Präzisierung:** Live = Ring **plus Zuwachs bis zum Überholen** (~75 ms, ≤ 450 B). Bytes ↔ 8,2 s passt; das Gehör (5–6 s) passt **nicht** — die Bilanz erklärt die Hördauer nicht |
| R27 | Bytebilanz eines Replug-Reads: **Host-Bytes = ID3 + (Ring + Zuwachs bis Überholen) + Stille**; Identität `hostAbs_nach − undΔ = absEnd` beim Überholen. Nach dem Überholen erzeugte Bytes erreicht die HU **nicht** (Cursor läuft durch Stille weiter) | **[B]** | s3 07:57:26: 1 511 044 − 471 640 = 1 039 404 = `absEnd`; Live 49,2–49,6 KB, ID3 3,1–3,5 KB (`id3Len` in s3 nicht geloggt, ab s4 im Poll). Lab-Nachbau: `nbt_hu_sim.py --golden REPLUG`. [`ANALYSE-S3-TONFENSTER`](../betrieb/artifacts-2026-10-08-feld/ANALYSE-S3-TONFENSTER-2026-10-08.md) M2, [`ANALYSE-STREAM-WEG`](../betrieb/artifacts-2026-10-08-feld/ANALYSE-STREAM-WEG-2026-10-08.md) |
| R28 | Cover (und Live-Ton) nach Replug kommen **nur** aus dem Sticky-ID3/Ring des **einen** aktiven Stream-Slots; alle anderen Slots = `Mp3Silence` mit Minimal-ID3 ohne APIC. Bild nach Replug braucht: (1) Stream genau dieses Slots läuft mit ID3, (2) **kein ESP-Reboot** beim Plug, (3) HU spielt genau diesen Slot. **Nicht senderspezifisch** | **[B]** ESP-Mechanismus / [S] Autoplay-Wahl der HU | s3: nur BOB erfüllte alle drei; Bayern (2,5 min / 69 s Stream) und Rock (39 s) scheiterten an zwei Plug-Reboots (07:47:00, 07:54:43), einem Replug außerhalb des Stream-Fensters und einem abgelehnten Play-Detect (07:55:20). Früher (28.09., 02.10.) Bayern/Rock mit Bild + Kurzton. [`ANALYSE-S3-TONFENSTER`](../betrieb/artifacts-2026-10-08-feld/ANALYSE-S3-TONFENSTER-2026-10-08.md) „Warum Bild nur bei BOB“; Gegenprobe s4 S3/S9. Offen: Q11, Q12 |
| R29 | E7-C: BUSY-Pacing funktioniert am NBT | **[B]** | Feld s6: Stall-off mehrfach ~6 s; Stall-on ~65 s Musik+ID3 bis EOF; nach Exit Stall-off wieder ~6 s. Ring blieb 48 KiB. Telemetrie Long-Audio `cmds=2272/retries=120730`, Session-Ende `2399/147865` — Snapshots nicht mischen. Evidence `EVID-BMWHU-2026-10-12-001`–`004` |
| R30 | S7-B armt BUSY erst nach echtem Head-Play | **[B] Lab**, Feld offen | 0.4.49: vor Arm Mid-File p50≈5,5 ms, `skipNotArmed`↑ und Retries flat; nach Head-`play.guess` `stallArmed=true`, p50≈1021 ms. `lab/play` allein armt nicht. [`lab-s7-stream-before-guess`](../betrieb/artifacts-2026-10-12-lab/lab-s7-stream-before-guess/ERGEBNIS.md) |
| R31 | D0 512 KiB bleibt auf 0.4.49 unter BUSY regressionsfrei | **[B] Lab** | p50≈734 ms/4 KiB, `undDelta=0`, ~86,9 s live, 524.288 B vollständig. D1–D3 bleiben offen. [`lab-d0-regression`](../betrieb/artifacts-2026-10-12-lab/lab-d0-regression/ERGEBNIS.md) |
| R32 | S6 las `fav0` 8 MiB nahezu vollständig, während ein anderer Slot live war | **[B] Reads/Device-Inhalt**, Ursache Ohr [H] | Session-Ende: 8.294.400 B = **98,88 %**, 2025/2048 4-KiB-Callbacks, `fromHead=2`, `midFile=2023`; Long-Audio-Trace bei Dateioffset 3.588.096…3.977.216 B, während `streamSlot=fav1`. Code liefert non-live Stationsslots als `Mp3Silence`. Starke Inferenz: späteres stummes Rock-Autoplay kam aus vorab gecachter Stille. Resume-P ist **nicht** als alleinige Ursache bewiesen. `EVID-BMWHU-2026-10-12-007`. [`Analyse 13.10.`](../betrieb/artifacts-2026-10-13-analyse/ANALYSE-D-RESUME-IDENTITY-2026-10-13.md) |
| R33 | Decoderposition P, physischer MSC-Read-Offset und Cache-Inhalt sind getrennt | **[B] Trennung**, Kausalität je Episode offen | R24: Replug liest ab 0, während die HU an P weiterspielt. `fromHead`/`midFile` klassifiziert nur gegen `headLbaSlop`; ein erster Body-Offset beweist keinen P-Reset. Kein Read bei Auswahl ist cache-hit-like und für Device-Head-Force unsichtbar. |
| R34 | Sichtbare Identity-Rotation hat P bisher nicht zuverlässig gebrochen | **[B] Serial/Label/Vol** · [?] Rest | **hu-probe 23.10. Identity (FW 0.3.19):** Label allein, Vol-ID allein und **Serial+Label+Vol** (`ident_b`) — kurzer USB-Cycle → Operator-Resume + Wire: **kein** Datei-Head-Scan, Resume-Atom am fortgesetzten Track (T1/T2/T3). Serial/Label/Vol (einzeln+kombiniert) als Resume-Key **REJECTED**. Frühere S3/S4: Serial+Root-Label+Name ebenfalls kein P-Breaker. Offen: C6–C8 (VID/PID/INQUIRY/Kapazität), Content/Size/Pfad (C1–C5). [`identity-multireview`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/MSC-IDENTITY-REMOUNT.md) |
| R35 | Unter aktivem Body-Stall: Menü/Enumeration ~**20 s** träge | **[B]** Phänomen / [?] Mechanismus | Feld s6: Menü/Dateien ~20 s; UI „eingefroren“, Stationswechsel zickig. Code-Check: Stall greift nur bei aktivem `streamSlot_`-Body — FAT/DIR/Boot nicht gebremst. Ursache der Menülatenz weiter `INFERRED`/`UNKNOWN` (`EVID-BMWHU-2026-10-12-006`, Gate HU-A8). [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md), [`UEBERGABE-S6`](../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md) |
| R36 | Türöffnen kann zusätzlichen Cold-Body-/Re-Read auslösen | **[S]** Effekt / [H] Kausalität | `EVID-USBMSC-2026-10-04-003` MEASURED; Kausalität noch INFERRED. Nicht mit OTG-Replug (R24) verwechseln |
| R37 | Soft-Remount (MSC NOT READY / `media_hide`) ist für die HU praktisch **wirkungslos** als Reset | **[B]** Operator | hu-probe 23.10.: Soft-Remount während Playback → keine Re-Enum-/Fresh-/Resume-Reaktion am Ohr; echter USB-Cycle (D+ Soft-Detach) nötig. Soft-Remount ≠ Soft-Cycle. [`identity`](../../../hu-probe/docs/feld/2026-10-23-gesamtbericht-identity-remount.md) |
| R38 | Kurzer USB-Cycle → echter FS-/FAT-/Root-Re-Enum **ohne** Datei-Head-Scan (wenn Zustand bekannt) | **[B]** Wire | Identity-Sessions 074455 / 074749 / 074908: nach Cycle FS-Enum, **keine** 32+128+6-Datei-Scans, Wiedereinstieg als Vollatom am Resume-Track. [`wire-074319/455`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-074319-074455.md) |
| R39 | Fresh-Datei-Scan (bekanntes kleines SynthFat ~158 KiB) = **32 + 128 + 6** Blöcke je Datei, head-first | **[B]** Wire · Gültigkeit ~158 KiB | 074319: je T1/T2/T3 Head 32, Struktur 128, **EOF-Probe 6** (= 3072 B am Dateiende, vermutlich ID3v1/Endframe). Früheres „32+128=160“ bleibt Head+Struktur; +6 ist kanonischer Fresh-Abschluss. **Gültigkeitsbereich:** bisher nur ~158‑KiB-Dateien (B69) — Größenleiter offen. |
| R40 | Maschineller Fresh-Diskriminator (M18): flächendeckender Head+EOF-Probe-Scan **nur** bei Fresh; nach Cycle **nie** | **[B]** Wire | 074319: EOF-**6** je ~158 KiB-Datei; folders_30 Fresh: EOF-**2** je ~120 KiB-Datei (Probe-Länge größenabhängig). Nach Cycle weder 074455 noch folders_30: kein Bibliotheks-Scan. |
| R41 | Cycle/Resume-Wiedereinstieg oft **tail70 → head240** (Vollatom) am Resume-Track; Folgetracks `240+70` | **[B]** Wire n=3 | 074455/074749/074908. `tail_then_head` = Resume/Restore-Korrelat, nicht „nach jedem Mount“ (Erst-Mounts bleiben head-first). |
| R42 | Soft-Detach-Dauer ≤ 30 s erzwingt **kein** Fresh (alles Resume) | **[S]** Operator | holdMs 200/1000/3000/10000/30000 → Resume an fortgesetzter Position. Wire der Detach-Stufen nachgeliefert unter `artifacts/20261023-detach-browse/` (B70). [`detach-browse`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) |
| R43 | ESP-RST und physisches OTG (~30 s bzw. **~99 s** + Zündung aus/ein) → Resume, kein Fresh | **[S]** Operator · **STRONG** gesamt | Navigator/Playlist-Position überlebt; die drei Mechanismen (Detach/RST/OTG) sind **nicht** vollständig unabhängig isoliert (RST enthält Detach, OTG enthält Zündung). Obergrenze getestet: ~99 s. |
| R44 | „Fresh = Zeit-Timeout seit Disconnect“ | **REJECTED** (≤ 99 s) | Soft-Detach ≤30 s + RST + OTG~99 s erlauben Resume. Echter Fresh-Trigger **UNKNOWN** (Kandidaten: HU-Kaltstart, Media-TTL ≫99 s, voller Schlaf-/Zündungszyklus). |
| R45 | Drei HU-Schichten: Navigator/Playlist ≠ Browse-/Titel-Cache ≠ Audio-Body | **[B]** Wire folders_30 + Identity | **folders_30 Wire:** vor Cycle Browse = Body-Rest `160/72`; nach Cycle FS-Enum + Dir-Reads, erster Datei-Atom = Resume-Track (ALBUM3/T08 `0/234`), weitere Browse-Titel wieder Vollatom — Cache flush, Position bleibt. Identity: Cycle ohne Fresh-`32+128+EOF`. Alte Lesart „Remount → Cache weg → Resume weg“ **falsch**. [`detach-browse` §4.3](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) |
| R46 | Remount ≠ Cold Start | **[S]** Heimfahrt `#23` (korr. 11.11.) | `#23` Remount @442–447 s → Resume **ROCK/R04** (Kopf 0–3840 ∥ 10760→EOF, R55), nicht Medium-Datei 1. **Korrektur 11.11.:** Der „2. Mount `#22` @~595,7 s mit 395xxx-LBA-Probe“ existiert im Trip **nicht** — Unmount/Mount/395xxx-Reads tragen `origin=post_finalize` (Upload-Phase, LBAs jenseits des Medium-Endes 393 699); die Offline-Checkpoints laufen dort lückenlos durch (I9). Passt zu R38/R43 (Cycle/OTG → Resume). [`heimfahrt`](../../../hu-probe/docs/feld/MSC-HEIMFAHRT.md) |
| R47 | Drei Read-Modi: Head/Selection · Eager Body · Neighbor/Interleave | **[B]** Heimfahrt | **A** Head: Einstieg oft `0/240` (+ `240/240`, `480/32`). **B** Eager Body: **100 %** File-Coverage (Nachrechnung 11.11., R53; die 93–99 % waren Episoden ohne Kopf-Atom), Bulk **240**, ~1 MiB/s (`#23` C01–C04, R01/R02). **C** Scheduler-Interleave: mehrere LBA-Regionen/Dateien verzahnt (R04-Sprünge; CHARTS H01↔H05). |
| R48 | Globaler Elevator **SUPERSEDED** | **[B]** Korrektur | Media-Leiter `tail_then_head` = lokales Nearest-LBA (**STRONG**, bleibt). Heimfahrt: kein global strikt aufwärts — **LBA-Scheduler** priorisiert Regionen und wechselt. |
| R49 | Prefetch-Lead kontextabhängig | **[S]** (präz. 11.11.) · Konstante 15 s **REJECTED** | **Natürlicher Autoplay-Wechsel:** Kopf-Vorlauf des Folgetitels **7,2–8 s vor Ende**, n=6 (`#22` M01→M02 7,7 s, M02→M03 7,2 s, P01→P02 7,8 s; 22.10. B032→B128 ~7,4 s, B128→B320 ~8 s, D010→D026 ~7,3 s) — R54. Abweichend: 158-KiB-Demo 20.10. Read erst beim Wechsel (~0 s), 11.11. 9,9-s-Tracks ~1,9 s. **Korrektur 11.11.:** Die „140–237 s Vorlauf“ in `#23` sind formal (Dauer − Abstand); dort liest die HU eine Kette von Folgetiteln Rücken an Rücken (R57) — kein Vorlauf vor dem Ende eines laufenden Titels. ~7–8 s ist der Normalfall, aber keine universelle Konstante |
| R50 | Eager Body ≠ Play Intent | **[S]** STRONG / Audible offen | `#23`: C01–C04 fast vollständig hintereinander, Atom-Abstände teils **~4 ms**, ohne Audible-Beweis. Großer Read beweist keine Decode-/Hör-Session → GATE-01 bleibt P0. |
| R51 | ~~Kurzer BUSY ohne Host-Reset~~ | **REJECTED** (Artefakt, 11.11.) | Der „16-Block-READ10 @453,365 s, 1,623 s gehalten, abandoned“ in `#23` ist ein Fehler in `analyze_session.py` (`first_data_us` ordnete DATA je `bot_tag` sessionweit zu; Tags starten nach Remount neu → Tag 129 aus Mount 2 bekam die DATA-Zeit aus Mount 1, „Haltezeit“ = Leerlauf bis zum nächsten TUR). Stream-Prüfung: **kein** CBW→CSW > 0,3 s in `#22`–`#24`. Tool korrigiert (I10). BUSY-Toleranz bleibt allein über E7/R29 (S6) belegt; `EVID-HUPROBE-2026-10-22H-009` im Audit zurückziehen |
| R52 | 4‑KiB-Takt / Bulk 240 / TUR auf großer Fahrt | **[B]** Heimfahrt verstärkt | `#23` File-Gap p50 **3,896 ms** (n≈10 k); READ10 Bulk **240**; Idle TUR **2,2388 s** — konsistent mit E3/E11/R15, jetzt auch unter `drive_home`/`drive_mix`. |
| R53 | Ein Titel, der zu spielen beginnt, wird **vollständig** (100 %) mit Bus-Geschwindigkeit gelesen — bis 7,2 MB ohne Obergrenze | **[B]** Heimfahrt nachgerechnet | 24 Instanzen in `#22`/`#23`/`#24` (Instrument-gültig, §9.1), z. B. J02 5,60 MB in 5,36 s, E02 6,23 MB in 6,75 s, R04 6,80 MB (26 Fragmente) in 7,66 s, H01 7,20 MB (14 065 Blöcke) 96 % im ersten Burst / 100 % nach 10,9 s, C01–C04 3,8–4,5 MB in 3,6–4,3 s. Durchsatz **0,9–1,05 MB/s** (4 KiB je 3,9 ms; 240er-CBW ≈ 116,5 ms). Audio-Vorlauf nach 4–8 s = ganze Titeldauer (150–420 s). Kein Plateau bis 7,2 MB; ≥ 8 MiB ungemessen (Q16). Abbruch nur durch Weiterschalten (CHARTS-Browse `#22`, R3). Widerlegt Matrix A15 (512-Block-Fenster) für reale Dateien |
| R54 | Natürlicher Autoplay-Wechsel = **Kopf-Vorlauf** des Folgetitels ~7–8 s vor Ende, **Rest beim Wechsel** in einem Zug | **[S]** n=6 | Kopfmenge `#22` (Medium bekannt, kein Scan): **Block 0–1536 = 768 KiB** (M02, M03, P02, E03, H05); 22.10. live nach Fresh-Scan: **Block 160–2848 = 1,31 MiB** (B320, K01, K02, J01). Dateien kleiner als die Kopfmenge werden ganz im Vorlauf gelesen (B128, D026). Rest: kurze Region um Block 3216–3872 oder verschränkt 1536→3840 ∥ 3840→, dann sequenziell bis EOF. Beispiel M02 (`#22`): Kopf @254,7 s, Rest @261,8–267,5 s = Ende M01 (Start 62,4 s + 200 s). Ursache der zwei Kopfmengen [?] |
| R55 | **Resume nach Mount:** Kopf **Block 0–3840 (1,875 MiB)** verschränkt mit **Resume-Position → EOF**; der Mittelteil folgt erst beim späteren Abspielen | **[B]** n=3 | `#22` J01: 0–3840 ∥ 12864–14991. `#23` R04 Mount 1: 0–3840 ∥ 7464–13284, Mitte 3840–7464 erst @402 s. `#23` R04 Mount 2: 0–3840 ∥ 10760–13284, Mitte 3840–10760 @528 s. Block 3840 ist auch die Grenze der Verschränkung beim Wechsel (R54). Präzisiert E14/R41 für große Dateien (R41 galt für ~158 KiB) |
| R56 | Body-Cache hält Daten **minutenlang**, auch über weitere Reads | **[S]** | `#23` R04: 6,6 MB @1–6 s gelesen, @402 s nur der fehlende Mittelteil nachgeholt → Rest ≥ 400 s im Cache. `#22` M01: komplett @60–66 s; beim Ordner-Loop M03→M01 @721,6 s nur Block 2304–6936 erneut gelesen, obwohl dazwischen M02+M03 = 10,5 MB gelesen wurden → Kopf/Ende von M01 (~2 MB) ≥ 655 s gehalten, Mitte verdrängt. Eviction-Regel [?] (Q4c) |
| R57 | **Ketten-Prefetch:** mehrere Folgetitel Rücken an Rücken vollständig | **[S]** | `#23` nach Remount: R01, R02, C01, C02, C03, C04, R03 + R04-Rest = **≈31 MB in 70 s**; Abstand Atom-Ende → nächster Titel **~4 ms** (C02→C03, C03→C04, R03→R04) — maschinell, kein Tastendruck. `#22` PODCAST: E01–E03 = 16,6 MB in 21 s. Danach in `#23` **21 min keine Reads** bis `max_duration` (Wiedergabe aus Cache oder Quellwechsel — Operator-Log fehlt, [?]). Reihenfolge `#23` R04→R01→R02→CLASSIC/C01…C04→R03→R04 kreuzt in den Unterordner. Wann Kette, wann nur Kopf-Vorlauf (R54; MIX `#22`): Q19 |
| R58 | Fresh-Scan je Datei = **160 Blöcke (80 KiB) Kopf + EOF-Probe**, **größenunabhängig** | **[S]** | 22.10. live: D010 59 KB … D180 1,1 MB, B128/B320 0,96/2,4 MB, COVER1–3, drive_mix 3,6–11 MB je 160 Blöcke (drive_mix-Werte aus `081410` teils durch Instrumentverlust gekürzt, I11). „Fresh-Scan skaliert mit der Größe“ **REJECTED**. Dateien ≤ 160 Blöcke liegen nach dem Scan vollständig im Cache. Ergänzt R39/A12 über ~158 KiB hinaus |
| R59 | Bitraten **32–320 kbit/s** (CBR und VBR) werden gelesen; Autoplay wechselt im Takt der Dateidauer | **[S]** Read/Timing · Ohr [?] | 22.10. `bitrate_mix` (B032/B128/B320 je 60 s): Wechsel bei ~60/120 s; `dur_mix` D010–D180; drive_mix VBR 96–320 kbit/s. Hörbarkeit nicht separat belegt (GATE-01). Hebt D3 und D5 (Read-Seite) |
| R60 | Autoplay **loopt im Ordner** | **[S]** n=1 | `#22` MIX: M01→M02→M03→**M01** (@721,6 s; Ende M03 = 481,7 + 240 s). Die Ordnerwechsel PODCAST/POP/ROCK in `#22` fielen mit Operator-„erster Song“-Wechseln zusammen (MSC-HEIMFAHRT). Prefetch kreuzt Unterordner (R57) — ob Autoplay das auch tut: Q19 |
| R26 | Replug-Lesemuster des aktuellen Titels: **1 Callback (Kopf, 4 KiB), ~19 ms Pause, 127 Callbacks im 5-ms-Takt**, gesamt **651–665 ms** (788–805 KB/s). 6-ms-Abstände unregelmäßig, kein 16er-Raster. Ohne laufenden Stream (nach ESP-Reboot) 3,75 ms je Callback, keine 19-ms-Pause | **[B]** Muster / [?] Ursache der 19 ms | s3 6/6 Replugs (`trace.jsonl`, `gap`); Taps 17–18 ms; Reboot-Plug 07:54:50 3 ms. Bestätigt R15 (Takt hängt am ESP-Zustand). Callback-Raster ≠ zwingend CBW-Größe (E11: oft 8 **oder** 240) |
| R18 | 51 Blöcke (208.896 B) von fav0 werden in der Rampe nach RST nie gelesen | [B] Zahl / [?] Ursache | s1-morgen: Summe 4× exakt **8.179.712** B; welche Blöcke → LBA-Trace (`msc.reads`) |
| R19 | Autoplay-Wechsel: Rampe pausiert nach ~4 MiB für 2–3 s, angetippte Auswahl nicht | [S] | s1-morgen Boot 0 (bei 4.194.304 B, 07:44:12–14), Boot 1 (3.985.408 B, 07:49:43–44) |
| R20 | Wiederanlauf nach RST: aktueller Titel in ≤ 3 s komplett neu gelesen (ein Lauf), dazu **8 verstreute 4-KiB-Reads** auf fav0 (`maxSeq` 4096); gesamt `rc=167` | [B] | s1-morgen 4/4 bei 512-KiB-Titel; bei Rock als aktuellem Titel startet direkt die Rampe (2/2) |
| R21 | Next-Track-Prefetch / Lead | **[B]** Struktur · Lead **VARIABLE** · 8/15 s **REJECTED** | PiDrive s1-morgen: teils ~15 s vor Wiedergabe-Ende (Ausreißer ~7 s) — nicht verallgemeinern. **Media-Leiter 22.10.:** Tail-Prefetch-Struktur (z. B. 160@off160) FACT; Lead ≈7,5–8 s nur VARIABLE ohne Audible. **Heimfahrt 22.10.:** MIX situativ ~7,2–7,7 s; ROCK/CLASSIC „140–240 s Vorlauf“ war formal (Kette, R57). **11.11.:** natürlicher Wechsel 7,2–8 s, n=6 (R54); „8 s als HU-Parameter“ weiter **REJECTED** (R49). Abend Hold-2→T3 weiter Prefetch-Kandidat ohne Marker (`GATE-01`). |
| R22 | Scan nach Plug: erster Lese-Burst ab LBA 0 ist **1.374.720 B** (3× identisch), danach ein Burst von 176.128 B auf einem Datei-Kopf | [B] | `msc.reads` p1-run-a/-b ms 217113–218891, m3seq Ep. 6 ms 148817; 176.128 B: p1 ab LBA 17377, m3seq Ep. 9 ab LBA 18161. Lab-Signatur für C7 |

### 5.2 Log-Beleg: Burst bei leerem Ring (07:58, Correlate-Watch)

```text
07:58:02.3 act=1 arm=1 base=0 end=0     host=294912 sB=294912 und=294912 live=0 ring=0
07:58:02.9 act=1 arm=1 base=0 end=0     host=438272 sB=438272 und=438272 live=0 ring=0
07:58:05.4 act=1 arm=1 base=0 end=4096  host=438272 ...   <- erstes Producer-Byte
07:58:10.6 act=1 arm=1 base=968 end=50120 host=438272 ... ring=49152 (voll)
07:59:29.3 act=1 arm=1 base=624457 end=673609 host=438272 ...   <- keine weiteren Reads
```

Quelle: `betrieb/artifacts-2026-10-06-feld/feld-av-0723/correlate-run-post-rst/correlate-watch.jsonl`

### 5.3 Log-Beleg: Play-Erkennung und Track-Wechsel (Bridge)

```text
07:58:01 [msc] play.reject seq_short uid=fav1 from=16465 +4096B age=64272ms
07:58:01 [trace] t=0ms play_uid=fav1
07:58:01 [trace] t=50ms audio.start fav fav1
07:58:02 [msc] play.reject cooldown uid=fav1 from=16465 +12288B
07:58:03 [msc] cold_body_burst s=1 lba=16481..16537 n=8 B=32768 ev=not_from_head
07:58:03 [audio_ack] {'op': 'start', 'uid': 'fav1', 'id3': True, 'warmup': 0}
07:59:35 [msc] play.reject seq_short uid=fav2 from=17489 +4096B
07:59:35 [audio] switch fav1 → fav2 (age=93.2s)        <- Track-Ende nach 87,3 s + ~6 s
```

Quelle: `bridge-0758-bayern.txt`, `bridge-0759-switch.txt`

### 5.4 Log-Beleg: Next-Track-Prefetch (st-55, `mscTrace`-Ausschnitt)

```text
ms=16230 gap=4 lba=17745 n=4096 kind=file tag="Radio BOB!"
ms=16234 gap=4 lba=17753 n=4096 kind=file tag="Radio BOB!"
ms=16238 gap=4 lba=17761 n=4096 kind=file tag="Radio BOB!"
...  (96 Einträge, durchgehend 3–5 ms, +8 LBA pro Read)
```

Zu diesem Zeitpunkt ist `playingUid=fav1` (Bayern). Quelle: `runde-0810/status/st-55.json`

---

## 6. Zusammenspiel mit dem ESP-Live-Pfad

### 6.1 Warum Muster A und B derselbe Mechanismus sind

```mermaid
sequenceDiagram
  participant HU
  participant ESP
  participant Pi as Pi_Producer
  HU->>ESP: Head-Read fav1 (Play-Erkennung)
  ESP->>Pi: play_uid
  Pi->>ESP: audio_start (Arm nach 50 ms bis 3 s)
  HU->>ESP: Rest der Datei, 4KiB-Bloecke ca. 1 MB/s
  Note over HU,ESP: Rest vor Arm gelesen = Muster B, nach Arm gelesen = Muster A
  ESP-->>HU: Ring leer, Stille, Cursor laeuft weiter
  Pi->>ESP: erstes Audio-Byte nach ca. 3,4 s
  Note over HU: HU spielt Cache, liest nicht mehr
```

| Muster | Bedingung | Beobachtung |
|--------|-----------|-------------|
| A | Arm, bevor die HU die Datei fertig gelesen hat | Rest der Datei läuft über den Live-Pfad, Ring leer → nur Underruns (`und = hostAbs`) |
| B | Datei vor dem Arm fertig gelesen (Scan, Body-Prefetch, Next-Track-Prefetch) | `hostAbs = 0`, `armed = false`, HU spielt Cache |

### 6.2 Zeitkonstanten

| Größe | Wert | Status | Beleg |
|-------|------|--------|-------|
| HU liest 512 KiB | ≈ 0,6 s | [B] | R1 |
| HU liest eine 7,2-MB-Datei | ≈ 9,6–10,9 s (8 MiB ≈ 10 s) | [B] / [S] | R53 (H01 `#22`); R1, R10 |
| Arm-Latenz `play_uid` → Stream aktiv | 50 ms (direkt) bis 2–3 s (bei Senderwechsel mit `audio_stop`) | [B] | `bridge-0758`, `bridge-0759-switch`, `bridge-0804` |
| Producer-Startlatenz | ≈ 3,4 s nach `audio_start` | [B] | Correlate 07:58 |
| Producer-Rate | ≈ 8,7 KB/s für ~60 s, dann 6,0 KB/s (48 kbit/s) | [B] | drei Läufe identisch |
| Golden Reference 01.10. | `live` = 49.152 B = eine Ringfüllung ≈ 8,2 s | [B] | `esp89-after-6s-loop-174626.json` |

### 6.3 Konsequenz

Mit Stille-bei-Miss sind pro Auswahl höchstens **Ringinhalt beim Arm + R_prod × 0,6 s ≈ 9 s** Ton möglich. Live-Betrieb verlangt, dass der ESP Reads **verzögert**, statt Stille zu liefern (siehe Analyse-Dokument, Abschnitt 5).

---

## 7. Abspielen und Decoder

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| D1 | Layer III CBR 48 kbit/s aus der Bridge wird dekodiert, hörbar. Die Bridge kodiert mono 22,05 kHz = **MPEG-2** (`pump_bridge.py`: `-ac 1 -ar 22050`) | [B] Ton / [S] Format | 01.10., 02.10. (Kurzton) |
| D2 | Stille-Frames (`kSil`, 156 B, 48 kbit/s / 44,1 kHz, LAME-Tag) werden ohne Fehler „gespielt“ | [B] | 07:58: ~87 s Stille aus dem Cache ohne Abbruch, danach regulärer Track-Wechsel |
| D3 | Spieldauer ergibt sich aus Dateigröße und Bitrate | [S] | R6; hu-probe 22.10. `bitrate_mix`/`dur_mix` und `#22` MIX: Wechsel ≈ Dateidauer (R54, R59) |
| D4 | Format-Wechsel in der Datei (Live MPEG-2 22,05 kHz mono ↔ `kSil` MPEG-1 44,1 kHz) bei jedem Underrun | [?] | nicht isoliert getestet (Stufenplan R7) |
| D5 | Andere Bitraten (32–320 kbit/s, VBR) | **[S]** Read/Autoplay · Ohr [?] | hu-probe 22.10. und Heimfahrt: gelesen und im Takt der Dateidauer gewechselt (R59); Hörbarkeit offen (GATE-01). PiDrive-Live weiter nur 48 kbit/s belegt |

---

## 8. Offene Fragen (Testkatalog)

| ID | Frage | Vorgeschlagener Test |
|----|-------|---------------------|
| Q1 | Welches Timeout-Modell begrenzt READ10/BUSY am NBT? | **Akzeptanz geklärt:** ~65 s bis EOF bei fortlaufenden Retries (R29). Offen ist Gesamtdauer je Kommando vs. Inaktivität ohne Daten. **CBW-Länge mitdenken (E11):** bei `blocks=240` (~122 KiB) ist die Datenphase eines Kommandos ≈30× so groß wie bei `blocks=8`; Timeout-Modelle „pro 4 KiB“ sind unvollständig. Nur bei Bedarf gezielt mit kontrollierten Retry-/Datenpausen messen. |
| Q2 | Spielt die HU während des Lesens oder erst nach Read-Ende? | **[S] während des Lesens** (F1-Abend, Marker ab 0). Formal offen: Video t(Tap→„null“) und 5-MB-vs-100-MB-Vergleich ([`F1-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md), Übergabe [`UEBERGABE-FELD-S2-ABEND-2026-10-07.md`](../betrieb/artifacts-2026-10-07-feld/UEBERGABE-FELD-S2-ABEND-2026-10-07.md)) |
| Q3 | Welche Identity-Komponente invalidiert P und/oder Cache? | **Dimension weitgehend geschlossen (23.10.):** USB-Serial, Root-Label, BPB Volume-ID — einzeln und kombiniert (`ident_b`) — **kein** Resume-Key (R34). Frühere S3/S4: Serial+Root-Label+Name ebenfalls kein P-Breaker. **Community [H] conflicted:** Sheet Label+Serial-Flush ≠ Feld. **Desk:** NBT-SQLite-Felder bleiben Kandidaten ohne Kausalnachweis. **Noch offen (niedrige Prio nach Größenleiter):** C6–C8 VID/PID/Product, INQUIRY, Kapazität; Content/Size/Pfad (C1–C5). **Nicht** weitere Serial/Label/Vol-Serien. Method: [`nbt-medium-identity-resume`](../../../technology-audit/methods/nbt-medium-identity-resume.md) |
| Q8 | Welche Blöcke liest die HU bei frischer Auswahl ab Kopf, in welcher Reihenfolge, wie weit voraus? | Feld s2: **5×** `r16_resume_like`, kein `head_like`. **Feld s3** `s3-20261008-074403`: ep3 **`r16_resume_like`** (`F8 B120 B120 F360…`); Ohr bestätigt Resume≠0 nach Remount. UI-Tap ≠ Offset 0 (R23). Artefakte s2 + [`s3 ERGEBNIS`](../betrieb/artifacts-2026-10-08-feld/feld-s3-prep/s3-20261008-074403/ERGEBNIS.md). **Entscheidend für Stall** (R10) |
| Q9 | Warum 5,1 statt 4,0 ms pro Read bei ESP-Play? | **Geklärt (Lab C2):** ESP Live-/Play-Pfad (+1 ms SG); Poll/Bridge nicht nötig. Siehe R15 |
| Q4 | Wie groß ist der HU-Cache / Read-Ahead? | **Aufteilen** — siehe Katalog [`EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md`](../betrieb/artifacts-2026-10-06-feld/EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md) |
| Q4a | Max. Eager-Read **einer** Datei? | **Teilantwort 11.11.:** ≥ 7,2 MB vollständig, keine Grenze sichtbar (R53). Offen ≥ 8 MiB: Einzeldatei 8/16/32 MiB, Medium bekannt vs. fresh |
| Q4b | Max. Bytes/Anzahl **mehrerer** gecachter Dateien? | N=1…64 × 512 KiB; Re-Select → Hit (keine Body-Reads) vs Miss. Hinweis 11.11.: Ketten-Prefetch ≈31 MB (R57) und Retention R56 — Kapazität weiter [?] |
| Q4c | Eviction-Strategie? | Sequenz dann frühe Datei erneut; optional Rückwärtslauf — FIFO/LRU/? Hinweis 11.11.: M01 Kopf/Ende gehalten, Mitte verdrängt (R56) |
| Q5 | In welcher Reihenfolge werden Tracks gewechselt / vorgelesen? | Mehrere Dateien mit eindeutigen Namen; Wechselfolge protokollieren (beobachtet: Bayern → BOB, zweimal) |
| Q6 | Wie reagiert die HU auf gültiges, kontinuierlich nachgeliefertes MP3? | ergibt sich aus dem ersten erfolgreichen Stall-Lauf |
| Q7 | Bekannte Prefill bis Offset X, dann Backpressure — wo stoppt/wartet die HU? | **nur nach Stall-Go**; Silence hinter X verbieten (sonst Cursor-Versatz). Marker-Blöcke zur Offset-Diagnose |
| Q10 | Wie viele Sektoren fordert die HU **je READ10-Kommando**? | **[B] CBW-seitig (Device-Stack), nicht „immer 4 KiB“:** hu-probe BMW S2 (FW 0.2.23 + Abend 0.2.30): READ10-`blocks` häufig **8** und **240**; Demo-EOF-Rest **69**; Atom = 240+69. Events/CBW ≈ 5,29 (`EVID-HUPROBE-2026-10-15-004`, E11). Event-/Callback-n=4096 bleibt Stack-Chunk (E5). Lab-Sim „Q10=4 KiB“ und PiDrive-`xfer` waren Callback-Ebene. **Offen:** Histogramm je Phase, Wire (GATE-01), T2-Atom offline. **Für Q1/Stall:** Busy hängt am offenen CBW — große Kommandos (240) mitdenken. Gate **HU-A10** teilweise belegt |
| Q11 | Warum startet der ESP bei manchen Plugs/Unplugs neu? (s3: 07:47:00 beim Plug, 07:54:43 beim Unplug; zerstört Stream + ID3, R28) | **Aufbau Feld:** ESP32-S3-DevKitC-1, UART-Buchse am Zigarettenanzünder-Netzteil, native USB-Buchse (OTG) an der HU; Pi ↔ ESP über TCP. Laut [Espressif-Schaltplan v1.1](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf) gehen beide Buchsen über je eine Schottky-Diode 1N5819 auf `VCC_5V` → LDO SGM2212 3,3 V; 10 µF nur auf der UART-Seite. Es speist die Quelle mit der höheren Spannung. **Hypothesen:** (1) Umschalt-Einbruch beim Abstecken (Last wechselt HU → Netzteil, zusammen mit WLAN-Spitze 300–500 mA → Brownout; passt zu 07:54:43), (2) Steck-Transient / Masse-Ausgleich zwischen Netzteil- und HU-Masse beim Anstecken (passt zu 07:47:00), (3) Gegenhypothese Software (Panic/Watchdog in Mount/Unmount-Pfad; in s3 kein Zustandsmuster). Häufigkeit: s3 2 von ~11 Steckvorgängen; Feld 30.09. „nach OTG oft ESP-Reboot … OTG-Strom → Reset“ ([`FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) §11.3). **Test ohne FW:** D1 UART-Buchse an Laptop → ROM-Bootmeldung `rst:0xf (BROWN_OUT_RST)` = Strom, `rst:0x1 (POWERON)` = Spannungsverlust, `rst:0xc` + „Guru Meditation“ = Panic, `rst:0x7/0x8` = Watchdog; D2 Netzteil-A/B (Powerbank, kurzes dickes Kabel); D3 VBUS-Blocker HU ↔ ESP (keine Umschaltung); D4 USB-Messadapter Min/Max. Ablauf: [`FELDPROTOKOLL-S4`](../betrieb/artifacts-2026-10-08-feld/FELDPROTOKOLL-S4-TONFENSTER.md) „Reboot-Diagnose“. **FW-Go:** `lastResetReason` + `resetCount` in `/api/status` ([`STALL-BUILD-SPEC`](../archiv/planung/STALL-BUILD-SPEC-2026-10-08.md) §3) |
| Q12 | Warum lehnte Play-Detect den Bayern-Tap 07:55:20 ab (43 Reads, `rej` +43, `guess` 0)? | Lab: Tap-Muster ab Resume-P (R16) ~40 s nach ESP-Reboot nachstellen (`nbt_hu_sim.py --golden GW`), `playMinSeqBytes` / Kopf-Regel prüfen; Feld: `playingUid` nach jedem Tap notieren (s4) |
| Q13 | Ist das stumme `fav0` in s6 primär vorab gecachte non-live Stille, Mid-File-Play ohne Arm oder beides? | S6 im Lab nachstellen: `fav1` live, `fav0` vollständig non-live vorlesen, danach `fav0` wählen. Auswahl klassifizieren: **kein Read** = cache-hit-like; **Mid-Read** = station-intent Mid-Play nötig; **Head-Read** = Play-Detect/S7-Gate korrigieren. Startgate **HU-A1** / Intent **HU-A4** — Method [`nbt-cache-eviction-play-intent`](../../../technology-audit/methods/nbt-cache-eviction-play-intent.md) |
| Q14 | Was bricht Resume-P / erzwingt Fresh? | **Identity Serial/Label/Vol:** REJECTED (Q3/R34). **Zeit seit Disconnect ≤99 s / Soft-Detach / ESP-RST / OTG+Zündung:** kein Fresh (R42–R44). **Offen:** echter Fresh-Trigger (Kaltstart, TTL≫99 s, Schlafzyklus); Resume-Key Content vs. Deskriptor (C1–C8 Rest). Auswertung künftig über M18 (EOF-6 ja/nein, R40). Gate **HU-A2** nur noch für C6–C8 / Content — **nicht** Serial/Label/Vol wiederholen. |
| Q16 | Verhalten bei Dateien ≫ 158 KiB (Größenleiter)? | **Für 2–7,2 MB beantwortet (11.11., Nachrechnung Heimfahrt):** ganze Datei mit Bus-Speed (R53), Kopf-Vorlauf 7–8 s (R54), Resume 0–3840 ∥ P→EOF (R55), Fresh-Scan 160 Blöcke (R58), kein 512-Block-Fenster. **Offen:** ≥ 8 MiB (S6: 8 MiB Rock oft stumm, R32) und Verhalten unter BUSY-Pacing über die ganze Datei (Q1). **Feldläufe ungültig:** 27.10. nur `post_finalize`-Hide-Poll (I7/I9, E19); 11.11. (0.3.38) Replay-Deadlock `replay_records=0` (I8, Fix 0.3.39 ungetestet), Schritte 3–8 nie gelaufen. Nächster Lauf nur 8/16 MiB mit hörbaren Markern, nicht die ganze Leiter. [`FELD-2026-11-11`](../../../hu-probe/docs/feld/FELD-2026-11-11-MSC-GROESSENLEITER.md) |
| Q17 | Browse-Cache-Flush vs. Navigator nach Cycle am Wire? | **[B] beantwortet (R45):** folders_30 `165220` — nach Cycle Dir-Re-Read + Vollatome der browsed Tracks, erster Atom = Resume-Titel; kein Fresh-Bibliotheks-Scan. Artefakt: `hu-probe/.../20261023-detach-browse/20261023-165220_bmw_free`. |
| Q18 | ~~Semantik der Remount-Positionsprobe (395xxx-LBA)?~~ | **Geschlossen 11.11. — Artefakt.** Die 395xxx-Reads sind `post_finalize`-Events in `12777_bmw_drive_home` (Upload-Phase, LBAs jenseits des drive_mix-Endes 393 699); im Trip gibt es an dieser Stelle keinen Mount (I9, R46) |
| Q19 | Wann liest die HU eine **Kette** von Folgetiteln (R57) statt nur den Kopf-Vorlauf (R54)? Wie weit reicht sie, kreuzt Autoplay Ordner? | Für PiDrive kritisch: Nachbarn eines Live- oder Steuer-Slots werden ggf. vollständig gelesen. Test: Medium mit markierten Nachbarn; Ordnerwechsel per Menü vs. Autoplay; hu-probe ≥ 0.3.40 mit Operator-Log (Tastendrücke/Quelle) |
| Q15 | Was erklärt die ~20 s Menüphase unter Stall? | Phänomen R35; Gate **HU-A8**. Code schließt FAT/DIR-BUSY aus — Ursache weiter offen |

Audit-Gates (**HU-A1…A11** in [`pidrive-2026-bmw-hu/README`](../../../technology-audit/audits/pidrive-2026-bmw-hu/README.md)): Reihenfolge A1 → A4 → A2 → …; **A10** (READ10-Größe) durch hu-probe S2 teilweise belegt (E11/Q10) — Histogramm je Phase + Wire offen; A7 bedarfsgetrieben; A5 (AV) zuletzt. Exit #6 Feld-Ohr (Sender/Menü) bleibt getrennt vom Busy-Pacing-Tonfenster. **Track-Atom / Eager-EOF:** Abend-Offline 18.10. **[B]** (E11/R2). **Heimfahrt:** Remount/Eager/Neighbor **[B]/[S]** (R46–R52), nachgerechnet 11.11. → R53–R60, R51 REJECTED. Offene P0: **Audible/Play-Intent (GATE-01)**, **Q1 BUSY über eine ganze Datei**, **Q16 ≥ 8 MiB**; Q18 geschlossen (Artefakt).

---

## 9. Instrument-Hinweise (nicht HU-Verhalten)

Diese Punkte beschreiben die **Messkette**, nicht die NBT:

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| I1 | Unter anhaltenden Host-Reads kann ESP-WiFi in ~3–5 s sterben; MSC bleibt nutzbar; Auto-Recovery ~30–100 s (hu-probe ≥0.2.11) | **[B]** Device | [`wifi-death-0.2.11`](../../../hu-probe/docs/feld/2026-10-14-wifi-death-0.2.11.md) — Telemetrie-Lücken nicht als HU-Abort lesen |
| I2 | BOT-CBW/CSW aus TinyUSB-Tap = Device-Stack, **nicht** Wire; GATE-01 Wire weiter offen | **[D]/[?]** | hu-probe `GATES.md`; E11/Q10 sind Stack-CBW-Claims. Analyzer Class-Hook (E18) = zweite Device-Ebene, ebenfalls nicht PHY-Wire |
| I3 | `read.gap_us` aus MSC-Callback belastbar; Event-`t_us`-Monotonie war in 0.2.11 teils gebrochen (BOT-Drain vs. Capture-Stamp) | **[B]** Instrument | [`review-abend-triage`](../../../hu-probe/docs/feld/2026-10-14-review-abend-triage.md); Pace über `gap_us`; Heimfahrt/Offline nur `capture_t_us` |
| I4 | MODE_SENSE6→`ep_stall` vor FW **0.2.18** = Instrument-Artefakt, **nicht** HU-Recovery | **[B]** Instrument / Claim HU-Recovery **REJECTED** | Offline-P0: 70/84 Stalls same-`t_us` wie ms6; nach Pad S2 `ep_stall=0`, ms6/cap=2,0 bleibt (`EVID-HUPROBE-2026-10-15-005`/`006`) |
| I5 | Burst „immer 39“ File-Reads | Profil-Konstante **REJECTED**; Demo-Atom-Erklärung **[B]** | Gap-Split p50=39, Histogramm auch 62–78 (`EVID-HUPROBE-2026-10-15-009`). **Abend 18.10.:** 39 = 30+9 Callbacks des Atoms 240+69 |
| I6 | usb-analyzer `bmw-hu-stimulus` × pidrive: Host↔DUT byte-exact | **[B]** Lab Instrument | Lab 02.11.: Stimulus-Reads = DUT-`bytesRead` (z. B. 31× / 109 056 B). Entschärft „blind vs. HU schweigt“ für L1/SCSI. **Not claimed:** echte NBT. [`Cross-Check`](../archiv/betrieb/2026-11-02-esp-usb-analyzer-crosscheck.md) |
| I7 | Capture-Upload / Persistenz kann Messkampagnen killen | **[B]** Instrument | Größenleiter 27.10.: Live-Reads während Play, Collector nur Hide-Poll → Q16 ohne HU-Daten. Soft-Cycle heilt Magenta/`NEED_RESET` ab hu-probe **0.3.21** (Device-Fix) |
| I8 | Replay-Deadlock (hu-probe 0.3.21–0.3.38): RAM-/Stored-Replay im Live-Pfad liefert `replay_records=0` | **[B]** Instrument | 11.11. Ladder `…_1r1`/`…_2r1` (7 Events, nur Meta); Lab `20261022-065150_lab_debian_free` (`replay_records=0`, B50) vermutlich derselbe Bug. Fix 0.3.39 (`pumpTcpWhilePending`) **nicht** feldverifiziert. Heimfahrt-Stored-Replay (0.3.17) **nicht** betroffen: `replay_records = offline_records` (26 097 / 13 627 / 1 742) |
| I9 | `post_finalize`-Events (nach Capture-Ende, live) landen in derselben Session-Datei | **[B]** Instrument | `#22`: 1045 Events (314 CBW, LBAs bis 395 263 > Medium) → falscher „2. Mount @595,7 s“ und Q18. 27.10. Ladder: **alle** 1822 Events `post_finalize` (Hide-Poll, E19). 20.10. free: 48–52 Events. `analyze_session.py` trennt sie für Read-Episoden, nicht für die Mount-Signatur-Liste. Auswertungen immer nach `origin` filtern |
| I10 | `analyze_session.py` `read_stalls`: DATA-Zuordnung über `bot_tag` sessionweit → Phantom-Haltezeiten nach Remount | **[B]** Tool · korrigiert 11.11. | Einziger Treffer `#23` → R51 REJECTED. Fix: erster DATA desselben Tags **nach** dem CBW (`data_times_us`/`first_data_after`); `#23` danach `held=[]` |
| I11 | MscBotTap-Ringverlust live (0.3.17 `tcp_live`) | **[B]** Instrument | `20261022-081410_bmw_free` (drive_mix live): `bot_pending_overflow` 146→684→1137 = **~990 verlorene BOT-Records**, 29 unvollständige READ10, J01 mit Löchern im 112/128-Block-Raster. Coverage/Scan-Größen dieser Session nicht verwenden. Die übrigen 22.10.-Leiter-Sessions hielten den Zähler konstant bei 146 (Altlast vor Session) → gültig. 11.11. free: 0→19, alle READ10 vollständig → gültig |
| I12 | Profil `lab_debian` startet MSC **soft-detached** (WiFi first) | **[B]** Ops-Falle | 10.11.: nach RST/Mode-Switch HU „kein Gerät“, `msc_soft_attached=false`; `POST /api/usb/cycle` nötig. Im Auto Profil `bmw` verwenden. [`FELD-2026-11-10`](../../../hu-probe/docs/feld/FELD-2026-11-10-I303A-REVAL-MSC.md) |
| I13 | Sichtgrenze TinyUSB/DWC2 | **[B]** Architektur · 0.3.40 ungetestet | Der Device-Stack sieht SETUP, Bus-Reset/Suspend/Resume/SOF und Xfer-Ergebnisse — **nicht** NAK, Tokens, CRC oder Wire-Timing (GATE-01-Wire bleibt Analyzer-Sache). hu-probe 0.3.40 ergänzt einen `dcd_event_handler`-Wrap (`usb_core`: Reset/Suspend/SETUP nach Typ, GET_DESCRIPTOR inkl. MS-OS 0xEE; EP-Stall/ClearHalt als `usb_epoch`) und meldet BOT-Ringverlust auch offline (`bot_ovf`, `bot_pending_overflow`); weder kompiliert noch feldgetestet. 0.3.17-Offline meldete Ringverlust nicht — `#22`–`#24` sind per Stream-Prüfung trotzdem verlustfrei (§9.1) |

### 9.1 Instrument-Gültigkeit der hu-probe-BMW-Sessions (Nachrechnung 11.11.)

Geprüft wurden CBW/CSW-Paarung in Stream-Reihenfolge, DATA-Summe je READ10 gegen `blocks × 512`, lückenlose `capture_seq`, monotone Zeit, Verlauf von `bot_pending_overflow` und `origin`.

| Sessions | FW / Transport | Ergebnis | Verwendbar für |
|---|---|---|---|
| `#22` `12777_bmw_drive_home`, `#23` `20261022-171751`, `#24` `20261022-173030` | 0.3.17 Stored-Replay | 895 / 509 / 78 READ10 vollständig, 0 unpaarig, `capture_seq` lückenlos, `replay = offline` | alles, nach Entfernen von `post_finalize` (I9) |
| 22.10. `080353`, `080544`, `080752`, `081152`, `61434` | 0.3.17 live | alle READ10 vollständig, Overflow konstant | Scan, Prefetch, Bitrate, Dauer |
| 22.10. `081410` (drive_mix live) | 0.3.17 live | ~990 BOT-Records verloren (I11) | nur Reihenfolge, keine Coverage |
| 20.10. free ×3 | 0.2.40 offline | vollständig | 158-KiB-Demo |
| 14./15./19.10. S0/S2 | 0.2.x | alle READ10 vollständig | bestehende E-/R-Zeilen bleiben |
| 11.11. `072308` free | 0.3.38 live | 19 Ring-Overflows, READ10 vollständig | Ops |
| 27.10. Ladder, 11.11. Ladder ×2, 22.10. Lab `065150` | 0.3.21 / 0.3.38 / 0.3.17 | **ungültig** (I7, I8) | nur Ops und E19 |

---

## 10. Connected / AOA — Control Plane (Abgrenzung und Desk-[D], nicht MSC-Wire)

**Einordnung:** Control Plane ≠ Storage Plane. Narrative: [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md) §§3/5. Desk-Stack: [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md).

**Feld an dieser HU (MSC/Analyzer):** E18/F15 — `303a:1001`+MSC → P-MOUNT; AOA-Counter 0; kein Media-UI ohne FAT.  
**hu-probe Direct-`18D1:2D00`:** Zubehör-UI + Reconnect-Loop; 51/52/53 und Bulk auf Callback-Schicht absent — siehe hu-probe Feld 2026-10-30 (nicht hier als MSC-[B] führen). AOA-Identity ≠ BCL ≠ Etch ≠ SAS ≠ RHMI/AV (C-D2/C-D9).

**Feld-Identitäten an dieser HU** ([`C1-STAND`](../../../hu-probe/docs/feld/C1-STAND.md), [`I303A 07.11.`](../../../hu-probe/docs/feld/I303A-FELD-2026-11-07.md), [`10.11.`](../../../hu-probe/docs/feld/FELD-2026-11-10-I303A-REVAL-MSC.md)):

| # | Identität | Status | HU-Reaktion |
|---|-----------|--------|-------------|
| C-F1 | `04E8:6860` phone-like, Vendor-Klasse | **[B]** Operator | „USB-Gerät wird nicht unterstützt“ |
| C-F2 | `303A:1001` Vendor-only (I-303A) | **[B]** Operator 07./10.11. | kein Gerätename, „kein USB-Gerät gefunden / nicht unterstützt“; an beiden USB-Buchsen gleich (kein Versorgungsartefakt) |
| C-F3 | `18D1:2D00` AOA-Accessory direkt | **[B]** Operator 30.10. | Zubehör-UI + Reconnect-Loop; 51/52/53 und Bulk auf Callback-Schicht absent |
| C-F4 | `303A:1001` + MSC + FAT-Medien | **[B]** | Medium sichtbar (E18/F15), Name aus iProduct (F16) |

Desk-Stack (BimmerGestalt / AAIdrive) — Kurzindex:

| # | Fakt | Status | Grenze |
|---|------|--------|--------|
| C-D1 | Lifecycle: Connected baut USB/BT + **BCL knock/handshake**, dann `ACTION_CAR_ACCESSORY_ATTACHED` → App TCP localhost → Etch → SAS | **[D]** | nicht am F20-Wire gemessen |
| C-D2 | Direct-ESP AOA-Identity ≠ Connected-Peer (kein BCL/Etch/SAS) | **[D]** Rolle / Feld-Reconnect nur **[H]** | H-Reconnect = INFERENCE |
| C-D3 | SAS: `sas_certificate` → Challenge 16 B → `sas_login(512)`; Android: Challenge XOR MD5(LE 2) dann RSA-MD5 | **[D]** | Analysis Authentication |
| C-D4 | P7B: `APP_AUTH` (Signatur) + `APP` (Permissions/`SAS.Digests.*`); HU `verifyResource` | **[D]** | Auth ≠ Authorization |
| C-D5 | Connected ≤5.1 exportierte `.SECURITY_SERVICE`; **≥5.1 / MyBMW nicht** | **[D]** | moderne Signierung **[?]** |
| C-D6 | „MyBMW liefert signChallenge via exportiertem Binder“ als aktueller Default | **REJECTED** | historisch Classic ok |
| C-D7 | RHMI-Layouts an Cert-SHA256 gebunden; freie XML **REJECTED** | **[D]** | |
| C-D8 | AM-Icon/Placeholder ≠ volle RHMI-Init | **[D]** | |
| C-D9 | Gates **G1…G4** (hu-probe `a68ef3b`); RHMI/CDS/AV = Nutzung **nach** G4, keine Gate-ID G5. hu-probe misst G1 (+teilweise G2 AOA); BCL/Etch/SAS/RHMI außerhalb | **[D]** Mapping | I-303A = nur G1 |
| C-D10 | **Zwei Phone-Pfade:** AAIdrive = Etch-Client; CarAPI → Connected führt `sas_*` stellvertretend (ContentProvider-Cert) | **[D]** | Audit PR #34 / EVID-SAS-026–028 |
| C-D11 | Connected-Apps-Pfad Cleartext („Nothing is encrypted“) — SAS/Etch in BCL DATA ohne TLS | **[D]** Doc | FX-G3-01; hilft nicht bei absent Bulk |
| C-D12 | AIDL `createSecurityContext`/`loadAppCert` ≠ Mermaid `initSecurityContext`/`loadApplicationCert`; AAIdrive `MainService` gated auf Security connected | **[D]** | EVID-SAS-029/030 |
| C-Q1 | F20: 6NR / Apps-Checkbox aktiv? | **[?]** | ohne das Pfad C tot |
| C-Q2 | **P1** FIELD-CONNECTED-REAL-01 / **P2** FX-G3-01: Phone∥Analyzer∥HU; `sas_*` korreliert | **[?]** geplant | [Plan](../../../hu-probe/docs/feld/FIELD-CONNECTED-REAL-01.md); nach I-303A (G1) |

**REJECTED (MSC↔Connected):** „AOA erkannt / Bulk ⇒ Connected-App offen.“ · „ESP-AOA = Phone-Connected-Rolle.“ · „Jede Connected-App ist direkter Etch-Client.“

### 10.1 Connected-App-Quellenmatrix (Desk-[D], BimmerGestalt)

Audit: [`bimmergestalt-idrive-2026-foreign`](../../../technology-audit/audits/bimmergestalt-idrive-2026-foreign/) · Inventar [`INVENTORY`](../../../technology-audit/projects/bimmergestalt-idrive-refs/INVENTORY.md) · RFCOMM-Delta [`bmw-bcl-rfcomm-role-2026-desk`](../../../technology-audit/audits/bmw-bcl-rfcomm-role-2026-desk/) · Secondary [`supra-idrive6-android-auto-2026-secondary`](../../../technology-audit/audits/supra-idrive6-android-auto-2026-secondary/) (`technology-audit@4f70751`, upstream pin `ac9a292`). Pins Stand Org-Audit 2026-10-28 (+ RFCOMM 2026-11-12 / Secondary 2026-11-13).

| Quelle | Pin | Prio | Was sie für uns löst | Was sie **nicht** löst |
|--------|-----|------|----------------------|------------------------|
| **BclCarLink** | `7cfd959` | P0 | BT-RFCOMM-Client, BCL Framing/Handshake/MUX, Watchdog, A2DP-Discovery-Hint | echte HU-SDP; USB/ENET-Wire |
| **BMWConnectedAnalysis** | `9e96ac6` | P0 | Architektur USB\|BT → BCL → ATTACHED → Etch; Doc-Claim USB/ENET | Code-Beweis USB-BCL (Contradiction 020) |
| **wireshark_bmw_bcl** | `07b7982` | P0 | Dissector-Namen (cmd/dest/AppTypes A4A/…) | OEM-Spec |
| **IDriveConnectKit** | `95492b0` | P0 | `BMWRemoting.etch`, Etch-URI, RHMI-Deser | Transport |
| **IDriveConnectKitAndroid** | `4a567bc` | P0 | ATTACHED-Intent, SecurityAccess-Lifecycle | RFCOMM öffnen |
| **AAIdrive** | `3e93419` | P0 | echte Etch-Client-Nutzung SAS→RHMI/AV/CDS | **öffnet kein RFCOMM** — wartet auf Tunnel+Security |
| **IDriveConnectAddons** | `270032d` | P1↑ | **2. unabhängige** SAS→RHMI/CDS-Implementierung im selben Kit-Stack | Transport |
| **Simulator / Simulator-kt** | `6a38086` / `6984020` | P1 | Fake-HU **Etch :4006** + SAS-Stub (Evidence 016) | SDP/RFCOMM/BCL-Wire |
| HassGestalt / IDriveExperiments | `63da6a4` / `4b6d5fa` | P1/P2 | RHMI-Muster | Transport |
| ReadYou / breezy-weather | meta | — | irrelevant für Protokollkern | — |

```text
Transport opener (RFCOMM/AOA)     Etch/SAS/RHMI consumers
─────────────────────────────     ───────────────────────
Connected / MyBMW  ──┐            AAIdrive
BclCarLink         ──┼── BCL ──►  IDriveConnectAddons
(Doc: USB Acc)     ──┘            CarAPI (SAS via Connected)
                                      ▲
                                      │ localhost TCP after ATTACHED
```

**Rollen-[D] (C-D13…):** Wer den physischen Kanal aufmacht ≠ wer Etch spricht.

### 10.2 BCL / BT-RFCOMM Desk-Fakten (Pins)

Sheet [`bmw-bcl`](../../../technology-audit/technologies/bmw-bcl/SHEET.md) · Handshake [`bmw-bcl-handshake`](../../../technology-audit/projects/bimmergestalt-idrive-refs/applications/bmw-bcl-handshake.md) · RFCOMM [`bmw-bcl-rfcomm`](../../../technology-audit/projects/bimmergestalt-idrive-refs/applications/bmw-bcl-rfcomm.md).

| # | Fakt | Status | Pin / Grenze |
|---|------|--------|--------------|
| C-D13 | BCL-Header 8 B BE: `cmd/src/dest/dataLen` + Payload | **[D]** | EVID-BG-001; kein F20-Wire |
| C-D14 | Dest **0x0FA4**=Etch, **0x1389**/5001=Watchdog | **[D]** | EVID-BG-002/007; EVID-BCLRF-004 |
| C-D15 | Session: Init **4 B** `12 34 56 78` → HU-HANDSHAKE(version, instanceId, bufferSize) → bei version>3 SELECTPROTO(3)+KNOCK → MUX | **[D]** | EVID-BG-003–006; Init = `decodeHex("12345678")` = 4 B, nicht ASCII-8 |
| C-D16 | Watchdog: Client sendet alle **5 s** Request `13 37 13 37` auf dest **5001**; **20 s** ohne Antwortaktivität → Shutdown | **[D]** | EVID-BCLRF-004 / `WatchdogProtocol.kt`@7cfd959. **Pong-Bytes der HU = UNKNOWN** — Listener zählt jedes empfangene Byte (`write(Int)`), validiert **nicht** `13371337` |
| C-D17 | Phone-App öffnet RFCOMM als **Client** auf SPP UUID `00001101-…` (`createRfcommSocketToServiceRecord`) | **[D]** | EVID-BCLRF-001/002; gilt für **BclCarLink**, nicht automatisch für MyBMW/F20. Channel aus SDP-Lookup, **nicht** hardcoded |
| C-D18 | HU = SDP-Provider / RFCOMM-**Server** (BclCarLink-Ableitung) | **[D]** INFERENCE | EVID-BCLRF-003. **F20 SABM-Initiator = UNKNOWN** bis B2-A **und** B2-B. Spannung zu Secondary „HU öffnet Apps-Link“ **nicht glätten**. Getrennt: SDP-Endpoint ≠ SABM-Initiator ≠ BCL-Initiator ≠ Etch-Consumer |
| C-D19 | A2DP-Connected ist nur **Discovery-/Eligibility-Hint** in BclCarLink (`hasBCL` via SPP); Transport bleibt RFCOMM | **[D]** | EVID-BCLRF-005; A2DP≠BCL **REJECTED** |
| C-D20 | Doc nennt USB/ENET als BCL-Träger; BclCarLink-Code nur BT-RFCOMM | **Contradiction / HYPOTHESIS** | EVID-BG-020/026 — **kein** REJECTED; Auto+AOA können auflösen |
| C-D21 | AAIdrive/Addons starten Etch erst nach Tunnel (**ATTACHED**) + Security connected | **[D]** | EVID-BG-011/027; EVID-SAS-030 |
| C-D22 | Simulator-kt = Etch-Server :4006 + SAS-Stub + RHMI/teilweise CDS — **kein** BT/RFCOMM/BCL; Layer E / B0.8 only, nicht Ersatz für B1/B2 oder Dummy-HU | **[D]** | EVID-BG-016; bt-analyzer `SIMULATOR_KT_AND_ANALYZER_SCOPE_20261113.md`; Simulator-Login ≠ Crypto-FACT |
| C-D23 | Dissector kennt AppTypes A4A/TouchCommand/Carplay/AndroidAuto | **[D]** | EVID-BG-019; Capture-Filter-Hinweis, kein F20-FACT |
| C-D24 | **OPEN dest 5001** nach ACTIVE = Bootstrap (Watchdog zuerst); **OPEN dest 4004** erst wenn lokaler Consumer TCP `:4007` verbindet | **[D]** | `BclMultiplexer.openProtocols` / `EtchProxyService`@7cfd959. Fehlen von OPEN 4004 ohne AAIdrive/Consumer ≠ Fail |
| C-D25 | `ACTION_CAR_ACCESSORY_ATTACHED` kommt **nach** lokalem Proxy listen (BCL ACTIVE → :4007 → Intent → Etch-Consumer) | **[D]** | `EtchProxyService.announceProxy` |
| C-D26 | BCL `ACTIVE` = Handshake (+ ggf. SelectProto/Knock) ok — **nicht** Watchdog/Etch/SAS/RHMI | **[D]** | `BclClientTransport.connect` State-Machine |
| C-D27 | BclCarLink `BclOutputStream`@7cfd959: (1) `write(Int)` → `ByteArray(b)` = Array der **Länge** b, nicht 1 Byte; (2) `write(buf,off,len)` → `sliceArray(off until len)` statt `off until off+len` | **[D]** Code-Defect | Fremdcode; Bootstrap oft mit Full-Arrays → meist OK. Risiko für Etch-Proxy / Partial Writes (B0.7/B0.8). **Kein Patch in unseren Repos** — Upstream; nicht als Gold-Wire werten |
| C-D28 | Welche Phone-Komponente am F20 den RFCOMM-Link öffnet (MyBMW vs. andere) | **[?]** | BclCarLink = experimenteller Owner (FACT-Client); offizielle App = Doc-INFERENCE bis Wire |
| C-D29 | HANDSHAKE liefert Fingerprints `version` / `instanceId` / `bufferSize`; Code: version>3 → SELECTPROTO(3)+KNOCK; Kommentar „version 4 has an unknown watchdog behavior“ | **[D]** | `BclClientTransport`@7cfd959 — B3-Gate: Branch an **version** prüfen |
| C-D30 | F20 RFCOMM-Initiator und BCL-Wire (Kanal X, SABM/UA, first UIH, HANDSHAKE, …) | **[?]** | A6 ACL **MEASURED**; alles darüber UNKNOWN. Negatives Phone-Connect (B2-A) ≠ negativer BCL-Befund |

### 10.2b Secondary Evidence — NBT-Evo-Familie (nicht F20-[B])

Quelle: [`supra-idrive6-android-auto-2026-secondary`](../../../technology-audit/audits/supra-idrive6-android-auto-2026-secondary/) · `EVID-SUPRA-2026-11-13-*` · Pin upstream `Sq00ky/…@ac9a292`.

```text
SECONDARY EVIDENCE · NBT-EVO FAMILY · F20-RELEVANZ: plausibel, nicht bewiesen
```

| # | Claim | Status | Grenze |
|---|-------|--------|--------|
| C-S1 | HU-Seite nutzt SPP; `/dev/btspp0` ist relevanter Serial-Endpunkt | Secondary FACT | EVID-SUPRA-001/002 — kein F20-SDP/Kanal-X |
| C-S2 | BMW Apps / MyBMW / Connected können SPP-/BCL-Pfad belegen bzw. konkurrieren | Secondary FACT/INFERENCE | EVID-SUPRA-003/007 |
| C-S3 | MyBMW kann mit anderen SPP-Nutzern (z. B. nbt-aad) konkurrieren | Secondary FACT | EVID-SUPRA-003 |
| C-S4 | AAIdrive ist nicht zwingend BT-Transport-Owner; kann bestehenden BCL-/Etch-Tunnel als Consumer nutzen | Secondary + Desk | EVID-SUPRA-006/008 · C-D21 · Lab C-L4 |
| C-S5 | HU kann BMW-BCL-/Etch-Verkehr an Protokollmerkmalen erkennen (`looksLikeBmwBcl`, u. a. `12 34 56 78`) | Secondary FACT (Heuristik) | EVID-SUPRA-005 — Framing bleibt Desk CROSSREF |
| C-S6 | Richtungsunterscheidung Android-Auto- vs. BMW-Apps-Pfade; AA ≠ BclCarLink-BCL | Secondary | Native AA UUID getrennt; EVID-SUPRA UNKNOWN-Tabelle |
| C-S7 | „HU öffnet MyBMW-Link“ (nbt-aad) vs. Phone-Client (BclCarLink) | **Spannung** | beide Source-FACTS; F20-Initiator = C-D30 **UNKNOWN** |

**Pflege:** C-S* dürfen **nicht** still zu F20-[B] werden. Messbedingung B1/B2: MyBMW/AAIdrive während Baseline-SDP/RFCOMM deaktivieren (Contention-Kontrolle = Versuchsbedingung).

### 10.3 Eigenes Lab (bt-analyzer) — TEST, nicht HU-Wire

Upstream: [`esp32.bt-analyzer`](https://github.com/MPunktBPunkt/esp32.bt-analyzer) · Application [`esp32-bt-analyzer/bmw-bcl`](../../../technology-audit/projects/esp32-bt-analyzer/applications/bmw-bcl.md) · Runbook [`CAR_A6_B1`](../../../bt-analyzer/docs/CAR_A6_B1.md).

| # | Claim | Status | Evidence |
|---|-------|--------|----------|
| C-L1 | Synth BCL-Framer (HANDSHAKE/DATA/UNKNOWN + sticky PayloadTooLarge) | **[B]** Lab | `LAB_BCL_SYNTH_STREAM_*` |
| C-L2 | Synth-BCL-Bytes über RFCOMM + HCI-TCP | **[B]** Lab | `LAB_BCL_SYNTH_STREAM_20261112T060654Z` |
| C-L3 | Dummy-HU SDP: SPP `0x1101` / Name „BMW Connected“ / ch.**5** → `CANDIDATE_STRONG` | **[B]** Lab | `LAB_BCL_DUMMY_HU_SDP_*` — **ch.5 = Lab only**, nicht BMW-Erwartung |
| C-L4 | External Phone (OnePlus) + MyBMW + AAIdrive gegen Dummy-HU `.131`: A2DP+SPP-Gate erfüllt, **kein RFCOMM** | **[B]** Lab negativ | `LAB_BCL_DUMMY_HU_A2DP_20261112T172006Z` `NO_RFCOMM` |
| C-L5 | „AAIdrive/MyBMW öffnen BclCarLink-artigen SPP zum Dummy“ | **REJECTED** (für diese Apps/Setup) | folgt aus C-L4 + C-D17/C-D21: falscher Peer für RFCOMM |

**Lesart C-L4/C-L5:** kein Widerspruch zum Desk-Stack. Dummy bot SDP+A2DP korrekt an; **AAIdrive ist Etch-Client**, nicht RFCOMM-Opener. Ohne Connected/MyBMW-Tunnel **oder BclCarLink** als Link-Owner entsteht kein SABM — UI „kein Verbindungsversuch“ in AAIdrive ist erwartet.

### 10.4 Soll-/Ist für A6→B3 (Feld F20) und Maßnahmen

Erwartungstabelle = Desk-Soll; Ist = Auto-Messung. **Kein Channel-5-Annehmen. Kein Initiator voraussetzen.**

| Stufe | Soll (Desk-Pin) | Ist (Stand 2026-11-13) | Nächste Aktion |
|-------|-----------------|------------------------|----------------|
| **A6** | `.87`↔HU ACL / Pairing | **[B]** FIELD PASS | `FIELD_A6_HU_20261113T062824Z` (BMW 38304 / SPP UUID gesehen) |
| **B1 SDP** | RFCOMM-Data-Service; UUID/Name/Kanal **X**; Zustände A–D | **[?]** | `bcl_sdp_probe`; einzelnes NONE ≠ final |
| **B2-A** | Phone/ESP initiiert RFCOMM → HU | **[?]** | SABM von `.87`; negativ ≠ BCL absent |
| **B2-B** | HU initiiert → `.87` SPP-Server **observe-only** | **[?]** | kein BCL-TX vor Klassifikation; negativ ≠ kein BCL |
| **B3 BCL** | INIT → HANDSHAKE → **version**-Branch → OPEN **5001**; OPEN **4004** nur mit Consumer | **[?]** | erst nach B2 BCL-Klassifikation; C-D24/C-D29 |
| **E / B4** | Capture Y: ATTACHED → :4007 → OPEN 4004 → Etch | **[?]** | AAIdrive als Consumer, nicht Opener |
| Lab T/B | Dummy SDP/RFCOMM + BclCarLink Differential | Synth/Dummy PASS; AAI **NO_RFCOMM** | B0.7; **B2-B observe-only mode**; C-D27 |
| Lab E | Simulator :4006 | nicht gelaufen | B0.8 — stark für Layer E, nicht A6 |
| Secondary | HU-SPP / Contention / Owner | C-S1…C-S7 | bleibt Secondary — kein F20-[B] |

**Maßnahmen (priorisiert)** — kanonisch: [`bt-analyzer/docs/MASSNAHMEN_BCL_A6.md`](../../../bt-analyzer/docs/MASSNAHMEN_BCL_A6.md) · Methodik: [`BCL_RFCOMM_TWO_MODE_20261113.md`](../../../bt-analyzer/docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md):

1. **P0 Feld:** B1 **zustandsweise (A–D)** + **B2-A und B2-B** am F20 — Wire-Entscheidung für C-D18/C-D30/C-D20. B2-Control: MyBMW/AAIdrive OFF.
2. **P0 Epistemik:** Layer **T / B / E** trennen. BclCarLink = FACT-RFCOMM-Client (Desk); F20-Initiator = **UNKNOWN**. AAIdrive = Etch-Consumer. Secondary C-S* ≠ F20-[B]. `OPEN 4004` ≠ Bootstrap-Pflicht; Watchdog-Pong-Bytes = UNKNOWN. `12 34 56 78` allein = Kandidat.
3. **P1 Lab:** **B2-B observe-only** auf ProfileManager; **B0.7** BclCarLink↔Dummy (version 3+4); **B0.8** Simulator :4006; optional Phone-HCI-Snoop als Differential.
4. **P1 Capture:** X = Transport only; Y = + AAIdrive. Pflichtfelder: channel X, SABM-Richtung, DLCI, first UIH, `12 34 56 78`, HANDSHAKE **version**/instanceId/bufferSize, OPEN 5001; AppTypes nur Filter.
5. **P2:** Lab-Evidence nur LAB; Secondary nur C-S*; `field_evidence` erst nach B1+. BclCarLink OutputStream-Bugs nicht als Gold-Wire werten.
6. **Nicht tun:** AAIdrive-alone vs Dummy; Channel 5 als Soll; Initiator voraussetzen; B2-A-Negativ = „kein BCL“; BCL-TX in B2-B; USB/ENET-BCL REJECTED; MSC↔Connected vermischen; Relay vor klassifiziertem BCL; Secondary still zu [B].

---

## 11. Pflegeregel

- Neue Feldbefunde mit Datum, FW-Version, Geometrie (`kReadyDetail`) und Quelle eintragen.
- Status nur auf **[B]** heben, wenn Rohdaten (Status-JSON, Correlate-Watch, Bridge-Log, hu-probe Session, Analyzer-Evidence) verlinkt sind. Evidence-IDs aus technology-audit-Audits mitführen, wenn vorhanden.
- Zählerwerte aus verschiedenen Snapshots nicht mischen. `liveBytes = streamBytes − underruns` ist nach einem Senderwechsel ungültig, solange `streamBytesServed_` nicht in `startStream()` zurückgesetzt wird.
- `mscTrace.tag` kann abgeschnitten sein (z. B. `Rock Antenn`) und ist kein eindeutiger Slotschlüssel. Datei/Slot aus LBA-Bereich plus `slotMap` zuordnen.
- Community-/SIB-Muster, Lab-Debian-Gaps und Analyzer-Host-Stimulus nicht still zu NBT-[B] machen. Host-Scope: nur diese NBT Evo.
- Event-/Callback-Größe (`xfer`, `n=4096`) und READ10-CBW-`blocks` getrennt führen (E5 vs. E11). Prefetch-Lead/Cache aus PiDrive nicht automatisch als hu-probe-FACT lesen; Eager-EOF/Track-Atom seit Abend-Offline 18.10. **[B]**; Heimfahrt Remount/Eager seit 22.10. **[B]/[S]**. Offline-Timing nur über `capture_t_us`, nie `replay_t_us`.
- hu-probe-Sessions vor jeder Auswertung nach `origin` filtern (`post_finalize` ≠ Trip) und die BOT-Vollständigkeit per Stream-Prüfung belegen (§9.1), bevor Coverage- oder Timing-Claims [B] werden. Ringverlust-Zähler (`bot_pending_overflow`) als Verlauf lesen, nicht als Absolutwert.
- AOA/Connected-Apps: Feld nur Abgrenzung E18/F15; Desk-[D] in **§10** (inkl. 10.1–10.4) und [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md) — nie still als MSC-[B]. Lab-TEST (`C-L*`) ≠ F20-[B]. Secondary (`C-S*`) ≠ F20-[B].
- RFCOMM-Opener (Connected/BclCarLink) und Etch-Consumer (AAIdrive/Addons) getrennt claimen — nie „App geöffnet“ als BCL-Transport-Beweis.
- F20 RFCOMM-Initiator nicht aus Desk oder Secondary voraussetzen; B2-A und B2-B getrennt führen; negativer Phone-Connect ≠ negativer BCL-Befund.
- Narrative Modelltexte und GPT-/KI-Zusammenfassungen gehören nach [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md) (inkl. Korrekturabschnitt); neue Messclaims zuerst hier mit Artefakt-Link.
