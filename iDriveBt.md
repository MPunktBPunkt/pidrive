# iDrive Bluetooth — Technische Referenz für PiDrive

**BMW 118d F20/F21 LCI 2017 · NBT Evo · PiDrive v0.11.122**  
Erstellt auf Basis von Quellcode-Analyse, BlueZ-Dokumentation und Felderfahrung.

> **Audio-Stack-Hinweis (ab v0.11.96):** PiDrive nutzt **PipeWire im System-Mode**
> (mit WirePlumber + pipewire-pulse), nicht mehr klassisches PulseAudio. Das ändert
> v. a. die **Sink-Namen** (`bluez_output.<MAC>.<N>` statt `bluez_sink.<MAC>.a2dp_sink`)
> und ersetzt die `module-bluetooth-*`-Modulkette durch WirePlumber. Die betroffenen
> Abschnitte unten sind entsprechend annotiert.

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

BMW sendet folgende Pass-Through-Opcodes über den AVCTP-Kanal. PiDrive sieht diese
allerdings **nicht als rohe Opcodes**, sondern als von BlueZ abstrahierte D-Bus-
Methoden/-Signale (`Next`, `Previous`, `Play`, `Pause`, `Stop`, …).

| Taste iDrive | Opcode (hex) | AVRCP-Op | D-Bus-Methode | PiDrive-Event |
|---|---|---|---|---|
| ► / OK | `0x44` | PLAY | `Play` | `play` |
| ❚❚ | `0x46` | PAUSE | `Pause` | `pause` |
| ■ | `0x45` | STOP | `Stop` | `stop` |
| ⏭ (Next) | `0x4B` | FORWARD | `Next` | `next` |
| ⏮ (Prev) | `0x4C` | BACKWARD | `Previous` | `previous` |
| 🔊+ | `0x41` | VOLUME_UP | (Volume) | `volumeup` |
| 🔊− | `0x42` | VOLUME_DOWN | (Volume) | `volumedown` |

> **Wichtig — zweistufiges Mapping:** Die Spalte *PiDrive-Event* ist nur das
> **Zwischen-Event** (siehe `integration/avrcp_trigger.py`). Der tatsächlich in
> `/tmp/pidrive_cmd` geschriebene **Trigger ist kontextabhängig** und entsteht erst in
> `map_event(event, ctx)`. Beispiele:
>
> | Event | Kontext `menu` | Kontext `radio` (FM/DAB) | Kontext `scanner` | Kontext `list_overlay` |
> |---|---|---|---|---|
> | `next` | `down` | `fm_next` / `dab_next` | `scan_up:<band>` / `scan_step:…` | `down` |
> | `previous` | `up` | `fm_prev` / `dab_prev` | `scan_down:<band>` / `scan_step:…` | `up` |
> | `play`/`pause`/`play_pause` | `enter` | `radio_stop` | `scan_next:<band>` / `enter` | `enter` |
> | `stop` | `back` | `back` | `back` | `back` |
> | `volumeup` / `volumedown` | `vol_up` / `vol_down` (kontextunabhängig) | | | |
>
> **Double-Tap** auf Play/Pause (innerhalb von `DOUBLE_TAP_SEC = 1.2 s`) erzeugt den
> Trigger `cat:0` („Jetzt läuft"). Der Kontext wird aus
> `/tmp/pidrive_status.json` + `/tmp/pidrive_menu.json` + `/tmp/pidrive_list.json`
> bestimmt (`get_context()`: `menu` | `radio` | `scanner` | `list_overlay`).

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

Das SBC-Encoding übernimmt der Bluetooth-Stack automatisch. PiDrive muss nur PCM-Daten
in den BT-Sink liefern (über die PipeWire-Pulse-Kompatibilitätsschicht):

```
rtl_fm / mpv / welle-cli
    → PCM (32000/44100/48000 Hz, mono/stereo)
    → PipeWire (System-Mode, Socket /var/run/pulse/native)
    → A2DP-Sink: bluez_output.<MAC>.<N>   ← PiDrive schreibt hier hin
       (Legacy-PA-Name war: bluez_sink.<MAC>.a2dp_sink)
    → SBC Encoding (PipeWire/BlueZ)
    → BT HCI → RF → BMW
```

**Achtung:** PiDrive schreibt in den A2DP-**Sink** (`bluez_output.<MAC>.<N>`), nicht in
eine Quelle. PipeWire/WirePlumber + BlueZ übernehmen die A2DP-Source-Rolle gegenüber
dem BMW. Den korrekten Sink-Namen ermittelt `modules/bluetooth/bt_audio.py:
find_bt_sink_for_mac()`; `bt_helpers.is_bt_a2dp_sink()` erkennt sowohl das
PipeWire- als auch das Legacy-PA-Schema.

### 4.3 Latenz und Pufferung

| Parameter | Typischer Wert |
|---|---|
| SBC-Frame-Größe | 128 Byte (13ms bei 48kHz) |
| A2DP-Puffer im BMW | ~200–400ms |
| Gesamtlatenz Pi→BMW | 250–600ms |

Für Radio/Streaming unkritisch. Für Sprachsteuerung/Diktat nicht geeignet.

### 4.4 Automatischer Reconnect

Nach BMW-Start versucht das iDrive aktiv den Reconnect (falls PiDrive gepairt und trusted).

PiDrive-Seite — es gibt zwei Mechanismen:
- **`integration/avrcp_trigger.py`**: `auto_connect_bmw()` verbindet gepairte Geräte beim
  Start; der `dbus-monitor`-Thread beobachtet zusätzlich `PropertiesChanged` auf
  `/org/bluez/hci0` (Connect/Disconnect, AVRCP-Events).
- **`modules/bluetooth/bt_watcher.py`**: aktiver Auto-Reconnect-Watcher, der gepairte
  Geräte **periodisch** (mit Backoff) erneut zu verbinden versucht — kein reiner
  D-Bus-Event-Listener, sondern proaktives Polling. Manuell aufweckbar via
  `bt_reconnect_last` bzw. `pidrivectl bt reconnect`.

Nach Reconnect erstellt **WirePlumber** den A2DP-Sink (`bluez_output.<MAC>.<N>`)
automatisch — kein PulseAudio-`module-bluetooth-discover` mehr.

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

### 5.4 PipeWire / WirePlumber BT-Integration (ab v0.11.96)

PiDrive nutzt **PipeWire System-Mode** statt klassischem PulseAudio. WirePlumber
übernimmt die Aufgaben der früheren PulseAudio-Modulkette automatisch:

```
WirePlumber (ersetzt die PulseAudio-Module):
  bluez-Monitor          → erkennt neue BT-Geräte automatisch
                           (früher: module-bluetooth-discover)
  Auto-Profil-Switch     → schaltet A2DP automatisch beim Connect
                           (früher: module-bluetooth-policy)
  Sink pro Gerät         → erstellt den A2DP-Sink automatisch
                           (früher: module-bluez5-device)

Rolle (WirePlumber-Config): bluez5.roles = [ a2dp_source ]   ← nur Source, kein hfp_ag
Sink-Name: bluez_output.{MAC_mit_Underscores}.{N}
Beispiel:  bluez_output.00_16_94_2E_85_DB.1
           (Legacy-PA-Name war: bluez_sink.00_16_94_2E_85_DB.a2dp_sink)

Socket (PA-kompatibel): /var/run/pulse/native  (pipewire-pulse)
```

> Details und Stolperfallen des WirePlumber-System-Mode (Seat-Monitoring, `hfp_ag`,
> D-Bus-Policy) stehen in `BluetoothError.md` und `KontextPiDrive.md`.

---

## 6. PiDrive D-Bus Architektur

### 6.1 Zwei unabhängige Empfangs-Pfade für BMW-Kommandos

BMW-Steuerbefehle erreichen PiDrive über **zwei getrennte Wege**:

```
BMW sendet AVRCP-Kommando
         │
         ▼
BlueZ (bluetoothd)  →  registrierter MPRIS2-Player org.mpris.MediaPlayer2.pidrive
         │                          │
         │ (System-D-Bus Signale)   │ (direkte D-Bus-Methodenaufrufe)
         ▼                          ▼
integration/avrcp_trigger.py     mpris2.py — PiDrivePlayer
   monitor_dbus() (dbus-monitor)    Next()/Previous()/PlayPause()/Play()/
         │                          Pause()/Stop()
         ▼                          │  (FESTES Mapping, kontextunabhängig:
   get_context() + map_event()      │   Next→down, Previous→up,
         │                          │   PlayPause/Play/Pause→enter, Stop→back)
         ▼                          ▼
   /tmp/pidrive_cmd   ◀─────────────┘ (ipc.append_trigger)
         │
         ▼
   main_core.py  →  trigger/td_* Module
```

> **Hinweis (Stand des Codes):** Der frühere zweite Monitor `monitor_bluetoothctl()`
> in `avrcp_trigger.py` ist **deaktiviert** (verursachte ~50 % dbus-CPU-Last). Aktiv ist
> nur **`monitor_dbus()`**; Connect/Disconnect-Events kommen über `PropertiesChanged`
> auf `/org/bluez/hci0`. Die Funktion `monitor_bluetoothctl()` existiert noch im Code,
> wird aber nicht gestartet.
>
> **Zwei Mapping-Logiken beachten:** Der `avrcp_trigger.py`-Pfad mappt
> **kontextabhängig** (`map_event()`), der `mpris2.py`-Pfad mappt **fest**
> (Next→`down` usw.). Je nachdem, welchen Pfad das BMW/BlueZ bedient, kann sich das
> Verhalten unterscheiden — relevant beim Feldtest im Fahrzeug.

### 6.2 dbus-monitor Filter

`monitor_dbus()` startet `dbus-monitor --system` mit **vier** Signal-Filtern:

```
type=signal,interface=org.mpris.MediaPlayer2.Player           ← primär (registr. Player)
type=signal,interface=org.bluez.MediaPlayer1                  ← Track/Playback/Position
type=signal,interface=org.bluez.MediaControl1                 ← Steuerbefehle
type=signal,interface=org.freedesktop.DBus.Properties,
            member=PropertiesChanged,path=/org/bluez/hci0     ← Connect/Disconnect
```

Geparst wird sowohl auf `member=<Methode>` (z. B. `member=Next`) als auch auf
String-Varianten (`"Next"`, `"Previous"`, …) und `PlaybackStatus`-Property-Changes
(`Playing`/`Paused`/`Stopped`).

### 6.3 Event-zu-Trigger Mapping

Das **Zwischen-Event** (D-Bus → Event-String) ist kontextunabhängig; der **finale
Trigger** entsteht kontextabhängig in `map_event()` (siehe Tabelle in Abschnitt 3.2):

| D-Bus-Methode/Signal | PiDrive-Event | Kontextabhängiger Trigger (Beispiele) |
|---|---|---|
| `Next` / FORWARD | `next` | `down` (menu) · `fm_next`/`dab_next` (radio) · `scan_up:<band>` (scanner) |
| `Previous` / BACKWARD | `previous` | `up` · `fm_prev`/`dab_prev` · `scan_down:<band>` |
| `Play` | `play` | `enter` (menu) · `radio_stop` (radio) · `scan_next:<band>`/`enter` (scanner) |
| `Pause` / `PlayPause` | `pause` / `play_pause` | wie `play`; Double-Tap → `cat:0` |
| `Stop` | `stop` | `back` |
| Volume up/down | `volumeup`/`volumedown` | `vol_up` / `vol_down` (kontextunabhängig) |

Mapping via `get_context()` + `map_event()` in `integration/avrcp_trigger.py`.
Der parallele `mpris2.py`-Pfad nutzt dagegen das feste Mapping aus Abschnitt 6.1.

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

# org.mpris.MediaPlayer2.Player  (exakt wie GetAll() in mpris2.py)
{
    "PlaybackStatus":   "Playing" | "Paused" | "Stopped",
    "LoopStatus":       "None",
    "Rate":             1.0,
    "Shuffle":          False,
    "Volume":           1.0,    # Start 1.0; Set(Volume) wird zwar entgegengenommen,
                                # aber NICHT auf die System-/DSP-Lautstärke angewandt
    "Position":         0,      # Live-Stream = immer 0
    "MinimumRate":      1.0,
    "MaximumRate":      1.0,
    "CanGoNext":        True,
    "CanGoPrevious":    True,
    "CanPlay":          True,
    "CanPause":         True,
    "CanSeek":          False,
    "CanControl":       True,
    "Metadata":         { ... } # siehe 7.3
}
```

> Root-Interface zusätzlich: `CanRaise = False`. Initiale Metadaten:
> `xesam:title = "PiDrive"`, leerer Artist/Album, `mpris:trackid = …/NoTrack`.

### 7.3 Metadata-Felder pro Quelle

| Feld | FM Radio | DAB+ | Webradio | Scanner | Spotify |
|---|---|---|---|---|---|
| `xesam:title` | Sendername | Sendername | Icy-Titel | Kanal/Freq | Track |
| `xesam:artist` | Freq/Station | DAB+ | Interpret | Frequenz | Artist |
| `xesam:album` | "UKW / FM" | "DAB+" | Sendername | "PMR446" etc. | Album |
| `xesam:genre` | "FM Radio" | "DAB+ Radio" | "Webradio" | "PMR" etc. | "Streaming" |
| `xesam:trackNumber` | (int, wächst) | (int, wächst) | (int, wächst) | (int, wächst) | (int) |
| `mpris:length` | 0 (Live) | 0 (Live) | 0 (Live) | 0 (Live) | 0 |

**Längen-Limits (Code):** `xesam:title`/`artist`/`album` werden auf **64 Zeichen**
gekürzt, `xesam:genre` auf **32 Zeichen** (`update_metadata()` in `mpris2.py`).

**Cover-Art (`mpris:artUrl`):** Vorgesehen ist ein Icon vom Pi-Webserver
(`http://<ip>:8080/cover/<quelle>`). ⚠️ **Achtung — Code-Stand v0.11.122:**
`update_metadata()` referenziert `art_url`, deklariert den Parameter aber **nicht** und
nutzt zudem `**{{…}}` (Set- statt Dict-Literal). Die Aufrufer (`update()`,
`announce_wifi_ip()`) übergeben `art_url=…`, wodurch der Aufruf mit `TypeError`
fehlschlägt. Da `main_core` `mpris2.update()` in `try/except: pass` kapselt, werden die
Display-Metadaten **still verworfen**. → Vor dem Fahrzeug-Feldtest fixen
(siehe Hinweis am Dokumentende).

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
8. WirePlumber: erstellt neuen A2DP-Sink (`bluez_output.<MAC>.<N>`)
9. PiDrive: avrcp_trigger.py erkennt Connected-Event (PropertiesChanged /org/bluez/hci0)
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
| Keine Genre-Anzeige | fehlender `xesam:genre` | seit v0.11.96 implementiert |
| BMW ignoriert Metadaten | AVRCP 1.4 Browsing-Request | nur Legacy Metadata, kein Browsing |
| Connect bricht nach 30s ab | Link Supervision Timeout | A2DP-Stream kontinuierlich halten |

### 9.2 BlueZ-spezifische Probleme

| Problem | Ursache | Lösung |
|---|---|---|
| `br-connection-page-timeout` | BMW nicht in Reichweite | Normal, wird wiederholt |
| `br-connection-profile-unavailable` | WirePlumber BT-Monitor inaktiv (Seat/`hfp_ag`) | siehe `BluetoothError.md` / `TROUBLESHOOTING.md` §3 |
| `no A2DP-Sink nach Connect` | WirePlumber-Sink noch nicht da | 2–3 s warten; sonst `systemctl restart wireplumber` |
| Sink verschwindet | bluetoothd/WirePlumber-Neustart | `systemctl restart wireplumber` (kein `bluetooth`-Restart bei verbundenem Gerät, v0.11.122) |
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

# Audio-Sinks (PipeWire über pipewire-pulse-Socket) — BT-Sink: bluez_output.<MAC>.<N>
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

# PiDrive AVRCP Logs (core.log und pidrive.log enthalten dieselben Einträge)
tail -f /var/log/pidrive/core.log | grep -E "AVRCP|MPRIS2|BT"

# Dedizierter AVRCP-Rohdaten-Log (jede D-Bus-Zeile, ideal für Feldtest-Analyse)
tail -f /var/log/pidrive/avrcp_raw.log
```

### 10.3 MPRIS2 Properties prüfen

```bash
# MPRIS2 Player-Status lesen — PiDrive registriert auf dem SYSTEM-Bus (nicht --session!)
dbus-send --system --print-reply --dest=org.mpris.MediaPlayer2.pidrive \
  /org/mpris/MediaPlayer2 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.mpris.MediaPlayer2.Player

# Bequemer über PiDrive selbst:
pidrivectl debug mpris status
pidrivectl debug mpris push --title "Test" --artist "PiDrive"
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

## Anhang: Offene Code-Punkte vor dem Fahrzeug-Feldtest

| Punkt | Datei | Status |
|---|---|---|
| **`mpris:artUrl` / Cover-Art** — `update_metadata()` referenziert `art_url` ohne Parameter + `**{{…}}` (Set statt Dict) → `TypeError`, in `main_core` still verschluckt | `mpris2.py` | 🔴 fixen: `art_url=""`-Parameter ergänzen, `{{…}}` → `{…}` |
| Zwei BMW-Empfangspfade mit **unterschiedlichem** Mapping (`avrcp_trigger.py` kontextabhängig vs. `mpris2.py` fest) | `mpris2.py`, `integration/avrcp_trigger.py` | 🟡 im Auto verifizieren, welcher Pfad bedient wird |
| `monitor_bluetoothctl()` vorhanden, aber deaktiviert (CPU-Fix) | `integration/avrcp_trigger.py` | ℹ️ bewusst, nur dbus-monitor aktiv |
| WirePlumber A2DP / DAB-Antenne / AVRCP-Tasten | — | 🟡 Feldtest im BMW ausstehend (s. `KontextPiDrive.md`) |

---

*Aktualisiert für PiDrive v0.11.122 — BMW 118d F20/F21 LCI 2017 · NBT Evo · BlueZ 5.x · PipeWire System-Mode*  
*Quellen: PiDrive-Quellcode (`integration/avrcp_trigger.py`, `mpris2.py`, `modules/bluetooth/*`), Bluetooth SIG AVRCP 1.4 Spec, PiDrive-Feldbeobachtungen*
