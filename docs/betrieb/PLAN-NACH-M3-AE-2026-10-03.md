# Plan nach Auto-M3 — A_then_E (2026-10-03)

**Basis:** [`artifacts-2026-10-03-m3/AUTO-M3-FELD-2026-10-03.md`](artifacts-2026-10-03-m3/AUTO-M3-FELD-2026-10-03.md)  
**Befund:** NBT Evo · L3 8 MiB · ~8 min Wiedergabe mit UI-Balken · **ΔreadCount=0** nach initialem Sweep → **A_then_E**.

---

## 1. Was damit entschieden ist

| Entscheidung | Status |
|--------------|--------|
| Fortlaufende MSC-Reads als Live-Pfad (Ebene 3/4) unter statischer L3-Datei | **nicht gestützt** |
| Plateau-/Cache-Gate als einzige Erklärung | weiterhin unnötig; Volumen skaliert beim Sweep, Play cached |
| Sofort Ring / PSRAM / BT-Hybrid bauen | **nein** |

---

## 2. Was als Nächstes kommt (Priorität)

### P0 — M3seq: kurze Dateien + Titelwechsel (Feld, eigene Session)

**Frage:** Erzwingt ein HU-Titelwechsel *nach* abgeschlossenem Prefetch neue, slot-spezifische Reads — oder bleibt alles im Cache?

**Setup (kurz):**
- FW weiter `0.4.42` L3 **oder** Lab-Env mit 3× **sehr kurzen** Slots (z. B. 64–128 KiB), eindeutig benannt.  
- Bridge `--no-audio`, Stream off.  
- Protokoll: Mount → 30 s Idle → Select A (20 s) → Select B (20 s) → Select C (20 s); LED + Zeiten.  
- Einmal **ohne** OTG, einmal **mit** Soft-Remount *zwischen* Selects (separat markiert).

**Erfolgskriterien:**
- Gültige Session (Export, ov erklärt, Serial stabil im Fenster).  
- Klassifikation: Reads nur Prefetch (**E** bei Select) vs. Select-triggered (**B**/schwach) vs. cursor-nah (**C** — unwahrscheinlich).

**Nicht mischen** mit Live-Overlay oder langem 8 MiB-Play.

### P1 — Remount als Produktoption (Design only)

Nur skizzieren, **nicht** implementieren bevor P0 negativ klar ist:
- Bei Senderwechsel: Soft-Remount / Serial-Bump → HU neu listen + Prefetch.  
- UX-Kosten (Unterbrechung, Delay) vs. Nutzen (frische Bytes).

### P2 — Lab: kurze-Slot-Geometrie

Optional vor nächstem Feldtermin:
- Env oder Flag für 3 kurze Messdateien mit PDMK dicht (nicht 30 s).  
- Lab-Host-Timeline: Idle vs. „Select“-Nudge analog.

### Später / eingefroren

- Ringbuffer / PSRAM / Pacing  
- BT-Hybrid  
- Armed/Live-Pass (braucht C/D)  
- L4 50 MiB  
- Mehrordner-Hierarchie (Nice-to-have nach P0)

---

## 3. Betriebsregeln für den nächsten Feldtermin

1. Vorher: `.89` = gewünschte FW; Bridge `--no-audio` für statische/seq Passes; `ensure_pump_bridge` nicht unbemerkt auf Audio zurücksetzen.  
2. Nach OTG: WLAN-Reconnect abwarten (RST falls nötig) **bevor** Messfenster zählt.  
3. Overflow nach Plug → Fenster erst ab Bridge-up bilanzieren.  
4. Jeder Versuch: neues Artefaktverzeichnis, Operator-Zeiten, A–E + Evidenzebene.

---

## 4. Ein-Satz-Zielbild

Zuerst klären, ob **Titelwechsel** überhaupt MSC weckt; wenn nein, ist Remount (oder ein anderer Host-Stimulus) die Produktfrage — nicht ein größerer Ring.
