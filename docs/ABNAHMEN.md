# Abnahmeprotokolle — PiDrive

**Stand:** v0.11.130 · 2026-09-15

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

## 2026-09-15 — iDrive-/Menü-Screenshots ins Repo

Zwei UI-Screenshots unter `docs/fahrzeug/`, eingebunden in [`fahrzeug/iDriveBt.md`](fahrzeug/iDriveBt.md) §11 und [`architektur/RUNTIME_FLOWS.md`](architektur/RUNTIME_FLOWS.md) I.2:

| Datei | Inhalt |
|-------|--------|
| `docs/fahrzeug/pidrive-wurzelmenue-favoriten.png` | PiDrive-Wurzelmenü, Favoriten zuerst (`1/6`) |
| `docs/fahrzeug/bmw-bluetooth-audio-favoriten.png` | BMW Bluetooth Audio → Favoriten: PiDrive, PiDrive Menü |

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
