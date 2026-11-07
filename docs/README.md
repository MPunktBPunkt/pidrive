# PiDrive — Dokumentationsindex

**Stand:** 2026-11-07 · HU-Beschreibung (Zwei-Plane) + Facts; MSC FULLMENU + Größenleiter offen · Doku-Aufräumen (Archiv betrieb/planung/fahrzeug)

Zentraler Einstieg für alle Projekt-Dokumente. Neue Dokumente werden **hier** eingetragen —
nicht im Repo-Wurzelverzeichnis (Ausnahme: [`../README.md`](../README.md)).

**Aktueller Stand:** **[`betrieb/AKTUELL.md`](betrieb/AKTUELL.md)** → Ampel [`betrieb/MSC-AKTUELL.md`](betrieb/MSC-AKTUELL.md) · Maßnahmen [`planung/MASSNAHMEN-MSC-FULLMENU.md`](planung/MASSNAHMEN-MSC-FULLMENU.md) · Facts [`fahrzeug/HU-Technical-Facts.md`](fahrzeug/HU-Technical-Facts.md) · Modell [`fahrzeug/HU-BESCHREIBUNG.md`](fahrzeug/HU-BESCHREIBUNG.md). Historisches unter `docs/archiv/`.  
Sibling-Repos: `esphub/esp32.pidrive` (Gadget-FW) · `hu-probe` (Messsonde) · `usb-analyzer` · `technology-audit` (Evidence).
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
| [architektur/SCANNER-PMR.md](architektur/SCANNER-PMR.md) | Scanner, Spektrum, PMR-Dauerdetektor (Architektur) | Entwickler | v0.11.155 |
| [betrieb/TROUBLESHOOTING.md](betrieb/TROUBLESHOOTING.md) | Fehlerbehebung im Betrieb | Betrieb im Fahrzeug | v0.11.132 |
| [betrieb/SPECTRUM-CLI.md](betrieb/SPECTRUM-CLI.md) | `pidrivectl spectrum scan/peek/last` | Betrieb, Entwickler | 2026-09-19 |
| [betrieb/PMR-MONITOR.md](betrieb/PMR-MONITOR.md) | `pidrivectl scanner monitor …` + USB-Recovery | Betrieb, Entwickler | 2026-09-21 |
| [archiv/betrieb/UKW-GAIN-SCAN-2026-09-19.md](archiv/betrieb/UKW-GAIN-SCAN-2026-09-19.md) | UKW Gain/PPM-Messung → Defaults fm_gain/ppm | Betrieb, RF | 2026-09-19 |
| [betrieb/antennen-vergleich-2026-09-22/](betrieb/antennen-vergleich-2026-09-22/README.md) | Antennen A–D (DVB-T, Teleskop, Bingfu, RTL-Stock): UKW/DAB/Airband/PMR | Betrieb, RF | 2026-09-22 |
| [archiv/betrieb/WEBUI-REVIEW-2026-09-18.md](archiv/betrieb/WEBUI-REVIEW-2026-09-18.md) | WebUI-Review (Archiv) | Entwickler | Archiv |
| [archiv/betrieb/CODE-REVIEW-2026-09-20.md](archiv/betrieb/CODE-REVIEW-2026-09-20.md) | Code-Review (Archiv) | Entwickler | Archiv |
| [betrieb/BOOT-SPEED.md](betrieb/BOOT-SPEED.md) | Boot-Zeiten: networkd-wait-online, wifi-recover, Core | Betrieb, Entwickler | 2026-09-20 |
| [betrieb/BOOT-USB-DEFER.md](betrieb/BOOT-USB-DEFER.md) | USB/BT verzögert freigeben + Hotplug-Release | Betrieb, Entwickler | 2026-09-24 |
| [betrieb/FRISCH-INSTALL.md](betrieb/FRISCH-INSTALL.md) | Soft-Smoke vs HW; Proxmox Bookworm-CT | Betrieb, Entwickler | 2026-09-24 |
| [betrieb/LAB-MENU-WLAN.md](betrieb/LAB-MENU-WLAN.md) | Dev: Pi `/menu` + ESP SoftAP/STA ohne Auto | Betrieb, Entwickler | 2026-09-25 |
| [archiv/betrieb/USB-MSC-STREAM-LISTING-2026-09-18.md](archiv/betrieb/USB-MSC-STREAM-LISTING-2026-09-18.md) | Lab: Stick-Listing leer während Live-Stream | Betrieb, ESP/USB | 2026-09-18 |
| [betrieb/MSC-AKTUELL.md](betrieb/MSC-AKTUELL.md) | **MSC Einstieg:** Stand, Lesereihenfolge, Ampel | Entwickler, nächste KI | 2026-11-06 |
| [archiv/archiv/betrieb/2026-11-02-esp-usb-analyzer-crosscheck.md](archiv/archiv/betrieb/2026-11-02-esp-usb-analyzer-crosscheck.md) | Verweis Lab USB-Gadget Cross-Check | Entwickler | 2026-11-02 |
| [planung/MASSNAHMEN-MSC-FULLMENU.md](planung/MASSNAHMEN-MSC-FULLMENU.md) | Identity/Detach → FULLMENU / D+-Cycle | Entwickler | 2026-10-23 |
| [archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md](archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) | Archiv: Maßnahmen 22.10. | Entwickler | Archiv |
| [fahrzeug/HU-PARAMETER-MATRIX.md](fahrzeug/HU-PARAMETER-MATRIX.md) | HU-Parametermatrix (Head-160, TUR, Vertrag) | Entwickler, Feld | 2026-11-06 |
| [fahrzeug/HU-BESCHREIBUNG.md](fahrzeug/HU-BESCHREIBUNG.md) | HU-Modellbericht: Zwei-Plane, CBW≠Callback, Stall-FACT, G1–G4, GPT-Korrektur | Entwickler, Planung | 2026-11-07 |
| [fahrzeug/HU-Technical-Facts.md](fahrzeug/HU-Technical-Facts.md) | Normative HU-Fakten [B]/[S]/[H]/[?] | Entwickler | 2026-11-07 |
| [archiv/betrieb/PLAN-NACH-M3-AE-2026-10-03.md](archiv/betrieb/PLAN-NACH-M3-AE-2026-10-03.md) | Plan Rev.5 (Archiv) | Entwickler | Archiv |
| [betrieb/artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md](betrieb/artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md) | Übergabe P0/Q3a → P1 Feld | Entwickler, nächste KI | 2026-10-04 |
| [archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md](archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) | USB-MSC Feld-/Lab-Log (Archiv) | Referenz | Archiv |
| [betrieb/BluetoothError.md](betrieb/BluetoothError.md) | A2DP-/Bluetooth-Fehleranalyse | Betrieb, Entwickler | — |
| [archiv/auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md](archiv/auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md) | MSC Host-Read-Nachweis: B7, Geometrie, L-Leiter, Fallbacks | Entwickler, ESP/USB | 2026-10-03 |
| [archiv/auftraege/AUFTRAG-B7-HU-REREAD.md](archiv/auftraege/AUFTRAG-B7-HU-REREAD.md) | B7 Feld: 150 s / Armed-Replug / Ordnerwechsel | Entwickler, Feld | 2026-10-03 |
| [archiv/auftraege/AUFTRAG-ESP-PLAY-DETECTION.md](archiv/auftraege/AUFTRAG-ESP-PLAY-DETECTION.md) | ESP: Menü-State + Live-Stream (Checkliste) | Entwickler, ESP/USB | 2026-09-30 |
| [fahrzeug/iDriveBt.md](fahrzeug/iDriveBt.md) | BT/AVRCP/MPRIS2-Referenz fürs BMW-iDrive | Betrieb im Fahrzeug | — |
| [fahrzeug/README.md](fahrzeug/README.md) | **HU-Lesereihenfolge** (Facts / Beschreibung / Connected) | Entwickler | 2026-11-07 |
| [fahrzeug/FORUM-RESEARCH-AVRCP-COVER-MSC.md](fahrzeug/FORUM-RESEARCH-AVRCP-COVER-MSC.md) | Foren-Auswertung AVRCP/Cover/MSC-Quellen | Entwickler | 2026-11-06 |
| [fahrzeug/CONNECTED-AAIDRIVE-STACK.md](fahrzeug/CONNECTED-AAIDRIVE-STACK.md) | Connected/AAIdrive Stack (Pfad C) | Entwickler | 2026-11-06 |
| [planung/MENUESTRUKTUR-MSC.md](planung/MENUESTRUKTUR-MSC.md) | Finales MSC-Menü-Zielbild (Baum, Cycle, Stall) | Planung | 2026-10-24 |
| [archiv/planung/IDEE-USB-MSC-MENUE.md](archiv/planung/IDEE-USB-MSC-MENUE.md) | Idee USB-MSC (Archiv) | Planung | Archiv |
| [archiv/planung/KONZEPT-USB-MSC.md](archiv/planung/KONZEPT-USB-MSC.md) | Konzept v1 Soft-Paging (Archiv; ersetzt durch MENUESTRUKTUR) | Planung | Archiv |
| [archiv/planung/PFAD-ESP32-PIDRIVE.md](archiv/planung/PFAD-ESP32-PIDRIVE.md) | Pfad → esp32.pidrive / PUMP | Planung | 2026-09-18 |
| [../assets/usb-msc-covers/README.md](../assets/usb-msc-covers/README.md) | USB-MSC Cover-Spec | Planung / Design | 2026-09-17 |
| [auftraege/README.md](auftraege/README.md) | Aktive Arbeitsaufträge | Entwickler | 2026-09-22 |
| [referenz/WELLE-CLI.md](referenz/WELLE-CLI.md) | welle-cli Optionen, HTTP, Kanäle | Entwickler | 2026-04-21 |
| [referenz/rtl2832u Stick](referenz/rtl2832u%20Stick) | Fasizi/RTL2832U+R820T2: HF/DSP/Kalibrierung (Langreferenz) | Entwickler, RF | 2026-09-25 |
| [referenz/FM-AM-RTL-REVIEW-2026-09-25.md](referenz/FM-AM-RTL-REVIEW-2026-09-25.md) | Abgleich Stick-Doku ↔ PiDrive FM/AM: umgesetzt / verbessern / zu aufwendig | Entwickler, RF | 2026-09-25 |
| [referenz/ESP32-S3-BOARD.md](referenz/ESP32-S3-BOARD.md) | DevKitC-1 **N8R2**: 8 MiB Flash, 2 MiB PSRAM (**Build an** ab 0.4.54) | Entwickler, ESP/USB | 2026-10-22 |
| [ABNAHMEN.md](ABNAHMEN.md) | Abnahmeprotokolle / HW-Messungen | Entwickler, QA | 2026-09-15 |
| [menue/MENU-ERGONOMIE.md](menue/MENU-ERGONOMIE.md) | Skip-Only-Tastendrücke | Entwickler | v0.11.127 |
| [../tests/idrive/README.md](../tests/idrive/README.md) | iDrive-Event-Skripte (M6) | Entwickler, QA | v0.11.127 |
| [../tests/README.md](../tests/README.md) | Testübersicht Offline-CI vs HW-Suite | Entwickler, QA | 2026-09-19 |

> Index-Regel: Stempel älter als zehn Patch-Versionen hinter `VERSION` → im Index mit ⚠ markieren.

### Archiv (historisch, nicht mehr gepflegt)

| Dokument | Hinweis |
|----------|---------|
| [archiv/analysen/README.md](archiv/analysen/README.md) | Rohanalysen (GPT-Dumps) |
| [archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt](archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt) | GPT Play-Detection (Roh) |
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
| [archiv/planung/](archiv/planung/) | IDEE/KONZEPT MSC v1, Maßnahmen 22.10. |
| [archiv/betrieb/](archiv/betrieb/) | FELDTEST lang, Reviews, Plan-nach-M3 |
| [archiv/fahrzeug/](archiv/fahrzeug/) | BT-Feldtests 16.09., AVRCP-Probe |

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
