# Feld s3 — Pocket P-Quelle · **nur ESP · ~15 min**

**FW Freeze 0.4.46 · ESP `.89` · kein Stick · kein Stall-OTA**  
**Volltext:** [`../FELDPROTOKOLL-P-QUELLE-ESP.md`](../FELDPROTOKOLL-P-QUELLE-ESP.md)

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep
# Terminal 1:
./run-s3.sh 1200
# Terminal 2 (vor jeder HU-Bedienung):
./mark.sh "…"
```

RST: `curl -s -m 3 -X POST http://192.168.178.89/api/restart`

| Min | Was |
|-----|-----|
| 0–2 | Video + Uhr · `run-s3` · `mark "s3 start P-Quelle"` · Serial laut sagen |
| 2–6 | **A:** Rock 40 s → RST → Rock 35 s |
| 6–9 | **B:** Rock 40 s → BOB 10 s → Rock 35 s |
| 9–14 | **C ★:** Rock 40 s → **Kabel ab 5 s** → rein → Index → Rock 35 s · Serial? |
| 14–15 | `mark "s3 ende"` · Ctrl-C |

**Zeitnot:** nur **C**, dann A.  
**Packen:** Pi · Handy · ESP-Kabel · PD0089

**Orakel (kurz):** Resume = Start≠0 / `r16_resume_like` · Kopf = Start bei 0 / `head_like`
