# Post-§11.10 — Ring-Rechnung & BT-Stand (Papier, 2026-10-02 Abend)

Kein Firmware-Build. Grundlage für Architekturentscheidung **nach** B7.

## 1. Ringkapazität (Idealrechnung)

Annahme Produzent/Konsument ≈ **6 kB/s** (48 kbit/s MP3). Nur gleichzeitig im Ring gehaltene Live-Bytes — **nicht** kumulative `streamBytes`.

| Ring | Rechnerische Hördauer | Bemerkung |
|------|----------------------|-----------|
| 48 KiB (Ist) | ≈ 8 s | Mit Kurzton/Cover **vereinbar**, Ursache nicht bewiesen |
| 128 KiB | ≈ 22 s | Clip-Hebel |
| 256 KiB | ≈ 44 s | Clip-Hebel |
| 1024 KiB | ≈ 171 s | Heap auf S3 prüfen, bevor je gebaut |

**ESP-Status Lab `.88` (2026-10-02 ~22:28):** `freeHeap≈117 kB` bei aktivem Stream — ein 256 KiB-Ring wäre **nicht** aus dem aktuellen Free-Heap ohne Umbau/PSRAM-Plan.

**Fazit:** Größerer Ring verlängert höchstens ein bereits geliefertes Fragment. Er ersetzt **kein** HU-Nachlesen und **keine** Play-Detection bei Cache-Wahl. Entscheidung erst nach B7.

## 2. BT-Architektur (Ist-Dokumentation)

| Fakt | Quelle |
|------|--------|
| Produkt heute: A2DP + AVRCP (3 MPRIS-Zeilen) | `KONZEPT-USB-MSC.md`, Feldtests |
| AVRCP-Browsing am NBT Evo **nein** (PSM 0x001B) | `BMW-AVRCP-PROBE.md` |
| USB und BT = **getrennte** BMW-Quellen / getrennte Hörpfade | `PFAD-ESP32-PIDRIVE.md` §1 — je Sitzung ein aktiver Pfad |
| Konzept lehnt „Menü USB + Ton BT“ als Hauptziel ab | `IDEE-USB-MSC-MENUE.md` P-A1 |
| `esp32.bt-gateway` | Classic-ESP32, Firmware **noch nicht gestartet** (`STATE.md` 2026-09-15) |
| Pi BlueZ-Pfad | parallel zu USB geplant, nicht abschalten |

**Für die Review-Option C:** BT ist ein **existierender** Audio-Transport auf dem Pi, **kein** Drop-in „USB-Menü steuert BT-Ton in einer Quellenansicht“. Nach B7 ggf. bewusst: MSC nur Menü/Cover **oder** Hörpfad ganz auf BT — nicht beides vermischen ohne UX-Entscheidung.

## 3. Lab-Prep heute

- B7-Tool Smoke gegen `.88` (12 s): Pipeline OK, `readCount` flat (kein Host-Burst) → Artefakt `artifacts-2026-10-02-b7-labprep/`
- Pi: `0.4.36` OTA-Bin + `RAPID_SWITCH_S` Guard vorhanden
- Proxmox `/dev/sg0` weiterhin offline → kein NBT-Suite-Lauf heute
