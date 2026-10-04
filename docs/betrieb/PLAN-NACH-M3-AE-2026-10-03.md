# Plan nach Auto-M3seq — Review-Konsolidierung (Rev.5, 2026-10-04)

**Einstieg:** [`MSC-AKTUELL.md`](MSC-AKTUELL.md)  
**Übergabe P0/Q3a (aktuell):** [`GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md)  
**Trace-Korrektur:** [`GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md)  
**Review Mistral/Claude/GPT:** [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md)  
**Semantik:** [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md)  
**Feld:** [`auto89-m3seq-2042/`](artifacts-2026-10-03-m3/auto89-m3seq-2042/) · Gegenindiz [`replug-1231-noselect/`](artifacts-2026-10-03-b7/replug-1231-noselect/)  
**Lab-Live:** [`artifacts-2026-10-04-lab/`](artifacts-2026-10-04-lab/)

---

## 0. Enger Befund (nach Voll-Trace + Review, V)

| Aussage | Status |
|---------|--------|
| Warmes Auto-Next / Trackende → Δrc=0 | ✅ gültig, **kein** Architektur-Negativ |
| Select / Erstabspiel → Voll-Burst (~1 MB/s) | ✅ mehrfach (V) |
| Mount-Scan = Köpfe (+ ggf. volle kleine Datei) | ✅ (V); **Scan-Freeze 512 KiB möglich** |
| Remount → Resume-Vollread ohne Select | ✅ (V) |
| Kaltes Auto-Next liest | 🔜 P1 (Morgenpass = Counter-Indiz, **kein** LBA-Beweis) |
| Payload-Frische | ✅ Q3b Lab PASS · 🔜 Feld-AV |
| MSC-Live als unendliche Overlay-Datei | weiterhin ungestützt |
| MSC-Sequenz (N Chunk-Dateien) | bedingt first-class bis P1×2 |

**Arbeitsmodell:** Eine Datei, ein Voll-Read beim ersten Start pro Mount.

---

## 1. Lab-Kalibrierung — unverändert PASS

A+B + M3seq-Rehearsal: siehe Rev.3/4. Operator: Bridge vor Plug.  
**Neu Pflicht:** Pre-Flight-Warmheit **pro Datei**, maschinenlesbar in EAR.

**Lab-Host 2026-10-04:** CT `.187` bekommt `/dev/sda`+`/dev/sg0` via Proxmox `pct set 100 --dev0/1` (unprivileged LXC: `mknod` bleibt gesperrt). Q3a Tool-Lauf: `PASS_WEAK` ([`lab88-q3a-0828/`](artifacts-2026-10-04-lab/lab88-q3a-0828/)).

---

## 2. Offene Fragen

| ID | Frage | Nächster Nachweis |
|----|--------|-------------------|
| **Q2c** | Liest kaltes Auto-Next Body-LBAs — wann relativ zum Übergang (±1,5 s)? | P1 Feld ×2 |
| **Q3a** | Liefert der ESP beim Start-Read frische B-Bytes? | P2a Lab |
| **Q3b** | Liefert MSC aktuelle B-Bytes hinter Scan-Kopf? / hörbar? | Lab **PASS** (Datenebene); Feld-AV offen |
| **Q1** | Select-Trigger | ✅ erledigt |
| **Q2w** | Warmes Auto-Next | ✅ Δrc=0, warm-konfundiert |
| **L4** | Liest NBT große Datei fortlaufend nach? | P2c Diagnose |

---

## 3. Arbeitsplan

| Prio | Arbeit | Done wenn |
|------|--------|-----------|
| **P0** | Menü-Lock in **pump_bridge** (nicht ESP-FW) | ✅ Lab+Deploy PASS; **Feld-HU noch offen**; P0/P1 = getrennte USB-Sessions |
| **P1** | Kalter Auto-Next Feld ×2 | Trace-Kaltstand (nicht nur bytes), ±1,5 s, EAR, A–E nur Diagnose; nach P0-Unplug |
| **P2a** | Q3a Lab A/B | ⚠️ PASS_WEAK ([`lab88-q3a-0828/`](artifacts-2026-10-04-lab/lab88-q3a-0828/)); Oracle nachziehen |
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

**Feld/Lab 2026-10-04 (Lab fertig → Feld):** P0 **PASS**. P1 **PASS_WEAK**. O1 zu. **Q3b Lab PASS**. **Detect-Log PASS** (`cold_body_burst`, Policy unverändert). Nächster Engpass: **Feld HU-Trace + Ohr/Film**. Übergabe: [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md).

---

## 4. Eingefroren (bis P1×2 grün)

Ring-Vergrößerung, PSRAM-Streaming, Pacing, Remount-Karussell-Impl, Live-Overlay-Optimierung, AAIdrive-Port.

**Ausnahme nach P1×2 + Q3a grün:** einmaliger, begründeter Ring ≥ Chunk-Größe für Sequenz-Prototyp.
