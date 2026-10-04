# Artefakte Lab / Review — 2026-10-04

**ESP Lab:** `192.168.178.88` · FW `0.4.42-dev` · Host-CT `DebianCursor` `192.168.178.187`  
**Normativ:** [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md) · Plan Rev.5

| Ordner / Datei | Inhalt |
|----------------|--------|
| `GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md` | Konsolidierung Mistral/Claude/GPT + eigene Nachrechnung |
| `lab88-baseline-0818/` | Live-Baseline nach `POST /api/lab/stop` (Status + Menü) |

## Blocker

Kernel hat `sda`/`sg0` (ESP MSC), Container ohne Device-Nodes:

```bash
sudo mknod -m 660 /dev/sda b 8 0
sudo mknod -m 660 /dev/sg0 c 21 0
```

Danach: Q3a Lab, Remount-Sweep, Preflight-Prototype.
