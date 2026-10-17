# Stall-Phasen-Leiter — Full 0…15 s

Phasen: `menu, id3, audio` · ms: `0, 1000, 2000, 5000, 10000, 15000`  
FW Lab `.88` · **0.4.53-dev** · Trigger: **SG_IO only**

## Lesart

- **Menü / ID3:** über alle Stufen ungebremst (~5 ms / ~31 ms, 0 retries, ID3 magic ok) — Spec bestätigt.
- **Audio:** Stall skaliert — Retries/Wall steigen mit `stallMaxMs`; Δbytes sinkt unter vollem 120‑KiB-CBW ab 2 s.
- **QD=1:** bei allen Audio-Stufen nur **eine** ESP-LBA (88), keine zweite LBA während BUSY → Lab-Host demonstriert QD=1 unter Stall.
- **HTTP:** durchgängig alive, kein ESP-Crash / kein Host-Fehler.

| phase | ms | Δbytes | Δretries | wall_ms | id3 | http | qd1 | 2nd LBA | err |
|---|---:|---:|---:|---:|:---:|:---:|:---:|:---:|---|
| menu | 0 | 4096 | 0 | 5.04 | False | True | True | False |  |
| menu | 1000 | 4096 | 0 | 5.01 | False | True | True | False |  |
| menu | 2000 | 4096 | 0 | 4.9 | False | True | True | False |  |
| menu | 5000 | 4096 | 0 | 4.95 | False | True | True | False |  |
| menu | 10000 | 4096 | 0 | 4.87 | False | True | True | False |  |
| menu | 15000 | 4096 | 0 | 4.91 | False | True | True | False |  |
| id3 | 0 | 8192 | 0 | 31.31 | True | True | True | False |  |
| id3 | 1000 | 8192 | 0 | 31.12 | True | True | True | False |  |
| id3 | 2000 | 8192 | 0 | 31.08 | True | True | True | False |  |
| id3 | 5000 | 8192 | 0 | 31.27 | True | True | True | False |  |
| id3 | 10000 | 8192 | 0 | 31.06 | True | True | True | False |  |
| id3 | 15000 | 8192 | 0 | 31.05 | True | True | True | False |  |
| audio | 0 | 122880 | 0 | 190.3 | False | True | True | False |  |
| audio | 1000 | 122880 | 13501 | 27501.13 | False | True | True | False |  |
| audio | 2000 | 73728 | 15034 | 30495.73 | False | True | True | False |  |
| audio | 5000 | 45056 | 21528 | 43373.72 | False | True | True | False |  |
| audio | 10000 | 36864 | 32766 | 65818.33 | False | True | True | False |  |
| audio | 15000 | 36864 | 45067 | 90408.85 | False | True | True | False |  |

## QD=1 (Audio)
- all_consistent: **True**
- any second LBA during BUSY: **False**

