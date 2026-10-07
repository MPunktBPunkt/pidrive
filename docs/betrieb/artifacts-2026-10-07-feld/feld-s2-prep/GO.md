# Feld s2 — Pocket (30 min)

**FW Freeze 0.4.46-dev · ESP `.89` · kein Stall-OTA**

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep
# Terminal 1:
./run-s2.sh 2400
# Terminal 2 (vor jeder HU-Bedienung):
./mark.sh "…"
```

RST: `curl -s -m 3 -X POST http://192.168.178.89/api/restart`

| Min | Was |
|-----|-----|
| 0 | Video: HU + Uhr `watch -n0.2 date +%T.%N`, Ton an |
| 1–2 | `run-s2` + `mark "s2 start"` — `msc.reads=` wächst |
| 3–12 | **3× A+C:** `Zn BOB tap` → 10 s → `Zn RST1` → 15 s → `Zn Rock tap` → 60 s → `Zn RST2` → 20 s |
| 12–21 | **E:** Hub+Stick · `E plug stick` · `E tap 100MB` ·30s· `E tap 5MB` ·30s· `E tap 100MB again` ·30s· `E replug ESP` |
| 21–25 | **B** (optional): Bayern bis Ende → Autoplay Rock 60 s |
| 25–30 | `mark "s2 ende"` · Ctrl-C · Video stop |

**Packen:** Pi · Handy · Stick `F1-5MB*` + `F1-100MB*` · USB-1.1-Hub · ESP-Kabel

**Abbruch:** keine Reads 20 s → Zyklus skip; ESP tot >45 s → Kabel ab/an; E0 >60 s → ohne Hub + `E ohne Hub`

**Danach:** `./run-q8.sh` bzw. `feld_q8_msc_order.py --reads … --trace …`
