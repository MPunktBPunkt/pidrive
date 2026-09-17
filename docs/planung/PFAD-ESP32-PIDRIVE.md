# Pfad: von der USB-MSC-Idee zu `esp32.pidrive` + PiDrive-Umbau

**Status:** Firmware-Lab läuft — **PUMP Menü+Activate** in [`esp32.pidrive` 0.3.1-dev](https://github.com/MPunktBPunkt/esp32.pidrive); Pi-Umbau (`usb_gadget`) noch offen  
**Stand:** 2026-09-17  
**Idee (Voraussetzung):** [IDEE-USB-MSC-MENUE.md](IDEE-USB-MSC-MENUE.md)  
**Konzept (Architektur):** [KONZEPT-USB-MSC.md](KONZEPT-USB-MSC.md)  
**Firmware-Repo / PUMP-Doku:** [`esp32.pidrive`](https://github.com/MPunktBPunkt/esp32.pidrive) · [PUMP.md](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/PUMP.md)  
**Vorbild Dokumentenladder:** `esp32.bt-gateway` (`PFLICHTENHEFT.md`, `OFFENE-PUNKTE.md`, `PHASE-0-MESSPLAN.md`, `PIDRIVE-INTEGRATION.md`)  
**Zielrepos:** `esp32.pidrive` (PlatformIO/Arduino auf S3) · Umbau in `pidrive`

---

## 0. Wozu dieses Dokument

Die USB-MSC-Idee ist ausgearbeitet, aber noch keine Spezifikation. Dieses Dokument beschreibt **wie** daraus werden:

1. ein **Pflichtenheft** für das ESP-Projekt `esp32.pidrive`, und  
2. ein **Umbauplan** für PiDrive (Renderer, Audio-Ausgang, Betriebsmodi, CLI/Abnahme),

ohne vor den Fahrzeug-Gates Code oder Repo-Skeleton zu erzwingen.

---

## 1. Abgrenzung zu `esp32.bt-gateway`

| | `esp32.bt-gateway` | `esp32.pidrive` (geplant) |
|--|--------------------|---------------------------|
| Chip | Classic **ESP32** (BR/EDR) | **ESP32-S3** (USB-OTG) |
| Auto-Schnittstelle | A2DP + AVRCP (Bluetooth) | USB-MSC + on-the-fly-MP3 |
| Pi-Link | PDAP über WLAN | **PUMP** — V1 über zweiten USB (UART/CDC), optional WLAN; nicht BLE-Audio |
| UI am BMW | 3 Zeilen (Browsing tot) | USB-Medienliste (Ordner/Dateien) |
| Ton zum BMW | SBC über A2DP | MP3-Sektoren über MSC |
| Status | Planung weit fortgeschritten | **Firmware 0.3.1-dev Lab** (MSC + SoftAP + PUMP Menü) |

**Produktentscheidung (Tendenz, 2026-09-17):** USB-Pfad **neben** dem bestehenden Bluetooth-Pfad — BlueZ/A2DP/AVRCP bleiben; neuer `audio_output=usb_gadget`. Je Sitzung genau **ein** aktiver Hörpfad zum BMW. Details: §1.1 und §2a.

---

## 1.1 Parallelbetrieb in PiDrive: BT belassen, USB addieren

**Ja — das ist das Zielmodell.** Der bisherige Bluetooth-Pfad wird nicht ersetzt und nicht „umgebaut, bis USB geht“. USB ist ein **weiterer Ausgang**, analog zu dem, was für `esp32.bt-gateway` schon als `audio_output=gateway` geplant ist.

### Ist heute

`audio_output` ∈ `{auto, klinke, bt, hdmi}` — CLI `pidrivectl audio route …`. Quellen und Menülogik sind davon getrennt; nur die Senke wechselt.

### Soll mit USB-Gadget

```
Quellen (DAB, Spotify, Webradio, …)     Menübaum (UID-API)
              │                                │
              ▼                                ▼
         Audio-Engine              Renderer je nach aktivem Pfad
              │                     ├─ bt → MPRIS 3 Zeilen
              │                     └─ usb_gadget → FAT-Export (Dateinamen)
              ▼
   audio_output =
     bt         → BlueZ A2DP → BMW          (unverändert)
     klinke/hdmi→ ALSA                      (unverändert)
     usb_gadget → PUMP → esp32.pidrive → BMW-USB-MSC  (neu)
     gateway    → PDAP → esp32.bt-gateway → BMW-BT    (geplant, anderes Repo)
```

| Regel | Bedeutung |
|-------|-----------|
| Code | BlueZ-/AVRCP-/MPRIS-Code bleibt; USB = neuer Client + Route |
| Laufzeit | **Ein** Hörpfad zum Auto gleichzeitig — nicht BT und USB parallel zum selben BMW |
| iDrive | Fahrer wählt Kachel „Bluetooth Audio“ **oder** „USB“; PiDrive folgt bzw. setzt `audio route` |
| Menü | Eine UID-API; zwei Renderer |
| DAB | Direct-ALSA-Bypass muss für `usb_gadget` bewusst mitgezogen werden (sonst stumm) — gleiches Thema wie beim BT-Gateway |

Arbeitspaket dazu: **U1** in §6. Owner-Frage **Q-USB-1** damit tendenziell beantwortet („neben“, nicht „statt“).

---

## 2. Hardware-Feststellung (Eingang in jedes Pflichtenheft-Kapitel)

Unter der Ist-Randbedingung **Pi 4: USB-C = nur Versorgung**:

- die **USB-A-Ports sind Host-only** → Pi allein kann dem BMW **keinen** virtuellen Stick zeigen;
- **Device-HW ist Pflicht** → Arbeitszielchip **ESP32-S3** im Projekt `esp32.pidrive`;
- Pi bleibt Gehirn (Quellen, Menü-UIDs, Encode oder PCM-Lieferung); S3 = MSC + Vorpuffer + HU-Timing.

Details: [IDEE-USB-MSC-MENUE.md](IDEE-USB-MSC-MENUE.md) §4.5.1.

### 2.1 Verkabelung Auto ↔ ESP (BMW-Seite)

Geplante Ist-Nutzung:

```
ESP32-S3  native USB (Device/OTG)
    │  Kabel USB-C ↔ USB-A (oder Board-seitig USB-A-Male)
    ▼
BMW NBT Evo  USB-Host-Buchse  (Armlehne o. Ä.)
```

Darüber läuft **nur** MSC + on-the-fly-MP3 zum Auto. Das ist **nicht** der Pi↔ESP-Link.

### 2.2 Zweite USB-Buchse am ESP32-S3-Board

Viele S3-Boards haben **zwei** physische USB-Buchsen — das sind **nicht** zwei volle OTG-Controller:

| Buchse (typisch) | Funktion | Parallel zum BMW-USB? |
|------------------|----------|------------------------|
| **USB / native OTG** | SoC GPIO19/20 → TinyUSB MSC Device | **diese** steckt am BMW |
| **UART / COM / USB-to-UART** | Bridge-Chip (CP210x, CH340, …) → UART0 | kann am **Pi USB-A (Host)** hängen |

Der native Controller ist **entweder** Host **oder** Device, nicht beides gleichzeitig auf demselben PHY. Die UART-Bridge ist ein **separater Chip** und kann **gleichzeitig** mit MSC-Device betrieben werden.

Zusätzlich: USB-OTG und USB-Serial-JTAG im SoC teilen sich oft **einen** internen PHY — für MSC am Auto die UART-Bridge-Buchse nutzen (nicht auf „beide native Funktionen parallel“ spekulieren).

---

## 2a. Pi ↔ ESP: wie kommunizieren? (PUMP-Transport)

Protokoll-Arbeitstitel **PUMP** (PiDrive USB Media Protocol): Control (Play-UID, Status, Buffer), Audio (PCM **oder** MP3-Frames), optional Menü-Seiten. Der **Transport** darunter ist wählbar.

**Wichtig:** „Bluetooth“ hier meint **nicht** den BMW-A2DP-Pfad. Der ESP32-S3 hat **kein** Classic-BT — nur BLE (+ WiFi + USB).

### Vergleich

| Transport | Bandbreite / Eignung | Verkabelung | Bewertung |
|-----------|----------------------|-------------|-----------|
| **A. USB-UART / CDC am zweiten Port** | Seriell bis ~1–3 Mbaud bzw. CDC: genug für **MP3-CBR** (~128–192 kbit/s) + Control; PCM stereo 44,1 kHz eng | Pi USB-A → ESP „UART“-Buchse; ESP OTG → BMW | **Empfehlung Labor + feste Einbaunähe** |
| **B. WLAN** (SoftAP/STA, wie PDAP) | PCM und MP3 problemlos | kein Kabel Pi↔ESP; ESP nur am BMW-USB | **Empfehlung wenn ESP an Armlehne, Pi entfernt** |
| **C. BLE** | für Live-Audio **zu schwach / ungeeignet**; höchstens Control | kabellos | **Nur Control — kein Audio-Transport** |
| **D. GPIO-UART** (TX/RX/GND) | wie A, ohne zweiten USB-Stecker | Litze Pi↔ESP | Alternative zu A im Eigenbau |
| **E. ESP als zweiter USB-Host** am Pi | OTG müsste Host sein → **Konflikt** mit Device am BMW | — | **verworfen**, solange ein PHY Device am Auto ist |

### Empfohlene Staffelung

1. **V1-Transport: A (zweiter USB = UART/CDC)** — deterministisch, kein WiFi-Jitter, Flash/Console dieselbe Buchse, passt zu „Pi hat freie USB-A-Hosts“.  
   Voraussetzung: Kabelreichweite Pi↔ESP akzeptabel (Handschuhfach / Mittelkonsole nah genug) **oder** langes USB-Kabel.
2. **V1.1 / Feld: B (WLAN)** — wenn der ESP fest an der BMW-USB-Buchse sitzt und der Pi woanders; PUMP über TCP/UDP analog PDAP-Ideen, aber **eigenes** Protokoll/Repo (`esp32.pidrive`, nicht PDAP vom BT-Gateway vermischen).
3. **BLE:** höchstens später für „ESP wach / Pairing-Hilfe“, **nicht** für den Hörstream.
4. **Encode auf dem Pi (Tendenz Q-USB-2):** MP3-Frames über PUMP → ESP puffert und bedient MSC. Entlastet S3-CPU und senkt die nötige Link-Rate gegenüber Roh-PCM.

### Referenz-Topologie (V1: zwei Kabel am ESP)

```
  5 V Netzteil ──► Pi 4 USB-C (nur Power)

  CSR-BT, RTL-SDR ──► Pi 4 USB-A (Host, unverändert)
  PUMP (CDC/UART) ──► Pi 4 USB-A (Host) ──► ESP „UART“-USB
                                              │
                                              │ ESP32-S3
                                              │
                         BMW USB-Host ◄── OTG-USB (Device, MSC+MP3)
```

Kabellos-Variante: UART-Link entfällt; Pi und ESP über WLAN; nur noch ESP-OTG→BMW.

### Was PUMP mindestens transportieren muss

| Richtung | Inhalt |
|----------|--------|
| Pi → ESP | Stream starten/stoppen; MP3- oder PCM-Frames; optional Directory-Snapshot / Station-Liste; Heartbeat |
| ESP → Pi | Buffer-Füllstand; aktive Datei / vermutete UID; USB enumerated ja/nein; Fehler; Action-MP3 getroffen |

Byte-Layout und Framing: kanonisch in [`esp32.pidrive` PUMP.md](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/PUMP.md) (V0.3 line-JSON). Live-MP3-Frames noch offen.

### Lab-Ist (2026-09-17)

| Thema | Stand |
|-------|--------|
| Firmware | `esp32.pidrive` **0.3.1-dev** SoftAP + MSC + PUMP |
| Bridge | `tools/pump_bridge.py` → `/tmp/pidrive_menu.json` / `/tmp/pidrive_cmd` |
| Menü | aktuelle Seite, max. 4 MSC-Slots; Navigation per activate |
| Audio USB | **0.4.0-dev Lab:** Live-MP3 im ESP-Puffer (48 kbit/s); Sample `GET /api/lab/stream` OK — Stick-Player am Host noch Feldtest |
| Pi-Paket | `usb_pump_client` / `audio_output=usb_gadget` noch offen |

---

## 3. Dokumentenladder (wie beim BT-Gateway)

Nicht alles auf einmal. Reihenfolge:

```
IDEE-USB-MSC-MENUE.md          ← Idee + Dension + HW-Voraussetzungen
        │
        ▼
KONZEPT-USB-MSC.md             ← Architektur, PUMP, FAT-MVP, Parallel-BT
        │
        ▼
Stick-Spike / BMW-USB-MSC-PROBE.md   ← Gate Fahrzeug (P-V1…P-V3)
        │
        ▼
PFAD-ESP32-PIDRIVE.md (dieses Doc)   ← Gates, Pflichtenheft-TOC, Umbaupakete
        │
        ├──────────────────────────────┐
        ▼                              ▼
Repo esp32.pidrive                     pidrive
  PFLICHTENHEFT.md                       docs/planung/UMBAU-USB-MSC.md
  OFFENE-PUNKTE.md                       (Arbeitspakete U0…Un)
  PHASE-0-MESSPLAN.md                    FEATURES / CLI / audio_output
  HUB-INTEGRATION.md (optional)
        │                              │
        └──────── Implementierung nach gemeinsamen Gates ────────┘
```

**Regel analog BT-Gateway:** Kein Firmware-Ordner / kein Produktiv-Umbau in `pidrive`, solange die Gates in §5 rot sind. Pflichtenheft-Kapitel mit `[FIX]` erst nach Gate-Freigabe; davor `[ENTWURF — Gate: …]`.

---

## 4. Skizze Pflichtenheft `esp32.pidrive`

Neues Repo (Vorschlag Struktur wie `esp32.bt-gateway/docs/planung/`):

| Dokument | Inhalt |
|----------|--------|
| `README.md` | Ein Satz Zweck, Chip, Nicht-Ziele |
| `docs/planung/PFLICHTENHEFT.md` | Verbindliche Spec (Kapitel unten) |
| `docs/planung/OFFENE-PUNKTE.md` | A-/Q-Entscheidungen, Reihenfolge |
| `docs/planung/PHASE-0-MESSPLAN.md` | Analyzer am echten BMW-USB (Reads, Prefetch, Buffer) |
| `docs/planung/PIDRIVE-INTEGRATION.md` | Was Pi liefern/empfangen muss |
| `docs/planung/HUB-INTEGRATION.md` | Optional: Flash/OTA über `iobroker.esp-hub` |
| `STATE.md` | Kurzer Projektstand |

### 4.1 Vorgeschlagene Pflichtenheft-Kapitel

Marken später `[FIX]` / `[ENTWURF — Gate: …]` wie im BT-Gateway.

| Kap. | Thema | Gate / Abhängigkeit |
|------|--------|---------------------|
| 1 | Zweck, Akteure; BT-Pfad bleibt parallel (`audio_output`) | Q-USB-1 Tendenz „neben“ |
| 2 | Systemarchitektur & Verantwortungsgrenzen (Pi / ESP / BMW / Hub) | HW §2 |
| 3 | Explizite Nicht-Ziele (kein Classic-BT auf S3, kein Variante-A-Hauptpfad, kein BLE-Audio, …) | Scope |
| 4 | Phase −1 / 0 — Stick-Spike + USB-Analyzer am NBT Evo | P-V*, Probe-Doc |
| 5 | USB Device Stack (TinyUSB MSC, Descriptors, Timing-Profile à la K61) | Phase 0 |
| 6 | Virtuelles FAT (Layout, Dateigrößen, Rebuild-Politik, Action-MP3s) | Scope MVP |
| 7 | Audio: Encode-Ort, Vorpuffer/ABSA-Äquivalent, Seek-Verhalten | Q-USB-2 |
| 8 | Protokoll **PUMP** + **Transport** (UART/CDC V1, WLAN optional) | Q-USB-3 |
| 9 | Auswahl-Erkennung (Read-Heuristik → `activate`/`next`) | Phase 0 |
| 10 | Betriebsmodi (USB enumerated, Streaming, Fail-Soft; WLAN-Setup nur wenn Transport B) | — |
| 11 | Diagnose / WebUI / Logs | Hub optional |
| 12 | Flash-Budget, Partitionen, OTA | Hub / Flash-Messung |
| 13 | Abnahmekriterien (Erkennung, 3 min Dauerbetrieb, Umschaltzeit, CLI) | — |

### 4.2 Verantwortungsgrenzen (Entwurf)

| Komponente | Kennt | Kennt nicht |
|------------|-------|-------------|
| **PiDrive** | Quellen, Menü-UIDs, Activate, PCM oder MP3 erzeugen, PUMP-Client, Modus `audio_output=usb_gadget` | USB-Deskriptoren, FAT-Sektoren, HU-Timing |
| **esp32.pidrive** | USB Device, virtuelles FAT, Vorpuffer, Read-Heuristik, PUMP-Server, ggf. MP3-Encode | DAB/Spotify-Semantik, BlueZ |
| **BMW** | USB-Host, Medien-UI, MP3-Decode | Herkunft der Bytes |
| **esp-hub** (opt.) | Flash/OTA/Inventar | Audio/USB-Logik |

### 4.3 MVP-Schnitt (Empfehlung für V1 des Pflichtenhefts)

Nicht der volle PiDrive-Baum. Dension-nah:

1. Flache `Stations/`-Liste (Favoriten + letzte DAB/FM/Web).  
2. `Settings/` mit Action-MP3s (`Scan.mp3` nur wenn sinnvoll, `About.mp3`).  
3. Ein Live-Stream on-the-fly.  
4. Tiefer Menübaum = V1.1+ nach stabilem Ton.

---

## 5. Gates bevor Pflichtenheft `[FIX]` und Umbau starten

| Gate | Ort | Kriterium | Blockiert |
|------|-----|-----------|-----------|
| **G-USB-0** | Fahrzeug | Stick-Spike: P-V1–P-V3 grün → `BMW-USB-MSC-PROBE.md` | alles Weitere |
| **G-USB-1** | Owner | Scope: Radio-flach-MVP vs. Abbruch vs. nur BT | Pflichtenheft Kap. 3/6 |
| **G-USB-2** | Labor/Auto | ESP MSC + eine Endlos-MP3 (Datei) am NBT Evo erkannt und spielbar | Kap. 5/7 |
| **G-USB-3** | Auto | Live PCM→MP3 ≥ 3 min ohne Dropouts; Umschaltzeit gemessen | Encode festnageln |
| **G-USB-4** | Beide Repos | PUMP-Minimal (Play-UID + Stream + Status) Laptop↔ESP | PiDrive-Umbau Produktiv |

Erst nach G-USB-0 sinnvoll: Repo `esp32.pidrive` anlegen und Pflichtenheft-Skeleton committen. Vorher reicht die Skizze hier.

---

## 6. Skizze Umbauplan PiDrive (`UMBAU-USB-MSC.md`)

Später eigenes Dokument unter `docs/planung/`. Arbeitspakete (Vorschlag):

| Paket | Ziel | Abhängigkeit |
|-------|------|--------------|
| **U0** | Sicherheitsnetz: FEATURES-Zeilen, CLI-Hooks, keine Regression BT/Klinke | vor jedem Umbau |
| **U1** | `audio_output=usb_gadget` **neben** `bt`/`klinke`/`hdmi` — BT-Code unverändert; nie zwei Hörpfade parallel zum BMW | G-USB-1 |
| **U2** | PUMP-Client (Status, connect, buffer KPIs) | G-USB-4 |
| **U3** | Audio-Pfad: Capture/Resample → PCM oder MP3 → PUMP | Encode-Entscheidung |
| **U4** | Menü-Renderer „USB-FAT-Export“ (UID→Pfad/Dateiname, paginiert/flach) | UID-API (Menü-Auftrag) |
| **U5** | Activate von Gadget-Events (`play_uid`, Action-MP3s) → Trigger-Dispatcher | U2+U4 |
| **U6** | `pidrivectl usb status\|probe\|push` für Fahrzeug-SSH | U2 |
| **U7** | WebUI: Gadget online/buffer/aktive Datei (kein zweites Menühirn) | U2 |
| **U8** | Abnahme HD-USB-1…n am Auto; Doku RUNTIME_FLOWS Abschnitt USB | G-USB-3 |

**Nicht** im Umbauplan: AVRCP-Browsing wiederbeleben; Menülogik nur im ESP; Variante A als Produktziel.

**Vorarbeit die sich lohnt unabhängig vom USB-Pfad:** kopflose UID-Menü-API ([AUFTRAG-MENUE-UND-GATEWAY.md](../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md)) — gleicher Vertrag für WebUI, CLI und späteren FAT-Export.

---

## 7. Offene Owner-Fragen (für `OFFENE-PUNKTE` im ESP-Repo)

| ID | Frage | Stand / Tendenz | Wirkung |
|----|--------|-----------------|---------|
| **Q-USB-1** | USB neben / statt BT? | **Tendenz: neben** (§1.1) — Owner-OK noch offen | Repo-Priorität |
| **Q-USB-2** | Encode auf Pi oder S3? | Tendenz: **Pi → MP3-Frames** | PUMP-Bandbreite, S3-CPU |
| **Q-USB-3** | Pi↔ESP-Transport? | Tendenz: **V1 = zweiter USB (UART/CDC)**; WLAN wenn Abstand; **nicht BLE-Audio** (§2a) | Verkabelung |
| **Q-USB-4** | V1 nur flache Stationsliste? | offen | Pflichtenheft Kap. 3 |
| **Q-USB-5** | Hub-OTA von Tag 1? | offen | Flash-Partitionen |
| **Q-USB-6** | Max. Senderwechsel-Zeit (s)? | offen | Puffergröße |
| **Q-USB-7** | Dension als Messgerät? | offen | Zeit vs. Geld |

---

## 8. Empfohlene nächste konkrete Schritte

1. **Jetzt (pidrive-Repo):** Idee + dieser Pfad gepflegt halten; keine Firmware.  
2. **Nächste Fahrzeugsitzung:** Stick-Spike → `docs/fahrzeug/BMW-USB-MSC-PROBE.md` (G-USB-0).  
3. **Owner:** Q-USB-1 („neben“ bestätigen) und Q-USB-4; Q-USB-3 Tendenz UART/CDC vs. WLAN nach Einbauplan.  
4. **Bei grünem Gate:** Repo `esp32.pidrive` anlegen, Pflichtenheft-Skeleton mit `[ENTWURF]`-Kapiteln aus §4.1, `OFFENE-PUNKTE` mit Q-USB-*.  
5. **Parallel in pidrive:** `UMBAU-USB-MSC.md` aus §6 — U1 = Route additiv, BT unangetastet.  
6. **Menü-UID-API** weiter wie geplant (nützt USB und Nicht-USB).

---

## 9. Entscheidungsstatus

| Datum | Stand |
|-------|--------|
| 2026-09-17 | Pfad skizziert: HW-Pflicht S3, Dokumentenladder, Pflichtenheft-TOC, Umbaupakete U0–U8, Gates G-USB-0…4, Owner-Fragen |
| 2026-09-17 | §1.1 Parallel-BT; §2a PUMP-Transport (UART/CDC V1, WLAN optional, BLE nicht für Audio); Q-USB-1/2/3 Tendenzen |
| 2026-09-17 | Konzept V0.2; **Repo [`esp32.pidrive`](https://github.com/MPunktBPunkt/esp32.pidrive) angelegt** (Hub-Pflicht, Lab-Plan) |

Nächstes Dokument nach Messung: `BMW-USB-MSC-PROBE.md`. Spec: `esp32.pidrive/docs/planung/PFLICHTENHEFT.md`.
