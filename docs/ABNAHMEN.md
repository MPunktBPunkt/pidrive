# Abnahmeprotokolle — PiDrive

**Stand:** v0.11.132 · 2026-09-15

Ergebnis-Dokumente werden **ergänzt**, nicht überschrieben. Jede Messung nennt Commit-Hash.

---

## 2026-09-15 — H0 Deploy-Gleichstand + Baseline (vor W0/W1)

| | |
|---|---|
| Host | `192.168.178.107` (Pidrive, LAN; früher `.105`) |
| Repo auf Pi | `/home/pidrive/pidrive` |
| Commit Pi (vor Sync) | `20b312d` |
| Commit Entwickler | `e86272e` (+ lokale W0/W1-Arbeit → `0.11.128`) |
| `grep -c "def test_menu"` auf Pi | **0** (H0 bestätigt: Pi kannte Menü-Tests nicht) |
| VERSION beider Seiten | `0.11.127` (Versionsdatei war kein Gleichstand) |
| Services | `pidrive_core=active`, `pidrive_web=active` |
| SSH | Schlüssel eingerichtet; BatchMode ok |

### Baseline `pidrivectl test all` (Pi @ `20b312d`)

- Dauer: ~65 s
- Ergebnis: **17 bestanden / 0 Fehler / 30 Warnungen**
- Kein MENU-Abschnitt (Code ohne `test_menu`)
- Artefakte: `/tmp/baseline/` auf dem Pi

---

## 2026-09-15 — W0/W1 (WebUI-Sicherheitsnetz + Fehler sichtbar)

### Lokal vor S11/S12-Fix (Nachweis Abnahme W1)

`pidrivectl webui selftest` meldete:

- `web.shared.audio.get_volume_data`: `name 'safe_run' is not defined` (S11)
- `web.shared.view_model.get_dab_scan_debug`: `name 'sys' is not defined` (S12)
- `web.shared.view_model.get_spectrum_debug`: `name 'sys' is not defined` (S12)

Zusätzlich WARN-Logs aus entschärften `except`-Blöcken.

### Nach Fix (S11/S12 Import)

| Prüfung | Ergebnis |
|---------|----------|
| `webui selftest` | **0 Fehler** |
| `webui check` | Exit 1 — genau die 3 erwarteten V4-Treffer: `prev_station`, `next_station`, `/api/ppm_calibrate` |
| C16 `td_hardware.py` | lokaler `import source_state` entfernt |

### Hardware-Verifikation (nach Deploy)

| | |
|---|---|
| Commit auf Pi | `adf7e16` |
| VERSION | `0.11.128` |
| Deploy | `git reset --hard origin/main` + Service-Restart |
| Log | `/tmp/hw_w01_2026-09-15_1234.log` |

| Prüfung | Ergebnis |
|---------|----------|
| `pidrivectl webui check` | Exit 1 — genau 3 V4-Treffer (`prev_station`, `next_station`, `/api/ppm_calibrate`) |
| `pidrivectl webui selftest` | **0 Fehler** |
| `pidrivectl menu verify` | OK — 287 Knoten, keine Verluste |
| `pidrivectl test webui` | ✓ check + ✓ selftest |
| **H2.1 C16** `radio_stop` / `spotify_toggle` | **kein** `cannot access free variable 'source_state'` mehr; `source_current` wird nach Toggle `spotify` |
| **H2.6 S11** `/api/audio` | `sinks` nicht leer, `current_volume` z. B. `54%` (vorher dauerhaft leer) |
| **H2.7 S12** `dab_scan_debug` / `spectrum_debug` | kein `name 'sys' is not defined` mehr |
| **W1.3** `degraded_imports` in Status | sichtbar: `modules.rtlsdr` / `modules.spectrum` (erwartet bis W4/C2) |
| H2.8 `processes` | weiterhin `[]` — gehört zu W2/S3 |
| H2.13 `activate:1` | HTTP 400 „nicht erlaubt“ — bekannt, Menü-Trigger noch nicht in Whitelist |

**Fazit für zweite Cursor-Instanz:** W0 und W1 sind auf HW `@adf7e16` verifiziert. Statuskette (W2), V4-Button-Fixes und RTL-SDR-Importbruch (W4) sind die nächsten Pakete. C16-Ausfall und S11/S12 sind behoben und am Pi nachweisbar.

---

## 2026-09-15 — W2 Statuskette + W3 tote Schichten (lokal)

| | |
|---|---|
| Code | lokal, **v0.11.129** (noch nicht auf Pi) |
| Pi | `192.168.178.107` — nach Stromausfall LAN; WLAN problematisch |

| Paket | Status |
|-------|--------|
| **W2** Statuskette | ✅ S1–S9: `status_age` top-level, Offline-Banner, `read_json_meta`, READY_FILE-Cleanup, `processes` in `write_status`, Hooks/Snapshot (S4), Feldnamen S5–S8, `/api/lists` |
| **W3** tote Schichten | ✅ `web/shared.py` gelöscht (E8), `api-core.js` Syntax, V5-Pfade, V4 prev/next+PPM; `page-index.js` **nicht** eingebunden |
| **W4** RTL-SDR-Import | ✅ C2: Imports → `modules.radio.*`; `_rtlsdr`/`_spectrum` nicht mehr `None`; MIGRATION_BACKLOG korrigiert |
| **W7/Stufe 1** | ✅ Z2–Z3–Z10 lokal; `pidrivectl source state\|history` |
| **W5** (Teil) | ✅ C1, C3, C4, C5(fast_bw), C7, C8, C9, C12–C14 — C5 Single-Prozess + CB-AM offen |
| **W6** | ✅ scanner in Status; CLI status / `--verbose`; Menü Stop |
| W8–W11 | ⬜ offen |

| Prüfung lokal | Ergebnis |
|---------------|----------|
| `pidrivectl webui check` | **0 Treffer** |
| `pidrivectl webui selftest` | **0 Fehler** |
| Import `modules.radio.fm/scanner/spectrum` | `_rtlsdr`/`_spectrum` gesetzt, `degraded_imports` leer |

**HW ausstehend (wenn Pi wieder erreichbar):** H2.4 (Core stop → Banner), H2.8 (`processes` nicht leer), H2.3 (Throttling), H2.5 (`api-core.js` ohne SyntaxError), **R5** Quellenwechsel nach W4, **R6/R7** Scanner PMR446, **R12–R14** Transitionen.

---

## 2026-09-15 — W7/Stufe 1 + W5 Teil (lokal, v0.11.130)

| | |
|---|---|
| Code | lokal **v0.11.130** — Pi unreachable |
| W7.1 Z2 | alle `begin_transition`-Aufrufer behandeln `False` → Progress „Blockiert“ |
| W7.2 Z3 | `in_transition()` räumt Stale auf (Datei=Speicher) |
| W7.3 Z3 | `check_stale_transition()` in Core-Loop (0.5 s) |
| W7.4 Z10 | `history` Ringpuffer; `pidrivectl source state\|history` |
| W5 C1/E3 | `scan_next`/`scan_prev`: Transition erst nach Treffer |
| W5 C7 | kaputtes `reason=` entfernt; `stop()` beendet keine fremde Transition |
| W5 C3 | Schmalband `-s` = max(48000, bw×4) — **[MESSEN] Vorher/Nachher auf Pi** |
| W5 C4 | Detect-Timeout Default 1.5 s — **[MESSEN]** |
| W5 C8/C9 | Freenet K5/K6; set_channel per `ch`; set_freq für Kanalbänder |

**Offen in W5:** C5 vollständiger Single-`rtl_fm`-Sweep (nur fast_bw-Lücke geschlossen), CB-AM.

---

## 2026-09-15 — Deploy + HW unter `192.168.178.107` (LAN)

| | |
|---|---|
| Host | `192.168.178.107` (LAN nach Stromausfall; WLAN problematisch) |
| Commit | `16586af` / **v0.11.131** (+ Scanner-Status-Fix nach Deploy) |
| Vorher | `f749a42` / 0.11.128 |
| Deploy | `git fetch` + `reset --hard origin/main`; Restart via `sudo -n /bin/systemctl restart pidrive_*` |

| Prüfung | Ergebnis |
|---------|----------|
| `webui check` / `selftest` | **0 Treffer / 0 Fehler** |
| `source state` | Speicher↔Datei übereinstimmend |
| H2.8 `processes` | **7–8 Einträge** (nicht mehr `[]`) |
| H2.4 `status_age` | während Core-Restart: age 3.5s + `status_error=stale` ✅ |
| R6 `pmr446 ch 1` | `rtl_fm … -s 50000` (C3) ✅; Kanal 446.00625 MHz |
| `degraded_imports` | **[]** (W4) |

Hinweis: NOPASSWD erlaubt nur `systemctl restart`, nicht `stop`/`start`. Host-Key für `.107` nach LAN-Wechsel erneuert.

---

## 2026-09-15 — W5 Rest + W6 (lokal, v0.11.131)

| | |
|---|---|
| W5 C5 Teil | VHF/UHF `fast_bw` ≥ 100 kHz (Schrittabdeckung) |
| W5 C12 | `check_hardware()` vor `play_freq`; pkill-Muster `--no-terminal` |
| W5 C13 | Menü-Aktivmarkierung über `scanner_band` / Label |
| W5 C14 | `scan_idx` bandgetrennt |
| W6 | `scanner`-Schlüssel in `write_status`; `pidrivectl scanner status`; Scan `--verbose` Hinweis; Menü `scanner_stop` |

---

## 2026-09-15 — Spektrum-Snapshot WebUI: JSON statt Bild + „RTL-SDR belegt“ trotz Idle

**Für Analyse in zweiter Cursor-Instanz** (W8/FastScan / RF-Tools). Kein Fix in diesem Commit — nur Befund.

| | |
|---|---|
| Host | `192.168.178.107` · User `pidrive` · Commit Pi `0801f4f` / v0.11.132 |
| Nutzer-Kontext | **Nichts abgespielt** (`pidrivectl now` → idle). Stick soll frei sein. |
| UI | WebUI → RF / DAB Tools → „📡 Snapshot“ / „Letztes“ |
| Erwartung Nutzer | Spektrum-**Bild** (FFT Leistung vs. Frequenz) |
| Ist | Roh-JSON in `<pre id="specPre">` — **kein Canvas/Chart** (`web/templates/rf-tools.html`) |

### Nutzer-Ergebnis (`GET /api/spectrum/last`, gekürzt)

- Outer: `"ok": true`, `"exists": true`, `mode: "fm_sweep"`, `windows_total: 21`, **`windows_ok: 0`**
- `candidates: []`, `candidates_all_count: 0`
- Jedes Fenster 87.5…107.5 MHz: `"ok": false`, **`"error": "RTL-SDR belegt"`**
- Parameter: `ppm: 49`, `gain: -1`, `sample_rate_hz: 2048000`, `sample_count: 131072`, `step_mhz: 1`

### Reproduktion (UI-Pfad)

```bash
# Button ruft faktisch (ohne mode=snapshot):
curl -s -X POST 'http://127.0.0.1:8080/api/spectrum/capture?center=446.1&ppm=49&gain=-1'
# Default mode=fm_sweep — Feld „Mitte MHz“ wird IGNORIERT (Query-Key center ≠ center_mhz)
curl -s 'http://127.0.0.1:8080/api/spectrum/last' | python3 -m json.tool
```

### Bekannte Code-Ursachen (Auftrag F7 + Folgefehler)

| ID | Befund | Ort |
|----|--------|-----|
| **F7** | Button „Snapshot“ setzt weder `mode=snapshot` noch `center_mhz` → Default **`fm_sweep`** (21 Fenster FM-Band) | `rf-tools.html` `captureSpectrum()`; `app.py` `api_spectrum_capture` Default `mode=fm_sweep` |
| **UI** | Kein Spektrum-Plot — nur `JSON.stringify` | `rf-tools.html` `loadSpectrumLast()` |
| **ok-Lüge** | `sweep_fm_band` setzt Ergebnis immer `"ok": true`, auch wenn **alle** Fenster fehlschlagen | `modules/radio/spectrum.py` `sweep_fm_band` |
| **Busy-Check** | Legacy `capture_spectrum` bricht bei `_rtlsdr.is_busy()` sofort mit `"RTL-SDR belegt"` ab — **ohne** `clear_stale_lock()` / `reap_process()` / `wait_until_free()` | `spectrum.py` ~840–841 vs. `RTLSDRBackend.capture_iq` (wartet bis 4 s) |
| **`is_busy`** | `True` wenn `find_rtl_processes()` **oder** `STATE_FILE.locked` | `rtlsdr.py`: `STATE_FILE=/tmp/pidrive_rtlsdr_state.json`, `LOCK_FILE=/tmp/pidrive_rtlsdr.lock` |
| **stdout-Bug** | Legacy `capture_spectrum` startet `rtl_sdr … -n N` **ohne** Dateiname `"-"` → Binary druckt Usage, stdout leer → `"keine IQ-Daten"`. `RTLSDRBackend` hat `cmd += ["-"]` korrekt | `spectrum.py` `capture_spectrum` vs. `RTLSDRBackend.capture_iq` |

Auftrag-Kontext: `docs/auftraege/AUFTRAG-WEBUI-SANIERUNG.md` Abschnitte **F6–F9**, DoD W8, H2.11/H2.12.

### Nachmessung am Pi (Idle, ~17:56 UTC+2, gleiche Session)

Nach Nutzer-Report, als Core idle und **keine** `rtl_*`/`welle`/`mpv`-Prozesse:

| Check | Ergebnis |
|-------|----------|
| `pidrivectl now` | Nichts läuft |
| `pidrivectl source state` | `idle`, keine Transition |
| `rtlsdr.is_busy()` | **`False`** |
| `/tmp/pidrive_rtlsdr_state.json` | **fehlt** |
| `/tmp/pidrive_rtlsdr.lock` | existiert; Inhalt enthält noch Meta `owner: "dab_play"`, `pid: 26030` (Stale-Spur nach früherem DAB) |
| `capture_spectrum(446.1, …)` direkt | **`ok: false`, `error: "keine IQ-Daten"`**, stderr = **Usage** von `rtl_sdr` (fehlendes `"-"`) |
| UI-äquivalenter POST (fm_sweep) | `mode=fm_sweep`, `ok: true`, `windows_ok: 0`, Fehler pro Fenster: **`keine IQ-Daten`** (nicht mehr „belegt“) |

**Interpretation für die Analyse-Instanz:**

1. Nutzer-JSON mit durchgängig **„RTL-SDR belegt“** trotz Idle → vermutlich **stale Lock/State oder Busy-Semantik**, nicht aktive Wiedergabe. `capture_spectrum` ruft vor `is_busy()` kein `clear_stale_lock()`. Früherer Owner laut Lock-Datei-Rest: **`dab_play`**.
2. Sobald Busy=false, scheitert derselbe Legacy-Pfad am **fehlenden `"-"`** → Measurement tot, auch bei freiem Stick.
3. UI/Mode-Bug (F7) erklärt, warum kein Einzel-Snapshot bei 446,1 MHz und warum 21 FM-Fenster erscheinen.
4. Selbst bei Erfolg käme `spectrum_db` (bis ~131k Floats) als JSON — **kein Bild**, bis RF-Tools gerendert wird (Auftrag F8 zu Antwortgröße beachten).

### Diagnose-Befehle für die andere Instanz

```bash
ssh pidrive@192.168.178.107
pidrivectl now; pidrivectl source state
pgrep -a 'rtl_|welle|mpv' || echo idle-procs
python3 - <<'PY'
import sys; sys.path.insert(0,"/home/pidrive/pidrive/pidrive")
from modules.radio import rtlsdr
print("busy", rtlsdr.is_busy())
print("procs", rtlsdr.find_rtl_processes())
print("state", rtlsdr._read_state())
PY
ls -la /tmp/pidrive_rtlsdr* /tmp/pidrive_spectrum.json
# Referenz-Capture MIT stdout-Dateiname (sollte Bytes liefern):
timeout 5 rtl_sdr -f 98000000 -s 2048000 -n 8192 - 2>/tmp/rtl_err | wc -c
# API wie UI:
curl -s -X POST 'http://127.0.0.1:8080/api/spectrum/capture?center=446.1&ppm=49&gain=-1' | head -c 400
# API wie Label „Snapshot“ eigentlich meint:
curl -s -X POST 'http://127.0.0.1:8080/api/spectrum/capture?mode=snapshot&center_mhz=446.1&ppm=49&gain=-1' | head -c 400
```

### Erwartete Fix-Richtung (nicht umgesetzt)

1. UI: `mode=snapshot&center_mhz=…`; optional Canvas aus downsampled `spectrum_db`.
2. Legacy `capture_spectrum`: `cmd += ["-"]`; vor Busy `clear_stale_lock`/`reap`/`wait_until_free` wie Backend.
3. `sweep_fm_band`: `ok = (windows_ok > 0)` o.ä.; Fehler aggregieren.
4. W8 laut Auftrag: CLI `pidrivectl spectrum …`, Watch/F3, Stations-Pipeline.

---

## 2026-09-15 — HW `test all` nach TK-A…E (v0.11.137)

| | |
|---|---|
| Host | `192.168.178.107` |
| Commit | `fba2715` / **v0.11.137** |
| Log | `/tmp/test_all_hw_20260915_194958.log` |
| JSON | `/tmp/pidrive_test_results.json` |
| Dauer | 132.5 s |
| Ergebnis | **21 bestanden · 2 Fehler · 24 Warnungen · 2 übersprungen** |

### Gegenüber Nutzer-Lauf @ v0.11.132 (19:25)

| | Vorher (0.11.132) | Jetzt (0.11.137) |
|---|---|---|
| Webradio / FM | ✓ | ✓ |
| Scanner | ✓ (falsch positiv möglich) | **✗** Spiegel=`scanner`, Gerät=kein `rtl_fm` (TK-B) |
| DAB Scan | ✗ SNR/FIC als Fehler | **⊘ SKIP** kein Signal (SNR 4.0, FIC 2476) — TK-E |
| Spotify | ⚠ | **⊘ SKIP** kein Dienst — TK-C |
| MPRIS2 | ✗ | ✗ unverändert |
| „RTL-SDR belegt“ in Suite-Stdout | ja (Log-Warnungen) | **0** Treffer in Suite-Stdout; in `pidrive.log` noch 3 Warnungen während Lauf |

### Fehler (2)

1. **MPRIS2** — `ServiceUnknown: org.mpris.MediaPlayer2.pidrive` (Watchdog meldet Verschwinden)
2. **Scanner FM** — `Spiegel=scanner Gerät=False (RTL=[])` — Quelle im Spiegel gesetzt, kein `rtl_fm`; parallel `pidrive.log`: `Scanner: RTL-SDR belegt` → TK-B deckt den alten False-PASS auf

### SKIP (2)

- DAB Scan 11B: Standort ohne Signal (TK-E)
- Spotify: weder librespot noch raspotify

### Fazit

Testkette TK-A/C/E wirkt: DAB/Spotify verdrehen den Exit-Status nicht mehr. TK-B zeigt einen echten Scanner-Pfad-Bug (commit ohne Gerät / Belegt trotz Stop). MPRIS2 und Scanner-Gerät sind die nächsten Fixes; SP-* noch offen. Auftrag: `docs/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md`.

---

## 2026-09-16 — M-A MPRIS2 Core-Absturz-Messung

| | |
|---|---|
| Host | `192.168.178.107` |
| Commit / VERSION | `9db988b` / **v0.11.137** (vor Teil-D-Code) |
| Methode | Auftrag `AUFTRAG-MPRIS2-STABILITAET.md` §6 Gegenprobe + Stress |

### Ergebnis

| Prüfung | Wert |
|---------|------|
| `NRestarts` vor / nach | **0 / 0** (unverändert) |
| Journal `SIGABRT` / `Main process exited` / `Scheduled restart` | **keine Treffer** im Messfenster |
| `mpris_push` Last | 30 (Web-Pfad) + 30 (DAB-Versuch) + 50 Stress ≈ **110** |
| D-Bus-Name `org.mpris.MediaPlayer2.pidrive` | **präsent** nach den Pushes |
| M3 (Core-Absturz durch Push) | **nicht bestätigt** in diesem Lauf |

### Deutung

Nach Schlüssel in §6: `NRestarts` unverändert bei früherem `ServiceUnknown` → eher **Namensverlust ohne Absturz** (Hebel **M-D**), nicht zwingend Thread-Abort (M-B/M-C). Teil D (Menüvorrang Q-K…) darf nach Auftragslogik weiterlaufen; M-B/M-C nur bei später reproduzierbarem Abort.

---

## 2026-09-16 — BF-A…BF-F Bluetooth-Fundament (v0.11.139)

| | |
|---|---|
| Commit | `e999c2b` |
| Host | `192.168.178.107` |
| VERSION | **v0.11.139** |
| Scope | D-Bus-Agent, dauerhafte Sichtbarkeit, CLI-Protokoll, BlueZ RegisterPlayer, alte Agent-Sitzung stillgelegt, Docs |

### HB0 (Werkbank) — gemessen am Pi

| Prüfung | Ergebnis |
|---------|----------|
| Offline-CI | **131 passed** |
| `bt_agent_dbus.py --selftest` | **bestanden** |
| `pidrive_btagent` | **active**, `Agent registriert … DisplayYesNo regel=always` |
| Adapter | `alias=PiDrive discoverable=on pairable=on timeout=0` |
| `DiscoverableTimeout` / `PairableTimeout` | **0** (btmgmt/busctl) |
| Core | erkennt `kind=dbus` Agent; bluetoothctl-Sitzung **stillgelegt** |
| `RegisterPlayer` | Log: **bei BlueZ angemeldet** |
| `org.mpris.MediaPlayer2.pidrive` auf SystemBus | **fehlt weiterhin** (ServiceUnknown) — getrennt von BF; eher M-D/Watchdog |
| `NRestarts` | **0** |

### CPU-Last / Temperatur (Werkbank, Idle+Dienste)

| | |
|---|---|
| Zeitpunkt | 2026-09-16 15:43 CEST |
| Commit auf Pi | `e999c2b` / v0.11.139 |
| Dienste | `pidrive_core`, `pidrive_web`, `pidrive_btagent` = active |

| Messwert | Ergebnis |
|----------|----------|
| Load average (1/5/15) | **0.64 / 0.44 / 0.20** |
| CPU busy (5‑s-Mittel) | **3.3 %** |
| `pidrive_core` CPU (5 s) | **0.4 %** einer Kernzeit (≈1.7 % Momentanwert, RSS 44 MB) |
| `pidrive_btagent` | ~0.1 % CPU, RSS 26 MB |
| RAM | **17.4 %** genutzt · 1524 MB frei / 1845 MB |
| SoC-Temperatur | **69.1 °C** (`vcgencmd` / thermal_zone0) |
| Throttle (`get_throttled`) | **0x0** — kein Under-Voltage / kein Thermal-Throttle |

Hinweis: zum Messzeitpunkt lief zusätzlich `welle-cli` mit ~53 % CPU (vermutlich Rest von DAB-Test); die Core-/Agent-Last blieb trotzdem niedrig.

### HB1–HB6

Am Fahrzeug — noch offen (Kopplung/Display). Siehe Auftrag §5.

---

## 2026-09-16 — HW `test all` nach BF (v0.11.139, ohne Antenne)

| | |
|---|---|
| Host | `192.168.178.107` |
| Commit | `fc16ead` / **v0.11.139** |
| Randbedingung | **Antenne nicht angeschlossen** |
| Log | `/tmp/test_all_hw_20260916_154539.log` |
| JSON | `/tmp/pidrive_test_results.json` |
| Dauer | 136.4 s |
| Ergebnis | **26 bestanden · 1 Fehler · 25 Warnungen · 2 übersprungen** |
| `NRestarts` vor/nach | **0 / 0** |
| Temp nach Lauf | 67.2 °C · Load 0.28 / 0.36 / 0.22 |

### Gegenüber Lauf @ v0.11.138 (14:52, mit vorherigem Stick-Zustand)

| | v0.11.138 | v0.11.139 (ohne Antenne) |
|---|---|---|
| Bestanden / Fehler | 26 / 1 | **26 / 1** |
| MPRIS2 GetAll | ✓ | ✓ |
| Webradio / FM Start | ✓ / ✓ | ✓ / ✓ |
| Scanner | ✗ TK-B | ✗ unverändert |
| DAB Play | ⚠ Wait for sync | ⚠ + Log „RTL-SDR belegt“ |
| DAB Scan 11B | ⊘ kein Signal | ⊘ SNR=0 (Antenne fehlt — erwartet) |
| Spotify | ⊘ | ⊘ |

### Fehler (1)

1. **Scanner FM 103.0** — `Spiegel=scanner Gerät=False (RTL=[])` — bekannter TK-B-Pfad (Commit ohne Gerät), unabhängig von der Antenne.

### SKIP (2)

- DAB Scan 11B: kein Signal (SNR 0) — **durch fehlende Antenne erklärt**
- Spotify: kein librespot/raspotify

### Warnungen mit Substanz

- DAB Play: `RTL-SDR belegt` vor Start → Folge des Scanner-Fails / Stick-Leak (nicht Antenne)
- BT nicht verbunden → kein A2DP-Live-Test
- FM startet trotz fehlender Antenne (Pipeline/Metadaten ok; Empfang nicht bewertbar)

### Fazit

Software-Pfad Menü/WebUI/MPRIS/Webradio/FM-Start unverändert grün. RF-abhängige DAB-Scan-SKIP ist mit abgezogener Antenne erwartbar. Einziger FAIL bleibt Scanner/RTL-Belegt (TK-B), nicht die Antenne.

---

## 2026-09-16 — BF-G…J + DA-A (v0.11.140) · vor der Fahrt

| | |
|---|---|
| VERSION | **v0.11.140** |
| Scope | Fehlschluss `bt pair` ohne Adresse; BF-H Messung; ObjectManager vor Pair; Agent-ts; CRLF→LF; DAB-Audioweg dokumentiert |

### BF-G — `pidrivectl bt pair` (ohne Adresse)

| Vorher | Nachher |
|--------|---------|
| Erfolg wenn *irgendein* Paired-Gerät + `last_id>0` | Erfolg nur bei Agent-Event `method=="Paired"` **oder** neuem MAC in der Paired-Menge |

### BF-H — Spieler-Anmeldung ohne bekannten Namen `[MESSEN]`

Messung am Pi (`192.168.178.107`, Core PID 150674 / v0.11.139):

| Schritt (Auftrag) | Ergebnis | Deutung |
|-------------------|----------|---------|
| `busctl tree org.bluez \| grep -i player` | **leer** | **erwartet** — lokales `RegisterPlayer` legt kein Objekt unter `org.bluez` an (BlueZ behält den Pfad auf der Sender-Verbindung; vgl. bluez#23 / media-api) |
| `busctl list \| grep mpris` | `org.mpris.MediaPlayer2.pidrive` **präsent** (root / pidrive_core) | Name da |
| Objekt `/org/mpris/MediaPlayer2` | Properties lesbar (Metadata, PlaybackStatus) | MPRIS export ok |
| `/var/log/pidrive/core.log` | `MPRIS2: bei BlueZ angemeldet (hci0 → /org/mpris/MediaPlayer2)` u. a. 15:36, 15:37, **15:38:54 nach Watchdog** | RegisterPlayer hält / wird nach Namensverlust erneut gesetzt |

**Fazit BF-H:** BF-D wirkt. HB5 ist nicht durch den Namensverlust allein gefährdet; M-D bleibt nachrangig. Ab v0.11.140 zusätzlich `/tmp/pidrive_mpris_bluez.json` als messbarer Marker (Journal zeigt INFO nicht).

### BF-I / BF-J

| ID | Änderung |
|----|----------|
| BF-I | `pair_with_agent`: ObjectManager-Prüfung vor `Pair()`; verständlicher Abbruch statt Timeout |
| BF-J | `agent_healthcheck` + `_start_bt_agent_early`: `ts` jünger als 30 s; CRLF→LF in `bt_agent_dbus.py` + `pidrive_btagent.service`; tote Imports entfernt |

### DA-A — DAB-Audioweg dokumentiert

- `docs/KontextPiDrive.md`: DAB = ALSA/Klinke, BT unerreichbar
- `docs/betrieb/TROUBLESHOOTING.md`: „DAB im Fahrzeug stumm, Webradio hörbar“ → AUFTRAG-DAB-AUDIOWEG

DA-B…DA-C warten auf Antenne / Messreihe.

