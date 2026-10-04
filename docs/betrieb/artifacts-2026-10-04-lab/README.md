# Artefakte Lab / Review — 2026-10-04

**ESP Lab:** `192.168.178.88` · FW `0.4.42-dev` · Host-CT `DebianCursor` `192.168.178.187` (Proxmox VMID 100)  
**Normativ:** [`GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md) · Plan Rev.5

| Ordner / Datei | Inhalt |
|----------------|--------|
| `GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md` | Konsolidierung Mistral/Claude/GPT + eigene Nachrechnung |
| `lab88-baseline-0818/` | Live-Baseline vor Device-Pass-through |
| `lab88-q3a-0826/` | Q3a erster Lauf (`PASS_WEAK`, Sample außerhalb absBase) |
| `lab88-q3a-0828/` | Q3a zweiter Lauf (`PASS_WEAK`, Sample im abs-Fenster; NOTES) |
| `lab88-p0-lock-0832/` | **P0** Menü-Lock Provokation **PASS** (Zurueck-UI abgelehnt, Namen stabil) |
| `lab88-p0-lock-deploy-105/` | **P0** Deploy auf Bridge-Pi `.105` + Provokation **PASS** |

## Host-Zugang

Unprivileged LXC blockiert `mknod`. Dauerhaft auf Proxmox-Host:

```bash
pct set 100 --dev0 path=/dev/sda,mode=0660,gid=6
pct set 100 --dev1 path=/dev/sg0,mode=0660,gid=6
# im CT: usermod -aG disk martin
```

## Tools

`tools/m3_lab_q3a_freshness.py` — Q3a A/B overlay vs host hash.  
`tools/m3_lab_p0_menu_lock_provocation.py` — P0 freeze vs Pi-UI overwrite.  
`esp32.pidrive/tools/pump_bridge.py --msc-lock` (default on) · `test_msc_session_lock.py`.
