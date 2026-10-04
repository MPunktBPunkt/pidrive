# Artefakte Lab / Review — 2026-10-04

**ESP Lab:** `192.168.178.88` · FW `0.4.43-dev` · Host-CT `DebianCursor` `192.168.178.187` (Proxmox VMID 100)  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md) · **Übergabe:** [`GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md`](GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md) · Plan Rev.5

| Ordner / Datei | Inhalt |
|----------------|--------|
| `GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md` | **Aktuelle Übergabe** — Q3b Lab PASS |
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

`tools/m3_lab_q3b_prefill.py` — Q3b Prefill Oracles A/B/C (ab LBA 761).  
`tools/m3_lab_q3a_freshness.py` — Q3a A/B overlay vs host hash.  
`tools/m3_lab_p0_menu_lock_provocation.py` — P0 freeze vs Pi-UI overwrite.  
`esp32.pidrive` SoftAP: `POST /api/lab/body_seed`, `GET /api/lab/body_read` (FW ≥0.4.43-dev).  
Host-`dd`: Session braucht Gruppe `disk` (`sg disk -c '…'`).
