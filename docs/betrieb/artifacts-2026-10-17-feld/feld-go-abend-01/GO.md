# Feld-Go · Abend 2026-10-17 (~20 min)

**FW erwartet:** `0.4.53-dev` auf `.89` (bereits OTA) · Stall **aus**  
**Pi:** `.105` · Scripts: `~/feld-go-abend-01/tools/`  
**Artefakte hier:** `docs/betrieb/artifacts-2026-10-17-feld/feld-go-abend-01/`

## Vor dem ersten Stecken

1. UART an ESP (falls Kabel da) — sonst wenigstens Status-Poll
2. Bridge prüfen: `systemctl is-active pidrive_pump_bridge` auf `.105`
3. Status:
   ```bash
   curl -s http://192.168.178.89/api/status | python3 -m json.tool | head -40
   ```
   Notieren: `version`, `resetReason`, `bpbVolumeId`, `usbSerial`, `otgUp`

## A — M20 Klasse-A-Repro (P0) · 3× minimum

Je Zyklus (OTG **raus → 3 s → rein**):

| # | Weiß? | Ton? | Dauer s | resetReason | uptime | plugCount | playingUid |
|---|-------|------|---------|-------------|--------|-----------|------------|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

Poll parallel (auf Laptop oder `.105`):
```bash
python3 ~/feld-go-abend-01/tools/feld_status_poll.py \
  --esp http://192.168.178.89 \
  -o ~/feld-go-abend-01/out/m20-poll-$(date +%H%M%S).jsonl \
  --interval 0.7 --seconds 90
```
*(Falls `feld_status_poll` andere Args hat: siehe `python3 … --help` — sonst manuell `curl` alle 1 s.)*

**Klasse A** = kein Weiß, WLAN hält, `resetReason` ≠ panic, Ton möglich.  
Ton-Dauer stoppen (Soll ~8 s ohne Stall).

## B — M22 Play-Guess (kurz)

Nach einem erfolgreichen LIVE: Status `playGuessCount` / `playingUid` notieren.  
Ohne Guess → Stall-Leiter **nicht** starten.

## C — M24 Ordner-Cache (Volume-ID only)

**OTG raus**, dann auf Laptop/Lab-Host (oder wo Repo liegt):

```bash
cd ~/projects/pidrive   # bzw. gepulltes Repo
python3 tools/feld_m24_volume_id.py --esp http://192.168.178.89 --apply \
  -o docs/betrieb/artifacts-2026-10-17-feld/feld-go-abend-01/m24-volume-id
```

Auf `.105` ohne volles Repo:
```bash
python3 ~/feld-go-abend-01/tools/feld_m24_volume_id.py --esp http://192.168.178.89 --apply \
  -o ~/feld-go-abend-01/out/m24-volume-id
```

Check `GATE.json`: `volume_id_changed` + `serial_unchanged`.  
Dann OTG stecken → **Favoriten/Menue sichtbar?**

- ja → Cache-Hypothese gestützt  
- nein → M25 Serial-Bump nächstes Mal; Ansicht „Ordner“ vs „Alle Titel“ prüfen

## D — Nur wenn A grün + Guess ok

Stall-Leiter fav1 — **heute optional**, nicht erzwingen wenn Zeit knapp.

## Nicht tun

Layout umbauen · Panic „gefixt“ sagen · Stall ohne Guess · Soft-Cycle×Stall · 512‑KiB-Wiederholung

## Kurz-Ampel nach der Fahrt

- M20: _/_ Klasse A  
- M24 Ordner: ja / nein / unklar  
- UART: ja / nein  
- Ton max: ___ s
