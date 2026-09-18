# USB-MSC: Listing vs. Live-Stream — Lab 2026-09-18

**Scope:** ESP32-S3 MSC-Gadget (`esp32.pidrive`) + Pi `pump_bridge` + Android-OTG / BMW-USB  
**Firmware-Kontext:** `0.4.9` → `0.4.10` → `0.4.11` → **`0.4.12-dev` (static FAT)**  
**Repos:** Lab (Pi + SoftAP/STA + Handy-OTG); Verhalten deckungsgleich mit Autoradio-Beobachtung

---

## Kurzfazit

**Ursache (bestätigt):** `startStream` hat FAT/Directory/Size/Clusterkette verändert → Host-Listing bricht.

**Fix ab 0.4.12-dev:** FAT/Dir/Sizes/Chains sind **immutable** nach Geometrie-Setup. Stream setzt nur `streamSlot_` und liefert den Ringbuffer als **Payload-Overlay** derselben virtuellen MP3. Writes → read-only (`tud_msc_is_writable_cb=false`, WRITE reject). Kein Remount mehr bei Stream.

**Noch offen (Problem B):** Handy-Cache / kein zuverlässiges `play.guess` → oft nur Demo-Testton. Separater Selection-Detector.

**Limit:** virtuelle Dateien ~64 KiB (512-Sektoren-Image) — Dauer-Wiedergabe braucht später größere virtuelle Kapazität.

---

## Setup

| Komponente | Rolle |
|---|---|
| ESP32-S3 (`esp32.pidrive`) | USB-MSC-Gadget (= Stick), SoftAP/STA, UART-PUMP |
| Raspberry Pi | `pump_bridge.py`: Menü + ffmpeg → MP3 über UART |
| Android-Handy | USB-OTG-Host, Dateien/Player |
| BMW / Autoradio | USB-Host (gleiches Listing-/Stream-Muster) |

```
[Webradio-URL] → Pi/ffmpeg → UART PUMP → ESP StreamBuffer
                                              ↓
                              USB-MSC FAT12 (virtueller Stick)
                                              ↓
                              Handy / Autoradio als USB-Host
```

---

## Was der Stick zeigt

**STATIONS** (Namen seit 0.4.10 aus Menü-LFN):

| Datei | UID |
|---|---|
| `Deutschrock (laut.fm).mp3` | `fav0` |
| `Rock Antenne.mp3` | `fav1` |
| `Rock Antenne Bayern.mp3` | `fav2` |

**SETTINGS:** `Menü….mp3` → Paging (`pump:page_next`), kein Audio-Stream.

Ohne Live-Stream: kurze **Demo-Stubs** aus `demo_fat.bin` (~1,5 s, ~880 Hz Testton).  
Mit Live-Stream: ein Slot wird auf große LBA-Range expandiert; Reads kommen aus dem Ringpuffer (Live-MP3).

---

## Kernverhalten (reproduzierbar)

| Zustand | Blaue Daten-LED | USB-Inhalt |
|---|---|---|
| Stream **aus** | aus / ruhig | Ordner + Menü-MP3s sichtbar |
| Stream **an** | blinkt | **leer / keine Titel / keine Einträge** |
| Stream stoppen | aus | Dateien **wieder da** |

Beispiel-Snapshot während Stream (`0.4.11-dev`):

- `stream.active=true`, `uid=fav0`, `streamSlot=0`, Slot `lba1=500` (expandiert)
- `streamBytes` wächst, Bridge: `[audio] forwarded … B/2s`
- Host sieht trotzdem oft leeren Inhalt

---

## Testreihe (Lab)

### 1) Menünamen (0.4.10-dev)

- **Ziel:** Statt `01ROCK.MP3` die Fav-Namen zeigen.
- **Ergebnis:** Nach OTA + frischem Mount korrekte LFN-Namen am Handy.
- **Gegenprobe Pi:** Directory-Dump `/dev/sda` LBA 35 (STATIONS) / 39 (SETTINGS).

### 2) Datei antippen → nur Testton

- Alle drei STATIONS-MP3s → nur Stub-Testton, kein Webradio.
- ESP: **kein** `play.guess`, kein frisches `audio_start` bei diesen Versuchen.
- **Interpretation:** Android spielt gecachten Stub; kaum erneutes sequentielles USB-Read. Bridge kann parallel trotzdem noch einen Rest-Stream fahren.

### 3) Stream läuft → leerer Stick

- LED blinkt; Ordner leer.
- Gleichzeitig oft `msc.write` (Android schreibt Boot/FAT/Dir-LBAs; Gadget ack’t, persistiert nicht).
- Deckungsgleich Auto: „keine abspielbaren Titel“ / leere Medienliste bei aktivem Stream.

### 4) Stream stop → Dateien zurück

- `audio_stop` / Lab-Stop → `msc.stream_off` → Listing wieder sichtbar.

### 5) 0.4.11-dev (Phone-Ansatz)

- Längere FAT-Ketten (~64 KiB je Station), Stub-Remap für neue Geometrie.
- Soft-`mediaPresent`-Remount bei Stream-Start/-Stop.
- **Status:** Listing-vs-Stream-Konflikt bleibt das Hauptproblem; Phone-Play weiter unzuverlässig.

---

## Hypothesen

**A) Host cached Directory / MediaStore**  
Einmal Stub + Dir gelesen; Live-Overlay unter laufendem Mount → alter Stand oder „kaputtes“ FS → leer.

**B) Stream expandiert File/FAT/Size**  
`startStream(uid)` verlängert Clusterkette und Directory-Size stark. Ohne Remount/Unit-Attention brechen viele Hosts die Sicht.

**C) Android-Writes**  
`msc.write` auf Meta-LBAs ohne Persistenz → inkonsistente Host-Sicht bis Remount + Stream aus.

**D) `looksLikePlay` vs. Phone**  
BMW: Indexfenster ~2,5 s nach Plug darf nicht armieren; Play = From-Head ≥ ~6 KiB.  
Android: oft ein Read + Cache → kein `play.guess` → nur Testton.

**E) Design-Zielkonflikt**  
Stabiles kleines Menü **oder** endloses Live-File — parallel bricht das Listing.

---

## Reproduktion

1. Stream aus, Stick stecken → STATIONS mit 3 MP3s.
2. Stream starten (USB-Play falls `play.guess`, SoftAP/Lab `/api/lab/play`, oder Bridge `audio_start`).
3. LED blinkt; Host neu listen → **leer**.
4. Stream stoppen → Dateien wieder da.

Zusatz Phone: MP3 öffnen ohne `play.guess` → nur Testton.

---

## Signale / APIs

- Events: `usb.otg.up/down`, `msc.prefetch`, `play.guess`, `msc.stream_on/off`, `msc.write`, `msc.remount`
- Status: `stream.active`, `streamSlot`, `streamBytes`, Slot-`lba0/lba1`
- Bridge: `[audio] ffmpeg <url>`, `forwarded … B/2s`
- SoftAP/STA: `/api/status`, `/api/events`, `/api/lab/play`, `/api/lab/stop`

---

## Bereits versucht

| Maßnahme | Wirkung |
|---|---|
| Menü-LFN (0.4.10) | Namen OK; Stream-Konflikt bleibt |
| Stream stoppen für Listing | hilft, kein Parallelbetrieb |
| Längere FAT + Remount (0.4.11) | Ansatz gegen Phone-Cache; Konflikt offen |
| WebUI `After=network.target` | Boot schneller — unabhängig von MSC |

---

## Offene Fragen

1. Wie gleichzeitig stabiles Verzeichnis **und** Live-MP3? (feste Size + Payload-Ring, Unit Attention, Remount-Policy, zweite LUN, …)
2. Remount bei jedem `menu_set` / `audio_start` — verträglich mit BMW NBT?
3. Android-Writes: streng read-only / Sense-Key?
4. Phone: SoftAP-Play + Remount als offizieller Pfad?
5. Ist „leer während Stream“ am Auto akzeptabel, wenn Ton trotzdem läuft — oder muss das Menü während Stream navigierbar bleiben?

---

## Verwandte Docs / Repos

- Firmware/Code: [`esp32.pidrive`](https://github.com/MPunktBPunkt/esp32.pidrive) — `src/msc/UsbMscGadget.*`, `tools/pump_bridge.py`
- Konzept: [`docs/planung/KONZEPT-USB-MSC.md`](../planung/KONZEPT-USB-MSC.md)
- Pfad: [`docs/planung/PFAD-ESP32-PIDRIVE.md`](../planung/PFAD-ESP32-PIDRIVE.md)
- Betrieb allgemein: [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
