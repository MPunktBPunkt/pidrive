# Lab-Replay s1-1700 nach C2 (Overnight Fortsetzung)

**ESP:** `.88` 0.4.46-dev · **kein Stall**

## Ergebnisse

| Lauf | Ergebnis |
|------|----------|
| Soft-RST → **G2** Muster B | PASS · `hostAbs_pre=0`, `hostAbs_after_arm=0`, `und_delta=0`, maxSeq=524288 |
| **G1** Muster A | PASS · `und=hostAbs=438272`, `silence_ratio=1.0` |
| `m3_lab_hu_eager_file` B-fav1-arm | Muster_A_like · hostAbs≈523776 (Arm vor *gesamtem* Read → ~volle Datei als und; anders als G1 mid-arm) |
| `m3_lab` A ohne Clean | verfälscht (Stream noch armed vom Vorlauf) |
| `m3_lab` A2 nach RST | BrokenPipe in `setup_menu` — Skript fragiler als `nbt_hu_sim` |

## Fazit

Feldmuster A/B gegen aktuelle FW **weiterhin reproduzierbar** über Golden G1/G2. `m3_lab_hu_eager_file` braucht Clean-State (soft_rst) und ist bei Pipe/Timeout unzuverlässig — für Regression **nbt_hu_sim** bevorzugen.
