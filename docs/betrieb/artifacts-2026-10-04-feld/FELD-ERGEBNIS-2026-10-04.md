# Feld 2026-10-04 — Ergebnis (Auto `.89`)

**FW:** `0.4.42-dev` L3 · **Bridge:** `.105` `pump_bridge` mit `--msc-lock` + Connect-Retry  
**Fenster:** ~10:43–11:07 · Ende: User musste fahren  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)

---

## Ampel

| Thema | Ergebnis | Beleg |
|-------|----------|--------|
| **P0 Menü-Lock** | **PASS** | [`p0-provokation/`](p0-provokation/) — Seal Rock/Bayern/BOB; `frozen_reject`; ESP-Namen stabil |
| **P1 kalter Auto-Next ×2** | **INCONCLUSIVE / nicht messbar** | [`p1-run-a/`](p1-run-a/) · [`p1-run-b/`](p1-run-b/) — HU Autoplay aus Scan-Cache |
| **Play-Detect (selten)** | **OK wenn Head-Read** | [`otg-1058/`](otg-1058/) — `play_uid` fav1→fav2, `audio_start`, ffmpeg, `audio_ack ok` |
| **Ton / Cover an HU** | **FAIL** (auch bei Detect) | User mehrfach: kein Ton, kein Bild; ESP `bufferMs=0` trotz `phase=play` |
| **LED** | **≠ Live-AV** | Blinkt bei großen MSC-Reads *oder* bei echtem Play; ohne Burst kein Feedback ([`otg-1103/`](otg-1103/)) |

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
2. **HU-Cache vs. Live-Read** — nach Scan spielt NBT oft ohne Head-Read → kein `play_uid` → stumme Playlist; LED kann trotzdem bei Prefetch/Vollread blinken.  
3. **AV-Pfad** — selbst wenn Detect+ffmpeg greifen: `bufferMs=0`, kein Ton/Cover an HU → Pump/MSC-Fill oder Ausgang, nicht „Menü kaputt“.

P1 (±1,5 s kalter Next) setzt voraus, dass (2) und ideal (3) greifen. Heute: **Entscheidungsregel P1 nicht GRÜN**.

---

## Nächste Schritte (Priorität)

1. **Lab: warum `bufferMs=0` bei `audio_ack ok`?** SoftAP/`lab/play` + Host-Read der Live-Datei; Bridge-Audio → MSC-Buffer → Host-`dd`.  
2. **Play-Detect vs. Cache:** Head-Read erzwingen oder Detect-Policy (warm/mid-file) bewusst erweitern — nur mit AV-Beweis.  
3. **P1 wiederholen** erst wenn mindestens einmal Ton an HU (Lab oder Feld).  
4. **Q3a Oracle** (Lab) parallel; Freeze Ring/PSRAM/Pacing halten.  
5. **BT-Hybrid** als Fallback bleibt im Plan, solange P1/AV nicht grün.

---

## Artefakte

| Ordner | Inhalt |
|--------|--------|
| `p0-provokation/` | EAR, menu before/after, `msc_lock.jsonl`, report **P0_PASS** |
| `p1-run-a/` · `p1-run-b/` | Preflight, reads, EAR, reports INCONCLUSIVE / no audio |
| `otg-1058/` | Play-Detect + AV-FAIL |
| `otg-1103/` | Cache-only Rock/BOB, LED-Semantik |
| [`FELD-P0-P1-CHECKLISTE-2026-10-04.md`](../FELD-P0-P1-CHECKLISTE-2026-10-04.md) | Taschenprotokoll (Prep) |
