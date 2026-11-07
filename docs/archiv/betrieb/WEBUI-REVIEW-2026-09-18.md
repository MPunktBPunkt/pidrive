# WebUI-Review — 2026-09-18

**Scope:** Aktive PiDrive-WebUI (`pidrive/web/`, Templates, Blueprints)  
**Version-Kontext:** v0.11.142-ish / Post-W0–W7  
**Methode:** Code-Review + Abgleich `tests/webui/routes.json` / `required_surface.json` / FEATURES / ABNAHMEN

---

## Gesamturteil

Alltags-UI (Player, BT, Audio, Diagnostics) ist nach der Sanierung tragfähig — `webui check`/`selftest` grün, Routen-Inventar deckungsgleich. Kritisch waren vor allem **Buttons mit HTTP-200 ohne Wirkung** und der **Spektrum-Snapshot-Pfad** (falscher Mode + kaputtes `rtl_sdr`-CLI).

---

## Funde und Status

| Prio | ID | Befund | Status |
|------|----|--------|--------|
| Hoch | R1 | RF-Tools „Snapshot“ ohne `mode=snapshot` / `center_mhz` → Default `fm_sweep` | **gefixt** |
| Hoch | R2 | Legacy `capture_spectrum` ohne `rtl_sdr … -` (stdout) → „keine IQ-Daten“ | **gefixt** |
| Hoch | R3 | Busy-Check ohne `clear_stale_lock` / `wait_until_free` | **gefixt** |
| Hoch | R4 | Webradio-Admin „Toggle“ → toter Trigger `webradio_toggle:` | **gefixt** (API) |
| Hoch | R5 | `dab_scan_replace` whitelisted, kein Handler (F-900) | **gefixt** (`store.replace_dab`) |
| Mittel | R6 | Webradio Delete-API ohne UI-Button | **gefixt** |
| Mittel | R7 | prev/next ohne Webradio (`web_prev`/`web_next` fehlten auch in Whitelist) | **gefixt** |
| Mittel | R8 | Favoriten: Spotify startete nicht | **gefixt** (`play_spotify`) |
| Mittel | R9 | Kein „Favorit merken“ in der Alltags-UI | **gefixt** |
| Mittel | R10 | Musik-Rename-API ohne UI | **gefixt** |
| Mittel | R11 | `audio_usb_gadget` fehlte in `routes.json` | **gefixt** |
| Mittel | R12 | Spektrum-Anzeige nur Roh-JSON | **teilweise** — Summary + einfacher Canvas |
| Niedrig | R13 | `sweep_fm_band` setzte immer `ok: true` | **gefixt** (`ok` = windows_ok > 0) |
| Offen | O1 | Menü-Fernsteuerung (F-095) | offen |
| Offen | O2 | WiFi-UI, DAB-Diag/Gain/Scanner-Settings in aktiver UI | offen |
| Offen | O3 | Spotify Detail/OAuth-Status | offen |
| Offen | O4 | DAB-Slides / Cover-Pipeline Web | offen |
| Offen | O5 | Legacy-Templates + `page-*.js`-Stubs | Dead Code, kein Fix nötig |
| Offen | O6 | Kein Auth auf `:8080` | bewusst LAN |

---

## Click-Test nach Fix

1. `/rf-tools` → Snapshot bei 446.1 → Response `mode=single`/`snapshot`, Peaks/Canvas, nicht 21 FM-Fenster  
2. `/webradio-admin` → Toggle enabled ↔ disabled; Delete entfernt Sender  
3. `/` Webradio aktiv → ⏮⏭ wechselt Sender; ★ merkt aktuellen; Spotify-Favorit startet Connect  
4. `/music-admin` → Rename Datei/Ordner  
5. `pidrivectl webui check|selftest|routes`

---

## Abgrenzung

Nicht behoben in diesem Durchgang: vollständiger Spektrum-Band-Plot (watch_channels), Menü-Remote, WiFi-Seite, Legacy-Aufräumen. Siehe FEATURES F-095 und Auftrag W8–W11.
