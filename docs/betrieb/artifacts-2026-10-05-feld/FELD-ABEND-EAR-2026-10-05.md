# Feld Abend EAR — 2026-10-05

**Vorlage aus Lab + GPT-Kritik.** C′ **nicht** wiederholen.

## 0. Vor dem Start
- Bridge `.105` → `.89` mit `--msc-lock`
- Seed **aus**
- Traces leer: `msc_reads` / `msc_lock` / diag

## 1. Gate (Pflicht, sonst kein AV)
```
curl -sS http://192.168.178.89/api/status | … slotMap names
curl -sS http://192.168.178.89/api/menu
journalctl … | grep MSC_MAP_FROZEN
```
**PASS Gate:** slotMap = Rock Antenne / Rock Antenne Bayern / Radio BOB! (+ Menue)  
**FAIL Gate:** Favoriten/Quellen/Stop oder Zurueck/… → **kein AV**, Remount/`Mehr…`/Bridge-Restart, neu gate.

## 2. AV
- Operator wählt Rock/Bayern/BOB auf HU
- Correlate + Ohr gleichzeitig
- Log: `active`, `liveBytes`, `underruns`, `absBase..absEnd`, `hostAbs` (`hostAbs < absEnd`)

## 3. PASS / FAIL
- **PASS:** Gate + `stream.active` + `liveBytes` steigt + hörbar  
- **FAIL Meta:** Gate nie grün → Lock/NVS-State, nicht Fenster  
- **FAIL Fenster:** Gate+active, aber Ohr still / hostAbs außerhalb → Cursor/Timing (nächster Lab-Fokus)

## 4. Verboten
RST nach Seed; C′; Detect-Umbau; Lock-Code ändern ohne Messung.
