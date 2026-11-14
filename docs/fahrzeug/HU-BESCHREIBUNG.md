# BMW F20 NBT Evo — HU-Beschreibung und Modellbericht

**Stand:** 2026-11-14 ~11:20 (Logcat silent ch6; B2-A-TX Matrix DM/refuse ch5–10 trotz A2DP-OK — C-BT21/22; Lab Dummy BCL PASS C-L13; F20-BCL-Bytes weiter offen). Davor C-BT15…20 / C-L7…C-L12; 2026-11-13 A6/B1/B2  
**Fahrzeug:** BMW 118d F20 LCI (2017), NBT Evo  
**Statusschema:** wie in [`HU-Technical-Facts.md`](HU-Technical-Facts.md) — **[B]** bewiesen · **[S]** stark belegt · **[D]** Desk · **[H]** Hypothese · **[?]** offen  
**Normative Tabellen:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md) · **Ops-Matrix:** [`HU-PARAMETER-MATRIX.md`](HU-PARAMETER-MATRIX.md) · **Connected-Detail:** [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md)

Dieses Dokument ist die **narrative Gesamtbeschreibung** der Head Unit für PiDrive: Lesetext mit Inhaltsverzeichnis und Quellen, nicht der Faktenkatalog. Messwerte, IDs (E/R/F/Q/C-D) und Rohbelege bleiben in den Facts; hier steht das Modell. Frühere GPT-Fließtexte (inkl. Erstfassung dieses Berichts) sind **Architektur-Skizze, nicht zitierfähige Faktenreferenz** — siehe §6.

---

## Inhaltsverzeichnis

1. [Zweck und Lesart](#1-zweck-und-lesart)
2. [Gesamturteil](#2-gesamturteil)
3. [Zwei-Plane-Architektur](#3-zwei-plane-architektur)
4. [Storage Plane — USB-MSC-Host](#4-storage-plane--usb-msc-host)
   - 4.1 Enumeration und SCSI
   - 4.2 Dateisystem und Medienliste
   - 4.3 Aggressiver Read-Ahead und Cache
   - 4.4 Drei Zustände, nicht einer
   - 4.5 Lesereihenfolge ≠ Abspielposition
   - 4.6 Prefetch und Nachbar-Eager
   - 4.7 Stall-Toleranz und Timingproblem
   - 4.8 Messbasis und Gültigkeit
5. [Control Plane — Connected Apps](#5-control-plane--connected-apps)
   - 5.1 Gates G1–G4 (+ Nutzung danach)
   - 5.2 AOA ≠ Connected App
   - 5.3 Feldstand an dieser HU
   - 5.4 SAS, RHMI, CDS, AV
   - 5.5 Bluetooth-Medienpfad (A2DP/AVRCP/HFP)
6. [Korrekturen (GPT-Fassung 07.11., Nachrechnung 11.11.)](#6-korrekturen-gpt-fassung-0711-nachrechnung-1111)
7. [PiDrive-Strategien und Folgen für Variante B](#7-pidrive-strategien-und-folgen-für-variante-b)
8. [Offene P0/P1-Fragen](#8-offene-p0p1-fragen)
9. [Quellenverzeichnis](#9-quellenverzeichnis)

---

## 1. Zweck und Lesart

| Dokument | Rolle |
|----------|--------|
| **dieses** | Lesemodell, Architektur, Strategie, TOC + Quellen |
| [`HU-Technical-Facts.md`](HU-Technical-Facts.md) | Normative Claim-Tabelle mit Belegstatus |
| [`HU-PARAMETER-MATRIX.md`](HU-PARAMETER-MATRIX.md) | Parameter × Status × nächster Test |
| [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md) | Desk-Stack Connected/AAIdrive |
| [`../betrieb/MSC-AKTUELL.md`](../betrieb/MSC-AKTUELL.md) | Operativer MSC-Einstieg / Ampel |

**Scope-Regel:** Alles mit Status **[B]/[S]** gilt nur für **diese** NBT Evo am gemessenen USB-Pfad, sofern nicht ausdrücklich Desk-[D] markiert. Andere BMW-Generationen und Lab-Stimulus-Hosts sind kein stiller Transfer.

---

## 2. Gesamturteil

**Storage Plane:** Die BMW NBT-Evo-HU ist ein aggressiver, dateiorientierter USB-MSC-Host mit mehrstufigem Zustand/Cache, großen READ10-Transfers und nachweislich hoher Toleranz gegenüber USB-Backpressure. Sie konsumiert nicht einfach kontinuierlich Audio, sondern fordert Daten in kontextabhängigen Leseoperationen an und kann daraus lokal weiter abspielen. Konkret (Heimfahrt nachgerechnet, R53–R58): Ein Titel, der zu spielen beginnt, wird **vollständig** mit ~1 MB/s gelesen (bis 7,2 MB belegt, keine Obergrenze sichtbar); der Folgetitel wird ~7–8 s vor Ende angelesen; nach einem Mount wird der Resume-Titel ab Kopf und ab Position gelesen; teils werden mehrere Folgetitel am Stück vorgelesen, und der Cache hält das minutenlang.

**Control Plane:** Parallel existiert eine Connected-App-/Accessory-Kette, deren Transport und höhere Protokollschichten getrennt vom Storage Plane betrachtet werden müssen (AOA/BT → BCL → Etch → SAS; danach RHMI/CDS/AV/AM als Nutzerebene). Desk-[D] stark, F20-Wire noch nicht durchgehend bewiesen. Seit 13.11. ist die Bluetooth-Seite der HU vermessen (SDP, Codecs, AVRCP, HFP; §5.5); ob die HU darüber BCL spricht, ist weiter offen.

Für PiDrive: Storage = Golden Path mit Timing-/Backpressure-Problem; Control = strategische Option mit Gates G1–G4. **I-303A** bleibt unberührt — Storage-Plane-Korrekturen ändern nichts an dem, was G1 auf der USB-Leitung sichtbar macht.

```
┌──────────────────────────────────────────────────────────┐
│                    BMW F20 NBT Evo HU                    │
│                                                          │
│  ┌──────────────────────┐   ┌─────────────────────────┐  │
│  │    STORAGE PLANE     │   │      CONTROL PLANE      │  │
│  │                      │   │                         │  │
│  │ USB MSC Host         │   │ Connected Apps          │  │
│  │ SCSI / BOT           │   │ USB AOA / BT            │  │
│  │ FAT12 / FAT16        │   │       │                 │  │
│  │ Media Scanner        │   │       ▼                 │  │
│  │ Read-Ahead           │   │  G2 BCL (+ Transport)   │  │
│  │ Navigator / Position │   │       │                 │  │
│  │ Browse-/Lib-Cache    │   │       ▼                 │  │
│  │ Audio-Body-Cache     │   │  G3 Etch-Tunnel         │  │
│  │        │             │   │       │                 │  │
│  │        ▼             │   │       ▼                 │  │
│  │     Decoder          │   │  G4 SAS                 │  │
│  │        │             │   │       │                 │  │
│  │        ▼             │   │       ▼ danach          │  │
│  │      AUDIO           │   │  RHMI / CDS / AV / AM   │  │
│  └──────────────────────┘   └─────────────────────────┘  │
│                                                          │
│        SEHR GUT BELEGT              TEILWEISE BELEGT     │
│        (Feld-[B]/[S])              (Desk-[D] + Lab;     │
│                                      F20-Wire offen)     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Zwei-Plane-Architektur

| Ebene | Transport | Stack (kurz) | Evidenz an dieser HU |
|-------|-----------|--------------|----------------------|
| **Storage Plane** | USB MSC | SCSI/BOT → FAT → Scanner → Cache → Decoder | **[B]/[S]** Feld/Lab (Facts E/R/F) |
| **Control Plane** | USB AOA und/oder BT | Accessory → BCL → Etch → SAS → RHMI/CDS/AV/AM | **[D]** Desk; Feld G1 + AOA partiell; BT-SDP **[B]** (C-BT1); SPP SCN6 OPEN **[B]** (C-BT15); BCL-Bytes **[?]** (HU silent ch6) |
| **BT-Medienpfad** (Variante A) | BT Classic | A2DP-Sink · AVRCP-CT 1.5 + Browsing · HFP-HF 1.6 | **[B]** ein Feld-Capture (Facts §10.5) |

Die Trennung ist keine Dokumentationskosmetik. MSC und Connected-App-Pfade haben **unterschiedliche USB-Identitäten, Zustandsmaschinen und Messinstrumente**. hu-probe führt deshalb getrennte Boot-Modi (`msc` vs. `aoa_*`); Analyzer-Feld bestätigt: MSC-Identity mountet Storage, ohne dass daraus Connected folgt (Facts E18/F15, C-D9).

**REJECTED:** „AOA erkannt ⇒ Connected App.“ · „ESP als 18D1:2D00 = Phone-Connected-Peer.“ · „MSC-Bulk oder AOA-Bulk ⇒ App-Stack offen.“

---

## 4. Storage Plane — USB-MSC-Host

### 4.1 Enumeration und SCSI

Nach dem Einstecken folgt klassische Mass-Storage-Kommunikation: INQUIRY, CAPACITY, PREVENT, MODE_SENSE, periodisches TEST UNIT READY, **keine Writes** (E1–E4, E12). Idle-TUR ist phasenstarr **≈ 2239 ms** (E3) — nicht „~1/s“.

Wichtig für Instrumentierung — **zwei Ebenen, nicht vermengen** (E5 vs. E11):

- **Event-/Callback-Ebene:** oft 4 KiB Chunks (TinyUSB-Puffer) → `n8kPlus` bauartbedingt 0 (E5).
- **CBW-/READ10-Ebene:** Blockzahlen häufig **8** und **240**; Demo-Track-Atom **240+69** (E11, Q10).
- `240 × 512 B = 122 880 B` ≈ **~30 × 4-KiB-Callbacks** pro offenem Kommando.

```
HU
  │
  │ READ10, z.B. blocks=240
  ▼
~122 KiB Datenphase
  │
  ├─ 4 KiB callback
  ├─ 4 KiB callback
  ├─ ...
  └─ ~30 callbacks
```

Aus `n8kPlus = 0` darf man **nicht** „die HU liest immer 4 KiB“ ableiten. Das Timing-Modell von PiDrive orientiert sich an der **offenen CBW-Datenphase**, nicht am einzelnen Callback. Innerhalb dieser Phase kann PiDrive BUSY/Backpressure liefern, ohne dass die HU zwangsläufig sofort abbricht.

Queue-Tiefe effektiv **1** ist **protokollbedingt** (BOT: CBW → Daten → CSW) — kein paralleler Multi-Outstanding-Client. Caveat aus Facts E6: Wire-QD-max weiter **UNKNOWN**, hu-probe-Wert `INFERRED` — kein bedingungsloses Wire-FACT.

### 4.2 Dateisystem und Medienliste

Die HU erwartet ein plausibles FAT12/FAT16 mit LFN, gültigen Dateiköpfen (ID3/APIC) und konsistenten Größen (F1–F5, M1–M3). Falsche FAT/Root → leere Liste. Analyzer-Pattern ohne Media-Dateien: SCSI-Mount **ohne** sichtbares Media-UI (F15).

Browse-UI kommt aus Directory/8.3; Player-Metadaten aus Dateikopf. Das ist Filesystem-/Media-Management, kein „Audio-Stream über USB“.

### 4.3 Aggressiver Read-Ahead und Cache

Vereinfachter Ablauf:

```
USB einstecken
     │
     ▼
Enumeration / SCSI
     │
     ▼
Dateisystem-Scan (Fresh: 160 Blöcke + EOF-Probe je Datei, größenunabhängig)
     │
     ▼
HU-interne Schicht
     ├── Navigator / Playlist-Position
     ├── Browse- / Titel-Cache
     └── Audio-Body-Cache
              │
              ├── Hit  → Wiedergabe ohne Body-Reads
              └── Miss → Eager Body (ganze Datei) → Cache → Decoder
```

Kernfakten:

| Aussage | Status | Ref |
|---------|--------|-----|
| Spielende / gewählte Datei wird komplett gelesen, bis 7,2 MB ohne Grenze | **[B]** | R2, R53 |
| Leserate nahe USB-FS (~1 MB/s / ~4 ms je 4 KiB Callback) | **[B]** | R1, R15 |
| Nach Vorlesen lange keine Reads bei laufender Wiedergabe | **[B]** | R5 (≥150 s) |
| Cache-Hit → keine Body-Reads | **[B]** | R9 |
| Next-Track / Neighbor wird vorgelesen | **[B]/[S]** | R4, R21, R47 |
| Mehrere Folgetitel am Stück vorgelesen (≈31 MB in 70 s), auch in Unterordnern | **[S]** | R57 |
| Body-Cache hält Daten ≥ 400–655 s, auch über weitere Reads | **[S]** | R56 |
| Fresh-Scan liest 160 Blöcke + EOF-Probe pro Datei, unabhängig von der Größe | **[S]** | R58 |
| Autoplay wechselt im Takt der Dateidauer, loopt im Ordner; 32–320 kbit/s gelesen | **[S]** | R59, R60 |
| USB und Audio entkoppelt (Cache dazwischen) | **[B]/[S]** | R5, R24, R33 |

Gegenüber 48 kbit/s Audio (~6 KiB/s) liest die HU grob **zwei Größenordnungen schneller**. Deshalb wirkt sie wie ein Festplattenbenutzer, nicht wie ein Just-in-Time-Player.

### 4.4 Drei Zustände, nicht einer

Facts R45/R46: Remount/Cycle ist **kein** Cold Start. „Ein Media Cache“ ist zu grob — mindestens drei getrennte HU-Zustände mit unterschiedlichem Invalidierungsverhalten:

```
HU
├── Navigator / Playlist-Position
│     └── kann über bestimmte Resets/Cycles erhalten bleiben
├── Browse / Library Cache
│     └── bei Cycle oft geflusht; Position bleibt
└── Audio Body Cache
      └── kann bei ESP-RST verloren gehen → Body wird erneut gelesen;
          Position oft trotzdem erhalten
```

Damit wird verständlich, dass **Resume-Position und USB-Leseverlauf zwei verschiedene Zustände** sind (R34, Q3; R24).

Serial / Root-Label / Volume-ID sind als Resume-Key **REJECTED** (R34). Soft-Remount (NOT READY) resetet die HU praktisch **nicht** (R37).

### 4.5 Lesereihenfolge ≠ Abspielposition

Bei Resume an Position **P** liest die HU nicht strikt „ab P vorwärts wie ein Audio-Cursor“:

- Out-of-order Muster mit Vor-/Rückwärtssegmenten (R16)
- Nach OTG-Remount: kompletter Titel ab Offset 0, Wiedergabe weiter bei P (R24)
- Große Dateien nach Mount: Kopf **0–3840 Blöcke (1,875 MiB)** verschränkt mit **P → EOF**; der Mittelteil folgt erst, wenn die Wiedergabe dort ankommt (R55; `#23` R04: Mitte 3840–7464 erst nach ~400 s)
- UI-Tap liest Umgebung von P, Remount-Read oft head-first Vollatom

**Abspielposition ≠ Lesereihenfolge** ist damit ein Architekturfakt (R23, R24, R33).

### 4.6 Prefetch und Nachbar-Eager

Nachgerechnet aus den drei Instrument-gültigen Heimfahrt-Sessions (`#22`–`#24`, 0.3.17 Stored-Replay) und den Media-Leiter-Sessions vom 22.10. (§4.8). Vier Lesemuster:

| Muster | Was die HU liest | Wann | Ref |
|--------|------------------|------|-----|
| **Spielstart / Auswahl** | ganze Datei, 0,9–1,05 MB/s (z. B. 7,2 MB in 9,6–10,9 s) | sofort | R53 |
| **Natürlicher Autoplay-Wechsel** | Kopf des Folgetitels (768 KiB bei bekanntem Medium, ~1,3 MiB nach Fresh-Scan), Rest beim Wechsel in einem Zug | Kopf **7,2–8 s vor Ende** (n=6) | R54 |
| **Resume nach Mount** | Kopf 0–3840 Blöcke ∥ Resume-Position → EOF; Mitte später | beim Mount | R55 |
| **Ketten-Prefetch** | mehrere Folgetitel komplett Rücken an Rücken (≈31 MB in 70 s, Abstand ~4 ms) | nach Remount/Ordnerwechsel; Auslöser [?] | R57 |

```
Titel N spielt (ganz im Cache)                 Titel N+1
|=================================|            |==========================|
                          7–8 s vor Ende:
                          Kopf N+1 lesen -----> [Kopf]
                                Wechsel: Rest -> [Kopf|=====Rest=========]
```

- Der Lead ist **kontextabhängig** (R49): ~7–8 s ist der Normalfall beim natürlichen Wechsel, aber keine universelle Konstante (kleine Demo-Dateien: Read erst beim Wechsel bzw. ~1,9 s vorher). „15 s“ ist **REJECTED**. Die früher genannten **140–240 s** in ROCK/CLASSIC waren formal berechnet; dort lief eine Kette (R57), kein Vorlauf vor dem Ende eines laufenden Titels.
- Das **512-Block-Fenster** (Matrix A15) gilt für reale Dateien nicht: keine Plateau-Grenze bis 7,2 MB. ≥ 8 MiB ist ungemessen.
- Drei Read-Modi (R47): Head/Selection · Eager Body (**100 %**) · Neighbor/LBA-Interleave. **Eager ≠ hörbares Play** (R50) — großer Read beweist keine Audible-Session (GATE-01 offen).
- Body-Reads können **vor** Head-Reads kommen (R8) — asynchroner Scanner/Prefetcher.
- Cache: Daten bleiben minutenlang; beim Ordner-Loop M03→M01 wurde nur die verdrängte Mitte von M01 neu gelesen (R56). Autoplay loopt im Ordner (R60).

### 4.7 Stall-Toleranz und Timingproblem

PiDrive will idealerweise Live-Audio liefern; die HU will Dateien in großen READ10-Phasen einsaugen. Stall-Toleranz ist **Feld-FACT**, kein „komplettes Unknown“:

| Größe | Richtwert | Status |
|-------|-----------|--------|
| 512 KiB lesen | ≈ 0,6 s | **[B]** |
| Audio 48 kbit/s | ≈ 6 KiB/s | Rechnung |
| Ringfenster ohne Stall | ≈ 6–9 s | **[B]/[S]** (R25, §6.3 Facts) |
| Stall-on bis EOF (512 KiB) | ≈ 65 s Musik+ID3; BUSY-Retries über Minuten | **[B]** (E7, R29) |
| Längste reale Haltezeit eines Kommandos (Heimfahrt, ohne BUSY-Stimulus) | < 0,3 s | **[B]** (§4.8; frühere R51 „1,6 s BUSY“ = Auswertungsartefakt) |

**REJECTED:** „Kleiner Ring = harte Dauerstrom-Grenze.“ Die HU ist nachweislich **stallexzessiv tolerant** — das Fenster ist größer als die frühere 100-ms-/300-ms-/3-s-Unsicherheitserzählung. Die gemessene BUSY-Toleranz ist eine **reale Designressource** für Backpressure: PiDrive muss nicht zwingend innerhalb jedes 4-KiB-Callbacks „fertig“ sein.

**Q1 Rest** (nicht „Q1 komplett offen“): Gesamtdauer pro Kommando vs. datenlose Inaktivität; dabei CBW-Blockzahl mitdenken (`blocks=240` → Retry hängt an ~122 KiB Datenphase, nicht an 4 KiB). Keine scheinpräzise Millisekunden-Grenze, solange blocks × Datenphase × Idle nicht systematisch vermessen sind. **Q16** ist für 2–7,2 MB durch die nachgerechnete Heimfahrt beantwortet (§4.6); offen bleiben ≥ 8 MiB und vor allem, ob BUSY-Pacing über die **ganze Datei** (Minuten, nicht 512 KiB) trägt. Die Größenleiter-Feldläufe 27.10. und 11.11. lieferten keine HU-Read-Daten (Instrument, §4.8).

Konsequenz: PiDrive muss die **Read-Requests** so bedienen, dass die HU-Illusion eines normalen MSC-Sticks erhalten bleibt — nicht „Audio tropfenweise nach Decoderuhr“.

Das verschärft sich durch §4.6: Die HU fordert beim Spielstart die **ganze Datei** an. Ein Live-Slot muss deshalb über seine gesamte Länge gepaced werden; was PiDrive zum Lesezeitpunkt noch nicht hat und trotzdem liefert, landet als Stille im HU-Cache und wird abgespielt.

### 4.8 Messbasis und Gültigkeit

Alle hu-probe-BMW-Sessions wurden am 11.11. nachgerechnet: CBW/CSW-Paarung in Stream-Reihenfolge, DATA-Summe je READ10, lückenlose `capture_seq`, Zeitmonotonie, Verlauf des Ringverlust-Zählers und `origin`. Ergebnis (Detail Facts §9.1):

| Sessions | Ergebnis |
|----------|----------|
| Heimfahrt `#22`–`#24` (0.3.17 Stored-Replay) | **gültig**, verlustfrei — nach Entfernen der `post_finalize`-Events (Upload-Phase, I9) |
| Media-Leiter 22.10. (`080353`…`081152`, `61434`), 20.10. free, S0/S2 | gültig |
| 22.10. `081410` (drive_mix live) | ~990 BOT-Records verloren (I11): nur Reihenfolge, keine Coverage |
| 11.11. free (0.3.38) | gültig für Ops |
| Größenleiter 27.10., 11.11. ×2, Lab `065150` | **ungültig** (Hide-Poll nach Capture-Ende bzw. Replay-Deadlock 0.3.21–0.3.38, I7/I8) |

Dabei fielen drei Fehlinterpretationen auf: der „~1,6-s-BUSY ohne Reset“ (R51) war ein Fehler in `analyze_session.py` (Tag-Wiederverwendung nach Remount, I10; korrigiert); der „zweite Mount in `#22` mit 395xxx-LBA-Probe“ (Q18) bestand aus `post_finalize`-Events; die 93–99-%-Coverage stammte aus Episoden ohne Kopf-Atom. Die hu-probe-Sicht bleibt durch TinyUSB/DWC2 begrenzt (keine NAK/Token/Wire-Zeiten, I13); 0.3.40 erweitert die Detektion, ist aber weder kompiliert noch feldgetestet.

---

## 5. Control Plane — Connected Apps

### 5.1 Gates G1–G4 (+ Nutzung danach)

Verbindliches Referenzmodell (hu-probe `a68ef3b` / Vier-Gate-Commit): **G1–G4**. RHMI/CDS/AV/AM sind **Nutzerebene nach G4**, keine konkurrierende Gate-Nummer **G5**.

```
G1  USB Identity / Class
G2  AOA / BT Transport + BCL
G3  Phone → localhost TCP → BCL → Etch
G4  SAS Authentication
    │
    └── danach: RHMI / CDS / AV / AM
```

| Gate | Inhalt | Messstand F20 |
|------|--------|---------------|
| G1 | USB Identity / Class | teilweise **[B]** (MSC; AOA-Identity-Versuche); **I-303A** |
| G2 | AOA/BT Transport + BCL | AOA-Beobachtung partiell; **BCL-Wire offen** |
| G3 | Phone localhost TCP → BCL → Etch | nicht am Wire |
| G4 | SAS Authentication | Desk-[D]; Feld offen |
| *(danach)* | RHMI / CDS / AV / AM | Desk-[D]; Feld offen — **keine Gate-ID G5** |

Detail und Primärquellen: [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md) · hu-probe [`GATES-Connected.md`](../../../hu-probe/docs/GATES-Connected.md).

### 5.2 AOA ≠ Connected App

Android Open Accessory (z. B. Already-Accessory `18D1:2D00`) ist nur ein **USB-Zustands-/Identitätsmodus**. Connected Apps brauchen darüber hinaus BCL-Framing, Etch, SAS und App-Autorisierung. Blindes Präsentieren von 51/52/53 oder einer Accessory-VID/PID beweist weder „AOA tot“ noch „Connected lebt“.

### 5.3 Feldstand an dieser HU

- Direct-ESP `18D1:2D00`: Zubehör-UI / Reconnect-Loop; kein verwertbarer Bulk-RX; 51/52/53 auf Callback-Schicht absent (Facts §10; Inference, kein abschließender „AOA unsupported“-Beweis).
- Analyzer MSC `303a:1001`: mountet Storage; `aoa51/52/53=0` trotz AOA-respond (E18).
- **Kein** durchgehender F20-BCL/Etch/SAS-Wire-Capture.
- BT-Analyzer 13.11. (`.87` als Phone, A6): Pairing, HU-SDP und A2DP/AVRCP/HFP gemessen (C-BT1–C-BT8). Die HU bietet sechs RFCOMM-Datendienste an: Kanal 5 mit eigener BMW-UUID `…deca-fade…` und Kanäle 6–10 als SPP. Im Leerlauf ohne Phone-App öffnete die HU **keinen** davon (C-BT8).
- 14.11. OnePlus↔echte HU (Logcat): SPP SCN6 OPEN, HU silent ch6 (C-BT15–20). Vormittag: B2-A-TX ch5–10 → DM/refuse auch bei „BT-Analyzer verbunden“ (C-BT21/22); parallel Phone↔Dummy BCL + AAIdrive grün (C-L13). Nächster Schritt: Phone HCI-Snoop Hex; b2a-tx isoliert.

### 5.4 SAS, RHMI, CDS, AV

Nach Desk (BimmerGestalt / AAIdrive):

- **SAS:** Cert → Challenge → Signatur → Login — Hard Stop ohne gültiges Material; Beobachtung gewünscht, keine Challenge-Fälschung als Ziel.
- **RHMI:** native iDrive-Widgets; Layouts an Cert-SHA256 gebunden — freie XML **REJECTED**.
- **CDS:** Fahrzeugdaten (Desk); Property-Verfügbarkeit am F20 ungemessen.
- **AV:** Entertainment-Kontext; ob Audio-Payload über Etch/BCL läuft oder nur Fokus + BT/A2DP: **UNKNOWN**. AAIdrive selbst verweist auf BT-Audio bei eingeschränktem AOA2-Audio.

Voraussetzung Fahrzeug: Apps/6NR bzw. ConnectedDrive-Apps — sonst ist Pfad C tot (C-Q1).

### 5.5 Bluetooth-Medienpfad (A2DP/AVRCP/HFP)

Gemessen am 13.11. mit BlueZ/PipeWire auf `.108` als Gegenstelle (Facts §10.5, ein Termin, HU ohne Phone-App):

- **Profile der HU:** A2DP-Sink 1.3, AVRCP-**Controller 1.5** (kein Target), HFP-**Hands-Free** 1.6, MAP-Client (MNS), OPP, PnP, dazu die sechs RFCOMM-Datendienste aus §5.3. Module und Strings stammen von ALPS.
- **Audio:** Die HU bietet SBC (Bitpool bis 53), AAC und MP3 an, jeweils mit SCMS-T und Delay Reporting. BlueZ hat SBC mit **48 kHz** gewählt. SBC-53 bei 48 kHz braucht ~357 kbit/s, bei 44,1 kHz ~328 kbit/s.
- **Metadaten:** Die HU fragt Titelattribute 1–7 **einzeln** ab, meldet elf Notification-Events an (Track, Status, Position im 1-s-Takt, Batterie u. a.) und öffnet den **Browsing**-Kanal. Die frühere Annahme „F20 = AVRCP 1.4 ohne Browsing“ ist für diese HU widerlegt.
- **Bedienung:** Lenkrad/iDrive kommen als AVRCP-Pass-through PLAY / FORWARD / BACKWARD an. Absolute Lautstärke wurde nicht genutzt.
- **HFP:** Die HU baut nach dem Pairing selbst HFP auf, scheitert an `AT+CHLD=?` gegen unseren AG ohne Telefonie, trennt und versucht es alle 20–35 s neu (C-BT7). Für reine Medien-Messungen stört das; Fix im Lab: HFP-AG in WirePlumber abschalten.

---

## 6. Korrekturen (GPT-Fassung 07.11., Nachrechnung 11.11.)

Gegenprüfung gegen [`HU-Technical-Facts.md`](HU-Technical-Facts.md) (Stand 2026-11-06+, R46–R52, E18/F15): Das **Zwei-Plane-Modell** und der PiDrive-Vertrag („kein Audio-Player, sondern dateiorientierter MSC-Host mit Cache“) sind korrekt. Die alte Storage-Plane-Erzählung ist als Architektur-Skizze brauchbar, aber **nicht als Faktenreferenz zitierfähig**. Vier konkrete Fehler und zwei kleinere Punkte:

| # | GPT-Aussage | Bewertung | Korrektur (Facts) |
|---|-------------|-----------|-------------------|
| 1 | Prefetch „~15 s vor Ende“, Ausreißer ~7 s → [S] | **veraltet / REJECTED** | Lead **kontextabhängig** (R49/R54): natürlicher Wechsel ~7,2–8 s (n=6); „15 s“ **REJECTED**; „140–240 s“ war formal (Kette R57) |
| 2 | Stall-Toleranz / Q1 „komplett offen“ (100 ms / 300 ms / 3 s?) | **falsch dargestellt** | Stall **Feld-FACT**: E7/R29 (BUSY über Minuten, ~65 s bis EOF). Q1 nur noch Rest: Dauer vs. Idle + CBW-Größe, Pacing über ganze Datei. (R51 am 11.11. als Artefakt zurückgezogen) |
| 3 | „HU immer 4 KiB“, seriell = FACT | **vermengt Ebenen** | Callback 4 KiB (E5) ≠ CBW oft **8/240** (E11). Track-Atom `240+69`. Timing = CBW-Sicht |
| 4 | „ein Media Cache“ | **zu grob** | ≥3 Zustände (R45): Navigator/Position ≠ Browse/Lib ≠ Audio-Body; unterschiedliches Invalidierungsverhalten |
| — | Gate **G5** (RHMI/CDS/AV) | **konkurrierendes Modell** | Referenz = **G1–G4**; RHMI/… = Nutzung **nach** G4 (`a68ef3b`) |
| — | Queue-Tiefe 1 als bedingungsloses FACT | **zu hart** | protokollbedingt **[B]**; Wire QD-max **UNKNOWN** / `INFERRED` (E6) |

**Richtig wiedergegeben** in der GPT-Fassung u. a.: R16 (nichtlineare Reads), R24 (Abspielposition ≠ Lesereihenfolge), R5 (keine Reads während Wiedergabe), ~9-s-Tonfenster-Konsequenz, Zwei-Plane-Epistemik.

**Praktische Konsequenz:** Backpressure-Planung geht von **gemessener hoher Stall-Toleranz** (E7/R29) aus, mit Q1-Rest und Q16 als offenen Flanken — nicht von „Q1 = komplettes Unknown“. Storage-Korrekturen berühren **I-303A / G1** nicht.

**Korrekturen aus der Nachrechnung 11.11.** (eigene frühere Auswertungen, nicht GPT):

| Bisher | Jetzt | Grund |
|--------|-------|-------|
| R51: Kurz-BUSY 1,6 s ohne Reset **[B]** | **REJECTED** | Tag-Bug in `analyze_session.py` (I10) |
| Q18: 395xxx-LBA-Probe beim 2. Mount `#22` | **geschlossen, Artefakt**; `#22` hatte einen Mount | `post_finalize`-Events (I9) |
| R46 belegt durch `#22` und `#23` | nur `#23` | dito |
| R47: Eager 93–99 % | **100 %** | Episoden ohne Kopf-Atom gezählt |
| R49: ROCK/CLASSIC 140–240 s Lead | formal; Kette R57 | Rechnung Dauer − Abstand |
| Matrix A15: Lesefenster 512 Blöcke | **widerlegt** bis 7,2 MB | R53 |
| Größenleiter 27.10./11.11. „Capture verloren“ | **ungültig** (Hide-Poll / Replay-Deadlock) | I7/I8 |
| 22.10. drive_mix live Coverage (z. B. J01 76 %) | nicht verwendbar | Ringverlust (I11) |

---

## 7. PiDrive-Strategien und Folgen für Variante B

| Variante | Pfad | Stand | Stärke | Risiko |
|----------|------|-------|--------|--------|
| **A** | BT A2DP + AVRCP | aktiv | stabiler Ton/Metadaten-Grundpfad; HU nutzt AVRCP 1.5 inkl. Browsing, AAC angeboten (§5.5) | Cover/UI limitiert; HFP-Reconnect-Schleife ohne Telefonie-AG; SBC-53 @ 48 kHz am Coex-Limit |
| **B** | Storage Plane / USB-MSC | Golden Path + Messung | Cover, HU-USB-UI, gut vermessen | Live vs. Eager-Read-Ahead |
| **C** | Control Plane / Connected | Forschung | native RHMI/AV-Nähe | Gates, Certs, 6NR, Wire offen |

Für Variante B bleibt die Leitfrage: Reads so bedienen (Stall/Backpressure über CBW-Datenphasen, gültige Heads, FULLMENU-Vertrag), dass Cache/Prefetch der HU **stick-kompatibel** bleiben. Arbeitsgrundlage = hohe Stall-Toleranz; Decoder-Experimente ohne Q1-Rest/GATE-01 lösen das Timingproblem nicht.

**Folgen des Lesemodells (§4.6) für PiDrive** — abgeleitet, nicht einzeln im Feld getestet:

1. **Live-Slot über die ganze Länge pacen.** Die HU liest beim Spielstart die ganze Datei mit ~1 MB/s (R53). Ein Ringfenster am Kopf reicht nicht; jeder noch nicht erzeugte Block muss per BUSY/NOT READY verzögert werden. Belegt ist Pacing bisher nur für 512 KiB (~65 s, S6). Das ist der wichtigste offene Test (Q1-Rest).
2. **Slotgröße.** Bis 7,2 MB liest die HU vollständig; ≥ 8 MiB ist ungemessen (S6: 8-MiB-Rock oft stumm, R32).
3. **Nachbarn sind nie „nur Liste“.** 7–8 s vor Ende wird der Kopf des Folgetitels gelesen (R54), teils eine ganze Kette inklusive Unterordner (R57), und Autoplay loopt im Ordner (R60). Jede Nachbardatei muss jederzeit gültigen Inhalt liefern oder selbst hinter Pacing stehen.
4. **Resume nach Mount.** Die HU liest Kopf 1,875 MiB + gespeicherte Position → EOF (R55). Ein Live-Slot muss mit beliebiger Resume-Position umgehen können.
5. **Cache verhindert Aktualisierung.** Daten bleiben minutenlang (R56), ein Cache-Hit erzeugt keinen Read (R9). Neuer Inhalt braucht eine neue Datei/LBA oder einen Cycle (R45 leert den Browse-/Body-Cache, die Position bleibt).
6. **Steuerdateien (Tap als Befehl).** Dateien ≤ 160 Blöcke (80 KiB) liegen nach dem Fresh-Scan schon komplett im Cache → ein Tap erzeugt keinen Read (R58). Ein erkennbarer Befehl braucht Reads jenseits Block 160. Prefetch, Kette und Ordner-Loop lesen Steuerdateien auch ohne Tap (Read ≠ Absicht, R50). Nach dem ersten Lesen wirkt eine Steuerdatei bis zum nächsten Cycle nicht erneut (R9/R45).
7. **Identität und Betrieb.** Der HU-Gerätename kommt aus USB-iProduct (F16); hu-probe im Auto nur mit Profil `bmw`, nicht `lab_debian` (Soft-Detach, I12). Vendor-only- und Phone-like-Identitäten meldet die HU als „nicht unterstützt“ (Facts §10).

**Folgen der BT-Messung (§5.5) für Variante A** — abgeleitet, nicht im Feld getestet:

1. **AVRCP-Target vollständig bedienen.** Die HU fragt Events `05 06 07 09 0c` an und gibt nach sechs Ablehnungen auf. Wer Position, Batterie oder Player-Wechsel anzeigen will, muss diese Events annehmen.
2. **Browsing ist ein echter Pfad.** Die HU fragt die Player-Liste über Browsing ab; eine leere bzw. fehlerhafte Antwort ist heute Standard bei BlueZ ohne MPRIS-Player.
3. **Codec.** AAC wird angeboten; SBC-53 @ 48 kHz liegt über dem bisher gemessenen Coex-Budget. 44,1 kHz oder AAC sind Kandidaten — offen, was die HU hörbar besser verarbeitet.
4. **HFP.** Ohne Telefonie-Funktion den HFP-AG nicht anbieten (oder vollständig mit `+CHLD` beantworten), sonst reconnectet die HU dauerhaft.

Hybrid denkbar (Ton über A/B, UI über C) — zwei Geräte/Stacks, hoher Aufwand.

---

## 8. Offene P0/P1-Fragen

| Priorität | ID | Frage |
|-----------|-----|--------|
| P0 | GATE-01 | Audible / Play-Intent vs. Eager-Read |
| P0 | Q1 (Rest) | BUSY-Pacing über eine **ganze** Datei ≥ 4 MiB mit Ohr; Dauer vs. Inaktivität; CBW-240 |
| P0 | Q16 (Rest) | Einzeldatei ≥ 8 MiB (8/16 MiB mit hörbaren Markern); 2–7,2 MB beantwortet (R53) |
| P1 | Q19 | Wann Kette statt Kopf-Vorlauf; Autoplay über Ordnergrenzen |
| P1 | Q4a–c | Cache-Größe / Multi-File / Eviction (Hinweise R56/R57) |
| P1 | F17 | `cache_place` am 10.11. ohne Dateien |
| P1 | C-Q1/C-Q2 | 6NR/Apps; FIELD-CONNECTED-REAL-01 / FX-G3-01 |
| P0 | B2-A/B2-B | BT-RFCOMM zur HU: Kanal 6 (SPP) und 5 (`deca-fade`) öffnen bzw. HU-Initiative abwarten; vorher HFP-AG aus (Facts §10.4) |
| P1 | C-BT9 | Wer nutzt HU-Kanal 5 (`deca-fade`)? Phone-HCI-Snoop mit MyBMW |
| P1 | BT-Codec | AAC vs. SBC-44,1 hörbar und im Coex-Budget |
| — | Q18 | **geschlossen** (Artefakt, §6) |

Vollkatalog: Facts §8 und Connected-Stack §7.

---

## 9. Quellenverzeichnis

### 9.1 Normativ (dieses Repo)

| ID | Dokument | Inhalt |
|----|----------|--------|
| N1 | [`HU-Technical-Facts.md`](HU-Technical-Facts.md) | Claim-Tabelle E/R/F/M/D/Q/C-D/I |
| N2 | [`HU-PARAMETER-MATRIX.md`](HU-PARAMETER-MATRIX.md) | Parameter-Ops |
| N3 | [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md) | Connected Desk-Abgleich |
| N4 | [`../betrieb/MSC-AKTUELL.md`](../betrieb/MSC-AKTUELL.md) | MSC-Ampel / Lesereihenfolge |
| N5 | [`../planung/MASSNAHMEN-MSC-FULLMENU.md`](../planung/MASSNAHMEN-MSC-FULLMENU.md) | Maßnahmen nach Identity/Detach |
| N6 | [`../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) | Früher Feld-/Lab-Log |

### 9.2 Feld- und Lab-Berichte (Auswahl)

| ID | Quelle | Thema |
|----|--------|-------|
| Fld1 | hu-probe [`heimfahrt`](../../../hu-probe/docs/feld/MSC-HEIMFAHRT.md) | Remount, Eager, Prefetch-Lead |
| Fld2 | hu-probe [`identity-multireview`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/MSC-IDENTITY-REMOUNT.md) | Serial/Label/Vol REJECTED |
| Fld3 | hu-probe [`detach-browse`](../../../hu-probe/docs/feld/archiv/2026-10-22-msc-kampagne/2026-10-23-wire-nachtrag-detach-browse.md) | Drei Schichten, Soft-Remount |
| Fld4 | hu-probe [`unabhängige Auswertung`](../../../hu-probe/docs/feld/MSC-TUR-MOUNT-FACTS.md) | TUR, Mount-Signatur |
| Fld5 | Analyzer [`Feldmatrix 06.11.`](../../../usb-analyzer/docs/reports/2026-11-06-field-host-matrix.md) | E18/F15 |
| Fld6 | PiDrive [`ANALYSE-S3-TONFENSTER`](../betrieb/artifacts-2026-10-08-feld/ANALYSE-S3-TONFENSTER-2026-10-08.md) | Replug, Ring, Cover |
| Fld7 | PiDrive [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md) | Stall-on ~65 s |
| Fld8 | hu-probe [`FELD-2026-11-11 Größenleiter`](../../../hu-probe/docs/feld/FELD-2026-11-11-MSC-GROESSENLEITER.md) | Lauf ungültig (Replay-Deadlock), Ops |
| Fld9 | hu-probe [`FELD-2026-11-10`](../../../hu-probe/docs/feld/FELD-2026-11-10-I303A-REVAL-MSC.md) | iProduct-Name, Soft-Detach, `cache_place` |
| Fld10 | hu-probe [`C1-STAND`](../../../hu-probe/docs/feld/C1-STAND.md) | Feld-Identitäten (nicht unterstützt / Zubehör) |
| Fld11 | bt-analyzer [`FIELD_B1_FROM_A6_20261113T062824Z`](../../../bt-analyzer/docs/evidence/FIELD_B1_FROM_A6_20261113T062824Z.md) | HU-SDP, A2DP, AVRCP, HFP (C-BT1–C-BT8) |
| Fld12 | bt-analyzer [`FIELD_PHONE_HU_LOGCAT_20261114T0924Z`](../../../bt-analyzer/docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md) | Phone↔HU SPP SCN6 OPEN; HU silent ch6 (C-BT15–20) |
| Fld12 | bt-analyzer [`HFP_SLC_A6_20261113`](../../../bt-analyzer/docs/analysis/HFP_SLC_A6_20261113.md) | HFP-SLC-Abbruch an `AT+CHLD=?` |

### 9.3 Audits / Evidence

| ID | Quelle |
|----|--------|
| A1 | technology-audit [`pidrive-2026-bmw-hu`](../../../technology-audit/audits/pidrive-2026-bmw-hu/) |
| A2 | [`hu-probe-heimfahrt-2026-10-22`](../../../technology-audit/audits/hu-probe-heimfahrt-2026-10-22/) |
| A3 | [`hu-probe-bmw-s2-abend-offline-2026-10-18`](../../../hu-probe/audits/hu-probe-bmw-s2-abend-offline-2026-10-18/) |
| A4 | [`esp32-usb-analyzer-2026-field-host-matrix`](../../../technology-audit/audits/esp32-usb-analyzer-2026-field-host-matrix/) |
| A5 | [`bmw-connected-sas-auth-2026-11-06`](../../../technology-audit/audits/bmw-connected-sas-auth-2026-11-06/) |
| A6 | technology-audit [`esp32-bt-analyzer/bmw-nbt-evo`](../../../technology-audit/projects/esp32-bt-analyzer/applications/bmw-nbt-evo.md) |

### 9.4 Fremd / Desk (Control Plane)

| ID | Quelle | Rolle |
|----|--------|-------|
| D1 | [hufman — BMW Connected Apps Protocol](https://hufman.github.io/stories/bmwconnectedapps) | BCL/Etch/SAS/RHMI |
| D2 | [BMWConnectedAnalysis](https://bimmergestalt.github.io/BMWConnectedAnalysis/) | Themenseiten |
| D3 | [BimmerGestalt/AAIdrive](https://github.com/BimmerGestalt/AAIdrive) | Connected-Client |
| D4 | [IDriveConnectKit](https://github.com/BimmerGestalt/IDriveConnectKit) | Etch-IDL |
| D5 | hu-probe [`GATES-Connected.md`](../../../hu-probe/docs/GATES-Connected.md) | Gate-Mapping |
| D6 | hu-probe [`CONNECTED-APP.md`](../../../hu-probe/docs/CONNECTED-APP.md) | Connected-Messpfad |
| D7 | lokaler BimmerGestalt-Download 13.11. (`Bimmer/`, Manifest `MANIFEST_2026-11-13.json`) | Code-Stand für Desk-Pins; `logcat.crash` = C-S8 |

### 9.5 Pflege

- Neue Feld-[B]-Claims zuerst in **HU-Technical-Facts**, dann Kurzübernahme hier.
- Desk-Claims nie still zu Storage-[B] hochstufen.
- Bei Widerspruch gilt die Facts-Tabelle mit verlinktem Artefakt.
- hu-probe-Sessions nur nach `origin`-Filter (`post_finalize` ≠ Trip) und Stream-Vollständigkeitsprüfung als [B] verwenden (Facts §9.1).
- GPT-/KI-Fließtexte nie still als Facts zitieren — Abweichungen in §6 nachziehen.
- Control-Plane-Gates: nur **G1–G4**; RHMI/CDS/AV ohne Gate-ID G5.
