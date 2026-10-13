# Lab Head-Trigger · 2026-10-05 ~17:54

**ESP:** `.88` · FW `0.4.45-dev` · PD0062 · Seed **aus** · kein Prefill · kein Detect-Umbau  
**Artefakt:** `lab88-head-trigger-1754/` · Tool: `tools/m3_lab_head_trigger.py`  
**Vorlauf:** `lab88-head-trigger-1752/` — C fail durch `cooldownMs=5000` (1 s Pause zu kurz)

## Ampel

| Phase | Ergebnis |
|-------|----------|
| A bob_mid (fav2 mid) | guessΔ=0 — kein Bayern-Arm |
| B mid→head (+237 KiB dann lba0) | **armed** fav1 · ring=**0** · live=0 |
| C head_only (nach Cooldown 6 s) | **armed** fav1 · ring=0 |
| D mid_only | guessΔ=0 — **kein Arm** |
| **PASS** | **true** |

## Kernbefund

1. **15:41-Form ist lab-reproduzierbar:** kurze Mid-Sequenz, dann Head ≥ `minSeqBytes` → `play.guess`, auch **ohne** Prefill (Ring leer → gleiches live=0-Risiko wie Feld/Arm-Diag).
2. Mid allein reicht nicht; Head allein reicht (nach Cooldown).
3. BOB-Mid allein armiert Bayern nicht — „Station vorher aktiv“ ist **kein** zusätzlicher Detect-Hebel; der Hebel ist die **Head-Sequenz** selbst.
4. Cooldown: zweiter Head-Tip innerhalb 5 s wird verschluckt (1752) — Lab/Feld-Messungen müssen `cooldownMs` einhalten.

## Was damit **nicht** erklärt ist

Warum die **HU im Auto** 15:41 einmal Mid→Head gemacht hat und 17:25/36 nicht. Lab zeigt nur: *wenn* diese LBA-Sequenz kommt, armiert Detect korrekt. Der Fahrzeug-Trigger (Next/UI/Cache) bleibt Feld-/HU-Verhalten.

## Nächste Schritte

1. Prefill-vor-Arm (bereits PASS) **vor** Head-Tip im Bridge-Pfad vorbereiten.  
2. Feld: gezielt Station-Next (BOB→Bayern) + Trace/JSONL **vor** Arm — suchen Mid→Head.  
3. Freeze hält.

```
Head-Trigger Lab: Mid→Head armt ✓ (ring=0)
Mid-only ✗ · Head-only ✓ · Cooldown beachten
HU-wann-Head weiter 🟠 (Feld)
Freeze hält
```
