# Stall-Phasen-Leiter (Smoke 0/1/2 s)

Phasen: `menu, id3, audio` · ms: `0, 1000, 2000`

## Lesart Smoke

- **Menü / ID3:** Stall greift nicht (Meta bzw. ID3-Kopf laut Spec ungebremst) — wall ~5 ms / ~31 ms, retries 0, ID3 `starts_id3=true`.
- **Audio @0 ms:** voller 240-Block-CBW in ~189 ms, Δbytes 122880, retries 0.
- **Audio @1 s / 2 s:** Stall aktiv — tausende Busy-Retries, wall ~8 s, Δbytes < 120 KiB, timeouts > 0. **Instrument wirkt.**

Vollleiter 0…15 s und QD=1-Zweit-LBA-Auswertung: nächster Lauf `stall-ladder-full-01`.

| phase | ms | Δbytes | Δretries | wall_ms | id3 | err |
|---|---:|---:|---:|---:|:---:|---|
| menu | 0 | 4096 | 0 | 5.13 | False |  |
| menu | 1000 | 4096 | 0 | 4.97 | False |  |
| menu | 2000 | 4096 | 0 | 4.86 | False |  |
| id3 | 0 | 8192 | 0 | 31.39 | True |  |
| id3 | 1000 | 8192 | 0 | 31.21 | True |  |
| id3 | 2000 | 8192 | 0 | 31.13 | True |  |
| audio | 0 | 122880 | 0 | 189.25 | False |  |
| audio | 1000 | 40960 | 3935 | 8180.87 | False |  |
| audio | 2000 | 28672 | 4172 | 8587.08 | False |  |
