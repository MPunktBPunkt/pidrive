# C2 Diagnose — OTHER-Phasen (2026-10-06)

**Vor Fix:** `full_file_old_classifier` ID3=1, SILENCE=6, **OTHER=121**  
**OTHER-Samples:** Sync nicht bei Offset 0 (`first4` oft `55555555`), `hits_phase0=0`, `best_phase` ∈ {12…132}, `best_hits≈26`.

**Ursache:** `classify_block` verlangte Sync am Blockanfang und zählte nur Phase-0-Tiles.

**Nach Fix (G1):** SILENCE=254, OTHER=0, `silence_ratio=1.0`, `classifier_ok=true`.

Rohdump: [`OTHER-DUMP.json`](OTHER-DUMP.json).
