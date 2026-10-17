# Übergabe · 2026-10-17 (nach Stall-Vollleiter + SG_IO-Behavior)

**Kanone:** [`MASSNAHMEN-NACH-6043a22.md`](MASSNAHMEN-NACH-6043a22.md) · [`METHODIK-MSC-WAHRHEIT.md`](METHODIK-MSC-WAHRHEIT.md) · [`BIN-RICHTLINIE.md`](BIN-RICHTLINIE.md) · Matrix Stand 17.10.

## Ein Satz

**Lab-Prep komplett** (Q10, Stall-Vollleiter+QD=1, Favoriten-Layout, SG_IO-Behavior). Feld-P0 bleibt **OTG-Panic** auf `.89`, danach OTA 0.4.53 + NBT A/B/C.

## Lab erledigt

| Artefakt | Ergebnis |
|----------|----------|
| `q10-calib-01` | all_match=true |
| `stall-ladder-smoke-01` | Instrument wirkt |
| `stall-ladder-full-01` | Menü/ID3 ungebremst; Audio skaliert; **QD=1 all_consistent**; HTTP alive |
| `favoriten-layout-01` | Root nur Ordner; Live unter Favoriten |
| `favoriten-read-behavior-sgio-01` | A/B nur fav0; C alle drei — **nur SG_IO** |
| `BIN-RICHTLINIE.md` | OTA-Kopie ≤3 MiB, Kanon in esp32.pidrive/dist |

## Feld (nächster Termin)

1. **M8 Panic/OTG (P0):** UART, resetReason, VBUS A/B — Checkliste MASSNAHMEN §5
2. **OTA `.89` → 0.4.53-dev** (Bin in `favoriten-layout-01/`)
3. **NBT A/B/C** wie Lab: erste Seite nur Ordner? Autoplay erst nach Favoriten?
4. Erst danach NBT-Stall-Leiter (nicht vor Panic-Klarheit)

## Nicht tun

512‑KiB wiederholen · 64er-Lab als HU · Ring blind · Soft-Cycle mit Stall · `dd`/`read()` als MSC-Wahrheit · Overnight als Langzeit · Soft-Cycle-Lab als BMW-F0-Beweis
