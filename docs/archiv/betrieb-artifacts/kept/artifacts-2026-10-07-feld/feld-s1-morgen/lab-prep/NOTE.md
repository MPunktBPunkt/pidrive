# Lab-Prep für Feld morgen (2026-10-07)

| Artefakt | Inhalt |
|----------|--------|
| `lab88-q4-cache-matrix/` | PASS: fav1→fav2→re-fav1 (0 Reads) → Remount → fav1 +128; fav0 8 MiB eager 2048 Reads (~32 s, HTTP-Timeout erwartet) |
| `marker-512kib.bin` / `marker-8mib.bin` | lokal generiert (`nbt_marker_file.py`); `*.bin` gitignored — Index JSON committed |

Regenerate markers:
```bash
python3 tools/nbt_marker_file.py --size-kib 512 --section-kib 50 --ksil-tiles --out lab-prep/marker-512kib.bin
python3 tools/nbt_marker_file.py --size-kib 8192 --section-kib 100 --ksil-tiles --out lab-prep/marker-8mib.bin
```
