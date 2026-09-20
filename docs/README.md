# PiDrive — Dokumentationsindex

**Stand:** v0.11.143 · 2026-09-19

Zentraler Einstieg für alle Projekt-Dokumente. Neue Dokumente werden **hier** eingetragen —
nicht im Repo-Wurzelverzeichnis (Ausnahme: [`../README.md`](../README.md)).

---

## Dokumente

| Dokument | Zweck | Zielgruppe | Stand |
|----------|-------|------------|-------|
| [FEATURES.md](FEATURES.md) | Funktions-Inventar mit CLI-Prüfungen (M0/W0) | Entwickler, QA | v0.11.143 |
| [KontextPiDrive.md](KontextPiDrive.md) | Entscheidungsverlauf, Changelog, Funktionsstatus | Entwickler, Planung | v0.11.143 |
| [architektur/ARCHITECTURE.md](architektur/ARCHITECTURE.md) | Struktur, IPC, Services, CLI-Kurzreferenz | Entwickler | v0.11.146 |
| [architektur/RUNTIME_FLOWS.md](architektur/RUNTIME_FLOWS.md) | Laufzeitpfade, Menü→Display, ESP/USB | Entwickler | v0.11.146 |
| [architektur/ZUSTANDSMASCHINE.md](architektur/ZUSTANDSMASCHINE.md) | Quellenwechsel, `play_gen`, Transitionen | Entwickler | v0.11.143 |
| [architektur/DEVELOPER_GUIDE.md](architektur/DEVELOPER_GUIDE.md) | Wo liegt welcher Code; OTA / source CLI | Entwickler | v0.11.146 |
| [betrieb/TROUBLESHOOTING.md](betrieb/TROUBLESHOOTING.md) | Fehlerbehebung im Betrieb | Betrieb im Fahrzeug | v0.11.132 |
| [betrieb/SPECTRUM-CLI.md](betrieb/SPECTRUM-CLI.md) | `pidrivectl spectrum scan/peek/last` | Betrieb, Entwickler | 2026-09-19 |
| [betrieb/UKW-GAIN-SCAN-2026-09-19.md](betrieb/UKW-GAIN-SCAN-2026-09-19.md) | UKW Gain/PPM-Messung → Defaults fm_gain/ppm | Betrieb, RF | 2026-09-19 |
| [betrieb/WEBUI-REVIEW-2026-09-18.md](betrieb/WEBUI-REVIEW-2026-09-18.md) | WebUI-Code-Review: Funde R1–R13 + Fixes | Entwickler, QA | 2026-09-18 |
| [betrieb/CODE-REVIEW-2026-09-20.md](betrieb/CODE-REVIEW-2026-09-20.md) | Struktur/Legacy/Flows: was veraltet, Ordner, Diagramm-Gültigkeit | Entwickler | 2026-09-20 |
| [betrieb/BOOT-SPEED.md](betrieb/BOOT-SPEED.md) | Boot-Zeiten: networkd-wait-online, wifi-recover, Core | Betrieb, Entwickler | 2026-09-20 |
| [betrieb/USB-MSC-STREAM-LISTING-2026-09-18.md](betrieb/USB-MSC-STREAM-LISTING-2026-09-18.md) | Lab: Stick-Listing leer während Live-Stream | Betrieb, ESP/USB | 2026-09-18 |
| [betrieb/BluetoothError.md](betrieb/BluetoothError.md) | A2DP-/Bluetooth-Fehleranalyse | Betrieb, Entwickler | — |
| [fahrzeug/iDriveBt.md](fahrzeug/iDriveBt.md) | BT/AVRCP/MPRIS2-Referenz fürs BMW-iDrive | Betrieb im Fahrzeug | — |
| [fahrzeug/BMW-BT-FELDTEST-2026-09-16.md](fahrzeug/BMW-BT-FELDTEST-2026-09-16.md) | Erster BT-/iDrive-Feldtest | Betrieb, QA | 2026-09-16 |
| [fahrzeug/BMW-ERSTER-TEST-2026-09-16.md](fahrzeug/BMW-ERSTER-TEST-2026-09-16.md) | Erster erfolgreicher Connect BMW 38304 | Abnahme / Entwickler | 2026-09-16 |
| [fahrzeug/BMW-AVRCP-PROBE.md](fahrzeug/BMW-AVRCP-PROBE.md) | AVRCP-Browsing-Probe | Entwickler | 2026-09-16 |
| [planung/IDEE-USB-MSC-MENUE.md](planung/IDEE-USB-MSC-MENUE.md) | Idee — USB-MSC-Menü / on-the-fly-MP3 | Planung | 2026-09-17 |
| [planung/KONZEPT-USB-MSC.md](planung/KONZEPT-USB-MSC.md) | Konzept — Architektur USB-MSC | Planung | 2026-09-17 |
| [planung/PFAD-ESP32-PIDRIVE.md](planung/PFAD-ESP32-PIDRIVE.md) | Pfad → esp32.pidrive / PUMP | Planung | 2026-09-18 |
| [../assets/usb-msc-covers/README.md](../assets/usb-msc-covers/README.md) | USB-MSC Cover-Spec | Planung / Design | 2026-09-17 |
| [auftraege/README.md](auftraege/README.md) | Aktive Arbeitsaufträge (aktuell leer) | Entwickler | 2026-09-19 |
| [referenz/WELLE-CLI.md](referenz/WELLE-CLI.md) | welle-cli Optionen, HTTP, Kanäle | Entwickler | 2026-04-21 |
| [ABNAHMEN.md](ABNAHMEN.md) | Abnahmeprotokolle / HW-Messungen | Entwickler, QA | 2026-09-15 |
| [menue/MENU-ERGONOMIE.md](menue/MENU-ERGONOMIE.md) | Skip-Only-Tastendrücke | Entwickler | v0.11.127 |
| [../tests/idrive/README.md](../tests/idrive/README.md) | iDrive-Event-Skripte (M6) | Entwickler, QA | v0.11.127 |
| [../tests/README.md](../tests/README.md) | Testübersicht Offline-CI vs HW-Suite | Entwickler, QA | 2026-09-19 |

> Index-Regel: Stempel älter als zehn Patch-Versionen hinter `VERSION` → im Index mit ⚠ markieren.

### Archiv (historisch, nicht mehr gepflegt)

| Dokument | Hinweis |
|----------|---------|
| Dokument | Hinweis |
|----------|---------|
| [archiv/auftraege/AUFTRAG-BLUETOOTH-FUNDAMENT.md](archiv/auftraege/AUFTRAG-BLUETOOTH-FUNDAMENT.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-DAB-AUDIOWEG.md](archiv/auftraege/AUFTRAG-DAB-AUDIOWEG.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-DISPLAY-RUECKMELDUNG.md](archiv/auftraege/AUFTRAG-DISPLAY-RUECKMELDUNG.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-FUNKPFAD.md](archiv/auftraege/AUFTRAG-FUNKPFAD.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-MPRIS2-STABILITAET.md](archiv/auftraege/AUFTRAG-MPRIS2-STABILITAET.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md](archiv/auftraege/AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-SPEKTRUM-UND-AVRCP.md](archiv/auftraege/AUFTRAG-SPEKTRUM-UND-AVRCP.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md](archiv/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md) | Erledigter Auftrag |
| [archiv/auftraege/AUFTRAG-WEBUI-SANIERUNG.md](archiv/auftraege/AUFTRAG-WEBUI-SANIERUNG.md) | Erledigter Auftrag |
| [archiv/MIGRATION_BACKLOG.md](archiv/MIGRATION_BACKLOG.md) | Migration-Backlog |
| [archiv/MIGRATION_STRUCTURE.md](archiv/MIGRATION_STRUCTURE.md) | Migration-Struktur |

### Geplant (noch nicht vorhanden)

| Dokument | Arbeitspaket |
|----------|--------------|
| `fahrzeug/BMW-DISPLAY-PROBE.md` | G2 — Display-Pfad im Fahrzeug |
| `fahrzeug/BMW-USB-MSC-PROBE.md` | Messung zur Idee USB-MSC-Menü |
| `planung/UMBAU-USB-MSC.md` | PiDrive-Arbeitspakete U0–U8 |

---

## Pfad-Mapping (alt → neu)

| Alter Pfad | Neuer Pfad |
|------------|------------|
| `docs/auftraege/AUFTRAG-*.md` | `docs/archiv/auftraege/AUFTRAG-*.md` |
| `ARCHITECTURE.md` (Wurzel) | `docs/architektur/ARCHITECTURE.md` |
| `TROUBLESHOOTING.md` | `docs/betrieb/TROUBLESHOOTING.md` |
| `MIGRATION_*.md` | `docs/archiv/MIGRATION_*.md` |

---

## Konventionen

### Versionsstempel

Jedes gepflegte Dokument beginnt mit `**Stand:** vX.Y.Z · <Datum>`. Wer ein Verhalten
ändert, zieht den Stempel im betroffenen Dokument nach.

### Neue Dokumente

- Unter `docs/<kategorie>/` anlegen — nie ins Repo-Wurzelverzeichnis.
- Im selben Commit in dieser Index-Datei eintragen (sonst schlägt `tools/check_docs.sh` fehl).

### Link-Prüfung / Offline-CI

```bash
tools/check_docs.sh
bash tools/ci_offline.sh
```

HW-Suite `pidrivectl test all` bleibt am Raspberry Pi (RTL/BT/Audio) und enthält
WebUI-Live-Smoke (`tools/webui_live_smoke.py`, Diagnose-Tab, `pidrivectl webui smoke`).
