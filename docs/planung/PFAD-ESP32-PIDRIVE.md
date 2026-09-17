# Pfad: von der USB-MSC-Idee zu `esp32.pidrive` + PiDrive-Umbau

**Status:** Planungsskizze — noch **kein** verbindliches Pflichtenheft, noch **kein** Implementierungsauftrag  
**Stand:** 2026-09-17  
**Idee (Voraussetzung):** [IDEE-USB-MSC-MENUE.md](IDEE-USB-MSC-MENUE.md)  
**Vorbild Dokumentenladder:** `esp32.bt-gateway` (`PFLICHTENHEFT.md`, `OFFENE-PUNKTE.md`, `PHASE-0-MESSPLAN.md`, `PIDRIVE-INTEGRATION.md`)  
**Zielrepos:** neu `esp32.pidrive` (ESP-IDF, ESP32-S3) · Umbau in `pidrive`

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
| Pi-Link | PDAP über WLAN | eigenes schmales Protokoll (Arbeitstitel **PUMP** — PiDrive USB Media Protocol; Name offen) |
| UI am BMW | 3 Zeilen (Browsing tot) | USB-Medienliste (Ordner/Dateien) |
| Ton zum BMW | SBC über A2DP | MP3-Sektoren über MSC |
| Status | Planung weit fortgeschritten | Idee + dieser Pfad |

**Produktentscheidung (offen, Q-USB-1):** Parallel betreiben (BT *oder* USB je Sitzung), USB ersetzt BT als Hörpfad, oder nur eines der beiden Gateways bauen. Bis Stick-Spike + Scope-Entscheidung keine Repo-Priorität gegen das BT-Gateway festnageln.

---

## 2. Hardware-Feststellung (Eingang in jedes Pflichtenheft-Kapitel)

Unter der Ist-Randbedingung **Pi 4: USB-C = nur Versorgung**:

- die **USB-A-Ports sind Host-only** → Pi allein kann dem BMW **keinen** virtuellen Stick zeigen;
- **Device-HW ist Pflicht** → Arbeitszielchip **ESP32-S3** im Projekt `esp32.pidrive`;
- Pi bleibt Gehirn (Quellen, Menü-UIDs, Encode oder PCM-Lieferung); S3 = MSC + Vorpuffer + HU-Timing.

Details: [IDEE-USB-MSC-MENUE.md](IDEE-USB-MSC-MENUE.md) §4.5.1.

---

## 3. Dokumentenladder (wie beim BT-Gateway)

Nicht alles auf einmal. Reihenfolge:

```
IDEE-USB-MSC-MENUE.md          ← erledigt (Idee + Dension + HW)
        │
        ▼
Stick-Spike / BMW-USB-MSC-PROBE.md   ← Gate Fahrzeug (P-V1…P-V3)
        │
        ▼
PFAD-ESP32-PIDRIVE.md (dieses Doc)   ← Skizze Pflichtenheft + Umbauplan
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
| 1 | Zweck, Akteure, Abgrenzung zu BT-Gateway | Q-USB-1 |
| 2 | Systemarchitektur & Verantwortungsgrenzen (Pi / ESP / BMW / Hub) | HW §2 |
| 3 | Explizite Nicht-Ziele (kein Classic-BT, kein Variante-A-Hauptpfad, kein voller Baum in V1, …) | Scope |
| 4 | Phase −1 / 0 — Stick-Spike + USB-Analyzer am NBT Evo | P-V*, Probe-Doc |
| 5 | USB Device Stack (TinyUSB MSC, Descriptors, Timing-Profile à la K61) | Phase 0 |
| 6 | Virtuelles FAT (Layout, Dateigrößen, Rebuild-Politik, Action-MP3s) | Scope MVP |
| 7 | Audio: PCM-Eingang, MP3-Encode-Ort, Vorpuffer/ABSA-Äquivalent, Seek-Verhalten | Encode-Entscheidung |
| 8 | Protokoll **PUMP** Pi↔ESP (Control, Audio/MP3-Frames, Status, Menu-Page) | Integration |
| 9 | Auswahl-Erkennung (Read-Heuristik → `activate`/`next`) | Phase 0 |
| 10 | Betriebsmodi (Setup SoftAP, Streaming, Fail-Soft, USB-Disconnect) | — |
| 11 | Diagnose / WebUI / Logs ohne Kabel am Auto | Hub optional |
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
| **U1** | Betriebsmodus `audio_output=usb_gadget` \| `bt` \| `local` — klar getrennt | G-USB-1 |
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

| ID | Frage | Wirkung |
|----|--------|---------|
| **Q-USB-1** | USB-Pfad neben, statt, oder statt erst nach BT-Gateway? | Repo-Priorität, Hardware-Budget |
| **Q-USB-2** | Encode auf Pi oder auf S3? | PUMP-Bandbreite, S3-CPU, Latenz |
| **Q-USB-3** | Pi↔ESP: WLAN (wie PDAP) oder UART/USB-Serial? | Verkabelung, Coexistence |
| **Q-USB-4** | V1 nur flache Stationsliste — bestätigt? | Pflichtenheft Kap. 3 |
| **Q-USB-5** | Hub-OTA von Tag 1 oder später? | Flash-Partitionen |
| **Q-USB-6** | Akzeptanz max. Senderwechsel-Zeit (s)? | Puffergröße, UX-Text |
| **Q-USB-7** | Dension als Messgerät kaufen? | Zeit vs. Geld für G-USB-0/3 |

---

## 8. Empfohlene nächste konkrete Schritte

1. **Jetzt (pidrive-Repo):** Idee + dieser Pfad gepflegt halten; keine Firmware.  
2. **Nächste Fahrzeugsitzung:** Stick-Spike → `docs/fahrzeug/BMW-USB-MSC-PROBE.md` (G-USB-0).  
3. **Owner:** Q-USB-1 und Q-USB-4 beantworten.  
4. **Bei grünem Gate:** Repo `esp32.pidrive` anlegen, Pflichtenheft-Skeleton mit `[ENTWURF]`-Kapiteln aus §4.1, `OFFENE-PUNKTE` mit Q-USB-*.  
5. **Parallel in pidrive:** `UMBAU-USB-MSC.md` aus §6 ausformulieren — aber U1+ erst nach G-USB-1.  
6. **Menü-UID-API** weiter wie geplant (nützt USB und Nicht-USB).

---

## 9. Entscheidungsstatus

| Datum | Stand |
|-------|--------|
| 2026-09-17 | Pfad skizziert: HW-Pflicht S3, Dokumentenladder, Pflichtenheft-TOC, Umbaupakete U0–U8, Gates G-USB-0…4, Owner-Fragen |

Nächstes Dokument nach Messung: `BMW-USB-MSC-PROBE.md`. Nächstes Spec-Dokument nach G-USB-0/1: `esp32.pidrive/docs/planung/PFLICHTENHEFT.md` (neues Repo).
