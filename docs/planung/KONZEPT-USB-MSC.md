# Konzept — USB-Medienpfad (`esp32.pidrive`)

**Dokumentstatus:** Entwurf V0.2 (Konzept, kein Pflichtenheft)  
**Stand:** 2026-09-17  
**Firmware-Repo:** [`esp32.pidrive`](https://github.com/MPunktBPunkt/esp32.pidrive) (ESP-IDF, Hub-Verteilung) · Planung dort unter `docs/planung/`  
**Idee / Voraussetzungen:** [IDEE-USB-MSC-MENUE.md](IDEE-USB-MSC-MENUE.md)  
**Pfad zu Spec & Umbau:** [PFAD-ESP32-PIDRIVE.md](PFAD-ESP32-PIDRIVE.md)  
**Referenzprodukt:** Dension DAB+U (virtuelle MP3 über USB-MSC)  
**Schwester:** `esp32.bt-gateway` (Classic-BT) — **parallel**, nicht Ersatz

---

## 1. Ausgangslage und Problem

PiDrive liefert Infotainment-Logik (Quellen, Menü, Trigger) und spricht den BMW heute über **Bluetooth A2DP + AVRCP**. Das Display zeigt nur **drei MPRIS-Zeilen**; AVRCP-Browsing öffnet der NBT Evo nicht ([BMW-AVRCP-PROBE.md](../fahrzeug/BMW-AVRCP-PROBE.md)). Navigation mit Skip = Cursor ist teuer ([MENU-ERGONOMIE.md](../menue/MENU-ERGONOMIE.md)).

Kommerzielle Nachrüstungen (Dension DAB+U) lösen „Liste + Ton am Werksradio“ anders: sie erscheinen als **USB-Stick mit virtuellen MP3-Dateien**. Der NBT Evo (inkl. Evo-Feldberichte) kann diesen Pfad — mit HU-Tuning und Pufferzeiten.

**Lücke:** PiDrive nutzt den USB-Medienpfad des BMW nicht. Der Pi 4 kann ihn mit der Ist-Verkabelung (USB-C = nur Netzteil, USB-A = Host) auch nicht selbst bedienen.

---

## 2. Kernidee

Ein **ESP32-S3** (`esp32.pidrive`) hängt am **USB-Host des BMW** als Mass-Storage-Device und liefert:

- ein **virtuelles FAT** (Ordner/Dateien = Menü / Sender / Aktionen),
- **on-the-fly-MP3**, den das Werksradio abspielt.

PiDrive bleibt das Gehirn. Der bestehende **Bluetooth-Pfad bleibt unangetastet** und wählbar. USB ist ein **zusätzlicher** `audio_output`.

```
                    ┌─────────────────────────────────────┐
                    │              PiDrive (Pi 4)           │
                    │  Quellen · UID-Menü · Trigger · Encode│
                    │  audio_output = bt | usb_gadget | …   │
                    └───┬─────────────────────┬─────────────┘
                        │                     │
            BlueZ A2DP/AVRCP            PUMP (UART/CDC V1
            (unverändert)               oder später WLAN)
                        │                     │
                        ▼                     ▼
                   BMW Bluetooth        ┌─────────────┐
                   Audio (3 Zeilen)     │ esp32.pidrive│
                                        │ ESP32-S3     │
                                        │ MSC + Puffer │
                                        └──────┬───────┘
                                               │ USB Device
                                               ▼
                                        BMW USB-Medien-UI
                                        (Liste + MP3-Decode)
```

**Ergebnis:** echte Listenbedienung über die BMW-USB-UI, ohne AVRCP-Browsing; BT bleibt Fallback und Paralleloption.

---

## 3. Designregeln

1. **Ein Hörpfad zum BMW gleichzeitig** — `bt` **oder** `usb_gadget` (oder klinke/hdmi), nie BT+USB parallel zum selben Auto.
2. **BlueZ-Code bleibt** — USB addiert Client + Route, ersetzt nichts.
3. **ESP kennt keine PiDrive-Semantik** — nur generische Items (uid, name, kind); Bedeutung nur auf dem Pi.
4. **USB = Ton + UI** (Dension-Vertrag) — keine „Stub-MP3 + Ton über BT“ als Produktziel.
5. **Pi erzwingt Audioformat** — Encode bevorzugt auf dem Pi (MP3-CBR-Frames); ESP puffert und bedient Sektor-Reads.
6. **Empirie vor Festschreibung** — Buffer, Timing-Profile, Dateinamenlimits am eigenen NBT Evo messen.
7. **Observe first** am USB: Read-Muster loggen, bevor Activate-Heuristik scharf geschaltet wird.
8. **MVP schmal** — flache Stations-/Favoritenliste vor vollem Menübaum.
9. **Zwei Kabelrollen trennen** — OTG→BMW ≠ Pi↔ESP-Link.
10. **Kein Classic-BT auf dem S3** — BLE nicht als Audio-Transport.

---

## 4. Was der ESP ist — und was nicht

| Ist | Ist nicht |
|-----|-----------|
| USB-MSC-Gadget + Vorpuffer | Zweites Infotainment |
| PUMP-Server | Quellen-Umschalter / Mixer |
| Generischer FAT-Renderer | DAB-/Spotify-Logik |
| Optional später WLAN-PUMP | Classic-BT-Gateway (das ist `esp32.bt-gateway`) |
| Teil der Hub-Familie (opt. Flash/OTA) | Ersatz für AUX/HDMI/BT-Routen |

---

## 5. Hardware-Konzept

### 5.1 Warum Extra-Hardware

| Pi-4-Anschluss | Rolle | MSC zum BMW? |
|----------------|-------|--------------|
| USB-C | nur Versorgung (Ist) | nein (Port belegt / Gadget würde Power-Konzept sprengen) |
| USB-A ×4 | nur Host | **nein** |

→ **ESP32-S3 mit nativem USB-OTG** ist Pflichtgerät für den Auto-Port.

### 5.2 Verkabelung (Zielbild V1)

```
Netzteil 5V ──────────► Pi 4 USB-C

CSR-BT, RTL-SDR ──────► Pi 4 USB-A (Host)
PUMP ─────────────────► Pi 4 USB-A (Host) ──► ESP Buchse „UART“ / USB-to-UART
                                                    │
                                                    │ ESP32-S3
                                                    │
BMW USB-Host ◄──────── ESP Buchse „USB“ / native OTG (Device, MSC)
```

- Kabel Auto: USB-A (BMW) ↔ USB-C/A (ESP OTG), je nach Board.
- Zweite Board-Buchse = Bridge-Chip, **parallel** nutzbar; kein zweiter OTG-Controller.
- Native OTG: Host **oder** Device, nicht beides gleichzeitig auf demselben PHY.

### 5.3 Kabellos-Variante (V1.1)

ESP nur am BMW-USB; PUMP über **WLAN**. Sinnvoll, wenn Pi und Armlehnen-USB weit auseinanderliegen.

### 5.4 Board-Hinweise (Auswahl später)

- DevKit mit **zwei USB-Buchsen** (OTG + UART-Bridge) bevorzugt für V1.
- Bus-Power vom BMW-USB prüfen (Strombudget vs. S3 + Antenne WiFi); sonst 5 V parallel.
- Kein ESP32 Classic für dieses Repo (kein OTG).

---

## 6. Software-Architektur

### 6.1 Schichten

| Schicht | Ort | Aufgabe |
|---------|-----|---------|
| Quellen / Zustandsmaschine | Pi | DAB, Spotify, … |
| UID-Menü-API | Pi | ein Baum, viele Renderer |
| Audio-Route | Pi `audio_output` | `bt` \| `usb_gadget` \| `klinke` \| `hdmi` \| (`gateway`) |
| PUMP-Client | Pi | Stream, Control, Status |
| MP3-Encode (Tendenz) | Pi | CBR, festes Input-PCM |
| PUMP-Server + Ringpuffer | ESP | Nachschub für MSC |
| Virtuelles FAT + TinyUSB MSC | ESP | Sektor-Reads beantworten |
| Read-Heuristik | ESP → Event an Pi | „Datei X wird gespielt“ |
| BMW USB-Host | Auto | Liste + Decode |

### 6.2 Datenflüsse

**Ton (usb_gadget aktiv):**

```
Quelle → (PipeWire/Capture, fest 44,1 kHz S16LE Stereo)
      → MP3-CBR Encode (Pi)
      → PUMP Audio-Frames
      → ESP Jitter-/Vorpuffer
      → MSC Read → BMW MP3-Decoder → Lautsprecher
```

**Steuerung Auto → Pi:**

```
Fahrer wählt Datei / Next/Prev am iDrive
  → BMW liest MSC-Sektoren
  → ESP Heuristik (aktive Datei / Track-Wechsel)
  → PUMP Event (play_uid | next | previous | action)
  → Pi map_event / Trigger-Dispatcher
```

**Menü Pi → Auto:**

```
UID-API / Favoriten-Export
  → PUMP Menu-Update (flach in V1)
  → ESP baut virtuelle Directory-Einträge
  → BMW listet Ordner/Dateien
```

**BT-Pfad (unverändert, wenn audio_output=bt):**

```
Quelle → PipeWire → bluez_output → A2DP
AVRCP → avrcp_trigger → Trigger
MPRIS → 3 Zeilen
```

### 6.3 Betriebsmodi (ESP)

| Modus | Bedeutung |
|-------|-----------|
| `BOOT` | Init USB Device, warte Enumeration |
| `ENUMERATED` | BMW sieht Stick; noch kein Live-Stream |
| `STREAMING` | Vorpuffer + MSC liefert Live-MP3 |
| `REBUILD` | Directory kurz einfrieren/ändern (selten) |
| `FAIL_SOFT` | PUMP weg: letzte Stille/Ansage-MP3 oder leerer Stream; Log |
| `SETUP` | nur wenn WLAN-Transport: SoftAP/Config |

BMW-USB-Disconnect ist **Normalzustand** (Zündung/Quelle gewechselt), kein Crash.

---

## 7. PUMP — Protokollskizze (noch nicht byte-fest)

Arbeitstitel: **PiDrive USB Media Protocol**. Transportunabhängig (UART/CDC oder WLAN).

### 7.1 Nachrichtentypen (Minimal)

| Typ | Richtung | Zweck |
|-----|----------|--------|
| `HELLO` / `AUTH` | beide | Version, Fähigkeiten (mp3_bitrate, max_buffer_ms) |
| `HEARTBEAT` | beide | Link-Leben |
| `STATUS` | ESP→Pi | usb_enumerated, buffer_ms, active_name, error |
| `STREAM_START` | Pi→ESP | uid, name, bitrate, declared_size_policy |
| `STREAM_DATA` | Pi→ESP | MP3-Frame-Blöcke (seq, payload) |
| `STREAM_STOP` | Pi→ESP | Ende / Quellenwechsel |
| `MENU_SET` | Pi→ESP | flache Liste `{uid, name, kind}` V1 |
| `EVENT` | ESP→Pi | `play_uid`, `next`, `previous`, `action:<name>` |
| `CMD_ACK` | ESP→Pi | Bestätigung STREAM_*/MENU_* |

### 7.2 Audio-Contract (Tendenz)

- Pi liefert **MP3 CBR** (z. B. 128 oder 192 kbit/s), nicht Roh-PCM in V1.
- ESP deklariert virtuelle Dateigröße groß/„endlos“; Seek ans Ende → Loop/Silence-Policy (messen).
- Vorpuffer-Ziel: konfigurierbar, Start **3000–8000 ms**, am NBT Evo kalibrieren (Dension-ABSA-Idee).

### 7.3 Transport-Profile

| Profil | Framing | Wann |
|--------|---------|------|
| `pump.uart` | COBS oder Length-Prefix über CDC/UART ≥ 921600 | **V1** |
| `pump.wlan` | TCP Control + UDP/TCP Data (analog PDAP-Ideen, **eigenes** Schema) | V1.1 |
| `pump.ble` | — | **nicht** für Audio |

PUMP darf **nicht** mit PDAP aus `esp32.bt-gateway` vermischt werden (andere Semantik, anderer Chip). Gemeinsam höchstens „Framing-Ideen“, nicht ein Wire-Format.

---

## 8. Virtuelles Dateisystem (V1)

### 8.1 Layout (MVP)

```
/
├── Stations/
│   ├── 01_ROCK_FM.mp3          ← uid → dab:…
│   ├── 02_Favorit_Antenne.mp3
│   └── …
└── Settings/
    ├── About.mp3               ← Action: Info-Ansage / no-op + Event
    └── Refresh.mp3             ← Action: MENU neu vom Pi holen
```

Später (V1.1+): `Sources/DAB/`, `Sources/Web/`, … aus voller UID-API — nur wenn Rebuild-Verhalten am HU erträglich ist.

### 8.2 Namensregeln (Arbeitshypothese, Spike prüfen)

- Kein führender `.` (Dension-Falle).
- ASCII/umlautarme Kurznamen; Länge-Limit am NBT Evo messen.
- Stabile Sortierpräfixe (`01_`, `02_`) statt nur Alphabet der UIDs.

### 8.3 Rebuild-Politik

- Directory **selten** ändern (Senderliste nach Favoriten-Edit, nicht bei jedem Metadaten-Tick).
- Now-Playing eher über `STATUS`/Dateiname der *aktuell gespielten* virtuellen Datei als über Dauer-Rescan.

---

## 9. PiDrive-Integration (Umbaurichtung)

Bereits vorhandenes Muster: `settings.audio_output` + `decide_audio_route()` in `modules/audio.py`.

| Erweiterung | Inhalt |
|-------------|--------|
| Setting | `usb_gadget` (+ `usb_pump_port` / Host/PSK bei WLAN) |
| Modul | `integration/usb_pump_client.py` (neu) |
| Route | bei `usb_gadget`: Capture→Encode→PUMP; BlueZ-A2DP zum BMW idle/nicht auto-connect |
| Events | PUMP `EVENT` → bestehende `map_event` / `/tmp/pidrive_cmd` |
| Menü | Renderer `usb_fat_export` über UID-API |
| CLI | `pidrivectl audio route usb_gadget`, `pidrivectl usb status\|probe` |
| DAB | Direct-ALSA-Bypass muss für diesen Output mitgezogen werden (sonst stumm) |

Bluetooth-, Klinke- und HDMI-Pfade: **keine funktionalen Einbußen** (U0-Sicherheitsnetz).

Detailpakete: [PFAD-ESP32-PIDRIVE.md](PFAD-ESP32-PIDRIVE.md) §6 (U0–U8).

---

## 10. Abgrenzung zu `esp32.bt-gateway`

| | BT-Gateway | USB-Pfad (`esp32.pidrive`) |
|--|------------|----------------------------|
| Problem | BlueZ-Stabilität, A2DP | Listen-UI + Ton ohne AVRCP-Browsing |
| Chip | ESP32 Classic | ESP32-S3 |
| Auto-Link | Bluetooth | USB-MSC |
| Pi-Link | PDAP/WLAN | PUMP UART→WLAN |
| UI | 3 Zeilen | Ordner/Dateien |
| Koexistenz | wählbarer `audio_output` | dieselbe Policy |

Beide dürfen langfristig existieren; Priorität ist Owner-Sache. Konzept hier legt **USB neben BT** fest.

---

## 11. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|--------|----------------|
| NBT Evo spielt Gadget-MP3 nicht / scannt ewig | Stick-Spike G-USB-0 vor Hardware-Kaufzwang |
| Prefetch löst falsche Activates aus | Observe-first, Heuristik-Schwellen, Spike-Logs |
| Umschaltzeit 5–15 s inakzeptabel | Puffer tunen; UX wie Dension kommunizieren; oder Abbruch |
| PUMP-Kabel zu kurz im Auto | auf WLAN-Transport wechseln |
| WiFi+USB-Last auf S3 | V1 ohne WLAN; Encode auf Pi |
| DAB bleibt stumm | explizites DAB→Capture-Paket (wie Gateway-Doku) |
| Directory-Rebuild triggert HU-Rescan | flache Liste, seltene MENU_SET |
| Verwechslung BT-Menü vs. USB-Liste | klarer Modus in Status/WebUI; eine Route aktiv |

---

## 12. Entwicklungsphilosophie & Gates

Analog BT-Gateway:

1. **Stick-Spike zuerst** (kein ESP) → `BMW-USB-MSC-PROBE.md`
2. **ESP MSC + Datei-MP3** am Auto (noch kein PUMP-Audio)
3. **PUMP + Live-MP3** (Laptop-Tester, dann Pi)
4. **Heuristik scharf** + flache Stationsliste
5. **PiDrive `audio_output=usb_gadget`** additiv
6. Erst dann tiefer Menübaum

Gates G-USB-0…4: [PFAD-ESP32-PIDRIVE.md](PFAD-ESP32-PIDRIVE.md) §5.

---

## 13. Namensgebung

| Name | Bewertung |
|------|-----------|
| **esp32.pidrive** | Favorit — Familie `esp32.*`, Zweck PiDrive-USB-Medien |
| `esp32.usb-msc` | technisch klar, weniger Produktbezug |
| `esp32.dab-u` | zu eng (nicht nur DAB) / Dension-Verwechslung |

Protokoll: **PUMP** (Arbeitstitel; Umbenennung im Pflichtenheft erlaubt).

---

## 14. Entscheidungsstand

| Thema | Stand |
|-------|--------|
| BT parallel belassen | **Konzept-Ja** (§2, §3) |
| USB = Ton+UI | **Konzept-Ja** |
| Chip ESP32-S3 | **Konzept-Ja** |
| PUMP V1 = UART/CDC | **Tendenz-Ja** |
| Encode auf Pi | **Tendenz-Ja** |
| MVP flache Stationsliste | **Empfehlung**, Owner Q-USB-4 |
| Repo/Firmware starten | **Nein** vor G-USB-0 |
| Pflichtenheft | nach Gates — Skizze in PFAD §4 |

---

## 15. Nächste Dokumente

| Dokument | Wann |
|----------|------|
| `fahrzeug/BMW-USB-MSC-PROBE.md` | nach Stick-Spike |
| `esp32.pidrive` Repo + `PFLICHTENHEFT.md` | nach G-USB-0/1 |
| `planung/UMBAU-USB-MSC.md` | mit Pflichtenheft-Skeleton |
| Dieses Konzept → V0.3 | nach Probe-Ergebnissen / Owner-OKs |
