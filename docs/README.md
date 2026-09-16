# PiDrive — Dokumentationsindex

**Stand:** v0.11.132 · 2026-09-15

Zentraler Einstieg für alle Projekt-Dokumente. Neue Dokumente werden **hier** eingetragen —
nicht im Repo-Wurzelverzeichnis (Ausnahme: [`../README.md`](../README.md)).

---

## Dokumente

| Dokument | Zweck | Zielgruppe | Stand |
|----------|-------|------------|-------|
| [FEATURES.md](FEATURES.md) | Funktions-Inventar mit CLI-Prüfungen (M0/W0) | Entwickler, QA | v0.11.132 |
| [KontextPiDrive.md](KontextPiDrive.md) | Entscheidungsverlauf, Changelog, Funktionsstatus | Entwickler, Planung | v0.11.132 |
| [architektur/ARCHITECTURE.md](architektur/ARCHITECTURE.md) | Struktur, IPC, Services, CLI-Kurzreferenz | Entwickler | v0.11.132 |
| [architektur/RUNTIME_FLOWS.md](architektur/RUNTIME_FLOWS.md) | Laufzeitpfade, Menü→Display | Entwickler | v0.11.127 |
| [architektur/ZUSTANDSMASCHINE.md](architektur/ZUSTANDSMASCHINE.md) | Quellenwechsel, Transitionen, Sperrschichten — Ist-Zustand und Lücken Z1–Z10 | Entwickler | v0.11.132 |
| [architektur/DEVELOPER_GUIDE.md](architektur/DEVELOPER_GUIDE.md) | Wo liegt welcher Code; OTA / source CLI | Entwickler | v0.11.132 |
| [betrieb/TROUBLESHOOTING.md](betrieb/TROUBLESHOOTING.md) | Fehlerbehebung im Betrieb | Betrieb im Fahrzeug | v0.11.132 |
| [betrieb/BluetoothError.md](betrieb/BluetoothError.md) | A2DP-/Bluetooth-Fehleranalyse | Betrieb, Entwickler | — |
| [fahrzeug/iDriveBt.md](fahrzeug/iDriveBt.md) | BT/AVRCP/MPRIS2-Referenz fürs BMW-iDrive | Betrieb im Fahrzeug | — |
| [auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) | Arbeitsauftrag Menü-Reifung & Gateway-Vorbereitung | Entwickler | 2026-09-15 |
| [auftraege/AUFTRAG-WEBUI-SANIERUNG.md](auftraege/AUFTRAG-WEBUI-SANIERUNG.md) | Arbeitsauftrag WebUI-Statuskette, Scanner, FastScan | Entwickler | 2026-09-15 |
| [auftraege/AUFTRAG-FUNKPFAD.md](auftraege/AUFTRAG-FUNKPFAD.md) | Funkpfad K1–K5 (Import, Bandbreite, Suchlauf) | Entwickler | 2026-09-15 |
| [auftraege/AUFTRAG-DISPLAY-RUECKMELDUNG.md](auftraege/AUFTRAG-DISPLAY-RUECKMELDUNG.md) | Rückmeldung ans BMW-Display (D1–D3) | Entwickler | 2026-09-15 |
| [auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md](auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md) | Spotify-Semantik + Testkette TK-A…E; §11 N1–N5, §12 WLAN/Version/Menü-IDs | Entwickler | 2026-09-16 |
| [auftraege/AUFTRAG-MPRIS2-STABILITAET.md](auftraege/AUFTRAG-MPRIS2-STABILITAET.md) | **Vorrang** — MPRIS2 SIGABRT, Core-Absturz-Hypothese (M1–M3, M-A…M-F) | Entwickler | 2026-09-16 |
| [auftraege/AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md](auftraege/AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md) | Menüvorrang beendet Blindnavigation (Q-K…Q-N, **zuerst**); FM-Rasterschritte statt modaler Eingabe, behebt D3/FM (Q-G…Q-J); Quellenordner startet letzten Sender (Q-A…Q-E); Suchlauf aufs BMW-Display (Q-F, gesperrt bis M-C) | Entwickler | 2026-09-16 |
| [auftraege/AUFTRAG-BLUETOOTH-FUNDAMENT.md](auftraege/AUFTRAG-BLUETOOTH-FUNDAMENT.md) | **Vorrang vor allem** — Kopplung scheitert am fehlenden Antwort-Agenten, Display am fehlenden Spieler (BT1–BT8, BF-A…BF-F, Stufenabnahme HB0–HB6) | Entwickler | 2026-09-16 |
| [auftraege/AUFTRAG-SPEKTRUM-UND-AVRCP.md](auftraege/AUFTRAG-SPEKTRUM-UND-AVRCP.md) | Spektrumanzeige zurückholen (SA1–SA7, SA-A…SA-F); AVRCP-Tab als Messbühne für die BMW-Rückgaben (AV1–AV8, AV-A…AV-F) | Entwickler | 2026-09-16 |
| [auftraege/AUFTRAG-DAB-AUDIOWEG.md](auftraege/AUFTRAG-DAB-AUDIOWEG.md) | **DAB bleibt im Fahrzeug stumm** — `welle-cli` schreibt direkt auf ALSA/Klinke, A2DP unerreichbar (DA1–DA5, Messreihe DA-M1…DA-M5, DA-A…DA-F, Abnahme HD1–HD6). DA-A vor der Fahrt | Entwickler | 2026-09-16 |
| [referenz/WELLE-CLI.md](referenz/WELLE-CLI.md) | welle.io/`welle-cli` Referenz: Optionen, HTTP-Endpunkte, `mux.json`, Gain-Index-Tabelle, Kanalfrequenzen (Quellcode-Analyse, Stand v0.9.4) | Entwickler | 2026-04-21 |
| [ABNAHMEN.md](ABNAHMEN.md) | Abnahmeprotokolle / HW-Messungen (W0/DoD) | Entwickler, QA | 2026-09-15 |
| [menue/MENU-ERGONOMIE.md](menue/MENU-ERGONOMIE.md) | Skip-Only-Tastendrücke (Baseline vor M4) | Entwickler | v0.11.127 |
| [../tests/idrive/README.md](../tests/idrive/README.md) | iDrive-Event-Skripte (M6) | Entwickler, QA | v0.11.127 |
| [../tests/README.md](../tests/README.md) | Testübersicht Offline-CI vs HW-Suite | Entwickler, QA | 2026-09-16 |
| [archiv/MIGRATION_BACKLOG.md](archiv/MIGRATION_BACKLOG.md) | Historisch — nicht mehr gepflegt | Archiv | v0.11.96 |
| [archiv/MIGRATION_STRUCTURE.md](archiv/MIGRATION_STRUCTURE.md) | Historisch — nicht mehr gepflegt | Archiv | v0.11.96 |

> Index-Regel: Stempel älter als zehn Patch-Versionen hinter `VERSION` → im Index mit ⚠ markieren.

### Geplant (noch nicht vorhanden)

| Dokument | Arbeitspaket |
|----------|--------------|
| `fahrzeug/BMW-AVRCP-PROBE.md` | G1 — BMW-Browsing-Probe |
| `fahrzeug/BMW-DISPLAY-PROBE.md` | G2 — Display-Pfad im Fahrzeug |

---

## Pfad-Mapping (alt → neu)

Für repo-übergreifende Verweise (z. B. `esp32.bt-gateway`):

| Alter Pfad (Repo-Wurzel) | Neuer Pfad |
|--------------------------|------------|
| `ARCHITECTURE.md` | `docs/architektur/ARCHITECTURE.md` |
| `RUNTIME_FLOWS.md` | `docs/architektur/RUNTIME_FLOWS.md` |
| `DEVELOPER_GUIDE.md` | `docs/architektur/DEVELOPER_GUIDE.md` |
| `TROUBLESHOOTING.md` | `docs/betrieb/TROUBLESHOOTING.md` |
| `BluetoothError.md` | `docs/betrieb/BluetoothError.md` |
| `iDriveBt.md` | `docs/fahrzeug/iDriveBt.md` |
| `KontextPiDrive.md` | `docs/KontextPiDrive.md` |
| `MIGRATION_BACKLOG.md` | `docs/archiv/MIGRATION_BACKLOG.md` |
| `MIGRATION_STRUCTURE.md` | `docs/archiv/MIGRATION_STRUCTURE.md` |
| `AUFTRAG-MENUE-UND-GATEWAY.md` | `docs/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md` |

---

## Konventionen

### Versionsstempel

Jedes gepflegte Dokument beginnt mit `**Stand:** vX.Y.Z · <Datum>`. Wer ein Verhalten
ändert, zieht den Stempel im betroffenen Dokument nach. Dokumente mit Stempel älter als
zehn Patch-Versionen gelten als prüfbedürftig und werden im Index markiert.

### Neue Dokumente (verbindlich, D5)

- Immer unter `docs/<kategorie>/` anlegen — nie ins Repo-Wurzelverzeichnis.
  Passt keine Kategorie, wird eine angelegt und hier begründet.
- Dateinamen: `KEBAB-CASE.md`, deutsch, sprechend (z. B. `BMW-AVRCP-PROBE.md`).
  Kein `camelCase`, kein `SCREAMING_SNAKE` mehr für neue Dateien.
- Im selben Commit in dieser Index-Datei eintragen (sonst schlägt `tools/check_docs.sh` fehl).
- Ergebnis-Dokumente (Messungen, Abnahmen) tragen Datum und Version im Kopf und werden
  **nicht** überschrieben, sondern ergänzt; Wiederholungsmessungen als neuer Abschnitt.

### Link-Prüfung

```bash
tools/check_docs.sh
```

Prüft relative Markdown-Links und meldet Dokumente ohne eingehenden Verweis (Waisen).

### Offline-CI (GitHub Actions)

```bash
bash tools/ci_offline.sh
```

Läuft auf jedem Push/PR (`.github/workflows/ci.yml`): Docs-Links, Shell-Syntax,
`compileall`, pytest (Imports, ipc/status, Scanner-BW, source_state, Menü-Verify,
WebUI-Check/Selftest, iDrive-Offline-Skript, Routen-Inventar, VERSION-Sync).

HW-Suite `pidrivectl test all` bleibt am Raspberry Pi (RTL/BT/Audio).
