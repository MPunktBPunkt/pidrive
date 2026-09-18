# USB-MSC Covers (Album Art für BMW / PUMP)

**Stand:** 2026-09-18 · Firmware [`esp32.pidrive` 0.4.3-dev](https://github.com/MPunktBPunkt/esp32.pidrive)  
**Zweck:** JPEG-Cover, die als **ID3v2 APIC** in den Live-MP3-Stream eingebettet werden und am Werksradio (NBT/iDrive USB-Medien) als Albumcover erscheinen können.

**Zentraler GitHub-Ordner (editierbar):**  
https://github.com/MPunktBPunkt/pidrive/tree/main/assets/usb-msc-covers

Die Bridge (`esp32.pidrive/tools/pump_bridge.py`, ab **0.4.3**) wählt Cover so:

1. **APIC** aus lokaler MP3 (`local_play` / `status.library_file`) — skaliert auf 320×320 / ≤8 KiB  
2. JPEG aus diesem Ordner (`stations/…`)  
3. Fallback-Textcover (Sender / Track / BT·WiFi)

Lab 2026-09-18: Billy-Talent embedded APIC + Webradio sticky ID3 inkl. APIC am Pi-MSC-Host verifiziert.  
`stations/` und `status/` sind bewusst leer (nur `.gitkeep`) — hier deine Logos ablegen.

---

## Wo taucht welches Bild auf?

| Ort | Sieht Cover? | Quelle | Hinweis |
|-----|--------------|--------|---------|
| **BMW NBT / USB-Medien** | Ziel | sticky ID3 APIC am Dateianfang der virtuellen `.MP3` | Feldtest offen; HU cached oft stark |
| **ESP SoftAP Web-UI** | **nein** | — | zeigt Menü/Stream-Metriken; kein `<img>` / kein `/api/lab/cover` |
| **`GET /api/lab/stream`** | Rohdaten | kompletter sticky Tag + Audio-Head | für `ffprobe`/mutagen; Header `X-Stream-Id3` |
| **`GET /api/lab/listen`** | nein | nur Ring-Audio | ID3 wird übersprungen |
| **PiDrive WebUI** | eigene UI | Library/Webradio-Admin | unabhängig vom MSC-APIC |

Kurz: Cover stecken im **Stream zum Radio** (und im Lab-Download), nicht im ESP-Webinterface.

---

## Ordnerstruktur

```
assets/usb-msc-covers/
├── README.md                 ← diese Datei
├── examples/                 ← Referenzbilder (Spec + Lab) — nicht Produktion
├── stations/                 ← Senderlogos (von dir) ← hier editieren
└── status/                   ← Zustandsbilder (geplant; Bridge liest sie noch nicht)
```

| Unterordner | Inhalt | Bridge nutzt? |
|-------------|--------|---------------|
| `stations/` | ein JPEG pro Sender / Station | **ja** (Priorität 2) |
| `status/` | WiFi / BT / DAB-Scan / idle | **noch nicht** (Spec vorbereitet) |
| `examples/` | Spec-Beispiele + Lab-Extrakte | nein (Referenz) |

---

## Bildgröße (verbindliche Spec)

| Parameter | Empfohlen | Hartes Limit (ESP sticky ID3) | BMW-Erfahrung |
|-----------|-----------|-------------------------------|---------------|
| Format | **JPEG** (`image/jpeg`) | JPEG | JPEG (PNG oft ok, JPEG sicherer) |
| Geometrie | **320×320** px | — | oft bis **~500–600** px gut; **>1000×1000** oft tot |
| Seitenverhältnis | 1:1 | 1:1 | quadratisch |
| Dateigröße | **≤ 8 KiB** (320 px, q≈70) | **gesamtes ID3 inkl. APIC ≤ 12 KiB** | einzelne Bilder gern &lt; 300 KiB, bei uns enger wegen UART |
| Qualität | JPEG quality **65–75** | — | zu große Dateien → langsamer ID3-Transfer |

### Warum so klein?

1. **ESP sticky ID3-Puffer** = max. **12 KiB** (`StreamBuffer::kId3Max`) — Tag + APIC müssen hinein.
2. UART **115200** — große Cover verzögern den Stream-Start.
3. Lab-Messung 0.4.2: generiertes Cover **320×320 ≈ 4 KiB**, gesamtes ID3 ≈ **5,1 KiB** — passt.

**Zum Anlegen eigener Logos:** 320×320 JPEG, Qualität 70, Datei möglichst unter **6–8 KiB**. Wenn du 500×500 willst: stark komprimieren und prüfen, dass `ID3-Gesamtgröße ≤ 12 KiB` (sonst kürzt/verweigert die Bridge).

---

## Dateinamen-Konvention

### Sender (`stations/`)

Bevorzugte Reihenfolge beim Lookup (geplant / Bridge):

1. `stations/<menu_node_id>.jpg` — z. B. `web_rock_antenne.jpg` (PiDrive `nodes[].id`)
2. `stations/uid_<uid>.jpg` — z. B. `uid_2835520419728495310.jpg`
3. `stations/<slug>.jpg` — slug aus Sendername (klein, `[a-z0-9_]+`)
4. Fallback: generiertes Text-Cover

Beispiele:

```
stations/web_rock_antenne.jpg
stations/web_radio_bob.jpg
stations/uid_2835520419728495310.jpg
```

### Status (`status/`)

| Datei | Verwendung |
|-------|------------|
| `status/wifi.jpg` | WLAN / IP (selten ändern) |
| `status/bt_connected.jpg` | BT verbunden |
| `status/bt_disconnected.jpg` | BT getrennt |
| `status/dab_scan.jpg` | DAB-Suchlauf aktiv |
| `status/idle.jpg` | optional Ruhezustand |

Status-Cover gehören eher auf **eigene virtuelle MP3-Slots** („Status.mp3“, „Suchlauf.mp3“), nicht auf jeden Menüklick — iDrive **cached** Albumart stark.

---

## ID3-Felder (was die Bridge setzt)

| Frame | Quelle | Beispiel Lab |
|-------|--------|--------------|
| `TIT2` (Title) | `/tmp/pidrive_status.json` → `track`, sonst Sendername | All you zombies |
| `TPE1` (Artist) | `artist`, sonst Genre | The Hooters |
| `TALB` (Album) | `radio_name` / Station | Rock Antenne |
| `APIC` type=3 Cover | JPEG aus diesem Ordner oder generiert | 320×320 |

Protokoll: nach `audio_start` sendet die Bridge Binärframes **`0x01 0x56`** (sticky ID3 append), danach Audio **`0x01 0x55`**.

Lab-Check am PC:

```bash
curl -o /tmp/s.mp3 http://<ESP-IP>/api/lab/stream
ffprobe -show_entries format_tags=title,artist,album /tmp/s.mp3
# Cover extrahieren: mutagen / MP3Tag / ffmpeg
```

Header `X-Stream-Id3: <bytes>` zeigt die sticky-Tag-Länge am ESP.

---

## Beispiele in `examples/`

| Datei | px | ~Größe | Hinweis |
|-------|-----|--------|---------|
| `example_station_320.jpg` | 320 | ~6 KiB | Spec-Standard |
| `example_station_500.jpg` | 500 | ~12 KiB | obere BMW-übliche Kante — **allein schon knapp für 12 KiB-ID3** |
| `example_status_*.jpg` | 320 | ~4 KiB | WiFi / BT / DAB-Scan-Vorlagen |
| `lab_rock_antenne_from_stream.jpg` | 320 | ~4 KiB | aus Live-Lab 0.4.2 extrahiert |

---

## Tipps zum Erzeugen

```bash
# ImageMagick: auf 320 quetschen + klein halten
convert logo.png -resize 320x320^ -gravity center -extent 320x320 \
  -quality 70 stations/web_rock_antenne.jpg

# Größe prüfen
identify -format '%wx%h %b\n' stations/*.jpg
```

Pillow-Einzeiler analog zu den `examples/` (siehe Bridge `make_cover_jpeg`).

---

## Grenzen (Autoradio)

- NBT/iDrive cached Cover oft beim **ersten Scan** der Datei — Live-Wechsel des APIC ohne neue Datei/UID kann ignoriert werden.
- Metadaten/Titelzeile waren bei Dension schon **unzuverlässig**; Cover ist Nice-to-have, Sendername über Dateiname ist robuster.
- Feldtest am eigenen NBT steht noch aus.

Firmware-/Protokoll-Details:  
[`esp32.pidrive` docs/planung/PUMP.md](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/PUMP.md) ·  
[`COVER-ID3.md`](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/COVER-ID3.md)
