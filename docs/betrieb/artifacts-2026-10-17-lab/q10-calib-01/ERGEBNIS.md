# Q10 Kalibrierung (SG_IO)

- ESP `http://192.168.178.88` · FW `0.4.52-dev`
- Methode: **SG_IO** `/dev/sg0` via `root@192.168.178.108` pct 100
- ESP Δbytes: **209408** · READ10 n=10
- blocks_hist: `{'1': 2, '8': 2, '32': 2, '128': 2, '240': 2}`
- all_match: **True**

| tag | LBA | req | esp | match |
|-----|----:|----:|----:|:-----:|
| r512 | 300 | 1 | 1 | ☑ |
| r4k | 0 | 8 | 8 | ☑ |
| r16k | 100 | 32 | 32 | ☑ |
| r64k | 200 | 128 | 128 | ☑ |
| r120k | 400 | 240 | 240 | ☑ |

Host read()/dd is NOT valid for Q10; page-cache can show data with ESP Δbytes=0.
