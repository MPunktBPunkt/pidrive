# PiDrive — Migration Backlog

**Stand v0.11.32 · Arbeitsorientiertes Migrationsdokument**

Dieses Dokument ergänzt `MIGRATION_STRUCTURE.md` (Shim-Status) um die Frage: **Warum ist etwas noch da, wer blockiert den Abbau, was ist der nächste Schritt?**

---

## A. Gesamtstatus

| Bereich | Reifegrad | Importstand | Shims vorhanden | Nächster Schritt |
|---|---|---|---|---|
| `menu/` | ✅ fertig | sauber | Facades bleiben | Root-Facades später entfernen |
| `trigger/` | ✅ fast fertig | sauber seit v0.11.32 | keine aktiven | abgeschlossen erklären |
| `web/` | ✅ fast fertig | sauber | `webui.py` (Entry) | Entry ablösen |
| `cli/` | ✅ fast fertig | sauber | Root-Shims entfernt | keine neuen Root-Pfade |
| `modules/bluetooth/` | ✅ fast fertig | intern sauber | Root-bt_*.py vorhanden | späterer Shim-Abbau |
| `modules/radio/` | ✅ fast fertig | intern sauber | Root-dab/fm/scanner vorhanden | späterer Shim-Abbau |
| `integration/` | 🔄 Übergang | Shims aktiv | 2 Shims (avrcp, mpv_meta) | kanonisieren |
| `core/` (main_core) | ⚠️ noch fragil | bereinigt v0.11.32 | Root-Entry bleibt | erst logisch zerlegen |

---

## B. Root-Shims / Root-Entrypoints — Backlog-Tabelle

### Aktive Root-Entrypoints (systemd)

| Datei | Service | Wer nutzt sie? | Blocker für Abbau | Nächster Schritt | Priorität |
|---|---|---|---|---|---|
| `main_core.py` | `pidrive_core.service` | systemd, alle Importe | Core-Logik zu eng verzahnt, Hochrisiko-Move | Erst logisch zerlegen, `core_callbacks.py` vervollständigen | P1 (nach v0.11.32) |
| `webui.py` | `pidrive_web.service` | systemd | Flask-Startkontext | Service auf `web/app.py` umstellen | P1 (v0.11.32) |
| `avrcp_trigger.py` | `pidrive_avrcp.service` | systemd | Service-Einstieg | `integration/avrcp_trigger.py` kanonisieren, dann Service umstellen | P1 (v0.11.32) |

### Integration-Shims

| Datei | Zielpfad | Was macht sie heute? | Blocker | Nächster Schritt | Priorität |
|---|---|---|---|---|---|
| `integration/avrcp_trigger.py` | `avrcp_trigger.py` (Root) | Shim: `from avrcp_trigger import *` | systemd startet Root | Root zum Shim machen, `integration/` zur Implementierung | P1 |
| `integration/mpv_meta.py` | `mpv_meta.py` (Root) | Shim: `from mpv_meta import *` | Root wird importiert | Root zum Shim machen | P2 |

### Module/Radio Root-Shims (niedrige Priorität)

| Datei | Zielpfad | Wer nutzt sie noch? | Nächster Schritt | Priorität |
|---|---|---|---|---|
| `modules/dab.py` | `modules/radio/dab.py` | evtl. externe Imports | Repo-weit prüfen, dann entfernen | P3 |
| `modules/fm.py` | `modules/radio/fm.py` | evtl. externe Imports | Repo-weit prüfen | P3 |
| `modules/scanner.py` | `modules/radio/scanner.py` | evtl. externe Imports | Repo-weit prüfen | P3 |
| `modules/rtlsdr.py` | `modules/radio/rtlsdr.py` | evtl. externe Imports | Repo-weit prüfen | P3 |
| `modules/spectrum.py` | `modules/radio/spectrum.py` | evtl. externe Imports | Repo-weit prüfen | P3 |

### Module/Bluetooth Root-Shims (niedrige Priorität)

| Datei | Zielpfad | Nächster Schritt | Priorität |
|---|---|---|---|
| `modules/bluetooth.py` | `modules/bluetooth/bluetooth.py` | Repo-weit prüfen | P3 |
| `modules/bt_*.py` (Root) | `modules/bluetooth/bt_*.py` | Repo-weit prüfen | P3 |

---

## C. Migrationsblöcke

### Block 1: `trigger/` abschließen — ✅ erledigt in v0.11.32

**Was war:**
- `main_core.py`: `import td_nav` / `import td_radio` als Root-Altimporte
- `td_nav.py`: `__import__("trigger_dispatcher")` (dynamischer Root-Pfad)

**Was gemacht:**
- Alle Root-`td_*`-Importe → `from trigger import td_*`
- Dynamische `__import__` → `from trigger.trigger_dispatcher import handle_trigger`

**Freigabekriterium erfüllt:** Altimport-Check im Installer grün.

---

### Block 2: IPC-Producer vereinheitlichen — ✅ erledigt in v0.11.32/27

**Was war:** Mehrere Producer schrieben per `open("w")` in `/tmp/pidrive_cmd` und überschrieben damit die Queue.

**Was gemacht:**
- `cli/adapters.py`, `avrcp_trigger.py`, `mpris2.py` → append-Mode
- `integration/mpris2.py`, `web/shared/files.py`, `web/shared.py` → append-Mode
- `modules/bluetooth/bt_connect.py` → `ipc.append_trigger()`
- `main_core.py` BT-Restart → `ipc.append_trigger()`
- `tools/inject_trigger.sh` → `printf >> `

**Freigabekriterium erfüllt:** Kein `open(..., "w")` mehr auf `/tmp/pidrive_cmd`.

---

### Block 3: `integration/` kanonisieren — 🔄 geplant v0.11.32

**Ziel:** `integration/avrcp_trigger.py` und `integration/mpris2.py` werden die echten Implementierungen, die Root-Dateien werden Shims.

**Dateien:**
- `integration/avrcp_trigger.py`: Shim → Implementierung (Root-`avrcp_trigger.py` wird Shim)
- `integration/mpris2.py`: bereits 327 Zeilen, weitgehend echt
- `integration/mpv_meta.py`: Shim → Implementierung

**Blocker:** `pidrive_avrcp.service` startet noch Root-`avrcp_trigger.py`.

**Nächste Schritte:**
1. Inhalt von Root-`avrcp_trigger.py` nach `integration/avrcp_trigger.py` verschieben
2. Root-`avrcp_trigger.py` → `from integration.avrcp_trigger import *; main()` (Shim)
3. `pidrive_avrcp.service` ExecStart auf `integration/avrcp_trigger.py` umstellen
4. Smoke-Test prüft `integration.avrcp_trigger`

**Freigabekriterium:** AVRCP-Events laufen nach Umstellung durch, Service stabil.

---

### Block 4: Web-Entry ablösen — 🔄 geplant v0.11.32

**Ziel:** `webui.py` wird reiner Shim, `pidrive_web.service` startet `web/app.py` direkt.

**Blocker:** Flask-Startkontext / `if __name__ == "__main__"` muss in `web/app.py` korrekt sein.

**Nächster Schritt:**
1. Prüfen: `python3 -m web.app` oder `python3 web/app.py` direkt startbar?
2. `pidrive_web.service` ExecStart anpassen
3. `webui.py` → `from web.app import app; app.run(...)` (Shim)

---

### Block 5: `main_core.py` logisch zerlegen — 📅 geplant v0.11.32+

**Warum noch nicht:**
- 620 Zeilen, trägt zu viele Verantwortungen
- Hochrisiko: Main-Loop, Trigger-Polling, BT, Audio, Status, Resume
- systemd startet direkt diese Datei

**Was sinnvoll wäre:**
- `core_callbacks.py` vervollständigen oder stilllegen
- Startup-Sequenz (`startup_tasks`) auslagern
- BT-Disconnect-Helpers auslagern

**Freigabekriterium:** Core läuft 30s+ stabil, kein Traceback, `pidrivectl status` online.

---

### Block 6: Systemd Core-Entrypoint modernisieren — 📅 geplant v0.11.32+

**Voraussetzung:** Block 5 (Core-Zerlegung) muss stabilen neuen Entry-Pfad liefern.

Erst dann: `pidrive_core.service` ExecStart auf neuen Pfad umstellen.

---

### Block 7: Root-Shim-Abbau (Module/Radio, Module/Bluetooth) — 📅 später

**Wann:** Nach Blocks 3–5, als gebündelte Abbauwelle.

**Voraussetzung:** Repo-weit kein Nicht-Shim-Code mehr, der auf Root-Shims zeigt.

---

## D. Was darf noch nicht angefasst werden

| Datei / Bereich | Warum liegen lassen |
|---|---|
| `main_core.py` physisch verschieben | Hochrisiko, systemd-Entry, zu viele Abhängigkeiten |
| `ipc.py`, `settings.py`, `log.py` verschieben | Core-Fundament, nicht vor logischer Zerlegung |
| `pidrive_core.service` ExecStart ändern | Erst wenn neuer Core-Entry stabil |
| Root-Shims `modules/bt_*.py` entfernen | Noch keine vollständige Inventur externer Nutzung |
| Root-Shims `modules/dab.py` etc. entfernen | Gleiche Begründung |
| `core_callbacks.py` produktiv nutzen | Halbfertige Extraktion — erst vervollständigen |

---

## E. Freigabekriterien

### `trigger/` gilt als fertig, wenn:
- [ ] Installer Altimport-Check grün (kein bare `import td_*`)
- [ ] Kein `__import__("trigger_dispatcher")` mehr im Code
- [ ] Import-Smoke-Test grün für `trigger.*`-Pfade
- [ ] Navigation, `play_*`, AVRCP-Events funktionieren end-to-end

→ **Erreicht mit v0.11.32** ✅

---

### `integration/` gilt als kanonisiert, wenn:
- [ ] `integration/avrcp_trigger.py` ist die echte Implementierung
- [ ] Root-`avrcp_trigger.py` ist nur noch Entry-Shim
- [ ] `pidrive_avrcp.service` startet stabil über neuen Pfad
- [ ] AVRCP-Monitor und Inject-Tests laufen durch

→ **Ziel: v0.11.32**

---

### `main_core.py` gilt als importseitig sauber, wenn:
- [ ] Keine Altimporte aus `td_*` (Root)
- [ ] Kein `trigger_dispatcher` als Root-Import
- [ ] Runtime-Smoke-Test grün (15s stabil, kein Traceback)

→ **Erreicht mit v0.11.32** ✅

---

### Installer/systemd gilt als modernisiert, wenn:
- [ ] Altimport-Check grün
- [ ] Import-Smoke-Tests prüfen kanonische Namespace-Pfade
- [ ] systemd ExecStart für Web/AVRCP auf neue Pfade umgestellt
- [ ] Runtime-Gate aktiv und schlägt bei Instabilität hart an

→ **Runtime-Gate: erreicht v0.11.32 ✅ · Web/AVRCP-Entry: Ziel v0.11.32**

---

## F. Nächste Releases — Übersicht

| Version | Fokus | Status |
|---|---|---|
| v0.11.32 | `trigger/` abschließen, IPC-Producer, Docs | ✅ |
| v0.11.32 | `integration/` kanonisieren, Web-Entry ablösen | 🔄 geplant |
| v0.11.32+ | `main_core.py` logisch zerlegen | 📅 nach Feldtest |
| v0.11.32+ | systemd Core-Entry modernisieren | 📅 später |
| tbd | Root-Shim-Abbau (Module/BT/Radio) | 📅 gebündelt |

---

*Weiterführend: `MIGRATION_STRUCTURE.md` (Shim-Status-Tabellen), `DEVELOPER_GUIDE.md` (Kanonische Pfade), `ARCHITECTURE.md` (Gesamtstruktur)*
