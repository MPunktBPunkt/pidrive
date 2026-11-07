# BMW F20 NBT Evo — HU-Beschreibung und Modellbericht

**Stand:** 2026-11-07 (Korrektur gegen Facts: Prefetch/Stall/CBW/Cache/Gates)  
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
5. [Control Plane — Connected Apps](#5-control-plane--connected-apps)
   - 5.1 Gates G1–G4 (+ Nutzung danach)
   - 5.2 AOA ≠ Connected App
   - 5.3 Feldstand an dieser HU
   - 5.4 SAS, RHMI, CDS, AV
6. [Korrektur der GPT-Zusammenfassung (2026-11-07)](#6-korrektur-der-gpt-zusammenfassung-2026-11-07)
7. [PiDrive-Strategien A / B / C](#7-pidrive-strategien-a--b--c)
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

**Storage Plane:** Die BMW NBT-Evo-HU ist ein aggressiver, dateiorientierter USB-MSC-Host mit mehrstufigem Zustand/Cache, großen READ10-Transfers und nachweislich hoher Toleranz gegenüber USB-Backpressure. Sie konsumiert nicht einfach kontinuierlich Audio, sondern fordert Daten in kontextabhängigen Leseoperationen an und kann daraus lokal weiter abspielen.

**Control Plane:** Parallel existiert eine Connected-App-/Accessory-Kette, deren Transport und höhere Protokollschichten getrennt vom Storage Plane betrachtet werden müssen (AOA/BT → BCL → Etch → SAS; danach RHMI/CDS/AV/AM als Nutzerebene). Desk-[D] stark, F20-Wire noch nicht durchgehend bewiesen.

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
| **Control Plane** | USB AOA und/oder BT | Accessory → BCL → Etch → SAS → RHMI/CDS/AV/AM | **[D]** Desk; Feld nur G1 (+ partielle AOA-Beobachtung) |

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
Dateisystem-Scan (Fresh: 32+128+EOF-Probe je Datei)
     │
     ▼
HU-interne Schicht
     ├── Navigator / Playlist-Position
     ├── Browse- / Titel-Cache
     └── Audio-Body-Cache
              │
              ├── Hit  → Wiedergabe ohne Body-Reads
              └── Miss → Eager Body (oft bis EOF) → Cache → Decoder
```

Kernfakten:

| Aussage | Status | Ref |
|---------|--------|-----|
| Gewählte / vorgelesene Datei oft bis EOF | **[B]** | R2 |
| Leserate nahe USB-FS (~1 MB/s / ~4 ms je 4 KiB Callback) | **[B]** | R1, R15 |
| Nach Vorlesen lange keine Reads bei laufender Wiedergabe | **[B]** | R5 (≥150 s) |
| Cache-Hit → keine Body-Reads | **[B]** | R9 |
| Next-Track / Neighbor wird vorgelesen | **[B]/[S]** | R4, R21, R47 |
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
- UI-Tap liest Umgebung von P, Remount-Read oft head-first Vollatom

**Abspielposition ≠ Lesereihenfolge** ist damit ein Architekturfakt (R23, R24, R33).

### 4.6 Prefetch und Nachbar-Eager

Next-Track-Prefetch **existiert** (R4, R21). Die Lead-Zeit ist **kontextabhängig** (R49) — **kein fixer Lead**:

- situativ ~7,2–7,7 s (MIX / Heimfahrt)
- in ROCK/CLASSIC-Sessions oft **140–240 s** Vorlauf
- Konstanten „8 s“ / „15 s“ als allgemeine Regel: **REJECTED** (auch frühere [S]-Lesart ~15 s + Ausreißer ~7 s ist veraltet)

Drei Read-Modi (R47): Head/Selection · Eager Body (~90–99 %) · Neighbor/LBA-Interleave. **Eager ≠ hörbares Play** (R50) — großer Read beweist keine Audible-Session (GATE-01 offen).

Body-Reads können **vor** Head-Reads kommen (R8) — asynchroner Scanner/Prefetcher.

### 4.7 Stall-Toleranz und Timingproblem

PiDrive will idealerweise Live-Audio liefern; die HU will Dateien in großen READ10-Phasen einsaugen. Stall-Toleranz ist **Feld-FACT**, kein „komplettes Unknown“:

| Größe | Richtwert | Status |
|-------|-----------|--------|
| 512 KiB lesen | ≈ 0,6 s | **[B]** |
| Audio 48 kbit/s | ≈ 6 KiB/s | Rechnung |
| Ringfenster ohne Stall | ≈ 6–9 s | **[B]/[S]** (R25, §6.3 Facts) |
| Stall-on bis EOF (512 KiB) | ≈ 65 s Musik+ID3; BUSY-Retries über Minuten | **[B]** (E7, R29) |
| Kurz-BUSY ohne Host-Reset | 16 Blöcke ~1,6 s, danach normal weiter | **[B]** (R51) |

**REJECTED:** „Kleiner Ring = harte Dauerstrom-Grenze.“ Die HU ist nachweislich **stallexzessiv tolerant** — das Fenster ist größer als die frühere 100-ms-/300-ms-/3-s-Unsicherheitserzählung. Die gemessene BUSY-Toleranz ist eine **reale Designressource** für Backpressure: PiDrive muss nicht zwingend innerhalb jedes 4-KiB-Callbacks „fertig“ sein.

**Q1 Rest** (nicht „Q1 komplett offen“): Gesamtdauer pro Kommando vs. datenlose Inaktivität; dabei CBW-Blockzahl mitdenken (`blocks=240` → Retry hängt an ~122 KiB Datenphase, nicht an 4 KiB). Keine scheinpräzise Millisekunden-Grenze, solange blocks × Datenphase × Idle nicht systematisch vermessen sind. **Q16** (Größenleiter) bleibt bewusst offen (27.10. Capture-Body verloren).

Konsequenz: PiDrive muss die **Read-Requests** so bedienen, dass die HU-Illusion eines normalen MSC-Sticks erhalten bleibt — nicht „Audio tropfenweise nach Decoderuhr“.

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

### 5.4 SAS, RHMI, CDS, AV

Nach Desk (BimmerGestalt / AAIdrive):

- **SAS:** Cert → Challenge → Signatur → Login — Hard Stop ohne gültiges Material; Beobachtung gewünscht, keine Challenge-Fälschung als Ziel.
- **RHMI:** native iDrive-Widgets; Layouts an Cert-SHA256 gebunden — freie XML **REJECTED**.
- **CDS:** Fahrzeugdaten (Desk); Property-Verfügbarkeit am F20 ungemessen.
- **AV:** Entertainment-Kontext; ob Audio-Payload über Etch/BCL läuft oder nur Fokus + BT/A2DP: **UNKNOWN**. AAIdrive selbst verweist auf BT-Audio bei eingeschränktem AOA2-Audio.

Voraussetzung Fahrzeug: Apps/6NR bzw. ConnectedDrive-Apps — sonst ist Pfad C tot (C-Q1).

---

## 6. Korrektur der GPT-Zusammenfassung (2026-11-07)

Gegenprüfung gegen [`HU-Technical-Facts.md`](HU-Technical-Facts.md) (Stand 2026-11-06+, R46–R52, E18/F15): Das **Zwei-Plane-Modell** und der PiDrive-Vertrag („kein Audio-Player, sondern dateiorientierter MSC-Host mit Cache“) sind korrekt. Die alte Storage-Plane-Erzählung ist als Architektur-Skizze brauchbar, aber **nicht als Faktenreferenz zitierfähig**. Vier konkrete Fehler und zwei kleinere Punkte:

| # | GPT-Aussage | Bewertung | Korrektur (Facts) |
|---|-------------|-----------|-------------------|
| 1 | Prefetch „~15 s vor Ende“, Ausreißer ~7 s → [S] | **veraltet / REJECTED** | Lead **kontextabhängig** (R49/R21): situativ ~7,2–7,7 s; ROCK/CLASSIC **140–240 s**. „8 s“ und „15 s“ als Konstante **REJECTED** |
| 2 | Stall-Toleranz / Q1 „komplett offen“ (100 ms / 300 ms / 3 s?) | **falsch dargestellt** | Stall **Feld-FACT**: E7/R29 (BUSY über Minuten, ~65 s bis EOF); R51 (~1,6 s BUSY ohne Reset). Q1 nur noch Rest: Dauer vs. Idle + CBW-Größe |
| 3 | „HU immer 4 KiB“, seriell = FACT | **vermengt Ebenen** | Callback 4 KiB (E5) ≠ CBW oft **8/240** (E11). Track-Atom `240+69`. Timing = CBW-Sicht |
| 4 | „ein Media Cache“ | **zu grob** | ≥3 Zustände (R45): Navigator/Position ≠ Browse/Lib ≠ Audio-Body; unterschiedliches Invalidierungsverhalten |
| — | Gate **G5** (RHMI/CDS/AV) | **konkurrierendes Modell** | Referenz = **G1–G4**; RHMI/… = Nutzung **nach** G4 (`a68ef3b`) |
| — | Queue-Tiefe 1 als bedingungsloses FACT | **zu hart** | protokollbedingt **[B]**; Wire QD-max **UNKNOWN** / `INFERRED` (E6) |

**Richtig wiedergegeben** in der GPT-Fassung u. a.: R16 (nichtlineare Reads), R24 (Abspielposition ≠ Lesereihenfolge), R5 (keine Reads während Wiedergabe), ~9-s-Tonfenster-Konsequenz, Zwei-Plane-Epistemik.

**Praktische Konsequenz:** Backpressure-Planung geht von **gemessener hoher Stall-Toleranz** (E7/R29/R51) aus, mit Q1-Rest und Q16 als offenen Flanken — nicht von „Q1 = komplettes Unknown“. Storage-Korrekturen berühren **I-303A / G1** nicht.

---

## 7. PiDrive-Strategien A / B / C

| Variante | Pfad | Stand | Stärke | Risiko |
|----------|------|-------|--------|--------|
| **A** | BT A2DP + AVRCP | aktiv | stabiler Ton/Metadaten-Grundpfad | Cover/UI limitiert |
| **B** | Storage Plane / USB-MSC | Golden Path + Messung | Cover, HU-USB-UI, gut vermessen | Live vs. Eager-Read-Ahead |
| **C** | Control Plane / Connected | Forschung | native RHMI/AV-Nähe | Gates, Certs, 6NR, Wire offen |

Für Variante B bleibt die Leitfrage: Reads so bedienen (Stall/Backpressure über CBW-Datenphasen, gültige Heads, FULLMENU-Vertrag), dass Cache/Prefetch der HU **stick-kompatibel** bleiben. Arbeitsgrundlage = hohe Stall-Toleranz; Decoder-Experimente ohne Q1-Rest/Q16/GATE-01 lösen das Timingproblem nicht.

Hybrid denkbar (Ton über A/B, UI über C) — zwei Geräte/Stacks, hoher Aufwand.

---

## 8. Offene P0/P1-Fragen

| Priorität | ID | Frage |
|-----------|-----|--------|
| P0 | GATE-01 | Audible / Play-Intent vs. Eager-Read |
| P0 | Q16 | Größenleiter ≫158 KiB (27.10. Capture verloren) |
| P0 | Q1 (Rest) | Timeout-Modell Dauer vs. Inaktivität; CBW-240 |
| P1 | Q4a–c | Cache-Größe / Multi-File / Eviction |
| P1 | Q18 | Semantik 395xxx-LBA-Probe beim Remount |
| P1 | C-Q1/C-Q2 | 6NR/Apps; FIELD-CONNECTED-REAL-01 / FX-G3-01 |

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

### 9.3 Audits / Evidence

| ID | Quelle |
|----|--------|
| A1 | technology-audit [`pidrive-2026-bmw-hu`](../../../technology-audit/audits/pidrive-2026-bmw-hu/) |
| A2 | [`hu-probe-heimfahrt-2026-10-22`](../../../technology-audit/audits/hu-probe-heimfahrt-2026-10-22/) |
| A3 | [`hu-probe-bmw-s2-abend-offline-2026-10-18`](../../../hu-probe/audits/hu-probe-bmw-s2-abend-offline-2026-10-18/) |
| A4 | [`esp32-usb-analyzer-2026-field-host-matrix`](../../../technology-audit/audits/esp32-usb-analyzer-2026-field-host-matrix/) |
| A5 | [`bmw-connected-sas-auth-2026-11-06`](../../../technology-audit/audits/bmw-connected-sas-auth-2026-11-06/) |

### 9.4 Fremd / Desk (Control Plane)

| ID | Quelle | Rolle |
|----|--------|-------|
| D1 | [hufman — BMW Connected Apps Protocol](https://hufman.github.io/stories/bmwconnectedapps) | BCL/Etch/SAS/RHMI |
| D2 | [BMWConnectedAnalysis](https://bimmergestalt.github.io/BMWConnectedAnalysis/) | Themenseiten |
| D3 | [BimmerGestalt/AAIdrive](https://github.com/BimmerGestalt/AAIdrive) | Connected-Client |
| D4 | [IDriveConnectKit](https://github.com/BimmerGestalt/IDriveConnectKit) | Etch-IDL |
| D5 | hu-probe [`GATES-Connected.md`](../../../hu-probe/docs/GATES-Connected.md) | Gate-Mapping |
| D6 | hu-probe [`CONNECTED-APP.md`](../../../hu-probe/docs/CONNECTED-APP.md) | Connected-Messpfad |

### 9.5 Pflege

- Neue Feld-[B]-Claims zuerst in **HU-Technical-Facts**, dann Kurzübernahme hier.
- Desk-Claims nie still zu Storage-[B] hochstufen.
- Bei Widerspruch gilt die Facts-Tabelle mit verlinktem Artefakt.
- GPT-/KI-Fließtexte nie still als Facts zitieren — Abweichungen in §6 nachziehen.
- Control-Plane-Gates: nur **G1–G4**; RHMI/CDS/AV ohne Gate-ID G5.
