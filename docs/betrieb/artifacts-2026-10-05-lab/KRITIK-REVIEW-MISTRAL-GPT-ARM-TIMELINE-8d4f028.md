# Kritik / Konsolidierung: Mistral + GPT · Lab Arm-Timeline `8d4f028`

**Datum:** 2026-10-05 Abend · **HEAD:** `8d4f028`  
**Quellen:** Matrix-1945, REPORT 1945-empty248, LAB-NEXT, MSC-AKTUELL, Reviews Mistral+GPT (Canvas)

---

## Konsens (beide Reviews)

| Befund | Stand |
|--------|--------|
| `253952` = 62×4096 Underrun seit Arm auf `absBase≈0` | 🟢 Lab-bewiesen (Fußnote: 62 im Feld noch Inference) |
| Persistenz/NVS-Cursor | 🔴 verworfen |
| Arm-Snap auf aktuelles `absBase` funktioniert | 🟢 Prefill + Versuch C |
| `audio_start` = Live-Pfad-Schlüssel | 🟢 |
| Mid-Historie ändert Arm-Start nicht | 🟢 |
| Remount ohne RST erhält Zustand | 🟡 dünn (1936; 1949 verschmutzt) |
| Blind-FW-Snap | ❌ verfrüht — Freeze hält |

**GPT-Korrektur an Mistral:** „Producer-Gate ist der Konstruktionsfehler“ = **plausible Hypothese**, noch **nicht** bewiesen. Zwei Stellrichtungen bleiben offen: Vorfüllen vs. Producer-Gate (vs. Kombi).

---

## Nächste Weiche (P0 Lab, kein FW)

1. **Producer A/B:** identischer 62×4KiB-Host-Burst — A freilaufender Pump (chunk>4KiB), B Pump pausiert bei Ring voll. Vergleich `liveBytes(t)`, `behind_base`, `absBase`.
2. **Prefill-Sweep:** 0 / 16 / 32 / 48 KiB vor Head + 248 KiB Burst — ab welchem Füllstand hält `live>0`?
3. **Remount sauber** mit Bridge-Mimic wiederholen.
4. Feld erst danach: dense Correlate ab `play_uid`/`audio_start` + `absEnd`-Steigung.

Freeze: kein Detect-/Snap-/Ring-Umbau.
