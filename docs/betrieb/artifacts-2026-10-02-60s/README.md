# Feld 60s Live-Read Passes — 2026-10-02

**Zentrale Frage:** Liest die BMW-NBT während der Wiedergabe kontinuierlich Live-MSC-Daten, oder nur Burst + Cache?

**Feld-Urteil (Nachmittag ~15:36–15:50):** **Mount-Scan + Cache** in den 60 s-Fenstern — siehe [`SESSION-1548-VERDICT.md`](SESSION-1548-VERDICT.md), Präzisierung §11.10, Zähler [`lab88-counter-semantics/`](lab88-counter-semantics/). Nachlesen später: offen (B7).

## Lab-Dryrun (Pipeline-Check)

| Pass | Ergebnis |
|------|----------|
| `fav0-145621` | Tool OK: `streamBytes_delta=356352`, 214 read-events over 60s, `underruns=0`. Paced MSC on Proxmox (**kein** BMW-Urteil). |

## Auto Feld

| Pass / Ordner | UID / Sync | Kurz |
|---------------|------------|------|
| `fav2-153656` | fav2 BOB ~15:36 | 60s: readsΔ=0, sbΔ=0 |
| `replug-1538-burst` | OTG ~15:38 | Burst bis sb≈981KiB / reads=421, dann stop |
| `fav1-153911` | fav1 Bayern ~15:39 | 60s: sb flat 980992, reads flat |
| `replug-1541-burst` | OTG ~15:41 | PUMP HTTP-Miss (Port = TCP); Outage-Fenster |
| `replug-1544-burst` | OTG ~15:44 | ESP `/api/status` ok; playing fav2 nach Burst |
| `fav1-bayern-1546` | ~15:46 Ohr Bayern | 60s poll: rc/sb eingefroren; Bridge forwarded weiter |
| `EAR-1541-1542.txt` | Sync-Notizen | BOB/Rock Antenne: Bild + kurze Sekunden Ton |

| `replug-1550-note` | OTG ~15:50 | gleiches Verhalten; Session-Ende |

FW `0.4.36-dev` · Guard-Fix · Bridge Pi `.105` → ESP `.89:9090`.
