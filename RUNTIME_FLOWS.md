# PiDrive — Runtime Flows

**Stand v0.11.122 · Debugging-Referenz für Laufzeitpfade**

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
    ├── Warte 2-3s (WirePlumber braucht Zeit für den Sink)
    ├── WirePlumber erkennt das A2DP-Profil automatisch und legt den Sink an
    │     Sink-Name: bluez_output.XX_XX_XX_XX_XX_XX.N   (PipeWire-Schema!)
    │     → modules/bluetooth/bt_audio.py: find_bt_sink_for_mac() ermittelt ihn
    ├── modules/audio.py — Sink-Auswahl / Routing
    └── source_state.update("bt_connected")
            │
            ▼
    Audio-Reroute: laufende Wiedergabe neu starten mit neuem Sink
        modules/webradio.py oder radio/fm.py
```

> **Sink-Namensschema:** Unter PipeWire/WirePlumber heißt der A2DP-Sink
> `bluez_output.<MAC>.<N>` — **nicht** `bluez_sink.<MAC>.a2dp_sink` (klassisches
> PulseAudio). `find_bt_sink_for_mac()` (ab v0.11.121) deckt beide Varianten ab.
> Ab v0.11.122 wird bei verbundenem Gerät der `bluetooth`-Dienst während der
> A2DP-Recovery **nicht** mehr neu gestartet (verhinderte Verbindungsabbrüche).

**Debugging:**
```bash
pidrivectl bt status
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks   # bluez_output.* suchen
journalctl -u wireplumber -u bluetooth | grep -i "a2dp\|connect\|sink"
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
    └── 10/10 PipeWire/WirePlumber, Librespot, ...
            │
            ▼
    Python Syntax-Check (alle .py)
    Shell Syntax-Check (install.sh)
    Altimport-Check (grep auf bare `import td_*`)
    Import-Smoke-Test (echter main_core-Startpfad: ~33 Module einzeln importieren,
                       danach webui / cli.cli / web.app / web.shared / web.api)
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

## I. Menü → BMW-Display → Lenkrad-/iDrive-Tasten

### I.1 Wo ist das Menü definiert?

Der komplette Menübaum wird **im Code** aufgebaut — es gibt keine Menü-Konfigurationsdatei:

| Was | Datei |
|---|---|
| Baum-Aufbau (`build_tree()`) | `menu/menu_builder.py` |
| Knoten + Navigation (`MenuNode`, `MenuState`) | `menu/menu_state.py` |
| Public-API-Facade (re-export) | `menu/menu_model.py` |
| Stationsdaten (FM/DAB/Web) | `menu/station_store.py` + `config/*stations.json` |

`build_tree(store, S, settings)` wird in `main_core.main()` einmal aufgerufen und bei
Änderungen (neue Sender, BT-Geräteliste, USB-Stick, `S["menu_rev"]`) via `rebuild_tree()`
neu erzeugt. Knotentypen: `folder` · `station` · `action` · `toggle` · `info`.

### I.2 Menübaum (Stand `build_tree()`, v0.11.123 — fahrtauglich)

Jeder Ordner (außer Wurzel) hat als **ersten** Eintrag „Zurueck" (per enter
bedienbar), weil die Hardware-„Zurück"-Funktion (Stop) im Fahrzeug oft fehlt.

```
PiDrive  (root)
├── Favoriten          Aktuellen Sender merken · gemischt FM/DAB/Web/Spotify/Scanner
├── Quellen
│   ├── FM Radio        Sender · Suchlauf · Nächster/Vorheriger · Frequenz manuell
│   ├── DAB+            Sender (flach, Favoriten zuerst) · Suchlauf · Nächster/Vorheriger
│   ├── Webradio        Sender · Sender neu laden
│   ├── Spotify         An/Aus · Status (live)
│   ├── Scanner         PMR446 · Freenet · LPD433 · CB-Funk · VHF · UHF
│   └── Bibliothek      music_dir abspielen · Zufällig · Stop · (+ USB-Sticks dynamisch)
├── Stop               (radio_stop — beendet die Wiedergabe)
├── Audio              Ausgang (Auto/Bluetooth/Klinke/HDMI) · Lauter · Leiser
├── Verbindungen       Bluetooth: Scan · Geräte · Reconnect · Trennen* · Aus*  ·  WiFi: An/Aus · Scan · Netzwerke
└── System             IP (live) · System-Info · Version · Neustart* · Ausschalten* · Update*
```

`*` = Aktion mit **Bestätigungs-Ebene** (erster Unterpunkt „Abbrechen", danach
„Ja, …"). Schützt vor versehentlichem Auslösen per Skip+Play und — bei „Bluetooth
trennen/aus" — vor dem Verlust der iDrive-Steuerung.

**Quellen:** Der Menübaum entsteht in `menu/menu_builder.py: build_tree()`. „Jetzt
läuft" als eigener Ordner entfällt — Titel/Sender stehen bereits in den
MPRIS2-Metadaten (siehe I.3). Lokale Musik (`Bibliothek`) liest `settings["music_dir"]`
(`modules/local_player.py`: mp3/flac/ogg/m4a/aac/wav/opus + `.m3u` + Ordner + Shuffle).
Favoriten quellenübergreifend inkl. Spotify; „Aktuellen Sender merken" →
`favorites_add_current` (`trigger/td_system.py`).

### I.3 Wie kommt das Menü auf das iDrive-Display?

**Wichtig:** Das iDrive rendert **kein** grafisches PiDrive-Menü. PiDrive ist für das
BMW ein „Audio-Player" — sichtbar werden nur die **drei MPRIS2-Textzeilen** (wie bei
einem Song). Es ist immer nur **der aktuell markierte Eintrag** sichtbar, nicht die
ganze Liste.

```
Navigation ändert MenuState  →  menu_state.rev++
        │
        ▼
main_core Core-Loop: rev geändert?
        ├── ipc.write_menu(export)        → /tmp/pidrive_menu.json  (für WebUI/CLI)
        └── mpris2.update(S, menu)         → BMW-Display
                │  (Menü-Zweig, wenn nichts spielt)
                ▼
        xesam:title  = Label des markierten Knotens   (nodes[cursor].label)
        xesam:artist = Pfad (z. B. "Quellen › DAB+")
        xesam:album  = "PiDrive Menü"
                │
                ▼
        PropertiesChanged auf System-D-Bus → BlueZ → AVRCP → iDrive zeigt die Zeilen
```

> **Voraussetzungen, damit überhaupt etwas erscheint:**
> 1. Im iDrive **Multimedia → Bluetooth** als Quelle wählen (Now-Playing-Ansicht).
> 2. `org.mpris.MediaPlayer2.pidrive` muss auf dem **System-Bus** registriert sein
>    (`pidrivectl debug mpris status`); D-Bus-Policy:
>    `/etc/dbus-1/system.d/pidrive-mpris2.conf`.
> 3. MPRIS2 startet nur bei vorhandenem BT-Adapter (`CAPS["bluetooth"]`).
>
> ⚠️ **Historischer Bug (gefixt):** Bis einschließlich v0.11.122 brach
> `mpris2.update_metadata()` mit `TypeError` ab (fehlender `art_url`-Parameter +
> `**{{…}}`), was `main_core` in `try/except: pass` verschluckte → **das Menü erschien
> nie auf dem Display.** Mit dem Fix wird der markierte Eintrag wieder gesendet.

### I.4 iDrive-/Lenkrad-Taste → Menü-Aktion

Das BMW sendet keine dedizierten „up/down/enter/back"-Tasten, sondern die fünf
AVRCP-Medienkommandos. Diese werden auf die Navigation gemappt:

| BMW-Aktion (AVRCP) | Trigger im Menü-Kontext | Wirkung (`menu/menu_state.py`) |
|---|---|---|
| Skip ⏭ (Next) | `down` | Cursor +1 |
| Skip ⏮ (Previous) | `up` | Cursor −1 |
| ► / ❚❚ (Play/Pause) | `enter` | Ordner öffnen bzw. Station/Aktion/Toggle ausführen |
| ■ (Stop) | `back` | eine Ebene zurück |
| Doppel-Tipp ►/❚❚ | `cat:0` | Sprung zu „Jetzt läuft" (nur über `avrcp_trigger.py`-Pfad) |

Verarbeitungskette: `enter`/`up`/`down`/`back` → `trigger/td_nav.py: handle()` →
`menu_state.key_*()` → `rev++` → erneut `write_menu()` + `mpris2.update()`.

> **Wichtig — was das iDrive überhaupt sendet:** Die Tasten der iDrive-Bedieneinheit
> (`MENU`, `BACK`, `OPTION`, `AUDIO`, `TEL`) und der Dreh-/Drück-Regler steuern die
> **BMW-eigene** Oberfläche und werden **nicht** als AVRCP an PiDrive weitergereicht.
> Zuverlässig bei PiDrive ankommen nur die **Medien-Transportkommandos** (Skip/Play/
> Pause, teils Stop) — typischerweise von den Lenkrad-/Medientasten, wenn im iDrive
> „Multimedia → Bluetooth" aktiv ist. PiDrive ist daher faktisch auf **up/down (Skip)**
> und **enter (Play/Pause)** angewiesen.
>
> **Deshalb: explizite „Zurueck"-Einträge.** Da `back` (= Stop) im Fahrzeug oft nicht
> ankommt, hat seit v0.11.123 **jeder Ordner** als ersten Eintrag „Zurueck" (Aktion
> `back`, per enter auslösbar). So kommt man auch ohne Stop-Kommando eine Ebene hoch.
> Zusätzlich: Doppel-Tipp Play (`cat:0`) springt an den Menüanfang; volle Bedienung
> jederzeit über WebUI/CLI.
>
> **Zwei Empfangspfade beachten** (siehe `iDriveBt.md` §6.1): Der `mpris2.py`-Pfad mappt
> **fest** (Next→down, Stop→back …), der `avrcp_trigger.py`-Pfad **kontextabhängig**.
> Im Menü-Kontext ergeben beide dasselbe; in Radio-/Scanner-Kontexten unterscheiden sie
> sich (z. B. Next→`fm_next`).

---

*Weiterführend: `TROUBLESHOOTING.md` (Was tun wenn etwas schiefgeht?), `DEVELOPER_GUIDE.md` (Wo liegt der Code?), `iDriveBt.md` (Bluetooth/AVRCP/MPRIS2-Details)*
