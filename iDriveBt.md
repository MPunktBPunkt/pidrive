# iDrive Bluetooth — Technische Referenz für PiDrive

**BMW 118d F20/F21 LCI 2017 · NBT Evo · PiDrive v0.11.57**  
Erstellt auf Basis von Quellcode-Analyse, BlueZ-Dokumentation und Felderfahrung.

---

## Inhaltsverzeichnis

1. [Systemarchitektur](#1-systemarchitektur)
2. [Bluetooth-Profile: vollständige Matrix](#2-bluetooth-profile-vollständige-matrix)
3. [AVRCP im Detail](#3-avrcp-im-detail)
4. [A2DP Audio-Streaming](#4-a2dp-audio-streaming)
5. [BlueZ-Stack unter Linux](#5-bluez-stack-unter-linux)
6. [PiDrive D-Bus Architektur](#6-pidrive-d-bus-architektur)
7. [MPRIS2 Interface](#7-mpris2-interface)
8. [Pairing-Prozess](#8-pairing-prozess)
9. [Bekannte Probleme und Workarounds](#9-bekannte-probleme-und-workarounds)
10. [Diagnosebefehle](#10-diagnosebefehle)

---

## 1. Systemarchitektur

### 1.1 Rollen im PiDrive-Kontext

PiDrive verhält sich gegenüber dem BMW iDrive **identisch wie ein Smartphone**:

```
┌─────────────────────────────────────┐
│ PiDrive (Raspberry Pi)              │
│                                     │
│  BlueZ 5.x (Linux Bluetooth Stack)  │
│  ├── A2DP Source   (sendet Audio)   │
│  ├── AVRCP Target  (empfängt Cmds)  │
│  └── MPRIS2 Target (D-Bus)          │
└──────────────┬──────────────────────┘
               │ Bluetooth BR/EDR
               │ (Classic BT, nicht BLE)
               ▼
┌─────────────────────────────────────┐
│ BMW NBT Evo (iDrive)                │
│                                     │
│  ├── A2DP Sink     (empfängt Audio) │
│  ├── AVRCP Controller (sendet Cmds) │
│  └── HFP Controller (Telefonie)     │
└──────────────┬──────────────────────┘
               │
               ▼ intern (MOST / BT Audio Bus)
┌─────────────────────────────────────┐
│ BMW DSP / Verstärker                │
│ → Fahrzeuglautsprecher              │
└─────────────────────────────────────┘
```

**Kernpunkt:** PiDrive ist die *Source*, BMW ist die *Sink*. Nicht umgekehrt.  
Das unterscheidet PiDrive von einem BT-Kopfhörer (der als Sink agiert).

### 1.2 Cambridge Silicon Radio Dongle

PiDrive nutzt einen **Cambridge Silicon Radio (CSR) USB-BT-Dongle**:

| Parameter | Wert |
|---|---|
| Chip | CSR (Qualcomm) — typisch CSR8510 oder CSR8511 |
| Bluetooth | BR/EDR (Classic), kein BLE für Audio |
| Interface | USB HCI |
| Linux-Treiber | `btusb` (im Kernel) |
| BlueZ-Unterstützung | vollständig |

Prüfen: `hciconfig hci0 version` — zeigt Chip-Version.

---

## 2. Bluetooth-Profile: vollständige Matrix

### 2.1 Für PiDrive relevante Profile

| Profil | Version | PiDrive-Rolle | BMW-Rolle | Priorität |
|---|---|---|---|---|
| **A2DP** | 1.3 | Source | Sink | 🔴 Pflicht |
| **AVRCP** | 1.4 | Target | Controller | 🔴 Pflicht |
| **MPRIS2** | — | Target (D-Bus) | — | 🔴 intern |
| HFP | 1.7 | (nicht genutzt) | Gateway | 🟡 optional |
| PBAP | 1.1 | (nicht genutzt) | Client | ⬜ irrelevant |
| MAP | — | (nicht genutzt) | Client | ⬜ irrelevant |

PiDrive implementiert **nur A2DP Source + AVRCP Target** — bewusst schlank.

### 2.2 SDP-Records die PiDrive publiziert

BlueZ registriert beim Pairing automatisch:

| Service | UUID | Bedeutung |
|---|---|---|
| A2DP Source | `0x110A` | PiDrive sendet Audio |
| AVRCP Target | `0x110C` | PiDrive empfängt Steuerbefehle |
| Generic Audio | `0x1203` | Pflicht-Record |

BMW sucht beim Pairing nach `0x110A` (A2DP Source) und `0x110C` (AVRCP Target).  
Ohne `0x110A` kein Audiostreaming. Ohne `0x110C` keine Tastensteuerung.

Prüfen: `sdptool browse <BMW-MAC>` oder `sdptool browse local`

### 2.3 A2DP Codec-Verhandlung

Beim Verbindungsaufbau verhandeln BMW und BlueZ den Audio-Codec:

| Codec | UUID | BMW F20 2017 | PiDrive | Empfehlung |
|---|---|---|---|---|
| **SBC** | `0x00000000` | ✅ mandatory | ✅ immer | **primär verwenden** |
| AAC | `0x00000002` | ⚠ SW-abhängig | ⚠ optional | instabil auf alten SW |
| aptX | `0x0000004F` | ❌ nein | ❌ nein | — |
| LDAC | — | ❌ nein | ❌ nein | — |

**Empfehlung:** SBC erzwingen für Stabilität. BlueZ bevorzugt automatisch den besten gemeinsamen Codec.

SBC-Parameter die BMW erwartet:
```
Sampling Freq:    44100 Hz (Standard) oder 48000 Hz
Channel Mode:     Joint Stereo (bevorzugt) oder Stereo
Block Length:     16
Subbands:         8
Allocation Method: Loudness
Bitpool:          2-53 (Standard) → ~328 kbps bei 44.1 kHz Joint Stereo
```

---

## 3. AVRCP im Detail

### 3.1 AVRCP-Versionen

| iDrive Generation | AVRCP | Praxisbeobachtung |
|---|---|---|
| CIC (bis 2012) | 1.0–1.3 | keine Metadaten |
| NBT (2013–2015) | 1.3 | Metadaten, kein Cover |
| **NBT Evo ID5 (2016+)** | **1.4** | **Cover teilweise, Browsing rudimentär** |
| NBT Evo ID6 (2017+) | 1.4 (partiell 1.5) | abhängig von SW-Stand |

**BMW 118d F20 2017 = NBT Evo ID5/ID6 → AVRCP 1.4**

Für PiDrive bedeutet das: wir müssen AVRCP 1.4-kompatibel antworten.  
AVRCP 1.6-Features (Browsing über OBEX) werden ignoriert oder führen zu Fehlern.

### 3.2 AVRCP Pass-Through Kommandos (BMW sendet → PiDrive empfängt)

BMW sendet folgende Opcodes über den AVCTP-Kanal:

| Taste iDrive | Opcode (hex) | Name | PiDrive-Trigger |
|---|---|---|---|
| ► / OK | `0x44` | PLAY | `play_pause` |
| ❚❚ | `0x46` | PAUSE | `play_pause` |
| ■ | `0x45` | STOP | `stop` |
| ⏭ (Next) | `0x4B` | FORWARD | `next` |
| ⏮ (Prev) | `0x4C` | BACKWARD | `previous` |
| 🔊+ | `0x41` | VOLUME_UP | `volumeup` |
| 🔊− | `0x42` | VOLUME_DOWN | `volumedown` |

Jedes Kommando kommt als **PRESSED** und **RELEASED** Event.  
BlueZ mapped diese auf `org.bluez.MediaPlayer1` D-Bus Properties.

### 3.3 Event Notification — was BMW registriert

BMW registriert via `REGISTER_NOTIFICATION` Command:

| Event | ID | Bedeutung für PiDrive |
|---|---|---|
| Playback Status Changed | `0x01` | Play/Pause/Stop korrekt senden |
| Track Changed | `0x02` | trackid bei Quellwechsel ändern |
| Track Reached End | `0x03` | für Radio nicht relevant |
| Playback Position | `0x05` | wir senden 0 (Live-Stream) |
| Available Players Changed | `0x0A` | bei Reconnect relevant |
| Addressed Player Changed | `0x0B` | bei Player-Wechsel |

**Kritisch:** BMW erwartet bei jedem Wechsel (Quelle, Sender, Titel) ein `TrackChanged (0x02)` Event.  
PiDrive implementiert das über `mpris:trackid`-Änderung + kurzes `Stopped`-Signal.

### 3.4 GetElementAttributes — Metadaten-Request

BMW fordert nach Track Changed die Metadaten an:

```
BMW → AVRCP GetElementAttributes(0x0000000000000000)
  Requested Attributes:
    0x01 = Title     → xesam:title  (max 64 Zeichen)
    0x02 = Artist    → xesam:artist (max 64 Zeichen)
    0x03 = Album     → xesam:album  (max 64 Zeichen)
    0x04 = Track Nr  → xesam:trackNumber
    0x07 = Genre     → xesam:genre  (max 32 Zeichen)

PiDrive → AVRCP GetElementAttributes Response
  via MPRIS2 Metadata D-Bus Property
```

BMW zeigt je nach Display-Version:
- **Zeile 1:** `xesam:title` (Titel / Sendername)
- **Zeile 2:** `xesam:artist` (Interpret / Frequenz)
- **Zeile 3 (klein):** `xesam:album` (Quellenname)

### 3.5 Absolute Volume — Achtung

AVRCP 1.4 unterstützt Absolute Volume Control. BMW kann versuchen, die Lautstärke direkt zu setzen.

**Bekanntes Problem:** Absolute Volume führt auf NBT Evo zu asynchronen Sprüngen und Konflikten mit der internen Lautstärkeregelung.

PiDrive-Verhalten: `Volume: 1.0` in MPRIS2 (fixiert), keine Absolute-Volume-Änderungen zurückschreiben. BMW regelt die Lautstärke intern über seinen DSP.

---

## 4. A2DP Audio-Streaming

### 4.1 Verbindungsaufbau (L2CAP Channels)

```
PiDrive                    BMW NBT Evo
   │                           │
   │──── L2CAP Connect ────────▶│  PSM 0x0019 (AVDTP Signaling)
   │◀─── L2CAP Connect Rsp ────│
   │                           │
   │──── AVDTP DISCOVER ───────▶│  Codec-Verhandlung
   │◀─── AVDTP DISCOVER RSP ───│
   │                           │
   │──── AVDTP SET_CONFIGURATION ▶│  SBC Parameters festlegen
   │──── AVDTP OPEN ──────────▶│
   │──── L2CAP Connect ────────▶│  PSM 0x0019 (AVDTP Media Transport)
   │──── AVDTP START ─────────▶│
   │                           │
   │════ SBC Audio Frames ═════▶│  Kontinuierlicher Stream
```

### 4.2 SBC Encoding in BlueZ

BlueZ übernimmt das SBC-Encoding automatisch. PiDrive muss nur PCM-Daten liefern (über PulseAudio):

```
rtl_fm / mpv / welle-cli
    → PCM (32000/44100/48000 Hz, mono/stereo)
    → PulseAudio (System-Mode)
    → BlueZ A2DP Sink (bluez_sink.<MAC>.a2dp_sink) ← PiDrive schreibt hier hin
    → BlueZ SBC Encoding
    → BT HCI → RF → BMW
```

**Achtung:** PiDrive schreibt in den PA-Sink (`bluez_sink.<MAC>`), nicht in eine Quelle.  
PulseAudio + BlueZ handeln die A2DP-Source-Rolle gegenüber BMW.

### 4.3 Latenz und Pufferung

| Parameter | Typischer Wert |
|---|---|
| SBC-Frame-Größe | 128 Byte (13ms bei 48kHz) |
| A2DP-Puffer im BMW | ~200–400ms |
| Gesamtlatenz Pi→BMW | 250–600ms |

Für Radio/Streaming unkritisch. Für Sprachsteuerung/Diktat nicht geeignet.

### 4.4 Automatischer Reconnect

Nach BMW-Start versucht das iDrive aktiv den Reconnect (falls PiDrive gepairt und trusted).  
PiDrive-Seite: `bt_watcher.py` überwacht BlueZ D-Bus Events und reagiert auf `Connected: yes`.

Nach Reconnect: PulseAudio-Modul `module-bluetooth-discover` erkennt neuen Sink automatisch.

---

## 5. BlueZ-Stack unter Linux

### 5.1 BlueZ-Architektur auf PiDrive

```
Kernel Space:
  btusb (CSR USB Adapter) → hci0
  bluetooth.ko (HCI Layer)

User Space:
  bluetoothd (BlueZ 5.x Daemon)
    ├── org.bluez.Adapter1    → hci0
    ├── org.bluez.Device1     → BMW MAC
    ├── org.bluez.MediaPlayer1 → AVRCP
    └── org.bluez.MediaControl1 → A2DP

PiDrive:
  avrcp_trigger.py
    ├── dbus-monitor (empfängt BlueZ Events)
    ├── bluetoothctl (Verbindungsverwaltung)
    └── /tmp/pidrive_cmd (Trigger an Core)
```

### 5.2 BlueZ D-Bus Interfaces

| Interface | Funktion |
|---|---|
| `org.bluez.Adapter1` | BT-Adapter (hci0), Scanning, Pairing |
| `org.bluez.Device1` | Gerät (BMW MAC), Connect/Disconnect |
| `org.bluez.MediaControl1` | AVRCP Controller-Seite (BMW sendet hierhin) |
| `org.bluez.MediaPlayer1` | AVRCP Player-Status (PiDrive publiziert) |
| `org.bluez.MediaEndpoint1` | A2DP Codec-Endpoint |

### 5.3 Relevante BlueZ-Properties

```bash
# BMW-Gerät inspizieren
busctl introspect org.bluez /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX

# A2DP Stream-Status
dbus-send --system --print-reply --dest=org.bluez \
  /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX/fd0 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.bluez.MediaTransport1

# AVRCP Player-Status
dbus-send --system --print-reply --dest=org.bluez \
  /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX/player0 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.bluez.MediaPlayer1
```

### 5.4 PulseAudio BT-Integration

```
PulseAudio Module-Chain:
  module-bluetooth-discover    → erkennt neue BT-Geräte automatisch
  module-bluetooth-policy      → schaltet Profile automatisch
  module-bluez5-device         → erstellt Sink pro verbundenem Gerät

Sink-Name: bluez_sink.{MAC_mit_Underscores}.a2dp_sink
Beispiel:  bluez_sink.00_16_94_2E_85_DB.a2dp_sink
```

---

## 6. PiDrive D-Bus Architektur

### 6.1 Zwei parallele Monitor-Pfade

```
BMW sendet AVRCP Kommando
         │
         ▼
BlueZ (bluetoothd)
         │
    ┌────┴────────────────────┐
    │                         │
    ▼                         ▼
dbus-monitor              bluetoothctl
(avrcp_trigger.py)        (avrcp_trigger.py)
    │                         │
    └────────┬────────────────┘
             │
             ▼
       map_event()
             │
             ▼
    /tmp/pidrive_cmd
             │
             ▼
       main_core.py
             │
             ▼
   trigger/td_* Module
```

**Warum zwei Pfade?**  
`dbus-monitor` ist zuverlässiger für Metadaten-Events.  
`bluetoothctl` ist zuverlässiger für Connect/Disconnect-Events.  
Beide zusammen decken alle Szenarien ab.

### 6.2 dbus-monitor Filter

PiDrive monitort zwei D-Bus-Interfaces:

```
interface=org.bluez.MediaPlayer1
  → Track Changed, Playback Status, Position
  → Player Properties (Title, Artist, Album)

interface=org.bluez.MediaControl1
  → Volume, Play/Pause/Skip Commands
```

### 6.3 Event-zu-Trigger Mapping

| D-Bus Event | PiDrive Event-String | Kontext |
|---|---|---|
| FORWARD pressed | `next` | radio/scanner |
| BACKWARD pressed | `previous` | radio/scanner |
| PLAY pressed | `play` | alle |
| PAUSE pressed | `pause` | alle |
| VOLUME_UP | `volumeup` | alle |
| VOLUME_DOWN | `volumedown` | alle |

Mapping via `get_context()` + `map_event()` in `avrcp_trigger.py`.

---

## 7. MPRIS2 Interface

### 7.1 Warum MPRIS2?

BlueZ 5.x nutzt MPRIS2 als Abstraktionsschicht zwischen Linux-Playern und AVRCP.  
PiDrive publiziert `org.mpris.MediaPlayer2.pidrive` auf dem D-Bus → BlueZ übersetzt das in AVRCP-Responses gegenüber BMW.

```
PiDrive mpris2.py
    → D-Bus: org.mpris.MediaPlayer2.pidrive
    → org.mpris.MediaPlayer2.Player (Properties)
    → BlueZ liest diese Properties
    → AVRCP GetElementAttributes Response an BMW
```

### 7.2 Publizierte Properties

```python
# org.mpris.MediaPlayer2 (Root Interface)
{
    "Identity":          "PiDrive",
    "CanQuit":           False,
    "HasTrackList":      False,
    "SupportedUriSchemes": [],
    "SupportedMimeTypes":  [],
}

# org.mpris.MediaPlayer2.Player
{
    "PlaybackStatus":   "Playing" | "Paused" | "Stopped",
    "LoopStatus":       "None",
    "Rate":             1.0,
    "Shuffle":          False,
    "Volume":           1.0,    # FIXIERT — kein Absolute Volume
    "Position":         0,      # Live-Stream = immer 0
    "CanGoNext":        True,
    "CanGoPrevious":    True,
    "CanPlay":          True,
    "CanPause":         True,
    "CanControl":       True,
    "Metadata":         { ... } # siehe 7.3
}
```

### 7.3 Metadata-Felder pro Quelle

| Feld | FM Radio | DAB+ | Webradio | Scanner | Spotify |
|---|---|---|---|---|---|
| `xesam:title` | Sendername | Sendername | Icy-Titel | Kanal/Freq | Track |
| `xesam:artist` | Freq/Station | DAB+ | Interpret | Frequenz | Artist |
| `xesam:album` | "UKW / FM" | "DAB+" | Sendername | "PMR446" etc. | Album |
| `xesam:genre` | "FM Radio" | "DAB+ Radio" | "Webradio" | "PMR" etc. | "Streaming" |
| `xesam:trackNumber` | (int, wächst) | (int, wächst) | (int, wächst) | (int, wächst) | (int) |
| `mpris:length` | 0 (Live) | 0 (Live) | 0 (Live) | 0 (Live) | 0 |

### 7.4 Rate-Limiting

BMW NBT Evo kann bei zu häufigen `PropertiesChanged`-Signalen hängen oder Metadaten verlieren.

PiDrive-Implementierung:
- **Max 1 Signal alle 300ms** (bei identischem Track)
- **Sofort bei Track-ID-Wechsel** (kein Rate-Limiting bei echtem Wechsel)
- **Stopped-Signal** wird kurz vor neuem Track gesendet (triggert `TrackChanged` Event im BMW)

---

## 8. Pairing-Prozess

### 8.1 Ablauf BMW ↔ PiDrive

```
1. BMW: Bluetooth Settings → Neues Gerät
2. BMW: sendet Inquiry / Page Scan
3. PiDrive (bluetoothd): antwortet auf Page
4. SDP Discovery: BMW liest PiDrive SDP Records
   → findet 0x110A (A2DP Source) + 0x110C (AVRCP Target)
5. PIN/Passkey: normalerweise automatisch (Just Works)
   → SSP (Secure Simple Pairing) falls BT 2.1+
6. Link Key wird gespeichert (trusted)
7. BMW verbindet A2DP + AVRCP
8. PulseAudio: erkennt neuen bluez_sink
9. PiDrive: avrcp_trigger.py erkennt Connected-Event
```

### 8.2 PiDrive Pairing-Befehle

```bash
# Voraussetzung: PiDrive als discoverable setzen
bluetoothctl discoverable on
bluetoothctl pairable on

# BMW soll nun PiDrive finden und pairen
# Nach Pairing:
bluetoothctl trust <BMW-MAC>

# Manuell verbinden (falls Auto-Connect fehlt)
pidrivectl bt connect <BMW-MAC>

# Status prüfen
pidrivectl bt status
```

### 8.3 Auto-Connect nach Neustart

BMW initiiert beim Start aktiv den Reconnect zu gespeicherten Geräten.  
PiDrive muss discoverable und connectable sein (bluetoothd macht das automatisch wenn `trusted=yes`).

Zeitfenster: BMW versucht ~30s nach Zündung an. Falls PiDrive nicht bereit → manuell via `pidrivectl bt reconnect`.

### 8.4 Wichtig: Cambridge Silicon Radio Dongle

Der CSR-Dongle muss vor BMW-Pairing bereit sein:

```bash
# Adapter-Status
hciconfig hci0

# Adapter aktivieren falls nötig
hciconfig hci0 up

# rfkill prüfen (oft blockiert)
rfkill list
rfkill unblock bluetooth
```

---

## 9. Bekannte Probleme und Workarounds

### 9.1 BMW-spezifische AVRCP-Probleme

| Symptom | Ursache | PiDrive-Workaround |
|---|---|---|
| Kein Titelwechsel auf Display | TrackChanged Event fehlt | `mpris:trackid` inkr. + kurz `Stopped` senden |
| Metadaten frieren ein | Notification Overflow | Rate-Limiting 300ms |
| Lautstärke springt | Absolute Volume Konflikt | Volume auf 1.0 fixiert |
| Keine Genre-Anzeige | fehlender `xesam:genre` | seit v0.11.57 implementiert |
| BMW ignoriert Metadaten | AVRCP 1.4 Browsing-Request | nur Legacy Metadata, kein Browsing |
| Connect bricht nach 30s ab | Link Supervision Timeout | A2DP-Stream kontinuierlich halten |

### 9.2 BlueZ-spezifische Probleme

| Problem | Ursache | Lösung |
|---|---|---|
| `br-connection-page-timeout` | BMW nicht in Reichweite | Normal, wird wiederholt |
| `no A2DP-Sink nach Connect` | PA-Modul noch nicht geladen | Warte 2–3s nach Connect |
| Sink verschwindet | bluetoothd Restart | PA `module-bluetooth-discover` neu laden |
| `AF_BLUETOOTH: not supported` | LXC-Container | Nur Entwicklung — Pi 4 kein Problem |

### 9.3 Audio-Probleme

| Problem | Ursache | Lösung |
|---|---|---|
| mpv rc=2 | kein PA-Sink (BT getrennt) | BT verbinden, dann play |
| Rauschen / Knackser | SBC Bitpool zu niedrig | BlueZ auto-verhandelt, kein Eingriff nötig |
| Kein Audio obwohl verbunden | falscher PA-Sink | `--audio-device=pulse/<exact-sink-name>` |
| Audio stoppt nach 30s | A2DP Suspend | Stream aktiv halten (mpv spielt) |

### 9.4 Unterschied PiDrive ↔ Smartphone

BMW erwartet bei Smartphones zusätzlich: HFP (Telefonie), PBAP (Telefonbuch), MAP (Nachrichten).  
PiDrive implementiert diese Profile **nicht**.

Folge: BMW zeigt ggf. Warnhinweise wie "Kein Telefonbuch gefunden". Das ist **kein Fehler**.  
Die Audiostreaming- und Steuerfunktionen sind davon unabhängig.

---

## 10. Diagnosebefehle

### 10.1 Verbindungsstatus

```bash
# PiDrive BT-Status
pidrivectl bt status
pidrivectl audio status
pidrivectl audio test

# BlueZ direkt
hciconfig hci0
bluetoothctl info <BMW-MAC>

# PulseAudio Sinks
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks

# A2DP Transport-Status
dbus-send --system --print-reply --dest=org.bluez \
  /org/bluez/hci0/dev_$(echo <BMW-MAC> | tr ':' '_')/fd0 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.bluez.MediaTransport1
```

### 10.2 AVRCP Events Live

```bash
# PiDrive AVRCP Monitor (empfehlenswert)
pidrivectl avrcp

# Raw D-Bus Monitor
dbus-monitor --system \
  "type=signal,interface=org.bluez.MediaPlayer1" \
  "type=signal,interface=org.bluez.MediaControl1"

# BlueZ Logs
journalctl -u bluetooth -f

# PiDrive AVRCP Logs
tail -f /var/log/pidrive/core.log | grep -E "AVRCP|MPRIS2|BT"
```

### 10.3 MPRIS2 Properties prüfen

```bash
# MPRIS2 Player-Status lesen
dbus-send --session --print-reply --dest=org.mpris.MediaPlayer2.pidrive \
  /org/mpris/MediaPlayer2 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.mpris.MediaPlayer2.Player
```

### 10.4 Bluetooth Adapter Details

```bash
# Adapter-Version und Features
hciconfig -a hci0
hcitool dev
btmon  # Live HCI-Log (sehr detailliert)

# LMP-Version (Bluetooth-Version des Adapters)
hciconfig hci0 version
# Ausgabe: "HCI Version: 4.0 (0x6)" = BT 4.0 — ausreichend für AVRCP 1.4

# Verbundene Geräte
hcitool con
```

### 10.5 SBC Codec-Parameter prüfen

```bash
# Nach erfolgreichem Connect: aktiver Codec
pactl list cards | grep -A5 "bluez_card"

# Codec-Details in BlueZ
dbus-send --system --print-reply --dest=org.bluez \
  /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX/fd0 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.bluez.MediaTransport1
# → Codec: 0x00 (SBC), Config: [Bitpool, Freq, Channels...]
```

---

## Anhang: BMW NBT Evo Software-Versionen

| SW-Stand | AVRCP-Verhalten | Bekannte Eigenheit |
|---|---|---|
| < 2016 | 1.3 | keine Metadaten-Aktualisierung |
| 2016–2017 (ID5) | 1.4 | Cover Art cache-buggy |
| 2017+ (ID6) | 1.4 partiell 1.5 | stabilere Metadaten |

SW-Stand prüfen: iDrive → Einstellungen → Fahrzeuginfo → SW-Versionen.

---

*Erstellt für PiDrive v0.11.57 — BMW 118d F20/F21 LCI 2017 · NBT Evo · BlueZ 5.x*  
*Quellen: BlueZ-Quellcode, Bluetooth SIG AVRCP 1.4 Spec, PiDrive-Feldbeobachtungen*
