# Feld 2026-10-04 — Ergebnis (Auto `.89`)

**FW:** `0.4.42-dev` L3 · **Bridge:** `.105` `pump_bridge` mit `--msc-lock` + Connect-Retry  
**Fenster:** ~10:43–11:07 · Ende: User musste fahren  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)

---

## Ampel

| Thema | Ergebnis | Beleg |
|-------|----------|--------|
| **P0 Menü-Lock** | **PASS** | [`p0-provokation/`](p0-provokation/) — Seal Rock/Bayern/BOB; `frozen_reject`; ESP-Namen stabil |
| **P1 kalter Auto-Next ×2** | **EVIDENCED / PASS_WEAK** (offline nachbewertet) | Identische fav0-Body-Bursts; Lauf B Burst1 **+0,35 s** vs Nominal — [`P1-OFFLINE-REGRADE-2026-10-04.json`](P1-OFFLINE-REGRADE-2026-10-04.json). Nicht voll GRÜN (Startuhr/Ohr). |
| **Play-Detect (selten)** | **OK wenn Warm-Head**; verpasst Cold-Burst | [`otg-1058/`](otg-1058/) — `play_uid` + ffmpeg; P1-Bursts oft `not_from_head` |
| **Ton / Cover an HU** | **FAIL** (auch bei Detect) | User: kein Ton/Bild; PD0058 **`streamBytes==underruns`** (0 Live-Bytes). **`bufferMs` ist tote Telemetrie** — siehe Lab `lab88-av-stream-1400/` |
| **LED** | **≠ Live-AV**; korreliert mit MSC-Bursts | Blinkt bei Rock-Body-Burst (~87 s); kein Burst (BOB-Cache) → kein Feedback |

---

## Timeline (verdichtet)

| Zeit | Serial | Ereignis |
|------|--------|----------|
| 10:43 | PD0052 | Online; erstes Siegel falsch (Audio-Menü) weil USB schon steckte |
| ~10:45–47 | PD0054→55 | Unplug/RST (weiß LED); Reseal Favoriten; **P0 PASS** |
| 10:49–52 | PD0056 | P1-A: Bayern „durch“, stumm; Auto-Next-Reads auf Rock (~8 MiB); LED bei Wechsel |
| 10:53–58 | PD0057 | P1-B: BOB→Bayern→Rock Autoplay, stumm; LED bei Wechsel zu Rock; **kein Ton** bestätigt |
| 10:58–11:02 | PD0058 | Replug: **Play-Detect** Bayern+BOB (`audio_start`); LED ja; **Ton/Bild nein**; 11:01 Wahl ohne Feedback |
| 11:03–11:07 | PD0059 | Rock voll gelesen + LED, `not_from_head`; BOB-Wahl ohne LED (Cache voll); Feldende |

---

## Drei getrennte Probleme (nicht vermischen)

1. **P0 / Menü-Identität** — gelöst im Feld (Lock in Bridge).  
2. **Cold-Body-Next existiert** — HU liest fav0-Body ~87 s nach Kurzdatei (LBA-Evidenz). Scan-Kopf (~0,33 MiB) bleibt „gefroren“; Detect reagiert oft falsch.  
3. **AV-Pfad** — Detect+ffmpeg ≠ hörbar; Metrik **`streamBytes` vs `underruns`**, nicht `bufferMs`.

Voll-GRÜN P1 braucht bessere Startuhr + Q3b (Inhalt des Bursts). Siehe [`GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md`](GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md).

---

## Nächste Schritte (Priorität)

1. **Lab Q3b / Prefill** hinter Scan-Kopf — Oracle auf Cold-Burst-LBAs.  
2. **Detect:** Cold-Body-Burst vs Warm-Head (zuerst nur loggen).  
3. **Feld mit Ohr/Film** nach Prefill.  
4. Freeze halten; BT-Hybrid Fallback.

---

## Artefakte

| Ordner | Inhalt |
|--------|--------|
| `p0-provokation/` | EAR, menu before/after, `msc_lock.jsonl`, report **P0_PASS** |
| `p1-run-a/` · `p1-run-b/` | Preflight, reads, EAR, reports INCONCLUSIVE / no audio |
| `otg-1058/` | Play-Detect + AV-FAIL |
| `otg-1103/` | Cache-only Rock/BOB, LED-Semantik |
| [`FELD-P0-P1-CHECKLISTE-2026-10-04.md`](../FELD-P0-P1-CHECKLISTE-2026-10-04.md) | Taschenprotokoll (Prep) |
