# Review-Paket: ESP-MSC ↔ BMW NBT — Feld 2026-09-28

**Zweck dieses Dokuments:** Alles Material für ein ausgiebiges Review (Problemverständnis, Telemetrie, Code-Anker, Artefakte, Hypothesen, offene Fragen, Abnahme).  
**Nicht:** fertige Lösungsskizze als Vorgabe — Optionen sind als Review-Fragen formuliert.

| Meta | Wert |
|------|------|
| Datum | 2026-09-28 (Feld ~07:40–15:55 Europe/Berlin) |
| FW live am Auto | **`0.4.24-dev`** |
| ESP STA | `192.168.178.89` · SoftAP `pidrive-2BC568` / `192.168.4.1` |
| Pi | `192.168.178.105` · `pidrive_pump_bridge` · PUMP-TCP `:9090` |
| HU | BMW NBT Evo (USB-Host), Host-Hint ESP: `hu-like` |
| Repos | `pidrive` (Doku/Bridge-Client) · `esphub/esp32.pidrive` (FW, uncommitted Stand 0.4.24) |
| Auftrag | [AUFTRAG-ESP-PLAY-DETECTION](../auftraege/AUFTRAG-ESP-PLAY-DETECTION.md) |
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

---

## 1. Executive Summary

### Symptom (aktuell)

Am BMW erscheinen korrekte Menüdateien (`Zurueck`, `Antenne Bayern  104.4 MHz`, `Hitradio RT1  90.2 MHz`) auf Stick **`PD0001`**. Die drei Dateien werden **automatisch nacheinander** abgespielt. Hörbar ist der **Stub-Testton** (Demo-MP3), nicht Live-FM/Web vom Pi — obwohl Pi zeitweise denselben Sender spielt und ESP `stream.active=true` melden kann.

### Was technisch schon grün ist

- USB-Enumeration, MSC-Ready, FAT-Root/DIR lesbar (`bytesDir > 0`)  
- LFN-Namen aus PiDrive-Menü  
- Serial/Volume-Bump → HU sieht „neuen“ Stick  
- PUMP-TCP Pi↔ESP  
- Teilweise `play.guess` → Bridge `audio_start` → ffmpeg → `audio_ack start`

### Was rot / kritisch ist

- HU **Auto-Play + Stub-Cache** dominiert das Hörereignis  
- Nach Index: `msc.quiet` („cache?“), wenig echte Play-Reads  
- Wenn Overlay armed: **`stream.underruns` extrem hoch**, `bufferMs=0`, ffmpeg endet oft schnell → kein stabiler Live-Bitstream zum Host  
- SoftAP-Navigation aktualisiert ESP-Menü sofort; BMW-Liste nur nach Remount/Re-Plug

### Ein-Satz-Diagnose

> Der NBT behandelt den ESP wie einen USB-Stick mit drei kurzen MP3s (Index → Cache → Playlist); PiDrive’s Live-Overlay hängt an USB-Re-Reads und einem warmen StreamBuffer — beides greift im aktuellen HU-Verhalten nicht zuverlässig.

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

**Implizite Annahme (jetzt Review-kritisch):** Der Host **liest nach der Auswahl erneut vom Stick** (oder konsumiert keinen fertigen Stub-Cache als Endprodukt). Wenn die HU den Stub-Head cached und als kompletten Track abspielt, hört man Testton — unabhängig davon, ob Bridge/ffmpeg grün sind. Genau das ist das aktuelle Feldproblem (§10).

### 3.7 Was am Dension-Vorbild bewusst übernommen / abweicht

| Dension | PiDrive Soll (Konzept) | Feld-Ist 2026-09-28 |
|---------|------------------------|---------------------|
| Eine Quelle (DAB), flache Liste | Viele Quellen, Favoriten-Fenster (3 Slots) | 3 Slots + Zurueck ok |
| On-the-fly-MP3 = einziger Ton | ebenfalls (`usb_gadget`) | Overlay oft underrun / ungenutzt |
| Mehrere Sekunden Vorpuffer | ESP StreamBuffer + Warmup | `bufferMs≈0`, Underruns hoch |
| HU-Config-Files / FW-Matrix | Empirie an einem NBT Evo | Auto-Play + Stub-Cache dominant |
| Stable Senderliste | Dynamisches Menü + Remount | Remount/Serial (`PD0001`) nötig |

### 3.8 Kurz: Soll-Erfolgskriterien (Produkt)

1. Liste am BMW = aktuelle PiDrive-Favoriten/Aktionen (nach Remount ok).  
2. Auswahl einer Datei → innerhalb weniger Sekunden **Live**-Audio derselben Quelle.  
3. Next/Prev bzw. andere Datei → neuer `play_uid`, neuer Stream, kein Dauer-Stub.  
4. BT-Pfad bleibt wählbar und unangetastet, wenn `audio_output=bt`.

Externe Vorbilder und Open-Source-Analoga: [§17 Vergleichsprojekte](#17-vergleichsprojekte-extern).

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

Stub ≈ 6,5 KiB gültige kurze MP3 (Testton). Das reicht der HU zum „fertigen Song“ aus dem Cache.

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

Aus Status ~15:55 und Events nach Re-Plug (~15:52):

| Signal | Wert | Lesart |
|--------|------|--------|
| Namen | Zurueck / Antenne / Hitradio | LFN + Remount ok |
| `bytesFile` | ~0,5–1,6 MiB | starker Index |
| `msc.quiet` | nach ~2 s Pause | Cache-Fenster |
| `play.guess` | Hitradio UID | Detector feuerte |
| `audio.start` + ffmpeg | ja | Bridge-Pfad ok |
| `stream.active` | true (zeitweise) | Overlay armed |
| `underruns` | ~8e4 | Live-Bytes fehlen am Read |
| `bufferMs` | 0 | kein Vorpuffer |
| `ffmpeg exit 0` | ~27 s nach Start | Forwarder tot |
| Nutzer hört | Testton-Playlist | Cache/Stub dominiert |

**Wichtig für Review:** Es gibt Phasen, in denen die **Software-Kette bis `audio_start` grün** ist, das **Ohr aber trotzdem Stub** hört. Das trennt „Detector/Bridge kaputt“ von „Host-Cache / Overlay-Consume kaputt“.

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
- Pulse-Monitor: `ffmpeg pulse:…mailbox…monitor @ 48k` — Abhängigkeit vom aktuellen Default-Sink.

### 9.3 Exemplarische Bridge-Sequenz (15:52 Hitradio)

Siehe [artifacts-…-bridge-excerpt.log](artifacts-2026-09-28-bridge-excerpt.log):

1. `msc.quiet`  
2. `play_uid` Hitradio  
3. `inject activate`  
4. `audio_stop` / `audio_start`  
5. `ffmpeg …`  
6. `audio_ack stop` dann `audio_ack start`  
7. später `ffmpeg exit 0`

---

## 10. Ursachenmodell (warum Testton)

### Hypothese H1 — Cache-Auto-Play (primär, starke Evidenz)

- Index liest Stub-Heads (+ Pad) → `msc.quiet`  
- HU spielt kurze MP3s aus MediaStore **ohne** kontinuierliche USB-Reads  
- Ohr = Stub; ESP sieht wenig Play-Traffic  

**Evidenz:** Nutzer-Auto-Play; `msc.quiet cache?`; hohe `bytesFile` vor Quiet; Testton trotz korrekter LFN.

### Hypothese H2 — Overlay armed, Host konsumiert nicht / underrunt (sekundär, starke Evidenz)

- `play.guess` + `stream.active` + ID3 ok  
- `underruns` enorm, `bufferMs=0`, ffmpeg exit  
- Selbst bei USB-Reads: leerer Ring → kein Radio  

**Evidenz:** Status-Snapshot Hitradio; Bridge-Log.

### Hypothese H3 — Detector zu streng / zu spät (teilweise)

- Viele Rejects im Index; Guess erst nach Quiet  
- Kann echte Plays verpassen oder erst mitten in der Playlist treffen  

### Hypothese H4 — SoftAP vs. BMW-Liste desynchron (gelöst für Namen via Remount; UX bleibt)

- ESP-Menü ≠ BMW-Anzeige ohne Remount/Serial-Bump  

### Verworfen / relativiert

- „Nur Favoriten-`*`“ als alleinige Ursache für leere Liste (Root-Destroy war der Killer).  
- „512 KiB reichen gegen Cache“ — **widerlegt** im Feld (HU indexiert trotzdem großzügig / spielt Stub-Head).

---

## 11. Was gelöst / was offen

| Thema | Status |
|-------|--------|
| Leere USB-Liste (Root-Destroy) | gelöst 0.4.19 |
| Illegal `*` in LFN | gelöst 0.4.18 + Bridge |
| Menü-Namen am BMW | gelöst mit Remount/Serial 0.4.20/24 |
| Stick-Identität erneuern | gelöst `PDnnnn` |
| Live-Audio hörbar | **offen (P0)** |
| Auto-Play Stub-Playlist | **offen (P0)** |
| Overlay-Underruns / ffmpeg-Halt | **offen (P0)** |
| Play-Detect Feintuning | offen (P1) |
| Remount-UX ohne manuelles USB | offen (P2) |

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

---

## 14. Review-Fragen & Optionen

*(Zur Bewertung — keine Prioritätsfestlegung durch dieses Dokument.)*

1. Ist der richtige Primärhebel **Stub-Bitstream** (kein abspielbarer Testton im Cache), **HU-Playlist-Vermeidung** (weniger/eine Datei), oder **erzwungener Re-Read** (Größe/Header/Fehler)?  
2. Wie korrelieren wir **zwingend** `audio_start` → erster Overlay-Host-Read → `underruns`-Delta? Fehlt Telemetrie?  
3. Ist `ffmpeg exit 0` nach ~30 s Symptom (Monitor-EOF) oder Bug (TCP/Bridge)?  
4. Soll SoftAP-Play **ohne** BMW-Re-Read als Abnahme zählen (Lab) oder nur Ohr am USB?  
5. Remount bei jedem `menu_set`: akzeptabler UX-Tradeoff vs. Sticky-Listing?  
6. Brauchen wir getrennte Profiles: `desk/phone` vs. `nbt-autoplay`?  
7. Ist 512 KiB Slot + 2 MiB Image die richtige Größenordnung oder Richtung Multi-MiB/„endlose“ Datei?  
8. Sollte `indexSettled_` anders definiert werden (z. B. nach N Bytes Index statt Quiet)?  

---

## 15. Repro / Mess-Checkliste

### Vorbereitung

```bash
curl -s http://192.168.178.89/api/status | jq '{fw:.version,phase:.msc.phase,guess:.msc.playGuessCount,rej:.msc.playRejectCount,stream:.msc.stream,slots:[.msc.slotMap[].name]}'
curl -s -X DELETE http://192.168.178.89/api/events
# optional:
curl -s -X POST http://192.168.178.89/api/lab/remount
```

### Am BMW

1. USB-Medien verlassen, 10 s warten, neu öffnen (Stick-ID notieren).  
2. **Nicht** Sofort-Skip: warten bis Liste steht.  
3. Beobachten: Auto-Play ja/nein? Ton Stub oder Live?  
4. Parallel Pi:  
   `journalctl -u pidrive_pump_bridge -f | grep -E 'msc|play_uid|audio|ffmpeg'`

### Erfolg nur wenn

- Ohr = Live-Sender **und**  
- `stream.underruns` steigt nicht explosionsartig **und**  
- nach `audio_start` File-Reads auf dem Stream-Slot weiterlaufen (`slotMap[].bytes` / Trace)

### Lab-Bypass (isoliert Audio-Pfad)

```bash
curl -s -X POST http://192.168.178.89/api/lab/play \
  -H 'Content-Type: application/json' \
  -d '{"uid":"<station-uid>"}'
curl -s http://192.168.178.89/api/status | jq .msc.stream
# SoftAP /api/lab/listen — Browser; BMW-Ohr separat bewerten
```

---

## 16. Abnahme

| ID | Kriterium | Stand |
|----|-----------|-------|
| A1 | Auswahl → `play.guess` + UID | teilweise |
| A2 | Live-Audio ≤ wenige Sekunden, nicht Stub | **fail** |
| A3 | Listing während Stream sichtbar | pass (static FAT) |

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

1. **Puffer vor dem Host** (Dension ABSA, Patent Ringbuffer, Hackaday Chunks) ist industrieüblich — unser Feld mit `bufferMs≈0` / massiven Underruns widerspricht dem erfolgreichen Muster.  
2. **Serial/Identity-Change** (vanheusden) ist bewährtes Mittel gegen HU-Cache — wir nutzen `PDnnnn` bereits für Menü-Refresh.  
3. **HU-spezifisches Timing/Config** (Dension K-Files) existiert kommerziell; wir haben nur ein Auto und müssen empirisch gegen Auto-Play/Stub-Cache steuern.  
4. Open-Source-Vorbilder streamen oft **eine** große Datei; PiDrive braucht zusätzlich **Menü-Semantik** (mehrere UIDs + Play-Detect) — das ist der schwerere Teil.

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
- **Extern:** [§17 Vergleichsprojekte](#17-vergleichsprojekte-extern)

---

*Ende Review-Paket. Bei Review-Start: Artefakt-JSONs + Bridge-Log mitlesen; FW-Diff `UsbMscGadget.*` 0.4.17→0.4.24 lokal.*
