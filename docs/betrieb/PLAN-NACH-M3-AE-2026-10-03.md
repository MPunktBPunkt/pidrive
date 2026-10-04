# Plan nach Auto-M3seq — Review-Konsolidierung (Rev.5, 2026-10-04)

**Normativer Gesamtbericht (Trace):** [`GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md)  
**Normativer Gesamtbericht (Review Mistral/Claude/GPT):** [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md)  
**Semantik:** [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md)  
**Feld:** [`auto89-m3seq-2042/`](artifacts-2026-10-03-m3/auto89-m3seq-2042/) · Gegenindiz [`replug-1231-noselect/`](artifacts-2026-10-03-b7/replug-1231-noselect/)  
**Lab-Live:** [`artifacts-2026-10-04-lab/lab88-baseline-0818/`](artifacts-2026-10-04-lab/lab88-baseline-0818/)

---

## 0. Enger Befund (nach Voll-Trace + Review, V)

| Aussage | Status |
|---------|--------|
| Warmes Auto-Next / Trackende → Δrc=0 | ✅ gültig, **kein** Architektur-Negativ |
| Select / Erstabspiel → Voll-Burst (~1 MB/s) | ✅ mehrfach (V) |
| Mount-Scan = Köpfe (+ ggf. volle kleine Datei) | ✅ (V); **Scan-Freeze 512 KiB möglich** |
| Remount → Resume-Vollread ohne Select | ✅ (V) |
| Kaltes Auto-Next liest | 🔜 P1 (Morgenpass = Counter-Indiz, **kein** LBA-Beweis) |
| Payload-Frische | 🔜 Q3a Lab / Q3b Auto |
| MSC-Live als unendliche Overlay-Datei | weiterhin ungestützt |
| MSC-Sequenz (N Chunk-Dateien) | bedingt first-class bis P1×2 |

**Arbeitsmodell:** Eine Datei, ein Voll-Read beim ersten Start pro Mount.

---

## 1. Lab-Kalibrierung — unverändert PASS

A+B + M3seq-Rehearsal: siehe Rev.3/4. Operator: Bridge vor Plug.  
**Neu Pflicht:** Pre-Flight-Warmheit **pro Datei**, maschinenlesbar in EAR.

**Blocker 2026-10-04:** CT `.187` sieht Kernel-`sda`/`sg0`, aber ohne Device-Nodes → Host-Reads/Q3 warten auf `sudo mknod`.

---

## 2. Offene Fragen

| ID | Frage | Nächster Nachweis |
|----|--------|-------------------|
| **Q2c** | Liest kaltes Auto-Next Body-LBAs — wann relativ zum Übergang (±1,5 s)? | P1 Feld ×2 |
| **Q3a** | Liefert der ESP beim Start-Read frische B-Bytes? | P2a Lab |
| **Q3b** | Spielt die HU frische B-Bytes (hörbar)? | Auto, mit Ton |
| **Q1** | Select-Trigger | ✅ erledigt |
| **Q2w** | Warmes Auto-Next | ✅ Δrc=0, warm-konfundiert |
| **L4** | Liest NBT große Datei fortlaufend nach? | P2c Diagnose |

---

## 3. Arbeitsplan

| Prio | Arbeit | Done wenn |
|------|--------|-----------|
| **P0** | Menü-Lock / MSC-Session-Lock | Provokation: Pi-UI-Wechsel → Name/UID/LBA unverändert; Regression reject/defer |
| **P1** | Kalter Auto-Next Feld ×2 | Trace kalt, Timing ±1,5 s, EAR-Preflight, A–E |
| **P2a** | Q3a Lab A/B | Hash-Kette + Marker, B-Bytes belegt |
| **P2b** | BT-Abnahme inkl. Quellwechsel-UX | 4-Punkte-Checkliste |
| **P2c** | L4 große Datei (64 MiB, gültiges Audio) | Read-Muster klassifiziert; **kein** P1-Blocker |
| **P3** | Sequenz-Prototyp | nur nach P1×2 + Q3a grün; dann Ring ≥ 1 Chunk |
| **P4** | Dension-Abgleich / 6NR / AAIdrive-Notiz | kein Sprint |

**Geometrie-Constraint:** Chunks ≥ ~768 KiB **oder** statischer Kopf-Vorlauf (~0,5 MiB). „Nur 32 KiB Kopf-Stale“ verworfen.

**Entscheidungsregel:**

```
P0 PASS → P1×2 (±1,5 s, kalt)
  GRÜN → Q3a
    GRÜN → Sequenz (A), BT Fallback
    ROT  → Payload-Fix, kein Architektur-Abbruch
  NICHT GRÜN → BT-Hybrid (B)
L4 positiv → A′ (Dension-Modus) parallel bewerten
Pfad C nur wenn B-UX scheitert und 6NR aktiv
```

---

## 4. Eingefroren (bis P1×2 grün)

Ring-Vergrößerung, PSRAM-Streaming, Pacing, Remount-Karussell-Impl, Live-Overlay-Optimierung, AAIdrive-Port.

**Ausnahme nach P1×2 + Q3a grün:** einmaliger, begründeter Ring ≥ Chunk-Größe für Sequenz-Prototyp.
