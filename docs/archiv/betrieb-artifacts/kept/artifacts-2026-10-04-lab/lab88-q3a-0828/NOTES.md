# Q3a Lab — 2026-10-04 `lab88-q3a-0828`

**Verdict:** `PASS_WEAK`  
**FW:** `0.4.42-dev` · Serial `PD0037` · Slot fav1 (512 KiB)

## Done (D)

1. Host-Device-Nodes im CT `.187` via Proxmox `pct set 100 --dev0/1` (nicht `mknod` — LXC unprivileged blockiert mknod).
2. Silence-Baseline A an Offsets 32–192 KiB gehasht.
3. Overlay B via Pump-TCP `audio_start(fav1)` + L1.mp3 (`feed=225280`).
4. Stream `abs=176128..225280`; Sample `file_off=196608` im Fenster.
5. **Host-Hash A≠B** (`6a57db9b…` → `94aa63e1…`) — ESP liefert nach Armierung andere MSC-Bytes.
6. SoftAP `overlay_read` ≠ Host-Fenster (Ring/Underrun-Silence vs. LAME-Payload) → kein striktes Byte-Match.

## Deutung (I)

- **Q3a Kernfrage „liefert der ESP B-Bytes auf dem MSC-Pfad?“** → **ja, schwach aber positiv** (Change-Nachweis).
- Striktes Oracle-Match braucht stabilen Ring (kein paralleles Nachfüllen / Sample unmittelbar nach Freeze) oder Host-Read vor weiterem `0x55`-Feed.
- Früherer Lauf `lab88-q3a-0826` (32 KiB-Sample außerhalb absBase) ebenfalls `PASS_WEAK`.

## Nicht erledigt

- Q3b (HU hörbar) — Auto only  
- P0 Menü-Lock Implementierung  
- P1 Feld
