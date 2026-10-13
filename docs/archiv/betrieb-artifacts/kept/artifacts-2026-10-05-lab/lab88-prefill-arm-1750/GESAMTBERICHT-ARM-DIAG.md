# Lab Prefill-vor-Arm · 2026-10-05 ~17:50

**ESP:** `.88` · FW `0.4.45-dev` · Serial PD0062 (soft-RST) · Seed **aus** · Artefakt: `lab88-prefill-arm-1750/`  
**Tool:** `tools/m3_lab_arm_diag.py --soft-rst --prefill-kb 96`  
**Kontext:** Feld 17:25 Review → Prefill-vor-Arm als Gegenmittel zu ring=0 @ Arm

## Ampel

| Phase | Ergebnis |
|-------|----------|
| mid_cold | guessΔ=0 rejectΔ=93 — **kein Arm** |
| Prefill 96 KiB | ring=**49152** (voll) vor Tip |
| tip_head | **armed** fav1 · ring=**49152** · live=**12288** · in_window · ov=0 |
| prefill_sustain (24 Samples) | max_live=**69632** · streak=**24/24** · **PASS** |
| field_like mid→head | armed guess 2→3 (Ring noch voll vom Prefill-Lauf) |

## Kernbefund

1. **Prefill vor Head-Arm hält liveBytes>0 anhaltend** — Gegenprobe zu Arm-Diag ohne Prefill (`lab88-arm-diag-1635`: ring=0, max_live=0).
2. Beim Arm: Ring voll, Host im Fenster, `underruns=0` am Tip; Sustain über Host-Weiterlesen + Pump-Pace.
3. Später im Sustain: `ahead>0` / `in_window=false` bei weiterem Host — liveBytes bleiben >0 (Underrun-Zähler steigt nicht mit), d. h. Producer hatte Vorsprung aus Prefill.
4. Mid-only bleibt Reject — Detect unverändert. Freeze hält.
5. `readOverflow=0` über Tip/Sustain (Remount-Feld-Anomalie hier nicht reproduziert).

## Abgrenzung

- Lab-Host steuert Head-Tip bewusst; Feld-**Head-Trigger** (wann HU selbst ab lba0 liest) bleibt offen.
- `audio_start`+Fill vor Tip = Reihenfolge-Test, kein Detect-/Ring-Umbau.

## Nächste Schritte

1. Feld erst mit Bridge-Pfad, der **vor** erstem Head-Read füllt (sobald Head-Trigger verstanden/repro).  
2. Optional Lab: Head-Trigger-Szenario isoliert (BOB mid → Bayern head) ohne Prefill-Restzustand.  
3. Freeze hält.

```
Prefill-vor-Arm Lab PASS (live streak 24/24)
mid≠Arm ✓ · ring@arm=full
Feld-Head-Trigger weiter 🟠
Freeze hält
```
