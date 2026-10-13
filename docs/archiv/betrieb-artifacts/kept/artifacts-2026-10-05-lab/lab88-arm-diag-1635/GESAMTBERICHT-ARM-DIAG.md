# Lab Arm-Diagnose · P2 · soft-RST clean

**ESP:** `.88` · Artefakt: `lab88-arm-diag-1635` · FW `0.4.45-dev` · Seed aus · kein Detect-Umbau

## Ampel

| Phase | Ergebnis |
|-------|----------|
| mid_cold (32+ KiB mid) | guessΔ=0 rejectΔ=93 coldΔ=1 — **kein Arm** |
| tip_head (≥minSeq from lba0) | **armed** play=fav1 · **ring_size=0** · host=0 · live=0 |
| field_like mid→head | armed=True ring=0 |
| post_arm ohne Prefill | max_live=0 max_ahead=0 |

## Kernbefund

1. **Mid-only armt nicht** — passt zu `evaluatePlay` → `not_from_head` / prefetch (Abend Tip-ohne-Stream oft = Mid-Reads).
2. **Head-Sequenz armt mit leerem Ring** (`ring_size=0` beim Arm) — erklärt Feld-15:41-Signatur **live=0 ab erstem active**, wenn HU danach sequentiell outrannt bevor Producer füllt (HU-Mimic A).
3. Detect-Policy unverändert. Freeze hält.

## Mistral-Review Gegenprüfung

Siehe [`KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md`](../KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md).
