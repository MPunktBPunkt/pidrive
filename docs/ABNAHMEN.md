# Abnahmeprotokolle — PiDrive

**Stand:** v0.11.128 · 2026-09-15

Ergebnis-Dokumente werden **ergänzt**, nicht überschrieben. Jede Messung nennt Commit-Hash.

---

## 2026-09-15 — H0 Deploy-Gleichstand + Baseline (vor W0/W1)

| | |
|---|---|
| Host | `192.168.178.105` (Pidrive) |
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

*(Abschnitt wird nach Pi-Lauf ergänzt.)*
