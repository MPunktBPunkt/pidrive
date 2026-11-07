# BMW 38304 — Erster erfolgreicher Verbindungstest

**Datum:** 2026-09-16 (ca. 18:55–19:45 CEST)  
**Fahrzeug:** BMW 38304 (`D4:36:39:CF:E1:B5`) — Headunit mit iDrive / NBT-Evo-Linie  
**Pi:** `Pidrive` · WLAN `192.168.178.105` · VERSION **0.11.141** (MPRIS-Fix live; Repo-HEAD am Pi ggf. älter)  
**Messablage:** `/var/log/pidrive/bmw_hb_messung_20260916_193414/`  
**Verwandt:** [BMW-AVRCP-PROBE.md](BMW-AVRCP-PROBE.md) · [AUFTRAG-BLUETOOTH-FUNDAMENT.md](../archiv/auftraege/AUFTRAG-BLUETOOTH-FUNDAMENT.md) · [iDriveBt.md](iDriveBt.md)

Nach Zündung aus: Agent **19:39:19** `Connected … connected=False`; danach wiederholt `avdtp … Host is down`.  
**Ist-Zustand jetzt:** Paired/Bonded/Trusted = **ja**, Connected = **nein** — erwartbar.

---

## 1. Kurzfazit

| Stufe | Ergebnis | Kommentar |
|-------|----------|-----------|
| **HB1** PiDrive in Geräteliste | **bestanden** | Alias `PiDrive`, Phone-Class |
| **HB2** Kopplung | **bestanden** | Passkey `376726`, Agent `always` → ja |
| **HB3** Reconnect Zündung | **teilweise** | Flaps / Page-Timeouts; nach manueller Auswahl oft ok |
| **HB4** Ton im Fahrzeug | **bestanden** | Webradio Rock Antenne über A2DP `bluez_output…RUNNING` |
| **HB5** drei Textzeilen Display | **teilweise** | Metadaten werden gesendet; Anzeige wechselhaft (s. §5) |
| **HB6** Tasten / Drehrad | **nicht bestanden** | **0** AVRCP-Events im Ringbuffer |
| **Browsing PSM 0x001B** | **nicht beobachtet** | Listenmenü über AVRCP fällt aus |

Das ist der **erste belegte End-to-End-Erfolg** von Pairing + A2DP-Ton. Steuerung und stabile Display-Metadaten sind die nächsten Baustellen.

---

## 2. Chronologie (aus Logs + Sitzung)

| Zeit (CEST) | Ereignis |
|-------------|----------|
| ~18:57 | Erste Kopplung (Passkey `345482`), kurz Connected, dann Flaps; Watcher hing noch an Sennheiser HD 4.40BT |
| 18:57–19:10 | HD aus BlueZ entfernt; `bt_last` → BMW; Connect/Disconnect-Rennen; hängender iDrive-Passkey-Dialog |
| ~19:10 | Alte Bindung am Pi gelöscht (Reset für frischen Passkey) |
| ~19:13–19:18 | Mehrere Scan/Pair-Versuche: BMW zeitweise unsichtbar; Pi→BMW `Page Timeout` |
| **19:21:31** | **Erfolgreiche Kopplung:** `RequestConfirmation passkey=376726 → ja`, danach `Paired` |
| 19:21–19:28 | Connect instabil (`br-connection-page-timeout`, `Host is down`, A2DP busy); Core-Restart wegen MPRIS-Fix |
| ~19:28 | A2DP wieder da; MPRIS zeigt u. a. ICY-Titel (z. B. Sk8er boy / Rock Antenne) |
| 19:32–19:36 | Nutzer hört Rock Antenne; Display zeitweise „Spotify Connect“ / „Unbekannt…“ |
| **19:34–19:36** | Strukturierte Messung (btmon + MPRIS-Snapshots + AVRCP-Watch) |
| **19:39:19** | Zündung aus → Agent `connected=False`; danach `Host is down` bis ≥19:46 |

Agent-Ereignisse (Journal `pidrive_btagent`, Auszug):

```
19:21:31 Connected              connected=True
19:21:31 RequestConfirmation    passkey=376726 → ja (Regel always)
19:21:52 Paired
19:21:53 Connected              True → False (Flap)
19:22:34…19:24:32             weitere Connect-Flaps
19:27:45–49                   btagent Restart (Deploy MPRIS-Fix)
19:28:42 Connected              connected=True   ← stabile A2DP-Phase
19:39:19 Connected              connected=False  ← Zündung aus
```

---

## 3. Hardware / Profile (während Verbindung)

### 3.1 Pi-Adapter

- Alias: **PiDrive**
- Class (während Test): Phone / Smart phone (`0x48020c` / verwandt)
- UUIDs u. a.: **A2DP Source `0x110A`**, **AVRCP Target `0x110C`**, AVRCP `0x110E`
- `Media1.RegisterPlayer` → `/org/mpris/MediaPlayer2` — Statusdatei `/tmp/pidrive_mpris_bluez.json`: `"ok": true`

### 3.2 BMW 38304

| Feld | Wert |
|------|------|
| MAC | `D4:36:39:CF:E1:B5` |
| Class | `0x00340408` (Icon `audio-headset` — aus Pi-Sicht die **Sink**) |
| Audio Sink | `0x110B` |
| A2DP | `0x110D` |
| AVRCP Target | `0x110C` |
| AVRCP | `0x110E` |
| Handsfree | `0x111E` (SDP: `ALPS_HFM` v1.6) |
| Modalias | `bluetooth:v05EBp0116d0103` |

BlueZ-Baum am Gerät: A2DP-SEPs (`sep1`/`sep2`/`sep3`), **kein** `…/playerN` (kein `org.bluez.MediaPlayer1` am Remote-Gerät).

### 3.3 Audio-Pfad (HB4)

- Sink: `bluez_output.D4_36_39_CF_E1_B5.1` (PipeWire), zeitweise **RUNNING**
- Quelle: Webradio **Rock Antenne** (`pidrivectl play web "Rock Antenne"`)
- Gehörte Titel (Status/ICY): u. a. RHCP, Jack and Diane / John Cougar, Friday I'm in love / The Cure, Sk8er boy / Avril Lavigne

---

## 4. Pairing-Erkenntnisse (HB2)

1. **BMW-initiiert vs. Pi-initiiert:** `Device1.Pair()` vom Pi scheiterte mehrfach mit **Page Timeout**, solange das Auto nicht wirklich pagebar war. Erfolg, als das Fahrzeug in Pairing war und der Agent die Bestätigung lieferte.
2. **Agent `always`:** Passkey wird am Pi automatisch bestätigt; Nutzer muss **am iDrive** die Zahl vergleichen.
3. **Störfaktor Sennheiser HD 4.40BT:** `bt_last_mac` zeigte auf den Kopfhörer; Watcher reconnectete ihn; UI zeigte „in Reichweite“ für gepaarte Geräte ohne Funk (False Positive in `bt known`).
4. **Hängender Passkey-Dialog:** iDrive zeigte „Passkey wird überprüft“, obwohl am Pi bereits gebunden war — Reset (Remove + neu koppeln) half.
5. Nach Zündung aus: Bond bleibt; Connect endet sauber (`Connected: no`).

---

## 5. Display / MPRIS (HB5)

### 5.1 Was der Pi gesendet hat

Während der Messung (Snapshots 19:34–19:35), durchgängig Connected + A2DP RUNNING:

| Property | Beispielwert |
|----------|----------------|
| `xesam:title` | `Rock Antenne Live` (Testpush) / ICY-Titel |
| `xesam:artist` | `Red Hot Chili Peppers` (Testpush) / `Rock Antenne` |
| `xesam:album` | `Webradio Rock Antenne` |
| `PlaybackStatus` | `Playing` |
| D-Bus-Name | `org.mpris.MediaPlayer2.pidrive` (root / pidrive_core) |

`RegisterPlayer` war laut Statusdatei erfolgreich.

**Baseline `status.json` zur gleichen Zeit (wichtig für HB5):**

```
radio=False, radio_playing=None, radio_type='WEB', radio_name='Rock Antenne',
track='Jack and Diane', artist='John Cougar', album='',
spotify=True, bt=True, bt_device='BMW 38304'
```

Das erklärt die fälschliche „Spotify Connect“-Anzeige: Spotify-Flag aktiv, Radio-Flag aus, Album leer — trotz laufendem WEB und hörbarem Ton.

### 5.2 Was am iDrive beobachtet wurde (Sitzung)

| Beobachtung | Einordnung |
|-------------|------------|
| Eintrag **PiDrive** im Menü | HB1/HB2 ok |
| Ton Rock Antenne | HB4 ok |
| Anzeige **„Spotify Connect“** bei laufendem Webradio | Bug: `spotify=True` (Dienst) überdeckte Radio-Zweig in `mpris2.py` — Fix in **v0.11.141** (`radio` vor Spotify; `radio_on = radio \|\| radio_playing`) |
| **„Unbekanntes Album / Unbekannter Interpret“** | Leere/überschriebene Felder bzw. BMW-Fallback; Status hatte zeitweise `radio=False`, `track=''` trotz `radio_type=WEB` |
| Nach Fix/Testpush zeitweise korrekte Titel | z. B. Sk8er boy; Testzeilen „Rock Antenne Live“ |

**HB5:** technisch sendet PiDrive Metadaten — **produktreif nur eingeschränkt**, bis Statusflags und Push-Pfad leerfreie, stabile drei Zeilen liefern und die Sichtprüfung wiederholt bestätigt ist.

### 5.3 Sichtprüfungstabelle (für Nachtrag)

| Gesendet (Beispiel) | Am iDrive? | Notiz |
|---------------------|------------|-------|
| title `Rock Antenne Live` | ? / zeitweise | Nutzer: teils Unbekannt / Spotify Connect |
| artist `Red Hot Chili Peppers` | ? | Ton war RHCP, Display nicht zuverlässig |
| album `Webradio Rock Antenne` | ? | |

---

## 6. AVRCP / Drehrad (HB6) und Browsing

### 6.1 Messung 19:34–19:36

| Artefakt | Ergebnis |
|----------|----------|
| `bmw_probe.btsnoop` | ~2,0 MB / 131 605 dekodierte Zeilen |
| Urteil Analyzer | **`kein_browsing_kanal`** |
| PSM 0x001B (Browsing) | nicht beobachtet |
| PSM 0x0017 (Control) | im Analyzer-Lauf nicht beobachtet |
| Pass-Through-Ops | leer |
| `pidrivectl avrcp events` | **0 Events** |
| `/tmp/pidrive_avrcp_events.json` | fehlt |
| Live-DBus während Drehen | keine `Next`/`Previous`/MediaPlayer1-Signale |

`avrcp_trigger.py` und `dbus-monitor` liefen, schrieben aber keine nutzbaren Steuer-Events.

### 6.2 Deutung

- **Browsing-Kanal öffnet der BMW nicht** → kein Listenmenü über AVRCP (Zielbild bleibt **3 Zeilen** MPRIS). Negatives Ergebnis ist für Gateway/A17 wertvoll ([BMW-AVRCP-PROBE.md](BMW-AVRCP-PROBE.md)).
- **Pass-Through vom Drehrad erreicht PiDrive in diesem Lauf nicht.** Mögliche Ursachen (noch offen): AVRCP-Target-Rolle/RegisterPlayer unvollständig für Controller-Befehle; BlueZ liefert kein `MediaPlayer1` am Remote; Mitschnitt startete auf bereits stehender ACL ohne erneuten Control-Setup; oder iDrive steuert nur lokal die BT-Quelle ohne Pass-Through an die Source.

**HB6: nicht bestanden** — nächster Hebel: gezielt MPRIS-Methodenaufrufe (`Next`/`Previous`) und AVCTP Pass-Through unter `sudo btmon` bei Skip/Drehsteller, ggf. nach frischem Connect.

---

## 7. Stabilität / Fehlerbilder (bluetoothd)

Wiederkehrend im Journal:

| Symptom | Bedeutung |
|---------|-----------|
| `br-connection-page-timeout` | Pi page’t BMW, Auto antwortet nicht (aus / nicht pagebar) |
| `avdtp_connect_cb … Host is down (112)` | A2DP nach Trennung / Zündung aus |
| `a2dp-sink profile connect failed … busy` | BlueZ versucht zusätzlich Sink-Rolle (Pi soll Source bleiben) |
| `error updating services: Input/output error` | SDP-Refresh während Pair gestört |
| `Unable to load LastUsed: rseid 1 not found` | SEP-Cache nach Reconnect |

Connect vom iDrive wirkte manchmal „tot“, obwohl Pi schon `Connected=yes` + Sink hatte — Auswahl der **Medienquelle** Bluetooth/PiDrive nötig.

---

## 8. Software-Fixes aus diesem Test

| Thema | Maßnahme |
|-------|----------|
| MPRIS Spotify-Flag überdeckt Webradio | `mpris2.py`: Radio-Zweig vor Spotify; `radio_on` über `radio`/`radio_playing` (auch wenn `radio_playing=None`) → **v0.11.141** / Commit `fcf7b86` |
| Falsches „Online“ für HD | BlueZ-Objekt ≠ Reichweite; Watcher/`bt_last` auf BMW |
| Agent CRLF / Lebendigkeit | BF-J zuvor (ts &lt; 30 s, LF) |

Offen: Status `radio=False` trotz laufendem WEB; leere ICY → BMW „Unbekannt“; AVRCP-Eingangspfad.

---

## 9. Abnahme nach Auftrag (HB)

| ID | Soll | Ist 2026-09-16 |
|----|------|----------------|
| HB0 | Werkbank | zuvor grün |
| HB1 | PiDrive in Liste | **ja** |
| HB2 | Pair + Passkey | **ja** (`376726`) |
| HB3 | Zündung-Reconnect | **teilweise** |
| HB4 | Ton Webradio | **ja** |
| HB5 | Title/Artist/Album | **teilweise** |
| HB6 | Tasten/Menü | **nein** (0 Events) |

---

## 10. Nächste Schritte (priorisiert)

1. **HB6 diagnostizieren:** bei verbundenem Auto Skip/Drehsteller + `sudo btmon` + Log ob `org.mpris.MediaPlayer2.Player.Next` aufgerufen wird.  
2. **Status-Maschine:** `radio`/`radio_playing` zuverlässig true bei WEB; nie leere `xesam:artist`/`album` an BMW.  
3. **HB5 Sichtprüfung wiederholen** mit bekanntem Testpush und Foto/Notiz der drei Zeilen.  
4. **HB3:** Reconnect nur vom Fahrzeug; Watcher nicht auf Fremdgeräte.  
5. Rohdaten der Messung auf dem Pi behalten; Bericht hier versionieren.

---

## 11. Rohdaten-Index

| Pfad | Inhalt |
|------|--------|
| `/var/log/pidrive/bmw_hb_messung_20260916_193414/` | Komplette Messung |
| `…/bmw_probe.btsnoop` | HCI-Mitschnitt |
| `…/mitschnitt.txt` | btmon-Text |
| `…/befunde.json` / `BMW-AVRCP-PROBE.md` | Analyzer |
| `…/mpris_snaps.txt` | Metadaten + Sink alle 15 s |
| `…/baseline.txt` | BT/MPRIS/Status Start |
| `/tmp/pidrive_bt_agent_events.json` | Pairing-Protokoll |
| `/tmp/pidrive_mpris_bluez.json` | RegisterPlayer-Status |
| `/var/log/pidrive/core.log` | Core INFO |
| `journalctl -u bluetooth` / `pidrive_btagent` | Systemd |

---

*Erstellt 2026-09-16 nach dem ersten erfolgreichen BMW-Test; Verbindung bei Berichtschluss getrennt (Zündung aus).*
