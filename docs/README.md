# PiDrive — Dokumentationsindex

**Stand:** v0.11.128 · 2026-09-15

Zentraler Einstieg für alle Projekt-Dokumente. Neue Dokumente werden **hier** eingetragen —
nicht im Repo-Wurzelverzeichnis (Ausnahme: [`../README.md`](../README.md)).

---

## Dokumente

| Dokument | Zweck | Zielgruppe | Stand |
|----------|-------|------------|-------|
| [FEATURES.md](FEATURES.md) | Funktions-Inventar mit CLI-Prüfungen (M0/W0) | Entwickler, QA | v0.11.128 |
| [KontextPiDrive.md](KontextPiDrive.md) | Entscheidungsverlauf, Changelog, Funktionsstatus | Entwickler, Planung | v0.11.128 |
| [architektur/ARCHITECTURE.md](architektur/ARCHITECTURE.md) | Struktur, IPC, Services, CLI-Kurzreferenz | Entwickler | v0.11.128 |
| [architektur/RUNTIME_FLOWS.md](architektur/RUNTIME_FLOWS.md) | Laufzeitpfade, Menü→Display | Entwickler | v0.11.127 |
| [architektur/ZUSTANDSMASCHINE.md](architektur/ZUSTANDSMASCHINE.md) | Quellenwechsel, Transitionen, Sperrschichten — Ist-Zustand und Lücken Z1–Z10 | Entwickler | v0.11.127 |
| [architektur/DEVELOPER_GUIDE.md](architektur/DEVELOPER_GUIDE.md) | Wo liegt welcher Code | Entwickler | v0.11.128 |
| [betrieb/TROUBLESHOOTING.md](betrieb/TROUBLESHOOTING.md) | Fehlerbehebung im Betrieb | Betrieb im Fahrzeug | v0.11.122 |
| [betrieb/BluetoothError.md](betrieb/BluetoothError.md) | A2DP-/Bluetooth-Fehleranalyse | Betrieb, Entwickler | — |
| [fahrzeug/iDriveBt.md](fahrzeug/iDriveBt.md) | BT/AVRCP/MPRIS2-Referenz fürs BMW-iDrive | Betrieb im Fahrzeug | — |
| [auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) | Arbeitsauftrag Menü-Reifung & Gateway-Vorbereitung | Entwickler | 2026-09-15 |
| [auftraege/AUFTRAG-WEBUI-SANIERUNG.md](auftraege/AUFTRAG-WEBUI-SANIERUNG.md) | Arbeitsauftrag WebUI-Statuskette, Scanner, FastScan | Entwickler | 2026-09-15 |
| [ABNAHMEN.md](ABNAHMEN.md) | Abnahmeprotokolle / HW-Messungen (W0/DoD) | Entwickler, QA | 2026-09-15 |
| [menue/MENU-ERGONOMIE.md](menue/MENU-ERGONOMIE.md) | Skip-Only-Tastendrücke (Baseline vor M4) | Entwickler | v0.11.127 |
| [../tests/idrive/README.md](../tests/idrive/README.md) | iDrive-Event-Skripte (M6) | Entwickler, QA | v0.11.127 |
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
