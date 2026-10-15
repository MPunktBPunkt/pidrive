# HU Technical Facts — BMW NBT Evo als USB-Massenspeicher-Host

**Stand:** 2026-10-15 (hu-probe BMW S0/S2 Feld-Audit: READ10-CBW blocks, ms6/cap=2, Gap-Messgröße; Prefetch/Eager/Cache weiter INFERENCE; technology-audit 0.7.1 HU-A1…A11; Menü-~20 s / Tür-Re-Read; Community Label+Serial vs. Feld R23/R34) · **Fahrzeug:** BMW 118d F20 LCI (2017), NBT Evo · **Gerät:** ESP32-S3 `esp32.pidrive` / `hu-probe` (USB-MSC Full-Speed, virtuelles FAT)
**Zweck:** Sammlung dessen, was über das Verhalten der Head Unit (HU) am USB-Port **bekannt und belegt** ist. Jede Aussage trägt einen Belegstatus und eine Quelle. Neue Feldtests sollen hier nachgetragen werden.

**Scope:** Belegte Plattform = **diese** NBT Evo am MSC-Port. Keine gemessenen Fakten zu CAN, MOST, CarPlay, Android Auto oder HU-WLAN/Ethernet-APIs. Andere BMW-Generationen = kein stiller Transfer. Lab-AV ≠ Feld-Ohr.

| Status | Bedeutung |
|--------|-----------|
| **[B]** bewiesen | direkt in Rohdaten gemessen, mehrfach oder byte-genau nachgerechnet |
| **[S]** stark belegt | konsistent in mehreren Läufen, aber nicht unter allen Bedingungen geprüft |
| **[D]** Desk-Fakt | an gepinntem Fremdcode/-artefakt belegt; keine Messung an dieser HU |
| **[H]** Hypothese | plausibel, noch nicht gemessen |
| **[?]** offen | unbekannt, Test nötig |

Begleitdokumente: [`../betrieb/artifacts-2026-10-06-feld/ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md`](../betrieb/artifacts-2026-10-06-feld/ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md) · [`../betrieb/artifacts-2026-10-06-lab/KONZEPT-HU-SIM-NBT-2026-10-06.md`](../betrieb/artifacts-2026-10-06-lab/KONZEPT-HU-SIM-NBT-2026-10-06.md) · [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) · Audit: [`bmw-nbt-evo` Sheet](../../../technology-audit/technologies/bmw-nbt-evo/SHEET.md) · [`pidrive-2026-bmw-hu` Evidence](../../../technology-audit/audits/pidrive-2026-bmw-hu/evidence.md) · [`hu-probe-bmw-s0s2-field-2026`](../../../technology-audit/audits/hu-probe-bmw-s0s2-field-2026/) · Report [`2026-10-15-hu-probe-bmw-s0s2-field`](../../../technology-audit/docs/reports/2026-10-15-hu-probe-bmw-s0s2-field.md) · Application C [`bmw-nbt-evo.md`](../../../technology-audit/projects/pidrive/applications/bmw-nbt-evo.md) · Foreign-Desk: [`bmw-nbt-media-index`](../../../technology-audit/audits/bmw-nbt-media-index-2026-foreign/evidence.md) · [`usb-bot-observation`](../../../technology-audit/audits/usb-bot-observation-2026-foreign/evidence.md) · hu-probe: [`bmw-s0-0.2.11`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-0.2.11-auswertung.md) · [`bmw-s0-0.2.2`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-auswertung.md) · Pin `@5dbec43` · [`profile`](../../../hu-probe/profiles/bmw_nbt_evo.json) (P1c noch offen)

---

## 1. Gesamtbild in einem Satz

Die NBT-Evo-HU behandelt USB-Medien wie eine Festplatte mit fertigen Dateien: Sie liest eine gewählte Datei **so schnell der Bus erlaubt bis zum Ende**, liest die **nächste Datei rund 15 s vor Track-Ende vor** (R21), spielt **aus ihrem Cache** und fordert erst beim nächsten Track wieder Daten an.

```mermaid
flowchart LR
  Plug["USB Plug"] --> Enum["Enumeration: INQUIRY, CAPACITY, TUR"]
  Enum --> Scan["Scan: FAT, Dirs, Datei-Heads, Body-Prefetch"]
  Scan --> Wait["Leerlauf, TUR ca. 1/s"]
  Wait --> Sel["Nutzer waehlt Track"]
  Sel --> Cached{"Datei im Cache?"}
  Cached -->|ja| PlayCache["Wiedergabe aus Cache, keine Reads"]
  Cached -->|nein| Eager["Eager-Read 4KiB-Bloecke ca. 1 MB/s bis EOF"]
  Eager --> NextPf["Naechste Datei komplett vorlesen"]
  NextPf --> PlayCache
  PlayCache --> Eof["Cache-Ende = Track-Ende"]
  Eof -->|"ca. 6 s"| Sel
```

---

## 2. Enumeration und SCSI-Verhalten

| # | Fakt | Status | Wert / Beleg |
|---|------|--------|--------------|
| E1 | INQUIRY ca. 1 s nach Plug | [B] | `msToInquiry=997`, `msPlugToFirstRead=1004` (`status-0758-bayern-1.json`); identisch 01.10. (`msToInquiry` ≈ 1000) |
| E2 | Kommandomix | [B] | PiDrive: `inquiry=1`, `capacity=3`, `prevent=7`, `startStop=0`, `otherScsi=0`; Firmware-Fingerprint `hint=hu-like`. **hu-probe:** `tur` ≫ `read10`, dazu `prevent_allow`, `mode_sense6`, `read_capacity10`, `inquiry`. **MODE_SENSE6 / READ_CAPACITY = 2,0** (S2 Kern 60/30; auch vor Stall-Fix) = Host-Muster, kein Stall-Indiz (`EVID-HUPROBE-2026-10-15-005`). [`bmw-s0-0.2.11`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-0.2.11-auswertung.md), Audit S0/S2 |
| E3 | TEST UNIT READY periodisch | [S] | `tur=73` bei ~93 s Uptime → ca. 0,8/s; 01.10.: `tur=101` in ~160 s; Golden ≈ 1/s. hu-probe Session-TUR-Hz p50 ~2,06 (Fenster ≠ idle-Profil; `EVID-HUPROBE-2026-10-15-012`) |
| E4 | Keine Schreibzugriffe | [B] | `writeCount=0`, `writeReject=0` in allen Snapshots; Golden `writes_expected: false`; hu-probe S0/S2: keine Writes in ausgewerteten CBWs (`001`/`003`) |
| E5 | Transfergröße **Event-/Callback-Ebene** fast ausschließlich 4 KiB | [B] Event | `xfer: n512=3, n2k=0, n4k=1536, n8kPlus=0` (07:58); `n4k=2293` (st-55). hu-probe File-n=4096 dominant (S0/S2). **Callbacks ≠ CBW:** TinyUSB-Puffer 4096 B → `n8kPlus` bauartbedingt 0; ein READ(10) kann viele Re-Entries erzeugen. CDB-Größe = E11 / Q10. Ablesbar: `n512=3` → 512-B-Callbacks; größere Datenphasen werden in 4-KiB-Chunks zerlegt |
| E6 | Queue-Tiefe 1, ein Kommando nach dem anderen | **[B]** protokollbedingt | Bulk-Only Transport: CBW → Daten → CSW, erst danach das nächste CBW (kein Pipelining). `mscTrace`: Abstand 3–5 ms, keine überlappenden Kommandos. LBAs innerhalb eines Segments monoton, **zwischen Segmenten nicht** (R16). Folge fürs Bremsen: Während ein READ wartet, kommt **kein** TEST UNIT READY (E3). QD-max p50=1 hu-probe `INFERRED` (Wire `UNKNOWN`, `012`) |
| E7 | Toleranz gegenüber langsamen READ10 / BUSY | **[B] NBT** | Feld s6: Stall-on lieferte ungefähr **65 s Musik+ID3 bis EOF** eines 512-KiB-Slots; Stall-off fiel reproduzierbar auf etwa **6 s** Ringfenster zurück. NBT akzeptiert damit TinyUSB-BUSY-Retries über Minuten. Die Operator-Dauer ist nicht poll-genau; Gesamtdauer- vs. Inaktivitätslimit bleibt offen (Q1 / HU-A7) — bei `blocks=240` hängt ein Retry an ~122 KiB Datenphase, nicht an 4 KiB (E11). Annahme „kleiner Ring = harte Dauerstrom-Grenze“ **REJECTED** (`EVID-BMWHU-2026-10-12-005`). S7-B Lab: BUSY erst nach Head-`play.guess`; D0 auf 0.4.49 regressionsfrei. Evidence `EVID-BMWHU-2026-10-12-001`–`005`. [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md), [`S7-D-SPEC`](../planung/S7-D-LEITER-SPEC-2026-10-12.md) |
| E8 | Physisches OTG detach→attach | **[B]** hu-probe | BMW S0 0.2.2: Host detach→attach **2,294–6,011 s** (11 Paare, Soft-Cycle ausgenommen). Soft-Lab detach→attach ≈ **0,30 s** (nicht als NBT-Fakt lesen). [`bmw-s0`](../../../hu-probe/docs/feld/2026-10-14-bmw-s0-auswertung.md), [`data-quality`](../../../hu-probe/docs/feld/2026-10-14-data-quality-and-params.md) |
| E9 | Kurze Verweildauer → kein DATA / keine Reads | **[B]** Muster / [?] Ursache | BMW S0 0.2.2: Fenster ~3,8 s → BOOT+FAT+ROOT ohne DATA; mehrere Plugs ~4,7–7,5 s ohne Read-Events. Inference: Dwell-Zeit für DATA/Playback nötig. Eager-EOF/Prefetch auf 256/512‑KiB-Demo **nicht** revalidiert |
| E10 | Replug-Scan-Grundmuster (kleines Medium) | **[B]** 256 KiB-Demo | 6/8 nicht-leerer Fenster: **22 Reads / 65 536 B** = BOOT+FAT+ROOT+DATA. Fenster 7 dichter Mehrfach-Scan (Instrument-/Drain-Artefakt in 0.2.2). Nicht auf große PiDrive-Slots übertragen |
| E11 | READ10-**CBW**-Blockzahl oft **8** und **240** | **[B]** hu-probe S2 | Device-Stack CBW (nicht Wire): häufig `blocks=8` (=4096 B) und `blocks=240` (=122 880 B → typ. 30×4096 `read`-Events); Events/READ10 ≈ **5,29**. Event-n=4096 = Stack-Chunk **und/oder** CBW-Größe — nicht blind „HU immer 4 KiB“. `EVID-HUPROBE-2026-10-15-004`. Gate **HU-A10** teilweise belegt. Report [`2026-10-15-hu-probe-bmw-s0s2-field`](../../../technology-audit/docs/reports/2026-10-15-hu-probe-bmw-s0s2-field.md) |

---

## 3. Dateisystem und Medienliste

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| F1 | FAT12 und FAT16 werden gelesen; Dateien mit LFN-Namen werden in der Medienliste angezeigt | [B] | Geometrien Legacy (FAT12 2 MiB), L0 (FAT12 4 MiB), L3 (FAT16 16 MiB) im Feld gelistet |
| F2 | Falsch gepatchte FAT/Root → leere Liste | [B] | Bug 0.4.19 (FELDTEST §4.2) |
| F3 | Dateien mit ungültigem Inhalt (0xFF) → Decoder überspringt, Playlist „rauscht durch“ | [B] | FELDTEST §4.3 |
| F4 | Volle Slot-Länge mit gültigen CBR-Stille-Frames + Xing → Datei bleibt stabil in der Liste | [S] | seit B2 (`Mp3Silence::fill`) |
| F5 | HU-Listenreihenfolge ≠ Slot-Reihenfolge des ESP | [S] | L0-Test 03.10.: BOB oben, Rock unten (Slots fav0=Rock, fav1=Bayern, fav2=BOB) |
| F6 | USB-Serial und Root-Volume-Label (`PDnnnn`) wechseln bei Remount | [B] | PD0082 → PD0084 (06.10.), PD0004 → PD0005 (01.10.); über ESP-RST bleibt die Identity gleich (PD0089, 7 Boots s1-morgen). **Präzisierung 13.10.:** `patchBoot()` lässt FAT-BPB-Volume-ID und BPB-Label aus dem Demo-Image unverändert; `formatVolumeLabel()` ändert nur den Root-Directory-Volume-Eintrag. „Label geändert“ war daher bisher keine vollständige FAT-Volume-Identity-Rotation. |
| F7 | Diese HU zeigt beim Abspielen nur einen **Fortschrittsbalken**, keinen Sekundenzähler | [B] | s1-morgen `f1-events.jsonl` 07:46:43 |
| F8 | Autoplay-Reihenfolge BOB → Bayern → Rock (`fav2 → fav1 → fav0`) | [B] | s1-morgen, mehrfach |
| F9 | USB-Hub an dieser HU: weder Stick noch ESP über den getesteten Hub erkannt (Protokoll: USB-1.1 geplant; Abend: USB-2-Hub) | [B] | F1-Abend 07.10. [`F1-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md) — Full-Speed-Erzwingen über Hub entfällt als Werkzeug |

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

---

## 5. Leseverhalten beim Abspielen (Kern)

### 5.1 Fakten

| # | Fakt | Status | Rechnung / Beleg |
|---|------|--------|------------------|
| R1 | Leserate ≈ USB-Full-Speed-Grenze | [B] | `mscTrace`: 4096 B alle 4 ms ≈ 1 MB/s; netto 665–816 KB/s (Runde 08:10), 774 KB/s (Replug 08:05) |
| R2 | Gewählte Datei wird bis EOF gelesen (oder bis zur Abwahl) | [B] | 86.016 + 438.272 = **524.288** (07:58); 163.840 + 360.448 = **524.288** (08:12:35); `fav0` 8 MiB: `bytes=8.421.376` (`status-pre-rst-0755`) |
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
| R13 | Überlebt der Cache einen ESP-RST (gleiche Serial)? | **[B] nein** | s1-morgen 07.10.: in **6/6** RSTs ist im ersten Poll (Uptime 2–3 s) eine Datei vollständig frisch gelesen (`maxSeq` = Dateigröße, `rc=167`). Frühere Lesart „BOB cache_hit_like nach RST“ war ein Poll-Artefakt ([`KORREKTUR-F2C-RST-ARTEFAKT.md`](../betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/KORREKTUR-F2C-RST-ARTEFAKT.md)). Neue Serial: nicht getestet |
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
| R34 | Sichtbare Identity-Rotation hat P bisher nicht zuverlässig gebrochen | **[S] Feld** | S3: P überlebt USB-Serial-/gekoppelten Root-Label-Wechsel. S4 K3 änderte zusätzlich den Dateinamen; P/Mid-File blieb. Konstant waren u. a. BPB Volume-ID, BPB-Label, Pfad, Größe und Startcluster. Daher Serial/Root-Label/Name-Kombination nicht wiederholen; vollständige FAT-Identity, Größe und Pfad getrennt testen. **Konflikt Community [H]:** Sheet `bmw-nbt-evo` nennt starkes Caching über Volume-Label+Serial — Feld widerlegt genau diese *getestete* Kombination als P-Breaker, nicht die Hypothese insgesamt (Q3/Q14 / HU-A2) |
| R35 | Unter aktivem Body-Stall: Menü/Enumeration ~**20 s** träge | **[B]** Phänomen / [?] Mechanismus | Feld s6: Menü/Dateien ~20 s; UI „eingefroren“, Stationswechsel zickig. Code-Check: Stall greift nur bei aktivem `streamSlot_`-Body — FAT/DIR/Boot nicht gebremst. Ursache der Menülatenz weiter `INFERRED`/`UNKNOWN` (`EVID-BMWHU-2026-10-12-006`, Gate HU-A8). [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md), [`UEBERGABE-S6`](../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md) |
| R36 | Türöffnen kann zusätzlichen Cold-Body-/Re-Read auslösen | **[S]** Effekt / [H] Kausalität | `EVID-USBMSC-2026-10-04-003` MEASURED; Kausalität noch INFERRED. Nicht mit OTG-Replug (R24) verwechseln |
| R26 | Replug-Lesemuster des aktuellen Titels: **1 Callback (Kopf, 4 KiB), ~19 ms Pause, 127 Callbacks im 5-ms-Takt**, gesamt **651–665 ms** (788–805 KB/s). 6-ms-Abstände unregelmäßig, kein 16er-Raster. Ohne laufenden Stream (nach ESP-Reboot) 3,75 ms je Callback, keine 19-ms-Pause | **[B]** Muster / [?] Ursache der 19 ms | s3 6/6 Replugs (`trace.jsonl`, `gap`); Taps 17–18 ms; Reboot-Plug 07:54:50 3 ms. Bestätigt R15 (Takt hängt am ESP-Zustand). Callback-Raster ≠ zwingend CBW-Größe (E11: oft 8 **oder** 240) |
| R18 | 51 Blöcke (208.896 B) von fav0 werden in der Rampe nach RST nie gelesen | [B] Zahl / [?] Ursache | s1-morgen: Summe 4× exakt **8.179.712** B; welche Blöcke → LBA-Trace (`msc.reads`) |
| R19 | Autoplay-Wechsel: Rampe pausiert nach ~4 MiB für 2–3 s, angetippte Auswahl nicht | [S] | s1-morgen Boot 0 (bei 4.194.304 B, 07:44:12–14), Boot 1 (3.985.408 B, 07:49:43–44) |
| R20 | Wiederanlauf nach RST: aktueller Titel in ≤ 3 s komplett neu gelesen (ein Lauf), dazu **8 verstreute 4-KiB-Reads** auf fav0 (`maxSeq` 4096); gesamt `rc=167` | [B] | s1-morgen 4/4 bei 512-KiB-Titel; bei Rock als aktuellem Titel startet direkt die Rampe (2/2) |
| R21 | Next-Track-Prefetch hängt an der **Wiedergabezeit**: ~15 s vor Wiedergabe-Ende, nicht direkt nach Read-EOF | [S] PiDrive | s1-morgen: Bayern 07:48:10 vs. BOB-Ende 07:48:25; Rock 07:49:38 vs. Bayern-Ende ~07:49:52; Ausreißer Boot 0 ~7 s. Nach Rock-Read-EOF nie Prefetch. **hu-probe S2:** Semantik ohne LBA+Marker-Formal weiter `INFERRED` (`EVID-HUPROBE-2026-10-15-010`) — nicht hochstufen |
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
| HU liest 8 MiB | ≈ 10 s | [S] | R1, R10 |
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
| D3 | Spieldauer ergibt sich aus Dateigröße und Bitrate | [S] | R6 |
| D4 | Format-Wechsel in der Datei (Live MPEG-2 22,05 kHz mono ↔ `kSil` MPEG-1 44,1 kHz) bei jedem Underrun | [?] | nicht isoliert getestet (Stufenplan R7) |
| D5 | Andere Bitraten (96k/128k) | [?] | nicht im Feld getestet |

---

## 8. Offene Fragen (Testkatalog)

| ID | Frage | Vorgeschlagener Test |
|----|-------|---------------------|
| Q1 | Welches Timeout-Modell begrenzt READ10/BUSY am NBT? | **Akzeptanz geklärt:** ~65 s bis EOF bei fortlaufenden Retries (R29). Offen ist Gesamtdauer je Kommando vs. Inaktivität ohne Daten. **CBW-Länge mitdenken (E11):** bei `blocks=240` (~122 KiB) ist die Datenphase eines Kommandos ≈30× so groß wie bei `blocks=8`; Timeout-Modelle „pro 4 KiB“ sind unvollständig. Nur bei Bedarf gezielt mit kontrollierten Retry-/Datenpausen messen. |
| Q2 | Spielt die HU während des Lesens oder erst nach Read-Ende? | **[S] während des Lesens** (F1-Abend, Marker ab 0). Formal offen: Video t(Tap→„null“) und 5-MB-vs-100-MB-Vergleich ([`F1-ERGEBNIS.md`](../betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md), Übergabe [`UEBERGABE-FELD-S2-ABEND-2026-10-07.md`](../betrieb/artifacts-2026-10-07-feld/UEBERGABE-FELD-S2-ABEND-2026-10-07.md)) |
| Q3 | Welche Identity-Komponente invalidiert P und/oder Cache? | **Geklärt negativ:** neue USB-Serial + gekoppeltes Root-Label (S3), zusätzlich neuer Dateiname (S4/K3) reichen in der getesteten Kombination nicht. **Community [H] conflicted:** Label+Serial als Cache-Flush (Sheet) ≠ Feld R23/R34. **Desk-Hinweis:** persistente NBT-SQLite-Felder umfassen USB-Serial, `identifier`, `mountpath`, `basepath`, `lastseen` und `last_sync`; ihre kausale Nutzung ist `UNKNOWN`. **Offen, einzeln testen (Gate HU-A2):** BPB Volume-ID, BPB-Label, Größe, Pfad/Directory-Position, Startcluster und Product-Revision; USB-Serial nicht erneut nur gekoppelt mit anderen Variablen testen. Je Lauf genau eine Variable, Replug bei P≫0; P, MSC-Offset und Cache-Hit getrennt protokollieren. Method: [`nbt-medium-identity-resume`](../../../technology-audit/methods/nbt-medium-identity-resume.md) |
| Q8 | Welche Blöcke liest die HU bei frischer Auswahl ab Kopf, in welcher Reihenfolge, wie weit voraus? | Feld s2: **5×** `r16_resume_like`, kein `head_like`. **Feld s3** `s3-20261008-074403`: ep3 **`r16_resume_like`** (`F8 B120 B120 F360…`); Ohr bestätigt Resume≠0 nach Remount. UI-Tap ≠ Offset 0 (R23). Artefakte s2 + [`s3 ERGEBNIS`](../betrieb/artifacts-2026-10-08-feld/feld-s3-prep/s3-20261008-074403/ERGEBNIS.md). **Entscheidend für Stall** (R10) |
| Q9 | Warum 5,1 statt 4,0 ms pro Read bei ESP-Play? | **Geklärt (Lab C2):** ESP Live-/Play-Pfad (+1 ms SG); Poll/Bridge nicht nötig. Siehe R15 |
| Q4 | Wie groß ist der HU-Cache / Read-Ahead? | **Aufteilen** — siehe Katalog [`EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md`](../betrieb/artifacts-2026-10-06-feld/EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md) |
| Q4a | Max. Eager-Read **einer** Datei? | Größenleiter 512 KiB…64 MiB Silence; `maxSeq`/`bytes` ohne Abwahl |
| Q4b | Max. Bytes/Anzahl **mehrerer** gecachter Dateien? | N=1…64 × 512 KiB; Re-Select → Hit (keine Body-Reads) vs Miss |
| Q4c | Eviction-Strategie? | Sequenz dann frühe Datei erneut; optional Rückwärtslauf — FIFO/LRU/? |
| Q5 | In welcher Reihenfolge werden Tracks gewechselt / vorgelesen? | Mehrere Dateien mit eindeutigen Namen; Wechselfolge protokollieren (beobachtet: Bayern → BOB, zweimal) |
| Q6 | Wie reagiert die HU auf gültiges, kontinuierlich nachgeliefertes MP3? | ergibt sich aus dem ersten erfolgreichen Stall-Lauf |
| Q7 | Bekannte Prefill bis Offset X, dann Backpressure — wo stoppt/wartet die HU? | **nur nach Stall-Go**; Silence hinter X verbieten (sonst Cursor-Versatz). Marker-Blöcke zur Offset-Diagnose |
| Q10 | Wie viele Sektoren fordert die HU **je READ10-Kommando**? | **[B] CBW-seitig (Device-Stack), nicht „immer 4 KiB“:** hu-probe BMW S2 (FW 0.2.23): READ10-`blocks` häufig **8** (=4096 B) und **240** (=122 880 B → typ. 30×4096 Events); Events/CBW ≈ 5,29 (`EVID-HUPROBE-2026-10-15-004`, E11). Event-/Callback-n=4096 bleibt Stack-Chunk (E5) und beweist allein keine CDB-Größe. Lab-Sim „Q10=4 KiB“ und PiDrive-`xfer` waren Callback-Ebene. **Offen:** vollständige Histogramm-Verteilung je Phase (Scan/Play/Prefetch), Wire-Beweis (GATE-01). **Für Q1/Stall:** Busy hängt am offenen CBW — große Kommandos (240) mitdenken. Gate **HU-A10** teilweise belegt. Report [`2026-10-15-hu-probe-bmw-s0s2-field`](../../../technology-audit/docs/reports/2026-10-15-hu-probe-bmw-s0s2-field.md) |
| Q11 | Warum startet der ESP bei manchen Plugs/Unplugs neu? (s3: 07:47:00 beim Plug, 07:54:43 beim Unplug; zerstört Stream + ID3, R28) | **Aufbau Feld:** ESP32-S3-DevKitC-1, UART-Buchse am Zigarettenanzünder-Netzteil, native USB-Buchse (OTG) an der HU; Pi ↔ ESP über TCP. Laut [Espressif-Schaltplan v1.1](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf) gehen beide Buchsen über je eine Schottky-Diode 1N5819 auf `VCC_5V` → LDO SGM2212 3,3 V; 10 µF nur auf der UART-Seite. Es speist die Quelle mit der höheren Spannung. **Hypothesen:** (1) Umschalt-Einbruch beim Abstecken (Last wechselt HU → Netzteil, zusammen mit WLAN-Spitze 300–500 mA → Brownout; passt zu 07:54:43), (2) Steck-Transient / Masse-Ausgleich zwischen Netzteil- und HU-Masse beim Anstecken (passt zu 07:47:00), (3) Gegenhypothese Software (Panic/Watchdog in Mount/Unmount-Pfad; in s3 kein Zustandsmuster). Häufigkeit: s3 2 von ~11 Steckvorgängen; Feld 30.09. „nach OTG oft ESP-Reboot … OTG-Strom → Reset“ ([`FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) §11.3). **Test ohne FW:** D1 UART-Buchse an Laptop → ROM-Bootmeldung `rst:0xf (BROWN_OUT_RST)` = Strom, `rst:0x1 (POWERON)` = Spannungsverlust, `rst:0xc` + „Guru Meditation“ = Panic, `rst:0x7/0x8` = Watchdog; D2 Netzteil-A/B (Powerbank, kurzes dickes Kabel); D3 VBUS-Blocker HU ↔ ESP (keine Umschaltung); D4 USB-Messadapter Min/Max. Ablauf: [`FELDPROTOKOLL-S4`](../betrieb/artifacts-2026-10-08-feld/FELDPROTOKOLL-S4-TONFENSTER.md) „Reboot-Diagnose“. **FW-Go:** `lastResetReason` + `resetCount` in `/api/status` ([`STALL-BUILD-SPEC`](../planung/STALL-BUILD-SPEC-2026-10-08.md) §3) |
| Q12 | Warum lehnte Play-Detect den Bayern-Tap 07:55:20 ab (43 Reads, `rej` +43, `guess` 0)? | Lab: Tap-Muster ab Resume-P (R16) ~40 s nach ESP-Reboot nachstellen (`nbt_hu_sim.py --golden GW`), `playMinSeqBytes` / Kopf-Regel prüfen; Feld: `playingUid` nach jedem Tap notieren (s4) |
| Q13 | Ist das stumme `fav0` in s6 primär vorab gecachte non-live Stille, Mid-File-Play ohne Arm oder beides? | S6 im Lab nachstellen: `fav1` live, `fav0` vollständig non-live vorlesen, danach `fav0` wählen. Auswahl klassifizieren: **kein Read** = cache-hit-like; **Mid-Read** = station-intent Mid-Play nötig; **Head-Read** = Play-Detect/S7-Gate korrigieren. Startgate **HU-A1** / Intent **HU-A4** — Method [`nbt-cache-eviction-play-intent`](../../../technology-audit/methods/nbt-cache-eviction-play-intent.md) |
| Q14 | Welche vollständige Medium-/File-Identity bricht Resume-P? | Boot- und Root-Sektor **vom präsentierten Blockdevice** sichern; USB-Serial, BPB Volume-ID, BPB-Label, Root-Label, Pfad, Name, Größe und Startcluster in einer Matrix erfassen. Head-Force und Rotation nie im selben Lauf kombinieren. Gate **HU-A2** |
| Q15 | Was erklärt die ~20 s Menüphase unter Stall? | Phänomen R35; Gate **HU-A8**. Code schließt FAT/DIR-BUSY aus — Ursache weiter offen |

Audit-Gates (**HU-A1…A11** in [`pidrive-2026-bmw-hu/README`](../../../technology-audit/audits/pidrive-2026-bmw-hu/README.md)): Reihenfolge A1 → A4 → A2 → …; **A10** (READ10-Größe) durch hu-probe S2 teilweise belegt (E11/Q10) — Histogramm je Phase + Wire offen; A7 bedarfsgetrieben; A5 (AV) zuletzt. Exit #6 Feld-Ohr (Sender/Menü) bleibt getrennt vom Busy-Pacing-Tonfenster. Prefetch/Eager/Cache/Burst-39: hu-probe-Audit **nicht** hochstufen (`009`/`010`).

---

## 9. Instrument-Hinweise (nicht HU-Verhalten)

Diese Punkte beschreiben die **Messkette**, nicht die NBT:

| # | Fakt | Status | Beleg |
|---|------|--------|-------|
| I1 | Unter anhaltenden Host-Reads kann ESP-WiFi in ~3–5 s sterben; MSC bleibt nutzbar; Auto-Recovery ~30–100 s (hu-probe ≥0.2.11) | **[B]** Device | [`wifi-death-0.2.11`](../../../hu-probe/docs/feld/2026-10-14-wifi-death-0.2.11.md) — Telemetrie-Lücken nicht als HU-Abort lesen |
| I2 | BOT-CBW/CSW aus TinyUSB-Tap = Device-Stack, **nicht** Wire; GATE-01 Wire weiter offen | **[D]/[?]** | hu-probe `GATES.md`; Peer-Review Abend 14.10.; E11/Q10 sind Stack-CBW-Claims |
| I3 | `read.gap_us` aus MSC-Callback belastbar; Event-`t_us`-Monotonie war in 0.2.11 teils gebrochen (BOT-Drain vs. Capture-Stamp) | **[B]** Instrument | [`review-abend-triage`](../../../hu-probe/docs/feld/2026-10-14-review-abend-triage.md); Pace weiter über `gap_us`, nicht `t_us`-Monotonie |
| I4 | MODE_SENSE6→`ep_stall` vor FW **0.2.18** = Instrument-Artefakt, **nicht** HU-Recovery | **[B]** Instrument / Claim HU-Recovery **REJECTED** | Offline-P0: 70/84 Stalls same-`t_us` wie ms6; nach Pad S2 `ep_stall=0`, ms6/cap=2,0 bleibt (`EVID-HUPROBE-2026-10-15-005`/`006`) |
| I5 | Burst „immer 39“ File-Reads | Konstante **REJECTED** / Cluster [H] | Gap-Split p50=39, Histogramm auch 62–78 (`EVID-HUPROBE-2026-10-15-009`) — nicht als Profil-Konstante |

---

## 10. Pflegeregel

- Neue Feldbefunde mit Datum, FW-Version, Geometrie (`kReadyDetail`) und Quelle eintragen.
- Status nur auf **[B]** heben, wenn Rohdaten (Status-JSON, Correlate-Watch, Bridge-Log, hu-probe Session) verlinkt sind. Evidence-IDs aus [`pidrive-2026-bmw-hu/evidence`](../../../technology-audit/audits/pidrive-2026-bmw-hu/evidence.md) bzw. [`hu-probe-bmw-s0s2-field-2026/evidence`](../../../technology-audit/audits/hu-probe-bmw-s0s2-field-2026/evidence.md) mitführen, wenn vorhanden.
- Zählerwerte aus verschiedenen Snapshots nicht mischen. `liveBytes = streamBytes − underruns` ist nach einem Senderwechsel ungültig, solange `streamBytesServed_` nicht in `startStream()` zurückgesetzt wird.
- `mscTrace.tag` kann abgeschnitten sein (z. B. `Rock Antenn`) und ist kein eindeutiger Slotschlüssel. Datei/Slot aus LBA-Bereich plus `slotMap` zuordnen.
- Community-/SIB-Muster und Lab-Debian-Gaps nicht still zu NBT-[B] machen. Host-Scope: nur diese NBT Evo.
- Event-/Callback-Größe (`xfer`, `n=4096`) und READ10-CBW-`blocks` getrennt führen (E5 vs. E11). Prefetch/Eager/Cache aus PiDrive nicht automatisch als hu-probe-FACT lesen.
