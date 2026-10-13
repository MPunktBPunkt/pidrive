# Feld s2 — Pocket (30 min) · **ohne Stick / ohne F1**

**FW Freeze 0.4.46-dev · ESP `.89` · kein Stall-OTA**  
**Heute:** nur **Q8/R10** (A+C). F1 später nachholen → Stall-Go bleibt offen.

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
| 3–18 | **5× A+C** (statt 3× + E): `Zn BOB tap` → 10 s → `Zn RST1` → 15 s → `Zn Rock tap` → 60 s → `Zn RST2` → 20 s |
| 18–25 | **B** (wenn Zeit): Bayern bis Ende → `B autoplay Rock` → Rock 60 s |
| 25–30 | Puffer: 6. Zyklus A+C · `mark "s2 ende"` · Ctrl-C · Video stop |

**Kein E.** Kein Hub/Stick nötig. Marke am Start: `./mark.sh "s2 start no-F1"`.

**Packen:** Pi · Handy · ESP-Kabel · PD0089

**Abbruch:** keine Reads 20 s → Zyklus skip; ESP tot >45 s → Kabel ab/an

**Danach:** `./run-q8.sh` — Episoden nach `Zn Rock tap` / `Zn RST2`
