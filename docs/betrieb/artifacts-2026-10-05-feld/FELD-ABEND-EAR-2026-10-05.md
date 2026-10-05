# Feld Abend EAR — 2026-10-05

**Vorlage:** Lab Lock-RST + konsolidierte Mistral/GPT-Kritik. C′ **nicht** wiederholen.

## 0. Vor dem Start
- Bridge `.105` → `.89` mit `--msc-lock`
- Seed **aus**
- Traces leer: `msc_reads` / `msc_lock` / diag
- **Artifact-Ordner** anlegen; Bridge-Journal von Session-Start mitschneiden

## 1. Gate (Pflicht, sonst kein AV)
```
curl -sS http://192.168.178.89/api/status   # slotMap names
curl -sS http://192.168.178.89/api/menu
journalctl -u pidrive_pump_bridge … | grep MSC_MAP_FROZEN
```
**PASS Gate:**  
- `slotMap` = Rock Antenne / Rock Antenne Bayern / Radio BOB! (+ Menue)  
- **und** Bridge `MSC_MAP_FROZEN [Rock Antenne,Rock Antenne Bayern,Radio BOB!,Menue]`  

**Pflicht-Artefakt:** die **erste** `MSC_MAP_FROZEN`-Zeile dieser Session speichern  
(schließt die Beweislücke „erstes Feld-Seal nicht geloggt“).

**FAIL Gate:** Favoriten/Quellen/Stop oder Zurueck/… → **kein AV**.

### Gate FAIL — Recovery
1. Soft-RST allein reicht **nicht** (Meta-first + NVS).  
2. **Reconnect derselben Bridge-Instanz ist kein Recovery** (Snapshot-Resend).  
3. Bridge **Prozess stoppen** → Root-Menü/Presets sicher → **Bridge neu starten** → neues `MSC_MAP_FROZEN` Rock abwarten.  
4. Oder USB Unplug/Replug (Session-End → sealing).  
5. Neu gate (inkl. erstes FROZEN loggen); erst dann AV.

## 2. AV (nur nach Gate PASS = Baustelle B)
- Operator: Rock/Bayern/BOB auf HU
- Correlate + Ohr gleichzeitig — **dicht**:
  ```
  python3 tools/feld_av_correlate.py --esp http://192.168.178.89 \
    --watch-s 90 --interval 0.5 --dense --out ARTIFACT/
  ```
- Log: `active`, `cursorArmed`, `liveBytes`, `underruns`, `absBase..absEnd`, `hostAbs`, `ahead`

## 3. PASS / FAIL
- **PASS:** Gate + `stream.active` + `liveBytes` steigt + hörbar  
- **FAIL Meta/Gate:** nie Sender-Slots → Lock/State (A), nicht Fenster  
- **FAIL Fenster:** Gate+active, Ohr still / `hostAbs` außerhalb → Cursor/Timing (B)

## 4. Verboten
- Formulierung „alle AV-Probleme erklärt“ / „Feldmorgen kausal bewiesen“  
- C′; Detect-Umbau; Lock-Code ändern ohne Messung  
- AV-Interpretieren bei Gate FAIL
