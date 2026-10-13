# Lab Lock nach ESP-Restart · 2026-10-05

**ESP:** `.88` · **Artefakt:** `lab88-lock-after-rst-1022/`  
**Anlass:** GPT-Kritik / Abend-Gate (Meta nach RST)

## Variante A — Sender bereits gesiegelt, dann Soft-RST

Bridge `--msc-lock` siegelt Rock/Bayern/BOB → `POST /api/restart`.

| | Ergebnis |
|--|----------|
| vor RST | Sender-Slots |
| nach RST | Sender bleibt (`fromNvs=true`, Inhalt Rock) |
| Abend-Gate | **PASS** |
| Feld-Morgen-Risiko | **nein** (NVS hatte Sender) |

## Variante C — kurzes Meta-Fenster, Bridge rettet

Kurz nach Boot Meta gesehen (PD0059), innerhalb ~10–15 s Bridge auf Rock (PD0060, `menuRev=8101`).

→ Frischer Bridge-Connect **kann** Meta→Sender retten, wenn Seal = Root-Presets.

## Variante D — Meta-Erstsiegel-Mechanismus (Feldmorgen stark erklärt)

1. Erstes `MSC_MAP_FROZEN` = **Favoriten/Quellen/Stop** (Pi-UI `path_ids=settings`)
2. Root-Menü will Rock → `frozen_reject want=[Rock…] have=[Favoriten…]`
3. ESP soft-RST → NVS lädt wieder **Meta**
4. Bridge bleibt frozen auf Meta → **kein** Rock-Rescue in derselben Instanz

| Check | |
|-------|--|
| Erstes Siegel Meta | **ja** |
| Rock abgewiesen | **ja** (reject n≥37) |
| Nach RST weiter Meta | **ja** |
| Abend-Gate | **FAIL** |
| Mechanismus belegt | **ja** |
| Feldmorgen kausal/direkt bewiesen | **nein** (erstes Feld-`FROZEN` nicht in Artefakt) |

Reject-Beispiel:
`frozen_reject want=[Rock Antenne,Rock Antenne Bayern,Radio BOB!,Menue] have=[Favoriten,Quellen,Stop,Mehr... (+3)]`

Erklärt den Morgen-AV-Zustand (`feld-av-0750` Meta + Reject) **sehr stark**; ersetzt nicht den fehlenden Erstsiegel-Log aus dem Feld.

## Abend-Maßnahmen (verbindlich)

1. **Vor AV:** `slotMap` + **erste** Session-`MSC_MAP_FROZEN` = Rock/Bayern/BOB (Zeile archivieren).  
2. Wenn Meta gesiegelt: **kein AV**. Recovery = **frischer Bridge-Prozess** + Root-Presets oder Unplug — **nicht** Soft-RST, **nicht** Same-Process-Reconnect.  
3. Nach Gate: AV = Baustelle B (Fenster/Ohr), Lock ist dann nicht mehr die Frage.  
4. Kein Lock-Code-Umbau vor Abend-Messung (Freeze).

## Ein Satz

**Nicht der Reset ist der Fehler, sondern ein falsches erstes Siegel (Meta) — NVS + Lock halten es; Soft-RST und Same-Process-Reconnect heilen das nicht.**
