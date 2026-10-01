# Review-Paket: ESP-MSC ↔ BMW NBT — Feld 2026-09-28

**Zweck dieses Dokuments:** Alles Material für ein ausgiebiges Review (Problemverständnis, Telemetrie, Code-Anker, Artefakte, Hypothesen, offene Fragen, Abnahme).  
**Stand Diagnose:** 2026-10-01 — Auto-Feld mit **0.4.29** (B2 Stille statt Testton; Overlay grün, HU-Cache); Lab **`.88` = 0.4.31-dev** (**B4** sequential cursor SoftAP pass).  
**Nicht:** fertige Implementierung — nächste Schritte sind priorisiert, Alternativen bleiben nachvollziehbar.

| Meta | Wert |
|------|------|
| Datum | 2026-09-28 (Feld ~07:40–15:55) · **Nachtest 2026-09-30 ~08:10–08:40** |
| FW live am Auto | **`0.4.26-dev`** (OTA 2026-09-30; vorher 0.4.24) |
| ESP STA | `192.168.178.89` · SoftAP `pidrive-2BC568` / `192.168.4.1` |
| Pi | `192.168.178.105` · `pump_bridge.py` manuell (+ `ensure_pump_bridge.sh`) · PUMP-TCP `:9090` |
| HU | BMW NBT Evo (USB-Host), Host-Hint ESP: `hu-like` |
| PUMP-Link Produkt | **offen** — SoftAP \| STA \| UART festlegen (§15.0); Feldtest ideal SoftAP/UART |
| Repos | `pidrive` (Doku/Bridge-Scripts) · `esp32.pidrive` (FW **0.4.26** + `pump_bridge.py`) · Hub-Binaries `iobroker.esp-hub/firmware/` |
| Auftrag | [AUFTRAG-ESP-PLAY-DETECTION](../auftraege/AUFTRAG-ESP-PLAY-DETECTION.md) |
| Multi-Review | [§18 Konsens Claude/GPT/Gemini/Grok](#18-multi-review-konsens-2026-09-28-abend) |
| Idee / Warum | [IDEE-USB-MSC-MENUE](../planung/IDEE-USB-MSC-MENUE.md) |
| Konzept (Soll) | [KONZEPT-USB-MSC](../planung/KONZEPT-USB-MSC.md) |
| Runtime-Flow | [RUNTIME_FLOWS § USB](../architektur/RUNTIME_FLOWS.md) |
| Lab-Vorgänger | [USB-MSC-STREAM-LISTING-2026-09-18](USB-MSC-STREAM-LISTING-2026-09-18.md) |
| Spec Play-Detect | esp32.pidrive `docs/planung/PLAY-DETECTION.md` |

### Rohartefakte (Snapshot ~15:55)

| Datei | Inhalt |
|-------|--------|
| [artifacts-2026-09-28-esp-status.json](artifacts-2026-09-28-esp-status.json) | `/api/status` komplett |
| [artifacts-2026-09-28-esp-menu.json](artifacts-2026-09-28-esp-menu.json) | `/api/menu` |
| [artifacts-2026-09-28-esp-events.json](artifacts-2026-09-28-esp-events.json) | `/api/events` |
| [artifacts-2026-09-28-esp-config.json](artifacts-2026-09-28-esp-config.json) | `/api/config` |
| [artifacts-2026-09-28-bridge-excerpt.log](artifacts-2026-09-28-bridge-excerpt.log) | Bridge-Journal 15:42–15:55 (gefiltert) |

**Bins:** `esp32.pidrive/dist/pidrive.0.4.18-dev` … `0.4.24-dev` `{ota,usb}.esp32s3.bin` (+ Hub-Kopie).

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)  
2. [Nutzerbeobachtungen (Feld)](#2-nutzerbeobachtungen-feld)  
3. [Soll-Konzept & Technik](#3-soll-konzept--technik)  
4. [Virtuelles Dateisystem (Geometrie)](#4-virtuelles-dateisystem-geometrie)  
5. [Play-Detection (Algorithmus)](#5-play-detection-algorithmus)  
6. [Telemetrie-Katalog](#6-telemetrie-katalog)  
7. [Live-Snapshot-Interpretation](#7-live-snapshot-interpretation)  
8. [Firmware-Iteration heute](#8-firmware-iteration-heute)  
9. [Bridge-/Pi-Verhalten](#9-bridge--pi-verhalten)  
10. [Ursachenmodell (warum Testton)](#10-ursachenmodell-warum-testton)  
11. [Was gelöst / was offen](#11-was-gelöst--was-offen)  
12. [Code-Anker](#12-code-anker)  
13. [Timeline](#13-timeline)  
14. [Review-Fragen & Optionen](#14-review-fragen--optionen)  
15. [Repro / Mess-Checkliste](#15-repro--mess-checkliste)  
16. [Abnahme](#16-abnahme)  
17. [Vergleichsprojekte (extern)](#17-vergleichsprojekte-extern)  
18. [Multi-Review-Konsens](#18-multi-review-konsens-2026-09-28-abend)

---

## 1. Executive Summary

### Zwei Baustellen (strikt trennen)

| ID | Problem | Status Feld | Primärhebel |
|----|---------|-------------|-------------|
| **A** | Menü-Navigation / Bridge-UID-State nach TCP-Reconnect | teilweise — Navigation funktioniert, bricht bei `stale/unknown uid` | Bridge: Snapshot behalten + Grace-Period; Link stabilisieren |
| **B** | Live-Audio vs. NBT-Cache/Readahead | **fail** — Stub-Testton aus HU-Cache | MSC: Silence+Xing, Pacing, Cursor/ID3; Warmup; Pulse-Quelle prüfen |

### Symptom (Ohr / UX)

Am BMW erscheinen korrekte Menüdateien (`Zurueck`, `Antenne Bayern  104.4 MHz`, `Hitradio RT1  90.2 MHz`) auf Stick **`PD0001`**. Die Dateien werden **automatisch** abgespielt; hörbar ist der **Stub-Testton**, nicht Live. Parallel: Menü lässt sich über mehrere Ebenen navigieren (`FM` → `Mehr…` → `Sender` → `A-M` → Stationen), bricht aber bei häufigen Bridge-Reconnects mit `stale/unknown uid` ab.

### Was technisch schon grün ist

- USB-Enumeration, MSC-Ready, FAT-Root/DIR (`bytesDir > 0`); Slot-Geometrie konsistent (Cluster 4/260/516/772 ↔ LBA 57/1081/2105/3129)  
- LFN-Namen, Serial/Volume-Bump (`PDnnnn`)  
- **Play-Detect feuert** (`play.guess` / `play_uid` mehrfach, auch Auto-Play ~6 s nach Plug)  
- `pump:page_next` und Mehr-Ebenen-Menü (wenn TCP stabil)  
- Bridge-Kette `activate` → `audio_start` → `audio_ack start` (Software bis Overlay-Armierung)

### Was rot / kritisch ist

- **Baustelle B:** Nach Guess ~1 s Full-Speed-Read (~1 MiB, 4 KiB/~4 ms), danach **keine** File-Reads mehr — Ohr = HU-Cache (Stub). `streamBytes == underruns` → **0 Live-Bytes** an den Host. Overlay/ffmpeg oft zu spät für das Lesefenster.  
- **Baustelle A:** ~10 TCP-Reconnects / 3 min (RSSI −76 dBm), `menu sync deferred`, danach `stale/unknown uid` für UIDs, die kurz zuvor gültig waren.  
- Snapshot ~15:55 ist **~5 min Nachlauf** (`bufferMs=0`, voller Ring, `ffmpeg exit 0` ≠ Zustand im Play-Fenster).  
- Serial bleibt bei Replug oft `PD0001` → HU-Cache-Treffer möglich.

### Ein-Satz-Diagnose (aktualisiert)

> Play-Detect und Menüpfad funktionieren grundsätzlich; kaputt sind (A) Bridge-Navigationszustand nach WLAN-Reconnect und (B) NBT-Readahead/Cache, der Stub spielt ohne den Live-Overlay zu konsumieren.

---

## 2. Nutzerbeobachtungen (Feld)

| # | Beobachtung | Zeit / Kontext |
|---|-------------|----------------|
| U1 | Kein Menü / „keine Titel“ / „angeschlossene Geräte enthalten keine Titel“ | Vormittag; ESP später offline |
| U2 | Nach Root-Fix: Listing ok, aber „nur Demo-Dateien“ | Nach 0.4.19 |
| U3 | Namen ändern sich (Zurueck / Sender A-M / …), nur Testton | Nach Remount-Fixes |
| U4 | Navigation Nächster/Zurück am BMW wirkt nicht | `play.guess=0` während Cache-Play |
| U5 | SoftAP zu Sender navigiert; BMW zeigt alte Dateien, kein Live-Ton | Vor Serial-Bump |
| U6 | **`PD0001` sichtbar**, Namen Antenne/Hitradio/Zurück korrekt, **wieder Testton-Auto-Play** | Nach 0.4.24 Remount |
| U7 | Navigation über mehrere Ebenen möglich (FM → Mehr → Sender → A-M), bricht aber „mitten im Menü“ | Bridge 15:44–15:45; `stale/unknown uid` nach Reconnect |

---

## 3. Soll-Konzept & Technik

> **Review-Lesart:** Abschnitte 3.1–3.6 = *wie es funktionieren soll*. Ab §4 = *wie es heute gebaut ist* und *was im Feld davon abweicht*.  
> Vollständige Planung: [KONZEPT-USB-MSC](../planung/KONZEPT-USB-MSC.md) · Herkunftsidee: [IDEE-USB-MSC-MENUE](../planung/IDEE-USB-MSC-MENUE.md).

### 3.1 Problem, das gelöst werden soll

PiDrive bedient den BMW heute primär über **Bluetooth A2DP + AVRCP**. Das Display zeigt nur **drei MPRIS-Zeilen**; AVRCP-Browsing öffnet der NBT Evo nicht. Skip = Cursor-Navigation ist ergonomisch teuer.

Kommerzielle Nachrüstungen (Referenz: **Dension DAB+U**) lösen „Liste + Ton am Werksradio“ anders: Gerät erscheint als **USB-Stick mit virtuellen MP3-Dateien**. Der NBT rendert seine **eigene USB-Medien-UI** (Ordner, Dateien, Dreh-Drück, Lenkrad Next/Prev). Ton = derselbe USB-MP3-Pfad (on-the-fly), nicht parallel BT.

**Lücke:** Der Pi 4 kann den BMW-USB-Host mit der Ist-Verkabelung nicht selbst als Gadget bedienen (USB-C = Netzteil, USB-A = Host). Deshalb sitzt ein **ESP32-S3** dazwischen.

### 3.2 Kernidee (Produktvertrag)

1. ESP hängt am BMW als **USB-MSC-Device** („virtueller Stick“).  
2. **Virtuelles FAT:** Ordner/Dateien = Menü / Sender / Aktionen; Dateinamen (LFN) = UI-Text.  
3. Fahrer wählt eine Datei → HU liest Sektoren → ESP erkennt „spielt Datei X“ → meldet UID an den Pi.  
4. Pi aktiviert die echte Quelle und schickt **Live-MP3** an den ESP.  
5. ESP liefert bei weiteren Reads den **Live-Bitstream statt Stub** → BMW-Decoder spielt PiDrive-Audio.  
6. **Ein Hörpfad gleichzeitig:** `audio_output = usb_gadget` **oder** `bt` (nie beide parallel zum selben Auto). BT bleibt Fallback.

**Designregel:** USB = Ton **und** UI (Dension-Vertrag). „Stub-MP3 am Stick + Ton über BT“ ist **kein** Produktziel.

### 3.3 Rollen der Komponenten

| Komponente | Soll-Rolle | Soll **nicht** |
|------------|------------|----------------|
| **PiDrive Core** | Quellen, UID-Menü, Trigger, `audio_output` | USB-Gadget sein |
| **pump_bridge** | `menu_set`, `play_uid`→Activate, ffmpeg→MP3-Frames, ID3/APIC | BMW-SCSI kennen |
| **ESP UsbMscGadget** | FAT rendern, SCSI READ beantworten, Play-Heuristik, StreamBuffer | Quellenlogik / Mixer |
| **BMW NBT** | Liste anzeigen, MP3 dekodieren, Cache/Read-ahead | PiDrive-Protokoll verstehen |

ESP kennt nur generische Items `{uid, name, kind}` — Semantik (FM-Freq, Web-URL, …) nur auf dem Pi.

### 3.4 Systembild (Ist-Lab = SoftAP/WLAN-PUMP)

```
┌─────────────┐  MSC READ/SCSI   ┌──────────────────────┐
│ BMW NBT Evo │ ◄──────────────► │ ESP32-S3 UsbMscGadget │
│ USB-Host    │                  │ FAT12 virt ~2 MiB    │
│ Liste+Decode│                  │ Stub-Head | Overlay  │
└─────────────┘                  └──────────┬───────────┘
                                            │ PUMP JSON+Bin TCP :9090
                                 ┌──────────▼───────────┐
                                 │ pump_bridge.py       │
                                 │ menu_set / play_uid  │
                                 │ audio_start + ffmpeg │
                                 └──────────┬───────────┘
                                            │
                                 ┌──────────▼───────────┐
                                 │ PiDrive Core         │
                                 │ FM/DAB/Web/…         │
                                 │ audio_output=usb_…   │
                                 └──────────────────────┘
```

V1-Konzept sah UART/CDC vor; Feld/Lab nutzt **WLAN (SoftAP oder STA) + TCP :9090** — gleiche Semantik, anderer Transport.

### 3.5 Soll-Ablauf End-to-End

```
A) Mount / Index
   BMW steckt / wählt USB-Medium
     → SCSI Inquiry / Read Capacity / FAT-Reads (Boot, FAT, Root, STATIONS)
     → ESP liefert Directory + Stub-Köpfe (Index darf „Datei existiert“ sehen)
     → HU zeigt Liste (Zurueck, Sender…); ESP markiert Index als settled (msc.quiet)

B) Auswahl (Fahrer)
   Fahrer wählt z.B. „Hitradio RT1…“
     → HU liest erneut vom Dateianfang (Play-Reads, nicht nur Prefetch)
     → ESP evaluatePlay → play.guess(uid) → PUMP Event play_uid
     → Bridge: Quelle aktivieren + audio_start + ffmpeg → MP3-Frames → ESP StreamBuffer
     → ESP stream.active für diesen Slot

C) Wiedergabe
   HU liest weiter Datei-LBAs
     → ESP onRead: StreamBuffer::readAt(offset)  (Live statt Stub)
     → BMW-Decoder hört Live-FM/Web
     → Vorpuffer hält Underruns klein (Dension-Idee: Sekunden Puffer vor dem Host)

D) Navigation
   SoftAP / Pi-Menü ändert Favoriten
     → menu_set → neue LFN im virtuellen FAT
     → HU sieht neue Namen erst nach Remount / Serial-Bump / Re-Plug
       (FAT nach Mount oft eingefroren — bekannte MSC-Eigenschaft)
```

**Lab-Bypass (ohne HU-Heuristik):** SoftAP `POST /api/lab/play` setzt künstlich `play.guess`/`play_uid` → prüft Audio-Pfad isoliert. Abnahme am Ohr bleibt trotzdem der BMW-USB-Pfad.

### 3.6 Stub vs. Live-Overlay (technischer Kerntrick)

| Phase | Was der Host lesen soll | Zweck |
|-------|-------------------------|--------|
| Index / vor Play | kurze **Stub-MP3** (Header + wenig Frames) | HU akzeptiert Datei, baut Liste/Cache |
| Nach `play.guess` + warmem Buffer | **dieselben Slot-LBAs**, Inhalt aus StreamBuffer | On-the-fly-Ersatz des Bits am gleichen „Dateipfad“ |
| Slot-Größe deklariert groß (512 KiB) | HU darf lange lesen / seeken | Platz für Live-Stream, nicht nur 6 KiB Song |

**Implizite Annahme (Feld widerlegt):** Der Host **liest nach der Auswahl erneut vom Stick**. Beim NBT gilt eher: aggressiver Prefetch → Cache → Playlist aus Stub **ohne** Re-Read. Overlay braucht deshalb **Warmup + Pacing + gültige Frames über die volle Länge**, nicht nur „nach Guess Bits austauschen“.

### 3.7 Was am Dension-Vorbild bewusst übernommen / abweicht

| Dension | PiDrive Soll (Konzept) | Feld-Ist 2026-09-28 |
|---------|------------------------|---------------------|
| Eine Quelle (DAB), flache Liste | Viele Quellen, Favoriten-Fenster (3 Slots) | 3 Slots + Zurueck ok |
| On-the-fly-MP3 = einziger Ton | ebenfalls (`usb_gadget`) | Overlay oft underrun / ungenutzt |
| Mehrere Sekunden Vorpuffer (ABSA 15–40 s) | ESP StreamBuffer + Warmup | `bufferMs≈0`, Underruns hoch |
| HU-Config-Files / FW-Matrix | Empirie an einem NBT Evo | Auto-Play + Stub-Cache dominant |
| Stable Senderliste | Dynamisches Menü + Remount | Remount/Serial (`PD0001`) nötig |

### 3.8 Kurz: Soll-Erfolgskriterien (Produkt)

1. Liste am BMW = aktuelle PiDrive-Favoriten/Aktionen (nach Remount ok).  
2. Auswahl einer Datei → innerhalb weniger Sekunden **Live**-Audio derselben Quelle.  
3. Next/Prev bzw. andere Datei → neuer `play_uid`, neuer Stream, kein Dauer-Stub.  
4. BT-Pfad bleibt wählbar und unangetastet, wenn `audio_output=bt`.

### 3.9 Konzept-Entscheidung (nach Vergleichs-Review Grok)

**Produktziel nicht aufgeben** (USB = UI + Ton, Pi = Gehirn, ESP = Gadget).  
**Technische Annahmen korrigieren** — das ist die eigentliche Überarbeitung:

| Behalten | Aufgeben / ersetzen |
|----------|---------------------|
| Multi-Level-Menü über MSC (langfristig) | Annahme „Host re-read nach Play“ |
| Remote-Audio Pi→ESP (WLAN/UART) | Annahme „48 KiB + bufferMs=0 reichen“ |
| Play-Detect → Overlay | Stub = kurzer Testton + 0xFF |
| Serial-Bump bei Identitätswechsel | Serial nur sporadisch / Lab-Remount |

### 3.10 Zielbild v1 (Review-Konsens 2026-09-30) — *BMW-robustes MSC-Menü*

Reviews (Folge-Runde) bestätigen A/B und schärfen das **lieferbare** v1 — kein neuer Architekturpfad:

| Regel | Inhalt |
|-------|--------|
| Geometrie | fest (Slots/FAT); Semantik nur per Snapshot/`menu_set` |
| Sichtbar | ≤4 Slots, Soft-Paging (`PAGE_CONTENT=3` + Nav) |
| Tiefe | bevorzugt 2–3 Ebenen; kein voller PiDrive-Dateibaum |
| Root-Beispiel | Favoriten · Quellen · Stop · Mehr… |
| Dynamik | FM/DAB/Suche nur als **feste Slots + Paging**, nicht frei mutierende Listen |
| Namen | kurz, FAT-sicher, Reihenfolge möglichst stabil |
| HU-Update | neue Namen oft erst nach **OTG-Replug / Serial-Bump** — Produktverhalten, nicht nur Lab-Workaround |
| Nicht über MSC | hochvolatile Detailzustände, WebUI-only-Bereiche |

**Lesart zu §3.9:** Hierarchie bleibt Konzept-Ziel; **v1 = bewusst reduziertes Snapshot-/Slot-Modell** (Code ist schon so). Volle PiDrive-Spiegelung ist verworfen. Folge: Baustelle A schließen → Menü-Export an v1 halten → B messgetrieben.

Externe Vorbilder: [§17](#17-vergleichsprojekte-extern) · Abweichungsanalyse: [§17.6](#176-warum-pidrive-anders-wehtut-grok).

---


## 4. Virtuelles Dateisystem (Geometrie)

### 4.1 BPB / Layout (seit 0.4.21, live gepatcht)

| Region | LBA | Inhalt |
|--------|-----|--------|
| BOOT | 0 | Demo-Boot + gepatchtes BPB (`total=4096`, `spf=8`, `spc=4`, `rootEnt=512`) |
| FAT0 | 1–8 | synthetisch + `patchFatFixed` |
| FAT1 | 9–16 | Spiegel |
| ROOT | 17–48 | Volume-Label (`PIDRIVE` / `PDnnnn`) + `STATIONS` + `SETTINGS` |
| STATIONS dir | 49–52 (cl 2) | `.` `..` + bis 3× (LFN+8.3) Station/Action |
| SETTINGS dir | 53–56 (cl 3) | Page/About-Slot |
| Slot 0 | 57–1080 | **512 KiB** |
| Slot 1 | 1081–2104 | **512 KiB** |
| Slot 2 | 2105–3128 | **512 KiB** |
| Slot 3 | 3129–3141 | kurz (~6 KiB) |

`demo_fat.bin` bleibt 256 KiB physisch; LBAs ≥512 bzw. außerhalb Stub-Remap werden synthetisiert (0x00/0xFF). Stub-Samples weiterhin aus Legacy-LBAs 43/59/75 im Image.

### 4.2 Kritischer Bug (behoben 0.4.19)

- **Falsch:** `patchFatChain` behandelte LBA 3–4 als FAT (`spf=2`-Annahme).  
- **Wahr:** Image/BPB hatte Root ab LBA 3 (`spf=1`).  
- **Effekt:** Beim Root-Read wurden `STATIONS`/`SETTINGS` mit FAT-Bytes überschrieben → leere HU-Liste.  
- **Fix:** FAT nur LBA 1–2 bzw. später 1–8/9–16; Root synthetisch.

### 4.3 Datei-Payload ohne Stream

| Phase | Sektoren ab Slot-Start | Inhalt |
|-------|------------------------|--------|
| `!indexSettled_` | 0–1 (~1 KiB) | Stub-MP3-Head |
| `!indexSettled_` | Rest | `0xFF` |
| `indexSettled_` | 0–15 (~8 KiB) | Stub-MP3-Head |
| `indexSettled_` | Rest | `0xFF` |
| `stream.active` & passender Slot | beliebig | `StreamBuffer::readAt(fileOff)` |

Stub ≈ 6,5 KiB gültige kurze MP3 (Testton), Rest **0xFF** (ungültige Frames). Der Decoder springt weiter → Playlist rauscht durch. Besser: **gültige Silence-Frames + Xing/Info über die volle Slot-Länge** (nicht „Stub entkernen“ → leere Dateien können aus der HU-Liste fliegen).

---

## 5. Play-Detection (Algorithmus)

### 5.1 Sequenzbildung

Bei File-Reads: Sequenz zählt Bytes vom (nahezu) Dateianfang; Mid-File-Prefetch setzt Sequenz zurück / markiert `prefetch`.

### 5.2 `evaluatePlay` (0.4.22+)

Reihenfolge:

1. inaktiver/leerer Slot → `bad_file`  
2. Start-LBA > `lbaStart + headLbaSlop` → `not_from_head`  
3. **`!indexSettled_` → `plug_window`** (Deep-Index-Schutz)  
4. Alter seit Plug < `playPlugWindowMs` → `plug_window`  
5. `seqBytes < playMinSeqBytes` → `seq_short`  
6. sonst `ok` → ggf. `play.guess` (Cooldown, already_playing)

### 5.3 `indexSettled_`

- gesetzt bei erstem `msc.quiet` (≥2 s keine File-Reads nach ≥2 KiB File-Traffic, Phase ≠ Play)  
- gelöscht bei Unplug / Remount  

### 5.4 Config (Snapshot)

Siehe [artifacts-…-config.json](artifacts-2026-09-28-esp-config.json):

- `playPlugWindowMs=500`  
- `playMinSeqBytes=6000`  
- `playHeadLbaSlop=12`  
- `playCooldownMs=5000`  
- `playPrefetchLbaSlop=2`  
- `labMode=true`

### 5.5 Reject-Reasons (im Feld gesehen)

| Reason | Bedeutung |
|--------|-----------|
| `plug_window` | zu früh / Index noch nicht settled |
| `not_from_head` + `prefetch` | Mid-File-Scan |
| `seq_short` | Head-Read zu kurz |
| `cooldown` | zweites Guess innerhalb Cooldown |

---

## 6. Telemetrie-Katalog

### 6.1 ESP Events (`/api/events`)

Wichtige Codes: `boot`, `msc.ready`, `msc.slots`, `msc.media_on`, `msc.remount`, `usb.otg.up/down`, `msc.phase`, `msc.first_read`, `msc.scsi.inquiry`, `play.reject`, `msc.prefetch`, `msc.quiet`, `play.guess`, `msc.stream`, `msc.stream_on/off`, `audio.start/stop`, `menu.set`, `pump.tcp*`, `pump.hello`, SoftAP/`wifi`/`mdns`.

Diag zusätzlich über PUMP: `{"t":"event","op":"diag","code":…,"detail":…}` → Bridge `[msc]` + `/tmp/pidrive_msc_diag.jsonl`.

### 6.2 `msc.phase`

| Phase | Typische Bedeutung |
|-------|-------------------|
| `scan` | Plug / Metadaten |
| `index` | File-Reads in Plug-Window |
| `quiet` | Pause nach Index → Cache-Verdacht |
| `play` | `play.guess` gefeuert |
| `idle` | Unplug |

### 6.3 Host-SCSI (`msc.host`)

Feldwerte typisch: `hint=hu-like`, `inquiry=1`, `capacity=3`, `tur` hoch, `prevent=7`, `msToInquiry≈1000`.

### 6.4 Slot-Stats

Pro Slot: `bytes`, `fromHead`, `midFile`, `maxSeq`, `lastAgeMs` — zeigen Index-Tiefe vs. Play.

### 6.5 Stream

`active`, `uid`, `size/cap/absEnd`, **`underruns`**, `id3Len`, `hasCover`.  
`readAt`: fehlt Daten hinter `absBase_` → `underruns_++` (Host bekommt Lücken/Leere).

### 6.6 Pi

- `/tmp/pidrive_usb_status.json` (poll)  
- `journalctl -u pidrive_pump_bridge`  
- `/tmp/pidrive_msc_diag.jsonl`

---

## 7. Live-Snapshot-Interpretation

> **Korrektur (Multi-Review):** Status-JSON ~15:55 ist **~5 min nach** dem Play-Ereignis (`msSincePlug` ≈ 324 600). `bufferMs=0`, Ring-Füllstand und `ffmpeg exit 0` sind **Nachlauf**, nicht der Zustand im Lesefenster ~15:52.

### 7.1 Play-Fenster Hitradio (~15:52, aus Events + Trace + Bridge)

| Signal | Wert | Lesart |
|--------|------|--------|
| Plug → Quiet | scan → first_read ~1 s → quiet ~file=557 KiB | Index |
| `play.guess` | Hitradio, ~6 s nach Plug, **ohne** manuelle Auswahl | Detector auf HU-Auto-Play |
| Leseburst nach Guess | ~95,9–97,1 s: ~1 MiB, 4 KiB alle ~4 ms | Full-Speed-Readahead, kein Pacing |
| Danach File-Reads | **keine** (auch Minuten später `lastReadLba` noch im Prefetch-Slot) | Ohr = **HU-Cache** |
| Overlay-Latenz | audio_stop/start + ffmpeg erst ~1,5–2,5 s nach Guess | Lesefenster auf Stream-Slot < 1 s → Overlay verpasst Consume |
| `streamBytes` vs `underruns` | **gleich** (z. B. 79872) | **0** Live-Bytes an Host geliefert |
| Ring | 48 KiB, absolut adressiert | Nach >48 KiB Dateioffset ist ID3-Kopf weg → späte Re-Reads = Leere |

### 7.2 Snapshot ~15:55 (Nachlauf — nicht überbewerten)

| Signal | Wert | Lesart |
|--------|------|--------|
| Namen | Zurueck / Antenne / Hitradio | LFN + Remount ok |
| `stream.active` / `underruns` / `bufferMs` | zeitweise true / ~8e4 / 0 | Nachlauf nach Timeout |
| `ffmpeg exit 0` | ~27 s nach Start | Forwarder tot; bei 48 kbit/s ≈ 154 KB — Ursache offen (Quelle/EOF?) |

**Wichtig:** Software-Kette bis `audio_ack start` kann **grün** sein, während das Ohr Stub hört — und der Snapshot den Play-Moment nicht mehr abbildet.

---

---

## 8. Firmware-Iteration heute

| Ver | Änderung | Feld-Ergebnis |
|-----|----------|---------------|
| 0.4.18 | FAT-safe Namen (`*`) | Nebenkriegsschauplatz |
| 0.4.19 | FAT-Patch trifft Root nicht | **Listing wieder da** |
| 0.4.20 | Remount bei Menu-Namenswechsel | Namen folgen nach Re-Plug |
| 0.4.21 | 2 MiB virt, 512 KiB Slots | tiefer Index; Cache bleibt |
| 0.4.22 | `indexSettled_` vor Guess | weniger False-Guess im Index |
| 0.4.23 | Stub-Head im Index nur ~1 KiB | Testton bleibt |
| 0.4.24 | Serial `PDnnnn` + Volume + 600 ms Hide; `/api/lab/remount` | **PD0001 + korrekte Namen**; Ton unverändert |

Git: Änderungen in `esp32.pidrive` **lokal uncommitted** (Stand Review). `HostScsiProbe.*` neu seit 0.4.17-Zweig.

---

## 9. Bridge-/Pi-Verhalten

### 9.1 `play_uid`-Dispatch (vereinfacht)

| UID/Typ | Aktion |
|---------|--------|
| `pump:page_next` / home | Paging |
| `folder` / `action` | `audio_stop` (ESP) + `stop_forward_only` + `activate` + `menu_set` (Remount-Risiko) |
| `station` / fav | `activate` + `audio.start` (zuerst intern `audio_stop`) |
| SoftAP lab | ESP sendet `play_uid` wie echter Guess |

### 9.2 Bekannte Bridge-Fallen

- `hold_menu_until` (~3 s): `menu_set` während Stream unterdrückt (Remount killt TCP) — Kommentar im Code.  
- `audio.start()` → immer erst `stop()` → Ack `op=stop` dann `op=start` ist normal.  
- Pulse-Monitor: `ffmpeg pulse:…mailbox…monitor @ 48k` — bei FM/DAB über `hw:1,0` kann der Monitor **Stille** sein (vor Overlay-Fixes messen).  
- **TCP-Reconnect:** früher `menu sync deferred` + State-Wipe → `stale/unknown`; jetzt Snapshot-Resync + UID-Grace (Feldtest).

### 9.3 Exemplarische Bridge-Sequenz (15:52 Hitradio) — Audio

Siehe [artifacts-…-bridge-excerpt.log](artifacts-2026-09-28-bridge-excerpt.log):

1. `msc.quiet`  
2. `play_uid` Hitradio  
3. `inject activate`  
4. `audio_stop` / `audio_start`  
5. `ffmpeg …`  
6. `audio_ack stop` dann `audio_ack start`  
7. später `ffmpeg exit 0` (Nachlauf)

### 9.4 Menü-Navigation (15:44–15:45) — Baustelle A

Nachgewiesen funktionsfähig (wenn TCP hält):

```
Hauptmenü → FM Radio / DAB+ → Mehr… (page_next) → Sender → Sender A-M → Antenne / Hitradio
```

| Zeit | Ereignis | Bedeutung |
|------|----------|-----------|
| 15:44:14 | `menu_set` FM/DAB | Ordner-Ebene |
| 15:44:24 | `play_uid` FM-Folder, `nav folder` ok | UID gültig |
| 15:44:31 | `reconnected` + `menu sync deferred` | State-Risiko |
| 15:44:32–33 | dieselbe UID → **`stale/unknown uid`** | Nav-State nach Reconnect inkonsistent |
| 15:44:54 | `play_uid pump:page_next` → `menu_set page=1` | Paging ok |
| 15:45:05…40 | weitere Reconnects (~1/min+) | Race BMW-Menü ↔ Bridge ↔ Audio |
| 15:45:35 | Station Antenne + `audio_start` | dann wieder Reconnect während Start |

**Race (vereinfacht):** BMW zeigt Menü X → TCP reconnect → Bridge invalidiert UID-Map → deferred `menu_set` → BMW sendet alte UID → `stale/unknown`.

---

## 10. Ursachenmodell

### Baustelle B — warum Testton (Audio)

#### H1 — Cache-Auto-Play + kurzes Lesefenster (primär, starke Evidenz)

- Index / Auto-Play liest Stub → `msc.quiet`  
- Nach Guess: ~1 s Full-Speed-Burst, dann **keine** USB-File-Reads mehr  
- Ohr = MediaStore-Cache (Stub); Live-Overlay wird nicht konsumiert  

**Evidenz:** Trace 95,9–97,1 s; `lastReadLba` Minuten später; Nutzer-Auto-Play.

#### H2 — Overlay zu spät / Ring liefert 0 Live-Bytes (stark, gekoppelt an H1)

- `streamBytes == underruns` → nie ein Live-Byte am Host  
- Warmup/ffmpeg-Start ~1,5–2,5 s nach Guess > Lesefenster  
- Absoluter Offset + 48 KiB-Ring: ID3-Kopf nach Durchlauf weg  

#### H3 — Detector zu streng (für diesen Feldtest **relativiert / nicht Engpass**)

- Guess kam; `playMinSeqBytes→2048` bringt für Audio nichts  
- Feintuning zurückstellen  

#### H5 — Pulse-Monitor = Stille bei FM/DAB (offen, prüfen)

- ffmpeg auf `mailbox.stereo-fallback` Monitor; Decoder ggf. `hw:1,0`  
- Messung: `ffmpeg -f pulse -i <monitor> -t 5 -af volumedetect -f null -` während FM + stderr loggen  

### Baustelle A — warum Menü „nicht durchkommt“

#### H4 — SoftAP/BMW-Liste desynchron (teilweise gelöst via Remount; UX bleibt)

#### H6 — TCP-Reconnect verwirft Nav-State (primär für Menü, starke Evidenz)

- Viele Reconnects, `menu sync deferred`, `stale/unknown uid` für zuvor gültige UIDs  
- `rev` zählt weiter → Format ok, Sync kaputt  

### Verworfen / relativiert

- „Play-Detect ist der Engpass“ — **widerlegt** für 2026-09-28 Nachmittag.  
- „FAT/Slot-Geometrie inkonsistent“ — **nachgerechnet ok**.  
- „512 KiB reichen gegen Cache“ — **widerlegt**.  
- „Stub komplett entkernen“ — **riskant** (HU kann Dateien verwerfen); Silence+Xing bevorzugen.

---

## 11. Was gelöst / was offen

| Thema | Status |
|-------|--------|
| Leere USB-Liste (Root-Destroy) | gelöst 0.4.19 |
| Illegal `*` in LFN | gelöst 0.4.18 + Bridge |
| Menü-Namen am BMW | gelöst mit Remount/Serial 0.4.20/24 |
| Stick-Identität erneuern (Lab-Remount) | gelöst `PDnnnn`; Unplug-Bump **0.4.25** |
| Play-Detect (`play.guess` / Auto-Play) | **ok für diesen Feldtest** |
| Mehr-Ebenen-Menü + `page_next` | **ok**, wenn TCP stabil |
| Nav-State nach TCP-Reconnect (`stale/unknown`) | **Fix im Bridge-Code** (Grace + Snapshot) — Feldtest offen |
| Serial pro Attach | **0.4.25** bumpt bei Unplug — Feldtest offen |
| WLAN-Reconnect-Rate Feld | **offen (P0 Link)** — SoftAP/UART bevorzugen |
| Live-Audio hörbar (nicht Stub-Cache) | **offen (P0 Baustelle B)** |
| Overlay-Pacing / Cursor / Silence+Xing | **offen (P0/P1 B)** |
| Pulse-Quelle vs. ALSA-Decoder | **offen (Messung vor großen B-Fixes)** |
| Play-Detect Feintuning (`minSeqBytes`) | **zurückgestellt** |
| Remount-UX ohne manuelles USB | offen (P2) |

### Empfohlene Reihenfolge (Konsens)

1. ~~Bridge: Nav-Snapshot + Grace-Period~~ → **umgesetzt** in `esp32.pidrive/tools/pump_bridge.py` (**Feldtest A/B/C** — siehe §15.1)  
2. Link: Feldtests SoftAP-direkt oder UART (weniger Reconnects bei schlechtem STA-RSSI).  
3. Audio-Messung: `tools/check_pulse_monitor.sh` während FM.  
4. MSC: Readahead-Messung → Pacing + Cursor/ID3; Silence+Xing.  
5. ~~Serial pro Plug~~ → **0.4.25** bumpt bei Unplug (Feldtest).

### Zwei Zustände — strikt getrennt (nicht vermischen)

```
TCP/WLAN-Reconnect  →  Bridge Nav-/UID-State   (Baustelle A — Grace + Snapshot)
USB Unplug/Attach   →  BMW MediaStore-Cache    (Serial PD0002… — Baustelle B-adjacent)
```

Grace 180 s ist robuster **Fallback** für den Feldtest, nicht die End-Architektur. Langfristig: atomarer `MenuSnapshot` (rev, page, nodes mit uid/action/parent). Grace vor dem Test **nicht** entfernen.

### Umgesetzt 2026-09-28 Abend (Code)

| Fix | Wo | Wirkung |
|-----|-----|---------|
| UID-Grace 180 s | `pump_bridge.py` | Folder/Station nach Drill-down/Reconnect weiter als `folder`/`station` erkannt (`[nav] grace hit`) |
| Menu-Snapshot resent | `try_reconnect` | statt `menu sync deferred` + State-Wipe |
| Kein Blind-Audio bei unknown | `play_uid` | verhindert Pulse-Start auf Folder-UIDs |
| Serial bei Unplug | `UsbMscGadget::applyUsbIdentity` 0.4.25 | nächster Attach ≠ `PD0001` |
| Nav Play-Detect | `evaluatePlay` / `isNavSlot` **0.4.26** | action/folder: `navMinSeqBytes=4096`; Cooldown blockiert keine Nav |

### Vorbereitung Autotest (2026-09-30)

1. **OTA 0.4.26** (sonst Nav-Fix fehlt): SoftAP `/ota-upload` oder Hub mit  
   `esp32.pidrive/dist/pidrive.0.4.26-dev.ota.esp32s3.bin` · prüfen: `curl -s http://192.168.178.89/api/status | jq .version`
2. **Bridge:** Grace-Code liegt auf dem Pi (`/home/pidrive/pump_bridge.py`). Fallback-Autostart: `scripts/ensure_pump_bridge.sh` (+ Cron). Ideal: einmal  
   `sudo install -m 440 scripts/sudoers-pidrive-pump-bridge /etc/sudoers.d/pidrive-pump-bridge`  
   dann `sudo systemctl restart pidrive_pump_bridge` (Pass B).
3. **Pass A:** nach `msc.quiet` gezielt **Zurueck** (ohne Lab) — erwarten `play.guess` + neue Namen.  
4. Dann Pass B (Bridge-Restart) / C (Paging) / D (Serial Unplug→`PDnnnn`).

### 11.1 Feldtest 2026-09-30 Vormittag (0.4.26)

| Schritt | Ergebnis |
|---------|----------|
| OTA `0.4.24` → **`0.4.26-dev`** | ok (`POST /ota-upload`); `hello_ack` + Menu-Snapshot |
| BMW Autoplay Stub (Zurueck / Nächster / Vorheriger / Favoriten) | **erwartet** — Baustelle B; `playGuessCount=0` nach Quiet |
| Manuelle Senderwahl am BMW | **kein** `play_uid` — HU spielt aus Cache, kein Re-Read |
| Lab-Play `Zurueck` | Nav greift (`action/back` → Pi-Menü Quellen); ESP-Slots folgten erst nach Bridge-Neustart |
| Lab-Play `pump:page_next` („Menue“) | `page→1` → Slots **Favoriten / Quellen / Stop / Mehr…** (`menu_ack` ok) |
| BMW zeigt neue Namen | **nur nach OTG Unplug/Replug** — Lab-Remount / Medienwechsel allein unzureichend |
| Serial | Unplug-Events `next=PD0002`/`PD0003` gesehen (D bedingt ok) |
| STA RSSI | ~−74…−75 dBm; vereinzelte TCP-Reconnects |

**Pass-Urteil:**

| Pass | Urteil | Hinweis |
|------|--------|---------|
| **A** Happy Path am BMW | **bedingt / rot für HU-`play_uid`** | Nav-Software ok per Lab; HU liefert nach Quiet kaum Guess |
| **B** Bridge-Restart | **teils grün** | Snapshot/Grace ok; siehe Bug unten |
| **C** Paging | **grün (Lab)** | `menu_set page=1` Ordnerliste; BMW-Sicht erst nach OTG |
| **D** Serial | **bedingt grün** | Bump gesehen, nicht systematisch am Display notiert |

**Neuer Bridge-Bug — `hello_ok_until`:** Nach `try_reconnect` setzte die Bridge früher `hello_ok_until = now+60`.  
`session_ok = (hello_ok_until == 0) or (now <= hello_ok_until)` → nach Ablauf der 60 s war `menu_set` **dauerhaft blockiert**, bis Prozess-Neustart. Folge: Pi-Menü wechselt, ESP-Slots bleiben alt (Feld 2026-09-30).  
**Fix (2026-09-30 Nachmittag):** `hello_ok_until = 0` nach gutem `hello_ack`, sonst `-1`; `session_ok = (hello_ok_until == 0)`. Deploy: `/home/pidrive/pump_bridge.py` auf dem Pi.

### 11.3 Feldtest 2026-09-30 Abend (~16:37–17:05) — A–D mit Fix

| Schritt | Ergebnis |
|---------|----------|
| FW / Bridge | `0.4.26-dev`; Fix deployed; `hello_ack` + `menu_ack` |
| Listing Root | BMW: Rock Antenne / Rock Antenne Bayern / Radio BOB! (Menue oft unsichtbar) |
| Lab `page_next` → Favoriten-Ordner → Lab Zurück | Nav-Kette ok; nach OTG BMW zeigt jeweilige Ebene |
| Manuell Sender nach Quiet / Pass B | **kein** `play_uid` — HU-Cache |
| Pass B Bridge-Restart + Lab `fav1` | `play_uid` + `audio_start` + ffmpeg + `stream.active`; **kein** `unknown` |
| Pass C Lab + OTG | BMW: **Favoriten / Quellen / Stop** |
| Volume-Name | BMW zeigt Gerät `PIDRIVE` / `PD0001` — Dateiliste erst nach Öffnen des Sticks |
| Pass D Serial | **fail/bedingt:** nach OTG oft ESP-**Reboot** (`boot` + Uptime ~1 min); `remountGen_` nur RAM → Unplug liefert erneut `next=PD0001`; Display bleibt PD0001 |

**Pass-Urteil Abend:**

| Pass | Urteil | Hinweis |
|------|--------|---------|
| **A** | **bedingt grün** | Lab-Nav + OTG-Listing ok; HU-`play_uid` nach Quiet weiter rot |
| **B** | **grün (Software)** | Restart + Lab-Station; manuell am BMW nicht bewertbar (Cache) |
| **C** | **grün** | Lab `page=1` + BMW nach OTG |
| **D** | **rot/bedingt** | Bump-Code feuert, aber Gen nicht NVS-persistent; OTG-Strom → Reset |

**Nächste Code-Schritte:** (1) `remountGen_` in NVS persistieren (+ ggf. ESP-Versorgung unabhängig von Host-OTG). (2) Baustelle B erst nach A-Nachzug: B0→B5. Kein Overlay-Patch parallel.

### 11.4 Feld + Lab 2026-10-01 (0.4.29 Auto / 0.4.30 Lab)

| Schritt | Ergebnis |
|---------|----------|
| Auto `.89` **0.4.29-dev** am BMW | Listing 3 Favoriten; **kein Testton** (B2 Silence+Xing) — Dateien wirken länger |
| Senderwahl / OTG Replug | Serial **`PD0002`** (Pass D); `play.guess` fav1 → Bridge ffmpeg → `overlay_warm` → `stream.active`, `underruns=0` |
| Ohr | **Stille** — nach Guess nur ~8–12 KiB File-Reads, danach keine USB-Reads (HU-Cache der Silence) |
| Auto offline (Fahrt) | Bridge temporär auf Lab `.88` |
| Lab **0.4.30-dev** B4 SoftAP | `tools/lab_b4_reread.py` **PASS** (ID3 sticky, `headResyncs`, `underrunΔ=0` nach Scroll) |
| Lab B4 MSC (Proxmox `/dev/sda`) | Head-reread nach Scroll: `streamBytes+=8192`, **`underruns+=0`**, `headResyncs` steigt |
| Lab **0.4.31-dev** sequential cursor | SoftAP Reads off=4 KiB…80 KiB: **underrun=0, live_ratio=1.0**; Status `cursorArmed`/`hostAbsCursor` |
| Lab paced MSC burst | Aggressiver Linux-Burst kann ESP-USB-Reset auslösen (Stream weg) — SoftAP-Pfad ist die stabile Lab-Messung |

**Lesart:** Software-Kette bis Overlay ist grün; A2 am Auto bleibt Cache/kein Re-Read. B4.31 liefert gültigen Stream bei Head-Re-Read **und** sequentieller Weiterlese. Bridge Lab aktuell → `.88`.

### 11.2 Lab-Rolle zweiter ESP (Review 2026-09-30)

Kein Extra-Konzept-Doc — nur Arbeitsaufteilung:

| Gerät | Rolle |
|-------|--------|
| **ESP1 (Auto)** | `192.168.178.89` · stabiler Fahrzeugstand; A-Fixes; Pass A–D; keine wilden B-Experimente |
| **ESP2 (Lab)** | Ziel-IP **`192.168.178.88`** (MAC `68B6B329339C`) · Debian/Proxmox-Host für Burst-/Silence-/Geometrie-Tests ohne Auto |

**Stand Lab-Hardware 2026-09-30:** `.88` antwortet noch als **`Ergometer-S3` / `fwType=ergo`** — für PiDrive-Lab erst **pidrive-FW** (z. B. 0.4.26 OTA/USB) flashen. USB am Proxmox (`192.168.178.108`) aktuell **kein** Espressif in `lsusb` (Kabel/Port prüfen; CT DebianCursor ohne USB-Passthrough — Tests besser am PVE-Host oder SoftAP/STA).

Debian ersetzt den NBT **nicht** (Cache/Autoplay/Reattach bleiben Auto-Themen). Es vorsortiert FAT/Slot/Overlay/`streamBytes`. **Phase‑1 NBT-Replay-Harness** (2026-10-01): `tools/nbt_suite.py` auf Proxmox via SG_IO — Baseline PASS/WARN, lab-safe ≤16 KiB/Burst (größere consecutive Slot-Reads rebooten den ESP). Auftrag: [esp32.pidrive AUFTRAG-NBT-REPLAY-HARNESS](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/auftraege/AUFTRAG-NBT-REPLAY-HARNESS.md).

---

## 12. Code-Anker

| Thema | Ort |
|-------|-----|
| Geometrie / Slots | `esp32.pidrive/src/msc/UsbMscGadget.h` (`kVirtSectorCount`, `kSlotSectors`, `slotRanges`) |
| onRead / Stub / Overlay | `UsbMscGadget.cpp` `onRead` |
| FAT/Root/Boot Patch | `patchBoot`, `patchRootDir`, `patchFatChain`, `patchDirNames` |
| Play-Detect | `evaluatePlay`, Sequenz in `noteDataRead` |
| Quiet / indexSettled | `UsbMscGadget::loop` |
| Remount + Serial | `remountMedia` · `USB.serialNumber` · `MSC.productRevision` |
| Lab Remount API | `App.cpp` `POST /api/lab/remount` |
| Host-SCSI | `HostScsiProbe.cpp` |
| Bridge play_uid | `tools/pump_bridge.py` ~1445+ |
| Bridge audio | `AudioFwd.start/stop` |
| fat_safe_name | `pump_bridge.py` |
| Pi Status-Poll | `pidrive/integration/usb_pump_client.py` |

---

## 13. Timeline

| Zeit | Ereignis |
|------|----------|
| ~07:42 | ESP offline (kein Ping); später „keine Titel“ |
| ~07:48 | Fix 0.4.18 vorbereitet (FAT-safe); OTA damals nicht möglich |
| 15:18 | ESP wieder `192.168.178.89`, OTG am Auto, Host `hu-like`, noch 0.4.17 |
| 15:19 | OTA 0.4.18 |
| 15:21 | Re-Plug: keine Titel; Diagnose Root-Destroy |
| 15:23 | OTA **0.4.19** → DIR-Reads, Listing |
| 15:25+ | Namen/Remount/512k/indexSettled (0.4.20–0.4.23) |
| 15:44 | SoftAP-Nav; BMW alte Liste |
| 15:50 | OTA **0.4.24**, Lab-Remount `ser=PD0001` |
| 15:51–15:52 | User USB-Zyklus; Quiet; `play.guess` Hitradio; audio_start; Underruns; Testton bleibt |
| 15:55 | Doku + Artefakte |
| **2026-09-30** | | |
| ~08:12 | Pi online; ESP erst SoftAP/STA später `.89` |
| ~08:19 | OTA **0.4.26-dev**; Bridge `hello_ack` + Snapshot |
| ~08:22–08:30 | HU Autoplay Stub; manuell kein `play_uid`; `hello_ok_until` blockiert `menu_set` |
| ~08:33 | Lab `page_next` → Favoriten/Quellen/Stop; BMW erst nach **OTG Replug** |
| ~08:38 | ESP abgesteckt (Fahrt); Doku §11.1 |
| ~16:20 | `hello_ok_until`-Fix deployed auf Pi |
| ~16:37–17:05 | Feld A–D Abend (§11.3): C grün am BMW; B Lab grün; D Serial nicht bootfest |
| **2026-10-01** | | |
| ~08:06–08:12 | Auto `.89` 0.4.29; B2 Stille; Guess+Overlay ohne Live-Ohr (Cache) |
| ~08:12+ | Auto offline; Lab OTA **0.4.30**; B4 SoftAP+MSC pass (§11.4) |
| ~09:15+ | Lab **0.4.31** sequential cursor SoftAP pass; paced MSC-Burst unzuverlässig (§11.4) |

---

## 14. Review-Fragen & nächste Experimente

### Priorisierte Experimente (messgetrieben)

1. ~~Fix `hello_ok_until`~~ — **deployed** 2026-09-30.  
2. ~~**Serial-Gen in NVS**~~ — FW **0.4.27-dev** (Feld: OTA + Pass D Unplug→PD0002 nach Reboot).  
3. Menü-Export an **v1 Snapshot/Slots** halten ([§3.10](#310-zielbild-v1-review-konsens-2026-09-30--bmw-robustes-msc-menü)).  
4. **B0→B1** (§15.2); optional ESP2+Debian-Host-Sim ([§11.2](#112-lab-rolle-zweiter-esp-review-2026-09-30)).  
5. **B2…B5** erst nach B0/B1.  
6. **Folgeauftrag:** atomarer `MenuSnapshot` (Grace = Übergang).

### Offene Fragen

1. Produkt-PUMP-Link: SoftAP vs. STA vs. UART?  
2. A2-Zielzeit: „wenige Sekunden“ vs. Warmup/ABSA-ähnlich — Zahl festlegen (Vorschlag: ≤5 s nach erstem Play-Read *oder* nach Warmup-OK).  
3. Remount bei jedem `menu_set`: akzeptabel vs. Sticky-Listing?  
4. Actions (`Zurueck`/`Mehr`) als kurze MP3s in derselben Playlist — Struktur ändern?

---

## 15. Repro / Mess-Checkliste

### 15.0 Mini-Checkliste vor jedem Feldtest

1. Neue `pump_bridge.py` deployed + `systemctl restart pidrive_pump_bridge`  
2. FW am ESP: `curl -s http://<esp>/api/status | jq .version` — ideal **`0.4.26-dev`** (Nav-Fix + Serial-Bump)  
3. Log-Filter läuft (unten)  
4. Reconnect-Methode für Pass B festgelegt: **`systemctl restart pidrive_pump_bridge`** (bevorzugt; nicht „WLAN kurz weg“)  
5. Protokoll-Spalten: Grace-Hits **A** vs. **B** getrennt · `snapshot resent` ja/nein · `unknown` ja/nein · Blind-`audio_start` nach unknown ja/nein · C: BMW-Anzeige vs. `page=`

```bash
journalctl -u pidrive_pump_bridge -f | grep -E 'hello_ack|snapshot resent|grace hit|unknown uid|menu_set|page|reconnected|audio_start|ffmpeg'
```

**Link:** Spontane Reconnects bei schlechtem STA (−76 dBm) sind **kein** Snapshot-Fail — als „A unter realem Link“ markieren. Ideal SoftAP-direkt oder UART für A/C.

### 15.1 Feldtest Baustelle A (jetzt)

> Nur Menü-/UID-Stabilität. **Ton/Stub egal** — sonst vermischt man A und B.

| Test | Ablauf | Erwartung / Schärfung |
|------|--------|------------------------|
| **A** Happy Path | Top → FM → Mehr → Sender → A-M → … **ohne** absichtlichen Reconnect | möglichst **0** `[nav] grace hit`. Grace zählen. Viele Grace-Hits in A = **bedingt grün** (Snapshot nach Drill-down unvollständig), nicht voll grün. **Kein** `unknown uid`. |
| **B** Reconnect | Menü offen → `systemctl restart pidrive_pump_bridge` → warten bis `hello_ack` **und** `menu snapshot resent` → **dann** denselben Eintrag. Ideal einmal **Folder**-UID (kritisch wie 15:44) und einmal Station | `snapshot resent` · UID gefunden (normal oder `grace hit`) · **kein** `unknown uid` · bei `unknown` **kein** `audio_start`/ffmpeg (Blind-Audio = Fail) |
| **C** Paging | `Mehr…` bis kein Mehr mehr; notieren was BMW zeigt („Seite 2: 3 Sender, kein Mehr“) vs. Log `page=` | `menu_set … page=0/1/2…` und HU-Inhalt passen; kein Sync-Abbruch |
| **D** Serial (separat) | Einmal Unplug/Replug; Stick-ID notieren | `PD0001`→`PD0002` (nur wenn FW≥0.4.25). Nicht mit A/B/C vermengen. Fehlt FW → „Serial nicht getestet“. |

**Urteil A:**

| Ergebnis | Folge |
|----------|--------|
| A+B+C voll grün (+ D optional) | Baustelle A fürs Fahrzeug **zu** → §15.2 B0 |
| A bedingt grün (viele Grace), B+C grün | A ok für Feld, Folgeauftrag MenuSnapshot |
| nur B rot | **nur** Bridge nachschärfen — kein Silence/Xing/Pacing |
| A schon rot | Snapshot/Lookup grundlegend — kein B-Code |
| Stub-Ton weiterhin | **kein** Fail von A/B/C |

### 15.2 Baustelle B — Sequenz B0→B5 (erst nach A grün)

Messgetrieben. **Kein** Silence/Xing/Pacing parallel zu B0/B1.

| ID | Frage | Abbruch / Pass |
|----|--------|----------------|
| **B0** | Pulse-Monitor = Stille bei laufendem FM/DAB? (`tools/check_pulse_monitor.sh`) | **Lab 09-30 pass:** System-Pulse Monitor trägt Tone (−22 dB) und Webradio (−15 dB). User-PipeWire Car-Only masked — Bridge nutzt `/var/run/pulse/native`. |
| **B1** | 1 lange Silence-/FAT32-Datei: wie viel/wie schnell liest der NBT? Liest er *nach* dem ersten Burst noch? | **Lab-Host `.88`:** 512 KiB Slot in **0,91 s** (~0,57 MB/s, 4 KiB-Chunks); danach **5 s idle = 0 Reads**. Entspricht Feld „Burst dann stille“. |
| **B2** | Silence+Xing über **volle** Slot-Länge (kein 6,5 KiB+0xFF) | **FW 0.4.28-dev** — Lab: ID3+Info + CBR-Silence-Frames (`fffb3064`), kein 0xFF-Pad. **Feld Auto-Play** noch offen. |
| **B3** | Pacing: leerer Ring → Silence/Busy statt Nullen | **FW 0.4.29:** Underrun→Silence-Frames. Lab paced (~Realtime): zuerst `underruns=0`, `streamBytes` wächst. Burst 96 KiB: live≈12 KiB + Silence-Rest. |
| **B4** | Cursor oder fester ID3-Kopf | **FW 0.4.31-dev** SoftAP sequential past head: `underrun=0`, live_ratio=1 (80 KiB). 0.4.30 nur Head-Remap. Feld-Ohr offen. |
| **B5** | Warmup vor `stream.active` (Sekunden, nicht 0; ABSA-Idee) | **FW 0.4.29:** `startStream` erst ab **8 KiB** Ring (`msc.overlay_warm`); vorher B2-Silence am Slot. |

**Lab 2026-09-30 Abend (ESP2 `.88` am Proxmox):** Bridge → `.88`; `tools/lab_overlay_consume.py`. Hinweis: aggressives Linux-`usb-storage`-Burst kann ESP USB-Reset/Reboot auslösen — NBT-Lastprofil anders; Feld trotzdem nötig.

**Dension-Ableitung (nicht 1:1 UX):** Puffer + lange nie endende Datei + Config — **nicht** „Station in &lt;2 s ohne Warmup“. Abnahme A2 muss eine Zahl bekommen (Warmup erlaubt), sonst bleibt A2 definitionsgemäß ewig rot. Actions (`Zurueck`/`Mehr`) möglichst nicht als kurze Playlist-MP3s neben Sendern.

### 15.3 Legacy-Lab (Audio-Ohr — nur nach B)

```bash
curl -s http://192.168.178.89/api/status | jq '{fw:.version,phase:.msc.phase,stream:.msc.stream,slots:[.msc.slotMap[].name]}'
# SoftAP lab/play — BMW-Ohr separat; underruns + weiterlaufende File-Reads
```

---

## 16. Abnahme

| ID | Kriterium | Stand |
|----|-----------|-------|
| A1 | Auswahl/Auto-Play → `play.guess` + UID | **pass** |
| A2 | Live-Audio nach Warmup/Play-Read (Zahl noch festlegen; Vorschlag ≤5 s) | **fail** — Sequenz B0→B5 |
| A3 | Listing während Stream sichtbar | **pass** |
| A4 | ≥2 Ebenen + `page_next` ohne `unknown uid` (A/B/C) | **bedingt grün** 2026-09-30 Abend (§11.3) — Lab+OTG; HU-Cache; Serial-D rot |
| A5 | Produkt-PUMP-Link dokumentiert | **offen** |

---

## 17. Vergleichsprojekte (extern)

Recherche 2026-09-28. Relevanz für Review: gleiche Grundidee (Host sieht USB-Stick / Dateien; Bitstream kommt on-the-fly), nicht 1:1-Kopien.

### 17.1 Kommerziell — gleiches Produktmuster wie PiDrive-Soll

| Projekt | Was es macht | Relevanz für uns | Links |
|---------|--------------|------------------|-------|
| **Dension DAB+U** | DAB(+)-Empfänger als USB-Stick; Sender/Actions = virtuelle MP3; HU-Config-Files; ABSA-Puffer | Primärreferenz (Menü + Ton über MSC) | [Produkt](https://www.dension.com/product/car-handsfree-and-multimedia/dabu/) · [USB-connected DAB](http://dab.dension.com/usb-connected-dab/) · [Support/Kompatibilität](https://techsupport.dension.com/781736-A-First-steps---compatibility) · [Support-Hub](https://techsupport.dension.com/745734-DABU) · [ars24](https://www.ars24.com/en/dension-dab-u-incl.-windshield-antenna) |
| **AP8224 „MP3DAB“-Dongles** | Billig-DAB-USB-Sticks; emulieren riesigen Stick (`MP3DAB`), Stationen als `.mp3`, Scan/CTL-Dateien | Beweis: Billig-MCU + virtuelles FAT + Live-MP3 am Host funktioniert | [GitHub AlbrechtL/AP8224-DAB-Dongle](https://github.com/AlbrechtL/AP8224-DAB-Dongle) (Reverse-Engineering / Protokollnotizen) |

### 17.2 Open Source / DIY — MSC + Live-Stream

| Projekt | Was es macht | Relevanz für uns | Links |
|---------|--------------|------------------|-------|
| **ESP8266+STM32 WiFi USB MP3 Dongle** | STM32 = MSC-Gadget (virt. 1 GB Stick); ESP8266 zieht MP3 per WiFi/UDP; Host-Reads → Remote-Chunks | Architekturnaheste Open-Source-Analogie (Gadget + WLAN-Nachschub) | [Hackaday.io #19747](https://hackaday.io/project/19747-esp8266stm32-wifi-usb-mp3-dongle) · [Files/Source](https://hackaday.io/project/19747/files) |
| **LCDTV Server (Lindsay Meek)** | PIC + WIZ550io: USB-MSC zum TV; Sektor-Reads → ATAOE/Ethernet → virtueller FAT/DLNA | Zeigt Sektor-Intercept + Netz-Backend; Puffer/Latenz-Thema | [GitHub lindsaymeek/TVServer](https://github.com/lindsaymeek/TVServer) · [Circuit Cellar / WIZnet](https://circuitcellar.com/wiznet2014/winners-second-meek/) |
| **vanheusden — Virtual USB (Pi Zero)** | `g_mass_storage` + Image-Rotation; **Serial-Nummer pro Image**, damit Auto neuen Stick erkennt | Direktes Vorbild für unser Serial-Bump (`PDnnnn`) / Remount | [vanheusden.com/electronics/virtual-usb](https://vanheusden.com/electronics/virtual-usb/) |
| **rgsilva — „Smartifying“ Hi-Fi** | Pi als Gadget; FUSE hijackt Reads einer „Datei“ → Live-MP3/Stream | Gleiches Cache-/Read-Problem am Consumer-Player | [rgsilva.com/blog/smartifying-my-hi-fi-system](https://rgsilva.com/blog/smartifying-my-hi-fi-system/) |
| **PicoVD** | RP2350 TinyUSB MSC, exFAT on-the-fly (read-only virt. Stick) | Saubere Virtual-Disk-Technik (kein Audio-Stream) | [GitHub pekkanikander/pico-extras-usb-msc-virtual-disk](https://github.com/pekkanikander/pico-extras-usb-msc-virtual-disk) |

### 17.3 Foren / Patente — Konzept bestätigt, Fallstricke dokumentiert

| Quelle | Kernaussage | Links |
|--------|-------------|-------|
| EEVblog: MSC real-time audio streaming | Sektorweise Reads abfangen; große Datei + Header; Host-Read-ahead unbekannt (2 s…60 s) | [EEVblog thread](https://www.eevblog.com/forum/projects/usb-mass-storage-file-transfers-and-real-time-fileaudio-streaming/) |
| VideoHelp: „fake mass storage stream“ | Host cached oft; Platzhalter-Datei / Buffer nötig | [forum.videohelp.com](https://forum.videohelp.com/threads/334693-Stream-audio-via-USB-as-fake-mass-storage) |
| **US 8,935,362** — Multi-media file emulation device | Emulation als MSD; Netz-Stream → Ringpuffer → Host liest „statische“ Datei | [Patents-Review (App.)](https://www.patents-review.com/a/20130318205-multi-media-file-emulation-device.html) · [Freepatents-ähnlich: USB drive emulation](https://www.freepatentsonline.com/y2010/0211874.html) |
| **US 8,606,071** — Interactive multimedia via storage interface | Live-AV → Encoder → Storage-Emulator an DASD/USB | Zusammenfassung u. a. über Patent-Indexseiten |

### 17.4 Abgrenzung (ähnlich, aber anderer Vertrag)

| Ansatz | Warum nicht unser Soll | Links |
|--------|------------------------|-------|
| USB **Audio Class** (UAC) Gadget | Host braucht UAC, nicht „MP3 vom Stick“ — BMW-USB-Medien-UI fällt weg | [Hackster RPi Audio Gadget](https://www.hackster.io/masonrf/rpi-zero-2-w-audio-gadget-448a6a) · Linux `f_uac1` |
| FM-Transmitter / Jack (mpradio) | Anderer physikalischer Pfad; kein HU-Listenmenü über USB | [morrolinux/mpradio](https://github.com/morrolinux/mpradio) |
| Nur Image-Swap ohne Live-Bitstream | Löst Playlist-Langeweile, nicht Live-Radio | vanheusden (oben) |

### 17.5 Review-Takeaways aus den Vergleichen

1. **Puffer vor dem Host** (Dension ABSA, Patent Ringbuffer, Hackaday Chunks) ist industrieüblich — unser Feld mit 0 Live-Bytes / verpasstem Lesefenster widerspricht dem erfolgreichen Muster.  
2. **Serial/Identity-Change** (vanheusden) ist bewährtes Mittel gegen HU-Cache — wir brauchen Serial **pro Attach**, nicht nur Lab-Remount.  
3. **HU-spezifisches Timing/Config** (Dension K-Files) existiert kommerziell; wir steuern empirisch gegen Auto-Play/Readahead.  
4. Open-Source-Vorbilder streamen oft **eine** große Datei; PiDrive braucht zusätzlich Menü-Semantik — deshalb Baustelle A (UID-State) und B (Overlay) getrennt halten.

### 17.6 Warum PiDrive anders „wehtut“ (Grok)

Vorbilder lösen dasselbe Grundproblem, aber **flach + lokal + stark gepuffert**. PiDrive weicht in fünf Punkten ab — genau dort sitzen A und B:

| Abweichung | Vorbilder | PiDrive Ist | Folge |
|------------|-----------|-------------|-------|
| **A Menü** | flach / stabil | Multi-Level + `page_next` + UID-State auf Bridge | Baustelle A (stale UID nach TCP-Reconnect) |
| **B Overlay** | 15–40 s Puffer, lange Datei, Host an Echtzeit | 48 KiB Ring, `bufferMs≈0`, absoluter Offset, kein Pacing | Burst → Cache → 0 Live-Bytes |
| **C Transport** | Tuner/Stream lokal im Gerät | Pi → WLAN-TCP → ESP | Reconnect killt State **und** Frames |
| **D Identität** | Serial/Image-Wechsel systematisch | oft `PD0001` (Bump erst 0.4.25) | HU-Cache-Treffer |
| **E Stub** | Silence + Xing über volle Länge | 6,5 KiB Testton + 0xFF | Playlist rast durch Stub |

**Kernsatz:** PiDrive will Dension-Ton **plus** Hierarchie-Menü über denselben fragilen Link. Vorbilder opfern Menü-Tiefe **oder** legen Puffer/Identität so aus, dass Cache/Reconnect den Hörpfad nicht killen. Fixes A+B schließen die Lücken, **ohne** das Produktziel aufzugeben ([§3.9](#39-konzept-entscheidung-nach-vergleichs-review-grok)).

### 17.7 Dension vs. Auto-Play / was wir *nicht* mitübernehmen

Dension **schaltet** Auto-Play nicht ab: nach Scan startet oft der erste Sender — **gewollt**. Jede Datei ist aber ein **gepufferter Dauer-Stream** (ABSA 15–40 s, K-Config), kein kurzer Stub. Track-Wechsel = neuer Buffer, **kein** Radio-Feeling.

| Übernehmen | Nicht übernehmen / klarstellen |
|------------|--------------------------------|
| Puffer vor Host, Identity-Wechsel, lange gültige Frames | UX „Umschalten in &lt;2 s ohne Warmup“ als Dension-Versprechen |
| Beweis: MSC+Live-MP3 am Auto-Host geht (auch AP8224/Hackaday) | Beweis gilt für **Schicht B (Bitstream)**, nicht für Multi-Level-UID-State (Schicht A) |
| Actions als eigene virtuelle Dateien | Actions als **kurze** Stub-MP3s in derselben Playlist wie Sender |

NBT-Auto-Playlist (Zurück/Mehr als Songs) löst man nicht über Namen, sondern über **weniger/längere gültige Tracks** + Pacing (B2–B4).

### 17.8 Kritische Lücken (Grok) — bewusst offen

| Lücke | Haltung |
|-------|---------|
| Grace = Pflaster, kein Nav-Modell | Feldtest-OK; Folgeauftrag `MenuSnapshot` |
| Serial nur Unplug | Mini-Check D; später monotonic Attach+Remount+NVS |
| B war Wunschliste | jetzt **B0→B5** messgetrieben (§15.2) |
| Link untergewichtet | Meta: Produkt-PUMP-Link **offen** (A5) |
| 3 Slots vs. 1 Datei | Geometrie-Experiment nach B1 |

---

## 18. Multi-Review-Konsens (2026-09-28 Abend)

Quellen: Claude (Artefakt-Detailanalyse), GPT (Bridge-Log / Menü-State), Gemini (Lösungsabriss + Vergleichsprojekte), Grok (Abgleich aller drei). **Gemeinsames Ergebnis:**

### 18.1 Was alle bestätigen

| Aussage | Konsens |
|---------|---------|
| Listing/LFN/`PD0001` ok | ja |
| Play-Detect feuert (auch Auto-Play) — **nicht** der Engpass | ja |
| `page_next` + Mehr-Ebenen-Menü funktionieren grundsätzlich | ja |
| Live-Audio: NBT-Readahead/Cache, Overlay nie/zu spät konsumiert, `streamBytes==underruns` | ja |
| Snapshot ~15:55 = Nachlauf | ja |
| FAT/Geometrie nicht die Ursache | ja |
| Bridge-Reconnect → `stale/unknown uid` = eigener Bug | ja |
| Zwei Baustellen strikt trennen; Menü-State **vor** großen MSC-Audio-Umbauten | ja |
| Stub nicht „entkernen“ → Silence+Xing | ja |
| Pulse-Monitor vor Overlay-Fixes prüfen | ja |

### 18.2 Priorität (Konsens-Reihenfolge)

1. Bridge Nav-Snapshot + Grace-Period; Link SoftAP/UART für Feld  
2. Pulse-Messung  
3. MSC Readahead-Messung → Pacing / Cursor / Silence+Xing  
4. Serial pro Attach  

### 18.4 Review der Cursor-Fixes (Grok / Gemini / GPT, Abend)

Konsens: Baustelle A richtig getroffen; B bewusst unangetastet = methodisch korrekt.

| Aussage | Konsens |
|---------|---------|
| Snapshot nach `hello_ack` = struktureller Fix für deferred-Lücke | ja |
| Grace 180 s = pragmatischer Fallback, langfristig atomarer MenuSnapshot | ja — Grace für Feldtest behalten |
| Unknown → kein Blind-Audio | ja |
| Serial-Bump = USB/MediaStore, getrennt von TCP-Nav | ja |
| Nächster Schritt nur Feldtest A/B/C, kein Overlay-Patch | ja |

### 18.5 Plan-Schärfung (Grok, spät)

- Pass A: Grace-Hits **zählen**; viele = bedingt grün  
- Pass B: `systemctl restart` Bridge; warten auf Snapshot; Folder-UID priorisieren; Blind-`audio_start` = Fail  
- Pass C: BMW-Anzeige vs. `page=` notieren  
- Serial = eigener Mini-Check D  
- B als **B0→B5**, nicht parallele Patches  
- Produkt-Link und A2-Zeitzahl noch festlegen  

---

## Anhang A — Slot-UIDs im Snapshot

| Name | UID |
|------|-----|
| Zurueck | `17092572655233380602` |
| Antenne Bayern  104.4 MHz | `8459731247190444814` |
| Hitradio RT1  90.2 MHz | `7954708905983732813` |
| Mehr… | `pump:page_next` |

## Anhang B — Related Docs

- [IDEE-USB-MSC-MENUE](../planung/IDEE-USB-MSC-MENUE.md) — Warum USB-MSC (AVRCP-Lücke, Dension)  
- [KONZEPT-USB-MSC](../planung/KONZEPT-USB-MSC.md) — Architektur, PUMP, FAT-MVP, Designregeln  
- [RUNTIME_FLOWS](../architektur/RUNTIME_FLOWS.md) — Laufzeitpfad `usb_gadget`  
- [AUFTRAG-ESP-PLAY-DETECTION](../auftraege/AUFTRAG-ESP-PLAY-DETECTION.md)  
- [USB-MSC-STREAM-LISTING-2026-09-18](USB-MSC-STREAM-LISTING-2026-09-18.md)  
- [LAB-MENU-WLAN](LAB-MENU-WLAN.md)  
- esp32.pidrive: `docs/planung/PLAY-DETECTION.md`, `PUMP.md`, `COVER-ID3.md`, `STATE.md`  
- **Extern:** [§17 Vergleichsprojekte](#17-vergleichsprojekte-extern) · [§18 Multi-Review](#18-multi-review-konsens-2026-09-28-abend)

---

*Ende Review-Paket. Artefakte + Bridge-Log mitlesen; Diagnose-Stand = §1 + §18 (nicht mehr „Play-Detect ist der Engpass“).*
