# PiDrive — Runtime Flows

**Stand v0.11.70 · Debugging-Referenz für Laufzeitpfade**

Dieses Dokument zeigt die echten Laufzeitpfade, nicht nur die statische Architektur. Es hilft dabei zu verstehen, welche Schichten bei einem Ereignis beteiligt sind und wo Debugging ansetzen muss.

---

## A. BMW iDrive → AVRCP → Trigger → Core → Aktion

```
BMW-Taste (z.B. ►)
    │
    ▼
Bluetooth BR/EDR (AVRCP Pass-Through)
    │  Opcode 0x44 (PLAY)
    ▼
bluetoothd / BlueZ
    │  D-Bus Signal: org.bluez.MediaPlayer1
    ▼
avrcp_trigger.py
    ├── dbus-monitor (Interface: org.bluez.MediaPlayer1)
    ├── bluetoothctl monitor (Connect/Disconnect-Events)
    │
    ├── get_context()   → Kontext bestimmen: menu | radio | scanner | list_overlay
    ├── map_event()     → Kontext + Opcode → Trigger-String
    │     Beispiel: radio + FORWARD → "next"
    │
    └── CMD_FILE append: printf "next\n" >> /tmp/pidrive_cmd
            │
            ▼
/tmp/pidrive_cmd  (append-Queue)
            │
            ▼
main_core.py — Core-Loop (alle 0.2s)
    check_trigger()
        ├── LIST_FILE Overlay prüfen (NAV-Commands blockiert?)
        ├── ipc.drain_triggers()  →  ["next"]
        ├── handle_trigger("next", ...)
        │       │
        │       ▼
        │   trigger/trigger_dispatcher.py
        │       ├── td_nav.handle("next")
        │       ├── td_radio.handle("next")   ← "next" = Sender wechseln
        │       ├── td_hardware.handle("next")
        │       ├── td_scanner.handle("next")
        │       └── td_system.handle("next")
        │
        └── needs_rebuild?  →  Menübaum neu aufbauen
```

**Debugging:**
```bash
pidrivectl avrcp              # Schritt 3: Events ankommen?
cat /tmp/pidrive_cmd          # Schritt 4: Trigger in Queue?
pidrivectl debug inject next  # Schritt 5: Core direkt testen
```

---

## B. WebUI-Button → `/api/cmd` → Trigger → Core

```
Browser-Klick (z.B. "▶ Play")
    │
    ▼
JavaScript (web/static/js/*.js)
    │  fetch('/api/cmd', { method: 'POST', body: { cmd: "play_web:Bayern 1" } })
    ▼
Flask / web/app.py
    │  Route: POST /api/cmd
    ▼
web/shared/files.py → write_cmd("play_web:Bayern 1")
    │  open(CMD_FILE, "a") ← append-Mode
    ▼
/tmp/pidrive_cmd
    │
    ▼
main_core.py — check_trigger()
    │
    ▼
trigger/td_radio.py — handle("play_web:Bayern 1")
    │  name = "Bayern 1"
    ▼
modules/webradio.py — play(name, S, settings)
```

**Debugging:**
```bash
# API direkt testen:
curl -X POST http://localhost:8080/api/cmd -d 'cmd=play_web:Rock Antenne'
# Queue prüfen:
tail -1 /tmp/pidrive_cmd
```

---

## C. `pidrivectl play web "Bayern 1"`

```
pidrivectl play web "Bayern 1"
    │
    ▼
cli/cli.py — args.cmd == "play", args.source == "web"
    │
    ▼
cli/service.py — svc.play("web", "Bayern 1")
    │
    ▼
cli/adapters.py — write_cmd("play_web:Bayern 1")
    │  open(CMD_FILE, "a") ← append-Mode
    ▼
/tmp/pidrive_cmd
    │
    ▼
main_core.py — check_trigger()
    │
    ▼
trigger/td_radio.py — handle("play_web:Bayern 1")
    │  Stationsname → URL aus stations.json
    ▼
modules/webradio.py — play(name, url, S, settings)
    │
    ├── mpv stop() (laufende Wiedergabe stoppen)
    ├── audio.get_bt_sink() oder audio.get_alsa_sink()
    ├── os.unlink(/tmp/pidrive_mpv.sock) ← Socket vorher löschen
    ├── Popen(["mpv", "--no-video", "--title=pidrive_web",
    │           f"--audio-device=pulse/{sink}", url])
    └── mpv_meta.start()   ← startet Metadaten-Thread
            │
            ▼
    mpv IPC-Socket: /tmp/pidrive_mpv.sock
            │
            ▼
    PipeWire → BT A2DP (bluez_sink.<MAC>) oder ALSA
```

**Wichtige Fallstricke:**
- `webui.py` ist nur Entry-Shim → `web/app.py` ist die echte Implementierung
- `mpv_meta.start()` darf **kein** `os.unlink()` aufrufen — löscht fertigen Socket
- Ohne PA-Sink: `mpv rc=2` nach 5s — erwartet, kein Bug

---

## D. `pidrivectl play local /home/pidrive/Musik/`

```
pidrivectl play local /home/pidrive/Musik/ --shuffle
    │
    ▼
cli/cli.py — args.source == "local"
    │  path = "/home/pidrive/Musik/"
    │  shuffle = True
    ▼
cli/adapters.py — write_cmd("local_play:/home/pidrive/Musik/|shuffle")
    │
    ▼
/tmp/pidrive_cmd
    │
    ▼
trigger/td_radio.py — handle("local_play:...")
    │  payload = "/home/pidrive/Musik/"
    │  shuffle = True
    ▼
modules/local_player.py — play(path, S, settings, shuffle=True)
    │
    ├── _collect_files("/home/pidrive/Musik/")
    │     → rekursiv alle .mp3/.flac/.ogg/.m4a/.aac/.wav/.opus
    │     → bei M3U: Playlist-Datei parsen
    ├── random.shuffle(files)
    ├── audio.get_bt_sink() / get_alsa_sink()
    └── Popen(["mpv", "--no-video", ...sink..., *files])
            │
            ▼
    PipeWire → BT A2DP oder ALSA
```

**Wichtig:** Audio-Pfad ist identisch mit Webradio — BT muss verbunden sein für BT-Ausgabe.

---

## E. BT-Connect → A2DP-Sink → Audio-Reroute

```
Bluetooth-Gerät kommt in Reichweite
    │
    ▼
bluetoothd erkennt bekanntes Gerät (paired=yes, trusted=yes)
    │  D-Bus Event: org.bluez.Device1 Connected=true
    ▼
avrcp_trigger.py — bluetoothctl monitor
    │  Event: "[CHG] Device XX:XX Connected: yes"
    ▼
/tmp/pidrive_cmd  ← append: "bt_connect:XX:XX:XX:XX"
    │
    ▼
trigger/td_hardware.py — handle("bt_connect:...")
    │
    ▼
modules/bluetooth/bt_connect.py — _on_connected(mac)
    │
    ├── Warte 2-3s (PA-Modul braucht Zeit)
    ├── PulseAudio: module-bluetooth-discover erkennt neuen Sink
    │     Sink-Name: bluez_sink.XX_XX_XX_XX_XX_XX.a2dp_sink
    ├── modules/audio.py — update_sink(new_sink)
    └── source_state.update("bt_connected")
            │
            ▼
    Audio-Reroute: laufende Wiedergabe neu starten mit neuem Sink
        modules/webradio.py oder fm.py:  _restart_with_sink(new_sink)
```

**Debugging:**
```bash
pidrivectl bt status
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks
journalctl -u bluetooth | grep -i "a2dp\|connect\|sink"
```

---

## F. DAB+ starten / Lock / DLS

```
pidrivectl play dab "Bayern 1"
    │
    ▼
trigger/td_radio.py — handle("play_dab:Bayern 1")
    │
    ▼
modules/radio/dab.py — play(name, S, settings)
    │
    ▼
modules/radio/dab_play.py — _start_welle(channel, name, ...)
    │
    ├── Gain-Berechnung (_get_dab_gain)
    ├── welle-cli Popen(["welle-cli", "-c", ch, "-g", gain, "-p", name])
    │     stdin = /dev/null, stderr = /tmp/pidrive_dab_welle.err
    ├── mpv Popen(["mpv", "--no-video", "--demuxer=rawaudio", ...]
    │     ← stdin vom welle-cli stdout
    │
    └── Lock-Monitoring (Thread)
            │  pollt alle 2s: welle-cli stderr + status
            ▼
    Lock erkannt → S["source"] = "dab"
                 → source_state.commit_source("dab")
                 → MPRIS2 Metadaten aktualisieren
                 │
                 ▼
    modules/radio/dab_dls.py — DLS-Monitor
            pollt Metadaten aus welle-cli stderr
            → S["radio_name"] = DLS-Text
            → mpris2 Track-Update
```

**Kein Lock indoor:** `SyncOnPhase failed` — normaler Zustand ohne DAB-Antenne.

---

## G. FM / Scanner

```
pidrivectl play fm 104.4
    │
    ▼
trigger/td_radio.py — handle("fm:104.4")
    │
    ▼
modules/radio/fm.py — play(freq, S, settings)
    │
    ├── rtl_fm Popen(["rtl_fm", "-f", "104.4M", "-M", "wbfm",
    │                  "-s", "250000", "-r", "32000", "-p", str(ppm)])
    ├── mpv Popen(["mpv", "--no-video", "--demuxer=rawaudio",
    │               "--demuxer-rawaudio-rate=32000", ...]
    │     stdin vom rtl_fm stdout (Popen-Pipe, kein shell=True)
    └── source_state.commit_source("fm")

Scanner (pidrivectl scanner pmr446 scan):
    trigger/td_scanner.py → modules/radio/scanner.py
    └── rtl_fm mit engem Squelch, Frequenz-Stepping
```

**Wichtig:** FM-Broadcast braucht `-M wbfm` — `-M fm` ist Schmalband (PMR), liefert kein Radio-Audio.

---

## H. Installer → Service-Start → Runtime-Smoke-Test

```
curl ... | bash  →  install.sh
    │
    ├── 1/10  Services stoppen
    ├── 2/10  Pakete installieren (apt, pip)
    ├── 3/10  git pull (mit settings.json stash/restore)
    ├── 4/10  Verzeichnisse anlegen
    ├── 5/10  /boot/config.txt (nur Pi)
    ├── 6/10  rc.local konfigurieren
    ├── 7/10  D-Bus Policy, pidrivectl symlink
    ├── 8/10  systemd Units aktivieren
    ├── 9/10  Berechtigungen setzen
    └── 10/10 PulseAudio, Librespot, ...
            │
            ▼
    Python Syntax-Check (alle .py)
    Shell Syntax-Check (install.sh)
    Altimport-Check (grep auf bare `import td_*`)
    Import-Smoke-Test (28 Module einzeln importieren)
            │
            ▼
    pidrive_core.service starten
    15s warten (Stabilitätsfenster)
            │
            ├── systemctl is-active? → nein → ABORT
            ├── NRestarts gestiegen? → ja  → ABORT
            ├── Traceback im Journal? → ja  → ABORT
            ├── status.json frisch?  → nein → WARN
            └── OK → Diagnose starten
                        │
                        ▼
                 pidrive/diagnose.py
                    (Core, Audio, BT, RTL-SDR, Prozesse)
```

**Relevante Signale nach Install:**
```bash
systemctl is-active pidrive_core
systemctl show pidrive_core --property=NRestarts --value
journalctl -u pidrive_core --since "2 minutes ago" | grep "Error\|Traceback"
cat /tmp/pidrive_status.json
```

---

*Weiterführend: `TROUBLESHOOTING.md` (Was tun wenn etwas schiefgeht?), `DEVELOPER_GUIDE.md` (Wo liegt der Code?)*
