# Gesamtbericht / Übergabe: P0 deployed, Q3a PASS_WEAK, P1 bereit

**Stand:** 2026-10-04 · für die nächste KI  
**Einstieg:** [`../../MSC-AKTUELL.md`](../../MSC-AKTUELL.md)  
**Repos (V):** `pidrive` @ `origin/main` · `esp32.pidrive` @ `2bc9055` = `origin/main`  
**FW:** Lab `.88` = `0.4.42-dev` (live PD0038) · Feld `.89` = `0.4.42-dev` L3 (**offline**, Timeout)  
**Bridge:** `.105` · `/home/pidrive/pump_bridge.py` mit `MscSessionLock` · systemd **active**, Connect-Retry auf `.89`  
**Plan:** Rev.5 · Review: [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md)  
**Evidenz:** **D** Messdaten · **I** Interpretation · **(V)** diese Sitzung nachgerechnet

---

## 0. Kurzurteil

Die Umsetzung seit Trace-Korrektur ist **stimmig und plan-konform**. P0 ist implementiert, lab-abgenommen, auf `.105` deployed und gegen Lab `.88` erneut PASS. Q3a ist ehrlich **PASS_WEAK**. Der Freeze (Ring/PSRAM/Pacing) wurde nicht angerührt.

**Nächster produktiver Schritt:** BMW-Feldtermin — P0-Feld-Provokation, dann **neue USB-Session**, dann P1 kalter Auto-Next ×2. Keine weitere große Implementierung vorher.

---

## 1. Was erledigt ist (D, V)

| Arbeit | Ergebnis | Artefakt / Commit |
|--------|----------|-------------------|
| Review-Gesamtbericht Rev.5 | Konsolidierung Mistral/Claude/GPT | `GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md` · `652bdb2` |
| Lab-Host `/dev/sda` | `mknod` im LXC gesperrt → **`pct set 100 --dev0/1`** dauerhaft | CT `.187` |
| Q3a Lab A→B | **PASS_WEAK**: Host-Hash ändert sich; SoftAP-Oracle-Match fehlt | [`lab88-q3a-0828/`](lab88-q3a-0828/) · `45d001a` · Tool `m3_lab_q3a_freshness.py` |
| P0 Lock **in pump_bridge** (nicht ESP-FW!) | `MscSessionLock`, `--msc-lock` Default an | `esp32.pidrive` `79fc96a` |
| P0 Unit-Test | PASS | `tools/test_msc_session_lock.py` |
| P0 Lab-Provokation | PASS: Favoriten bleiben, Zurueck-UI → `frozen_reject` | [`lab88-p0-lock-0832/`](lab88-p0-lock-0832/) · `0de933b` |
| P0 Deploy `.105` | Binary + Backup; Pi-Provokation vs `.88` PASS | [`lab88-p0-lock-deploy-105/`](lab88-p0-lock-deploy-105/) · `15f05bb` |
| Connect-Retry | Initial-TCP retry statt Exit-1-Loop | `esp32.pidrive` `2bc9055` |
| Cron ensure | `@reboot` + `*/2` auf `.105` | siehe §3 |

---

## 2. Kritische Bewertung Mistral / GPT / Umsetzung

### 2.1 Übernehmen

| Punkt | Quelle | Entscheidung |
|-------|--------|--------------|
| `pct set` statt `mknod` | alle | dauerhafte Lösung |
| P0 Lab-Kette (Provokation + `frozen_reject`) | Mistral | Spezifikation getroffen |
| Q3a ehrlich PASS_WEAK | Mistral/GPT | nicht aufwerten |
| P1 trotz PASS_WEAK fahren (misst HU) | Mistral | ja; Q3a als Restrisiko führen |
| P0-Feld noch offen | beide | erste Amtshandlung im Feld |
| **P0 und P1 = getrennte USB-Sessions** | GPT | **verbindlich** |
| Kaltstand per Body-LBA-Trace, nicht nur `slotMap.bytes` | GPT | **verbindlich** |
| 768 KiB = Hypothese, keine bewiesene Grenze | GPT | übernehmen |
| Freeze halten | alle | halten |

### 2.2 Korrigieren

1. **Mistral: „P0 in ESP-FW“ ist falsch.** Der Lock sitzt ausschließlich in `pump_bridge.py` (`MscSessionLock`). Kein Firmware-OTA nötig für P0.  
2. **Cron-Panik relativieren (V):** `ensure_pump_bridge.sh` ist **idempotent** — Exit 0 wenn systemd active **oder** `pgrep` Bridge findet; startet nur sonst. Kein planmäßiger Restart alle 2 min. Restrisiko: Race bei parallelem Cron+manual, `pgrep` ≠ TCP-health. Vor Plug trotzdem: ein Prozess, Ziel `.89`, TCP up.  
3. **GPT: „Remote-Sync der Commits nicht geprüft“** — **(V) jetzt geprüft:** beide Repos `HEAD == origin/main`.

### 2.3 Fazit Bewertung

Umsetzung methodisch sauber. Ein operativer Check vor Plug (Bridge-Zustand), eine interpretative Schwäche (Q3a Oracle), eine protokollarische Schärfung (P0/P1 Session-Trennung). **Kein P1-Blocker**, wenn dokumentiert.

---

## 3. Live-Systemzustand (V, 2026-10-04)

| Komponente | Status |
|------------|--------|
| Lab ESP `.88` | up, `0.4.42-dev`, plugged, Serial PD0038 |
| Auto ESP `.89` | **unreachable** (Connect-Timeout) |
| Bridge `.105` | systemd **active**; Prozess retry auf `.89:9090` |
| `ensure_pump_bridge.sh` | Cron installiert; Skript idempotent (V) |
| Lab-Host CT 100 | `/dev/sda`+`/dev/sg0` via pct |

---

## 4. Q3a — Kurzfassung

**Verdict:** PASS_WEAK  
**D:** `changed_A_to_B=true`, Stream active, Host-Hash ≠ Silence-Hash.  
**Nicht D:** `match_overlay=false` (Ring/Underrun vs SoftAP-Oracle).  

Q3a ≠ Q3b. Entscheidungsregel-„Q3a grün“ ist **noch nicht** erfüllt. P1 trotzdem: misst HU-Read, nicht Oracle.

---

## 5. P0 — Kurzfassung

**Ort:** Bridge (`--msc-lock`), nicht ESP-FW.  
**Lab + Deploy vs `.88`:** PASS.  
**Feld-HU:** offen.  

**Feld-Regel (GPT, verbindlich):**

```
PHASE 1 P0-Feld  → USB-SESSION BEENDEN
PHASE 2 P1       → neue Serial/Mount, frischer Scan, Preflight, dann messen
```

P0 darf den Kaltstand von P1 nicht vergiften.

---

## 6. P1-Protokoll (verbindlich für nächsten Feldtermin)

### Vorab in EAR fixieren

- `preflight` pro Slot: bytes, body-LBA-Reads seit Scan, Trace-Vollständigkeit, `cold` + Begründung  
- Timing-Erfolg: erster Body-Read kaltes Ziel **±1,5 s** Nominalende (Morgenpass-Indiz; kein LBA-Beweis)  
- Umfang ≈ Dateigröße (Voll-Burst)  
- `ov=0`, TCP up **vor** Plug, neue Serial  
- Erfolg = boolesche Felder; A–E nur Diagnose (Klasse B ≠ „Erfolg“)

### Ablauf

1. Bridge: ein Prozess, Ziel `.89`, TCP up; Cron/ensure nicht parallel manuell starten.  
2. **Phase P0:** Provokation UI → Namen/UID/LBA stabil + `frozen_reject` → Artefakt → **Unplug**.  
3. **Phase P1a:** neuer Mount → Scan → Preflight (kalt per Trace) → nur kurze Datei → kein Select auf Ziel → Auto-Next → LBA/Timing.  
4. **Phase P1b:** komplette Wiederholung, neue Session.  
5. Erst ×2 werten.

### Entscheidungsregel (unverändert Rev.5)

```
P0 Feld PASS → P1×2
  GRÜN → Q3a (Oracle nachziehen)
    GRÜN → Sequenz (A), BT Fallback
    ROT  → Payload-Fix, kein Architektur-Abbruch
  NICHT GRÜN → BT-Hybrid (B)
L4 positiv → A′ parallel
Pfad C nur wenn B-UX scheitert + 6NR
```

---

## 7. Offene Stränge

| Strang | Status | Nächster Schritt |
|--------|--------|------------------|
| P0 Feld-HU | 🔜 | Phase 1 am Auto |
| P1 kalter Auto-Next | 🔜 | Phase 2 ×2 |
| Q3a Oracle | ⚠️ PASS_WEAK | parallel nachrüsten |
| Q3b hörbar | 🔜 | nach P1, mit Ton |
| P2b BT | 🔜 | parallel Checkliste |
| P2c L4 | optional | kein P1-Blocker |
| Scan-Freeze / Chunk | Hypothese ≥768 KiB | kein Code vor P1 |
| Ring/PSRAM/Pacing | ❄️ | Freeze |

---

## 8. Explizit nicht tun

Ring vergrößern · PSRAM · Pacing · Remount-Karussell · AAIdrive-Sprint · Architekturentscheidung aus PASS_WEAK · P0 und P1 in einer USB-Session vermischen · Kaltstand nur aus `slotMap.bytes==0` ableiten · Hörbarkeit aus `phase=play` ableiten.

---

## 9. Übergabe an die nächste KI (1 Absatz)

P0 (`MscSessionLock` in **pump_bridge**, nicht ESP-FW) ist lab-PASS, auf `.105` deployed, Connect-Retry aktiv; Cron-ensure ist idempotent (V), trotzdem vor Plug Bridge-Zustand prüfen. Q3a = PASS_WEAK (Host liest geänderte Bytes; Oracle offen) — im P1-Bericht so führen. Sobald Auto+`.89` online: **zuerst** P0-Feld-Provokation, **dann Unplug**, **dann** frische Session für P1×2 nach Rev.5 (±1,5 s, Preflight mit Body-LBA-Trace, volle JSONL, A–E nur Diagnose). Parallel optional Q3a-Oracle und BT-Abnahme. Freeze halten bis P1×2 + echtes Q3a-Grün. Quellen: dieser Bericht, Review-Gesamtbericht, `lab88-q3a-0828/`, `lab88-p0-lock-0832/`, `lab88-p0-lock-deploy-105/`, Trace-Korrektur + `auto89-m3seq-2042/` + `replug-1231-noselect/`.

---

## 10. Referenzen

- Plan Rev.5: [`../../PLAN-NACH-M3-AE-2026-10-03.md`](../../PLAN-NACH-M3-AE-2026-10-03.md)  
- Review: [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md)  
- Trace-Korrektur: [`../artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](../artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md)  
- Semantik: [`../../MSC-STATUS-SEMANTIK-0.4.42.md`](../../MSC-STATUS-SEMANTIK-0.4.42.md)  
- Ensure-Skript (Repo): [`../../../../scripts/ensure_pump_bridge.sh`](../../../../scripts/ensure_pump_bridge.sh)
