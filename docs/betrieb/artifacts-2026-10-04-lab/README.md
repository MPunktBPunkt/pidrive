# Artefakte Lab / Review — 2026-10-04

**ESP Lab:** `192.168.178.88` · FW `0.4.44-dev` · Host-CT `DebianCursor` `192.168.178.187` (Proxmox VMID 100)  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md) · **Übergabe:** [`GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md) · Plan Rev.5

| Ordner / Datei | Inhalt |
|----------------|--------|
| `GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md` | **Aktuelle Übergabe** — Feldauftrag |
| `GESAMTBERICHT-DETECT-COLD-BODY-2026-10-04.md` | Detect-Log Lab |
| `lab88-detect-cold-1536/` | `cold_body_burst` Log **PASS** (Cold loggt, Warm feuert Detect) |
| `detect-cold-vs-warm-offline/` | PD0056/57 → `not_from_head` Offline |
| `GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md` | Q3b Lab PASS |
| `lab88-q3b-1515/` | Q3b Prefill Oracles A/B/C **PASS** (fromOff=348160 / LBA 761) |
| `lab88-av-stream-1400/` | `bufferMs` tote Telemetrie; Ring füllt |
| `GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md` | Konsolidierung Mistral/Claude/GPT |
| `GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md` | P0-Deploy / Q3a PASS_WEAK |
| `lab88-baseline-0818/` | Live-Baseline vor Device-Pass-through |
| `lab88-q3a-0826/` | Q3a erster Lauf (`PASS_WEAK`) |
| `lab88-q3a-0828/` | Q3a zweiter Lauf (`PASS_WEAK`) |
| `lab88-p0-lock-0832/` | **P0** Menü-Lock Provokation **PASS** |
| `lab88-p0-lock-deploy-105/` | **P0** Deploy auf Bridge-Pi `.105` **PASS** |

## Host-Zugang

Unprivileged LXC blockiert `mknod`. Dauerhaft auf Proxmox-Host:

```bash
pct set 100 --dev0 path=/dev/sda,mode=0660,gid=6
pct set 100 --dev1 path=/dev/sg0,mode=0660,gid=6
# im CT: usermod -aG disk martin
```

## Tools

`tools/m3_lab_q3b_prefill.py` — Q3b Prefill Oracles A/B/C (ab LBA 761; len-check).  
`tools/m3_lab_detect_cold_body.py` — Lab: `cold_body_burst` Log vs Warm-Head.  
`tools/m3_offline_detect_cold_vs_warm.py` — Offline PD0056/57 Detect-Regel.  
`tools/m3_lab_q3a_freshness.py` — Q3a A/B overlay vs host hash.  
`esp32.pidrive` SoftAP: `body_seed`/`body_read` (≥0.4.43); Event `cold_body_burst` (≥0.4.44).  
Host-`dd`: Gruppe `disk` (`sg disk -c '…'`).
