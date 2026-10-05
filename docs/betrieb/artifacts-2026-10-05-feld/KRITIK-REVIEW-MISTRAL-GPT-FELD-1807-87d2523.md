# Kritik / Konsolidierung: Mistral + GPT · Feld 17:55/18:07 + Lab Prefill (`87d2523`)

**Datum Review:** 2026-10-05 Abend  
**HEAD:** `87d2523` · FW `0.4.45-dev`  
**Quellen:** Feld-Gesamtberichte 1755/1807, Lab Prefill/Head-Trigger, `bridge-1809.txt`, `correlate-final.json`, `STREAM-COUNTER-SEMANTIK.md`, Lab `series-A.jsonl` (HU-Mimic)

---

## 1. Gesichert (beide Reviews)

| Befund | Beleg |
|--------|--------|
| **Head-Trigger im Feld** | Beide Arme (15:41, 18:07) kurz nach **ESP-RST**; 17:55 **ohne** ESP-RST trotz Remount/Next → kein Head, `guess=0` |
| **Auslöser sichtbar** | `bridge-1809`: Mid, dann Read ab `from=16465` (fav1 lba0), `seq_short` 4096 B, danach ≥6 KiB → `play_uid fav1` |
| **Prefill (Lab)** | Ring voll vor Head → `live>0`, `in_window`, 24/24 Sustain (`eb697bd`) |
| **Feld 18:07 Arm** | `guess=1`, Ring voll, ffmpeg — aber **`live=0`**, `streamBytes=underruns=253952` |
| **Freeze** | Kein Detect-/minSeq-/Lock-Umbau vor Lab-Beweis |

---

## 2. Korrektur: `hostAbs=253952` (Mistral §10 ← GPT)

**Verworfen:** „Persistierter / alter Cursor über RST“ (zu stark, nicht belegt).

**Plausible Mechanik (code-konsistent, Lab-Muster bestätigt):**

- Erster Live-Read armt Cursor auf **`absBase`** (oft ≈0).
- Outside-Miss: **`underruns++`** und **`hostAbsCursor++` pro Byte** — auch ohne Ring-Treffer.
- Producer scrollt Ring → **`absBase`/`absEnd` laufen vor**.
- Snapshot bei Arm-Messung: Cursor kann **weit vor** aktuellem Fenster liegen (18:07: Host 253952, Fenster 457112..506264).

**Konstanz 15:41 und 18:07:** Gleicher Wert heißt sehr wahrscheinlich **gleicher HU-Lese-Umfang** (~62×4096 Live-Pfad-Bytes), nicht NVS — **`hostAbs == streamBytes`** in beiden Fällen. Feld-**Arm-Timeline** fehlt noch für 🟢.

**Lab-Kreuzcheck:** `lab88-hu-mimic-1617/series-A.jsonl` — Sample 1: `cursorArmed=false`, `hostAbs=0`; Sample 2: `hostAbs=16384`, `underruns=12288`, `live=4096`.

---

## 3. Geometrie 18:07 vs 15:41

| Session | Fenster vs Host | Deutung |
|---------|-----------------|---------|
| 15:41 | Fenster **hinter** Host (~43 KiB) | Host „ahead“ |
| 18:07 | Fenster **~200 KiB vor** Host | Cursor durch Underruns zurück, Ring gescrollt |

Gleiche Signatur `live=0`, **unterschiedliche Layouts** — „Host outrannt“ allein ist für 18:07 unpräzise.

**Resync:** Nur `nearHead` + Seek-Back → Snap auf `absBase` (`STREAM-COUNTER-SEMANTIK.md`). Ob HU das je triggert → **`fileOff` + `headResyncs` pro Read** loggen.

---

## 4. P0 Lab (Konsens, vor Feld/FW-Fix)

1. **Arm-Timeline:** Übergang `cursorArmed false→true` mit **`absBase`/`absEnd`/`hostAbs`/`underruns`/`fileOff`/`headResyncs`** je Read bis stabil oder 253952.
2. **Versuch C:** Producer laufen (`absBase ≫ 0`), **dann** Head-Arm — Snapt Cursor auf aktuelles `absBase`? `live>0`?
3. **Versuch A/B:** Referenz (leerer Ring vs Prefill PASS, bereits in `eb697bd`).
4. **Nicht:** pauschaler FW-Snap — initialer Arm setzt bereits `hostAbs=absBase`; Problem = **Timing** (Arm vs Producer vs HU-Burst).

---

## 5. Ampel (konsolidiert)

| Thema | Stand |
|-------|--------|
| RST → Head-Read | 🟡 starkes Muster, n klein |
| Prefill-vor-Arm | 🟢 Lab |
| Feld Arm | 🟢 15:41 + 18:07 |
| 253952 = Underrun-Zähler | 🟠 plausibel + Lab-Muster, Feld-Timeline offen |
| Feld Ton / live>0 | 🔴 |
| Sequenz-GO | 🔴 gesperrt |

**Gesamt:** 🟡 — Head-Trigger verstanden; letzte Meile = **Arm-/Producer-Timing** (Messung, kein blindes Prefill).
