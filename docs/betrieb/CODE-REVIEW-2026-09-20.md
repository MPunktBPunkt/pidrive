# PiDrive — Code-Review (Struktur, Legacy, Flows)

**Stand:** v0.11.146 · 2026-09-20  
**Scope:** Repo-Struktur, Shims/Legacy, systemd, Docs vs. Code, Flussdiagramme  
**Methode:** Code + Docs-Abgleich (kein Live-HW-Lauf in diesem Durchgang)

---

## Gesamturteil

Die **Kern-Laufzeitpfade** (AVRCP → `/tmp/pidrive_cmd` → Core → Module → Status/MPRIS) und die **Trigger-Architektur** sind weiterhin gültig und gut dokumentiert. Die Paket-Migration (`menu/`, `trigger/`, `modules/radio|bluetooth`, `web/`, `cli/`, `integration/`) ist weitgehend durch.

Schwächer: **Dokumentationsdrift** (Architektur ohne ESP/USB-PUMP), **tote systemd-Units**, **halbfertige Shim-Lage**, und ein paar **Monolithen** (`cli/cli.py`, `spectrum.py`, `web/app.py`). Ordnerstruktur muss nicht umgeworfen werden — eher gezielt nachziehen und Legacy abschneiden.

---

## 1. Flussdiagramme / RUNTIME_FLOWS — noch gültig?

Dokument: [`docs/architektur/RUNTIME_FLOWS.md`](../architektur/RUNTIME_FLOWS.md) (Stand-Stempel v0.11.127).

| Flow | Urteil | Bemerkung |
|------|--------|-----------|
| **A** BMW → AVRCP → `pidrive_cmd` → Core → Dispatcher | ✅ gültig | `check_trigger` / `drain_triggers` / `trigger/*` unverändert |
| **B** WebUI `/api/cmd` → Queue | ✅ gültig | Entry: `web/app.py` (Shim `webui.py` entfernt 2026-09-20) |
| **C** `pidrivectl play web` | ✅ gültig | |
| **D** Local-Play | ✅ gültig | |
| **E** BT-Connect / A2DP | ✅ gültig | PipeWire-Sink-Hinweis korrekt |
| **F** DAB+ / welle-cli | ✅ gültig | |
| **G** FM / Scanner | ✅ gültig | PMR vs. WBFM-Hinweis korrekt |
| **H** Installer / Smoke | ✅ weitgehend | Pfade in Units oft `/home/pi/…` → `install.sh` ersetzt |
| **I** Menü → MPRIS → iDrive | ✅ Kern gültig | Menübaum-Skizze passt zu `menu_builder` |
| **I.4** Doppel-Tipp `cat:0` → „Jetzt läuft“ | ⚠️ veraltet | „Jetzt läuft“-Ordner entfällt; `cat:0` öffnet **Root-Kind 0 = Favoriten** |
| **ESP / USB-MSC / PUMP** | ❌ fehlt | Kein Flow in RUNTIME_FLOWS/ARCHITECTURE — Code + Units existieren (`usb_pump_client`, `pidrive_pump*`, `audio_usb_gadget`) |

**Fazit Flussdiagramm:** Das „klassische“ PiDrive-Diagramm (BT/AVRCP/Menü/Radio) ist **noch die richtige Debugging-Landkarte**. Für den aktuellen Auto-Pfad (ESP-Gadget) ist es **unvollständig** — dort gilt ergänzend [`USB-MSC-STREAM-LISTING-2026-09-18.md`](USB-MSC-STREAM-LISTING-2026-09-18.md) und [`../planung/PFAD-ESP32-PIDRIVE.md`](../planung/PFAD-ESP32-PIDRIVE.md).

Zustandsmaschine ([`ZUSTANDSMASCHINE.md`](../architektur/ZUSTANDSMASCHINE.md), v0.11.143) ist aktueller und deckt `play_gen` ab — das passt zum Code.

---

## 2. Was ist veraltet / tot?

### 2.1 Systemd-Units ohne Ziel-Datei

| Unit | ExecStart-Ziel | Status |
|------|----------------|--------|
| `pidrive.service` | `…/launcher.py` | **tot** — Datei fehlt (Display-Ära) |
| `pidrive_display.service` | `…/main_display.py` | **tot** — Datei fehlt |
| `pidrive_web.service` | `…/webui.py` | aktiv, aber nur Shim |
| `pidrive_pump_bridge.service` | `/home/pidrive/pump_bridge.py` | außerhalb dieses Repos (esp32.pidrive) |

**Empfehlung:** `pidrive.service` / `pidrive_display.service` nach `systemd/legacy/` oder entfernen + Hinweis in ARCHITECTURE. Nicht aktiv lassen.

### 2.2 Shims — Docs vs. Reality

| Docs (`ARCHITECTURE` / `MIGRATION_STRUCTURE`) | Realität (v0.11.146) |
|-----------------------------------------------|----------------------|
| `web/shared.py` Re-Export-Shim | **fehlt** — nur `web/shared/` |
| `modules/spectrum.py`, `rtlsdr.py`, `bluetooth.py` Shims | **fehlen** — Import nur über `modules.radio.*` / `modules.bluetooth.*` |
| `modules/dab.py`, `fm.py`, `scanner.py` | ✅ noch da |
| `webui.py`, `avrcp_trigger.py` | ✅ noch da (`webui` von systemd genutzt) |

`MIGRATION_STRUCTURE.md` ist korrekt als **historisch** markiert — Inhalt aber weiter inkonsistent (viele „🔄 Shim“-Zeilen sind falsch). Nicht als Checkliste verwenden.

### 2.3 Legacy WebUI

- `templates/index_legacy.html`, `index_full.html`, `templates/legacy/` — Dead Code (auch WebUI-Review O5).
- Harmlos, solange nicht verlinkt; Aufräumen = eigener Commit ohne Funktionsänderung.

### 2.4 Pfad-Hardcoding

Units im Repo: Mix aus `/home/pi/pidrive` und `/home/pidrive/pidrive`. `install.sh` patched vieles — für manuelles `systemctl`-Debugging und Pump-Units leicht verwirrend. Pump-Bridge-Pfad liegt **außerhalb** des PiDrive-Trees.

---

## 3. Ordnerstruktur — verbessern?

**Nicht nötig:** große Umbenennung (`core/`, erneutes Shim-Karussell). Die aktuelle Mappe ist verständlich.

**Sinnvolle, kleine Schritte:**

1. **Docs nachziehen**  
   - `ARCHITECTURE.md`: `integration/usb_pump_client.py`, `music_library.py`, `source_autoplay.py`, Audio-Route `usb_gadget`, Services `pidrive_pump*` eintragen.  
   - `RUNTIME_FLOWS.md`: Flow **J** „Webradio → usb_gadget → pump_bridge → ESP MSC“.  
   - Stand-Stempel auf aktuelle `VERSION` setzen.

2. **Shim-Abschneiden**  
   - systemd `pidrive_web` → direkt `web/app.py` (oder `python -m web.app`).  
   - Danach `webui.py` / Root-`avrcp_trigger.py` entfernen.  
   - Radio-Shims `modules/{dab,fm,scanner}.py` erst löschen, wenn `rg` keine Alt-Imports mehr zeigt (aktuell schon fast leer).

3. **Monolithen splitten (nur bei Anfassen)**  
   | Datei | ~LOC | Richtung |
   |-------|------|----------|
   | `cli/cli.py` | 2200+ | Subcommand-Module unter `cli/commands/` |
   | `modules/radio/spectrum.py` | 1600+ | capture / persist / plot trennen |
   | `web/app.py` | 1200+ | weitere Routes in `web/api/` (Muster existiert schon) |
   | `modules/bluetooth/bt_connect.py` | 1100+ | connect vs. recover |

4. **Root-Kern belassen**  
   `main_core.py`, `ipc.py`, `settings.py`, `mpris2.py` im Paket-Root sind ok — `core/`-Umzug hat hohen Risiko-/Nutzen-Nachteil (siehe alter Migrationsplan Phase 3).

5. **Doppel-Repo-Grenze klar halten**  
   ESP-Firmware + `pump_bridge.py` bleiben in `esp32.pidrive`; PiDrive hält Client + Unit + Docs. Kein Copy der Bridge in dieses Repo ohne Deploy-Story.

---

## 4. Sonstige Auffälligkeiten

| Thema | Befund |
|-------|--------|
| **WebUI Hang** | Große `/tmp/pidrive_spectrum.json` blockierten View-Model; Fix in Commit `1d1097f` (slim persist + Size-Guard + Flask `threaded=True`) |
| **Audio-Monitor** | `/api/audio/listen` braucht threaded Flask — sonst hängt Polling |
| **Diagnose RTL** | Live-Probe + `present`/`usb_id` (älterer Fix) — Docs/UI sollten „Stick nicht gefunden“ vs. Fehler trennen |
| **Golden Menu** | `menu_golden.py` groß; bei Menü-Änderungen Lint/Golden mitziehen |
| **Kein Auth auf :8080** | bewusst LAN (WebUI-Review O6) |
| **Tests** | `tests/` + `test_suite.py` parallel — CI-Offline vs. HW-Suite in `tests/README.md` beachten |

---

## 5. Empfohlene Reihenfolge (wenn weitergearbeitet wird)

1. ARCHITECTURE + RUNTIME_FLOWS um ESP/USB-Flow und Stand-Stempel ergänzen (Doc-only).  
2. Tote Units `pidrive.service` / `pidrive_display.service` deprecaten/entfernen.  
3. `pidrive_web` auf `web/app.py` umstellen → Shim `webui.py` streichen.  
4. `cat:0`-Kommentar in AVRCP/RUNTIME_FLOWS auf „Favoriten“ korrigieren.  
5. Legacy-Templates erst löschen, wenn `webui check`/`routes` grün bleiben.

---

## 6. Kurzantwort auf die Ausgangsfragen

| Frage | Antwort |
|-------|---------|
| Welche Teile sind veraltet? | Display-Launcher-Units, Legacy-Templates, Teile der Shim-Doku, „Jetzt läuft“/`cat:0`-Text, ARCHITECTURE ohne PUMP |
| Ordnerstruktur verbessern? | Ja, aber **inkrementell** (Docs, Units, Shim-Abbau, Route-Splits) — kein Big-Bang |
| Flussdiagramm noch gültig? | **Ja für BT/AVRCP/Core/Radio**; **nein als vollständige Systemkarte** ohne ESP-USB-Pfad |
