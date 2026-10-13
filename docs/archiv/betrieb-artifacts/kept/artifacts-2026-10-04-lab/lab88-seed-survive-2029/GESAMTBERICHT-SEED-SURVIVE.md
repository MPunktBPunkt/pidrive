# Lab — Seed Survive + Hit · 20:29 · PD0042

**FW:** `0.4.45-dev` (OTA von 0.4.44 nach Lab-RST)  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-lab/lab88-seed-survive-2029/`  
**Tool:** `tools/m3_lab_seed_survive.py --hit --settle-s 30`

## Ampel

| Schritt | Status | Beleg |
|---------|--------|-------|
| Arm Seed B | **PASS** | `active=True`, fromOff=348160 |
| Oracle A | **PASS** | SoftAP `Q3B1B…` |
| Survive 30 s | **PASS** | `active=True`, uptime 6s→38s (kein Reboot) |
| Host-Hit LBA 761 | **PASS** | `bytesServed` 0 → **32768** |

## Deutung

1. RAM-Seed bleibt ohne RST über das Settle-Fenster aktiv — der 1738-GO-Fail (Reboot ~4 s nach Seed) ist **kein** genereller FW-Timer.  
2. Host-Body-Read ab LBA 761 liefert Seed-Bytes (`bytesServed` steigt) auf 0.4.45.  
3. Feld morgen: Prepare-Gate + Watchdog; kein RST nach Seed.

## Freeze

Ring/PSRAM/Pacing/Detect unverändert.
