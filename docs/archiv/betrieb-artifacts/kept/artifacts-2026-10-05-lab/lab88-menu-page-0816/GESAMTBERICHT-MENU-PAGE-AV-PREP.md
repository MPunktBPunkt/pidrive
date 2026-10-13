# Lab Menü-Seite + AV-Prep · 2026-10-05

**ESP:** `http://192.168.178.88` (PD0046) · **Artefakt:** `lab88-menu-page-0816/`  
**Tool:** `tools/m3_lab_menu_page_session.py` · **AV Host:** `av-mpeg-smoke/` (A+B PASS)

## Ergebnis (PASS)

| Test | Ergebnis |
|------|----------|
| P0 Lock: Meta-`menu_set` abgewiesen, MSC bleibt Rock/Bayern/BOB | **PASS** (`bridge.log` `frozen_reject`) |
| Feld-ähnliche Meta-Slots (Pump `menu_set` Favoriten/Quellen/Stop) | **PASS** (`field_meta_slotMap`) |
| Meta/Stop: kein Live-Producer (`stream.active=false`) | **PASS** |
| Rückweg `pump:page_home` | **PASS** (Sender in API) |
| Remount + Reseal | **PASS** (`status-04-return-remount`) |
| AV-Smoke Sender + Pump + Host-dd | **PASS** (`liveBytes>0`, MPEG Stage B) |

## Befund

1. **Mit `--msc-lock` (wie Feld-Bridge):** Pi-UI/Settings-Menü (Favoriten/Quellen/Stop) wird an der Bridge **nicht** auf MSC durchgereicht; API und `slotMap` bleiben auf **Rock Antenne / Bayern / BOB**. Session-`playingUid` kann trotzdem `page_next` / Stop sein — ohne `audio_start` kein Stream (`stream.active=false`).

2. **Ohne Lock (Kontrolle):** Direktes Pump-`menu_set` mit Meta-Slots reproduziert die **Feld-Menüseite** in API + `slotMap` (wie PD0064 morgens).

3. **Abend-Feld:** Operator braucht **Sender-Seite** auf der HU (Rock/Bayern/BOB), dann AV/Correlate. C′ nicht wiederholen. Wenn HU auf Meta-Seite hängt: **`Mehr…` → Seite 1** (`pump:page_home`) oder Remount-Prozedur aus `status-04`; erst bei sichtbaren Sendern AV.

## Operator-EAR (Abend)

```
Bridge .105 → .89 --msc-lock wie morgens.
HU muss Rock/Bayern/BOB zeigen — nicht Favoriten/Quellen/Stop.
Meta-Seite: kein Ton (stream.active=false); Correlate Negativ ok.
AV: Seed aus + Correlate + Ohr wenn Sender-Slots + liveBytes>0.
```
