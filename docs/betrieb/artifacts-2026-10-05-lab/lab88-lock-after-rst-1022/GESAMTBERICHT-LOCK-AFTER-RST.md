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

## Variante D — **Feld-Falle** (bestätigt)

1. Erstes `MSC_MAP_FROZEN` = **Favoriten/Quellen/Stop** (Pi-UI `path_ids=settings`)
2. Root-Menü will Rock → `frozen_reject want=[Rock…] have=[Favoriten…]`
3. ESP soft-RST → NVS lädt wieder **Meta**
4. Bridge bleibt frozen auf Meta → **kein** Rock-Rescue

| Check | |
|-------|--|
| Erstes Siegel Meta | **ja** |
| Rock abgewiesen | **ja** (reject n≥37) |
| Nach RST weiter Meta | **ja** |
| Abend-Gate | **FAIL** |
| **Feld-Falle bestätigt** | **ja** |

Reject-Beispiel:
`frozen_reject want=[Rock Antenne,Rock Antenne Bayern,Radio BOB!,Menue] have=[Favoriten,Quellen,Stop,Mehr... (+3)]`

Das deckt den Morgen-AV-Zustand (`feld-av-0750` Meta + Lock-Konflikt) besser als „nur HU zeigt falsch“.

## Abend-Maßnahmen (verbindlich)

1. **Vor AV:** `slotMap` + Bridge-Log `MSC_MAP_FROZEN` müssen Rock/Bayern/BOB sein.  
2. Wenn Meta gesiegelt: **kein AV**. Bridge stoppen, `/tmp/pidrive_menu.json` auf Root, Bridge neu → neues Seal; oder USB Unplug/Replug (Session-End → sealing).  
3. Soft-RST allein rettet **nicht**, solange Meta eingefroren und in NVS liegt.  
4. Kein Lock-Code-Umbau vor Abend-Messung (Freeze).

## Ein Satz

**Das Risiko ist nicht RST an sich, sondern: erstes Siegel = Meta → Lock + NVS halten Meta über RST.**
