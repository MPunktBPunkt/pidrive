# USB-MSC Covers — eigene Album-Bilder für Radio & SoftAP

**Stand:** 2026-09-18 · Bridge/Firmware ab **0.4.5**  
**Ordner auf GitHub:** https://github.com/MPunktBPunkt/pidrive/tree/main/assets/usb-msc-covers

Hier legst du **JPEG-Dateien** ab. Die Bridge bettet sie als ID3-Cover (APIC) in den USB-Stream ein — sichtbar am Werksradio und in der ESP-SoftAP unter „Cover / Now Playing“.

---

## Kurz: Welches Bild wann?

| Priorität | Wann | Datei |
|-----------|------|--------|
| 1 | Bibliothek spielt eine MP3 **mit** eingebettetem Cover | aus der MP3 (APIC) |
| 2 | Es gibt eine passende Datei unter `stations/` | `stations/….jpg` |
| 3 | Sonst **immer** | **`default.jpg`** (dieser Ordner, Root) |
| 4 | Nur wenn `default.jpg` fehlt | generiertes Text-Bild |

**Default-Pfad (verbindlich):**

```
assets/usb-msc-covers/default.jpg
```

→ auf dem Pi typisch: `/home/pidrive/pidrive/assets/usb-msc-covers/default.jpg`  
Ersetze diese eine Datei, wenn du ein globales Fallback-Logo willst.

---

## Reale Beispiele — Dateien, die du anlegen kannst

Aus deiner aktuellen `config/stations.json` (Webradio).  
**Bevorzugter Dateiname** = `stations/<id>.jpg` (Spalte „Datei“).  
Pfad immer unter `assets/usb-msc-covers/`.

### Global

| Datei | Wirkung |
|-------|---------|
| `default.jpg` | Cover für **jeden** Stream ohne eigene `stations/`-Datei und ohne MP3-APIC |

### Webradio-Sender (echte IDs)

| Sender | Datei zum Anlegen |
|--------|-------------------|
| Rock Antenne | `stations/web_rock_antenne.jpg` |
| Rock Antenne Bayern | `stations/web_rock_antenne_bayern.jpg` |
| Rock Antenne Heavy Metal | `stations/web_rock_antenne_heavy.jpg` |
| Rock Antenne 80er | `stations/web_rock_antenne_80er.jpg` |
| Rock Antenne Alternative | `stations/web_rock_antenne_alternative.jpg` |
| Radio BOB! | `stations/web_radio_bob.jpg` |
| Radio BOB! Rock Classics | `stations/web_radio_bob_classics.jpg` |
| Radio BOB! Metal | `stations/web_radio_bob_metal.jpg` |
| Radio BOB! Blues | `stations/web_radio_bob_blues.jpg` |
| SWR Rock FM | `stations/web_rock_fm.jpg` |
| ROCK ANTENNE Heavy Metal (BOB) | `stations/web_bob_ra_heavymetal.jpg` |
| ROCK ANTENNE Classic Rock (BOB) | `stations/web_bob_ra_classic.jpg` |
| ROCK ANTENNE Reggae (BOB) | `stations/web_bob_ra_reggae.jpg` |
| ROCK ANTENNE 80er (BOB) | `stations/web_bob_ra_80er.jpg` |
| Deutschrock (laut.fm) | `stations/web_lautfm_deutschrock.jpg` |
| Classic Rock (laut.fm) | `stations/web_lautfm_classicrock.jpg` |
| Metal (laut.fm) | `stations/web_lautfm_metal.jpg` |
| 1000 Rockhits (laut.fm) | `stations/web_lautfm_1000rockhits.jpg` |
| Radio Paradise | `stations/web_radio_paradise.jpg` |
| Bayern 3 | `stations/web_bayern3.jpg` |

Beispiel zum Sofort-Start (nur Deutschrock + Default):

```
assets/usb-msc-covers/default.jpg
assets/usb-msc-covers/stations/web_lautfm_deutschrock.jpg
```

Neuen Webradio-Sender in `stations.json` mit `"id": "web_mein_sender"` angelegt?  
→ Cover-Datei: `stations/web_mein_sender.jpg`.

### Status-Bilder (noch nicht von der Bridge geladen)

Vorbereitet für später — Dateien kannst du schon erzeugen, Wirkung kommt erst wenn verdrahtet:

| Geplant | Datei |
|---------|-------|
| WLAN | `status/wifi.jpg` |
| BT verbunden | `status/bt_connected.jpg` |
| BT getrennt | `status/bt_disconnected.jpg` |
| DAB-Scan | `status/dab_scan.jpg` |
| Idle | `status/idle.jpg` |

### Nicht nötig

Menüpunkte ohne Live-Stream brauchen **kein** Cover: Zurück, Mehr…, Seite 1, Stop, Ordner (Favoriten/Quellen/…).

---

## So findest du den Dateinamen für einen Sender

### Variante A — ESP SoftAP (einfachste)

1. Sender im SoftAP-Menü **Play**en  
2. Tab **Auto-Test** → Block **Cover / Now Playing**  
3. Dort steht:
   - **Quelle** — `file` / `default` / `embedded` / …  
   - **Aktuell** — welche Datei gerade genutzt wird (z. B. `default.jpg`)  
   - **Ersetzen mit** — genauer Pfad, den du anlegen solltest  
   - **Kandidaten** — alle Dateinamen, die die Bridge der Reihe nach sucht  

Beispielanzeige:

```
Quelle:     Default (default)
Aktuell:    default.jpg
Ersetzen:   assets/usb-msc-covers/stations/web_rock_antenne.jpg
Kandidaten: …/stations/web_rock_antenne.jpg · …/stations/uid_123….jpg · …
```

→ Lege genau die Datei unter **Ersetzen** ab (320×320 JPEG, ≤8 KiB), Sender neu starten — fertig.

### Variante B — Menü-JSON auf dem Pi

```bash
python3 -c "
import json
m=json.load(open('/tmp/pidrive_menu.json'))
for n in m.get('nodes') or []:
    if n.get('type') in ('station','action') or n.get('playable'):
        print(n.get('id'), '|', n.get('label'), '| uid=', n.get('uid'))
"
```

Daraus werden die Dateinamen gebaut (Reihenfolge):

1. `stations/<id>.jpg` — z. B. `stations/web_rock_antenne.jpg` ← **bevorzugt**  
2. `stations/uid_<uid>.jpg` — z. B. `stations/uid_2835520419728495310.jpg`  
3. `stations/<slug>.jpg` — aus Label, nur `a-z0-9_`, z. B. `stations/rock_antenne_laut_fm.jpg`  

### Variante C — Hint-Datei nach Play

Nach jedem Stream schreibt die Bridge:

`/tmp/pidrive_cover_hint.json`

```json
{
  "src": "default",
  "rel": "default.jpg",
  "preferred": "stations/web_rock_antenne.jpg",
  "candidates": ["stations/web_rock_antenne.jpg", "stations/uid_….jpg"],
  "default": "default.jpg",
  "folder": "assets/usb-msc-covers/"
}
```

---

## Was ist *kein* Station-Cover?

| Thema | Ordner | Status |
|-------|--------|--------|
| Sender / Webradio / Library-Fallback | `stations/*.jpg` | **aktiv** |
| Globales Fallback | **`default.jpg`** | **aktiv** |
| WiFi / BT / DAB-Scan Platzhalter | `status/*.jpg` | Spec vorbereitet, Bridge **nutzt sie noch nicht** |
| Lab-Beispiele | `examples/` | nur Referenz, nicht Produktion |

Menü-Einträge wie „Zurueck“, „Mehr…“, „Seite 1“ brauchen **kein** Cover (kein Live-Stream).

---

## Ordnerstruktur

```
assets/usb-msc-covers/
├── README.md          ← diese Datei
├── default.jpg        ← IMMER Fallback, wenn kein stations/-Treffer
├── stations/          ← ein JPEG pro Sender (von dir)
│   └── web_….jpg
├── status/            ← geplant (wifi, bt, …) — noch ungenutzt
└── examples/          ← Spec/Lab-Referenz
```

---

## Bildgröße

| | Empfohlen | Hart |
|--|-----------|------|
| Format | JPEG | JPEG |
| Pixel | **320×320** | — |
| Datei | **≤ 6–8 KiB** | APIC-Teil ≤ ~8 KiB; ganzes sticky ID3 ≤ **12 KiB** |

```bash
convert logo.png -resize 320x320^ -gravity center -extent 320x320 \
  -quality 70 stations/web_rock_antenne.jpg
identify -format '%wx%h %b\n' default.jpg stations/*.jpg
```

---

## Wo erscheint das Cover?

| Ort | Ja? |
|-----|-----|
| BMW USB-Medien (Ziel) | ja (Feldtest offen) |
| ESP SoftAP Cover-Block + `/api/lab/cover` | ja |
| SoftAP Stream-Hören (`/api/lab/listen`) | nein (nur Audio) |

---

## Tipps

- Ein Logo für **alle** Sender ohne eigene Datei: nur `default.jpg` tauschen.  
- Ein Logo für **einen** Sender: Datei unter dem in SoftAP genannten **Ersetzen**-Pfad.  
- Library-MP3 mit eigenem APIC: hat Vorrang; override mit `stations/<id>.jpg` (Station-Datei schlägt Default, aber nicht embedded APIC — dafür Cover aus der MP3 entfernen oder Sender über Webradio).  
- iDrive cached Cover oft — nach Dateiwechsel ggf. anderen Slot/UID anspielen.

Firmware: [`COVER-ID3.md`](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/COVER-ID3.md) · Bridge: `esp32.pidrive/tools/pump_bridge.py`
