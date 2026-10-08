# Ergebnis Lab-Abend · 2026-10-08 · `lab-abend-1556`

**ESP:** `.88` · FW `0.4.46-dev` · L3 · SG `/dev/sg0` (= `sda` PIDRIVE USB_MEDIA 16 M)  
**Auftrag:** [`../../artifacts-2026-10-08-feld/AUFTRAG-LAB-ABEND-2026-10-08.md`](../../artifacts-2026-10-08-feld/AUFTRAG-LAB-ABEND-2026-10-08.md)

| Block | Ergebnis | Artefakt | Entscheidung fürs Feld |
|---|---|---|---|
| L0 Self-Test | **PASS** | `l0-self-test.log` | Werkzeuge ok |
| L0 golden ALL (G1–G5) | **PASS** | `l0-all/` | Simulator freigeben |
| L0 Bridge 48k / target 6000 / marker 1 s | **PASS** · ~5590 B/s (±2 k) · `marker=1s` | `l0-bridge.log`, `l0-bridge-rate.json` | Bridge-Flags freigeben |
| L0 Name-Override | **TEIL** · `menu_set` zeigt `Radio BOB LAB 1008`; Disk-Scan ohne OTG-Unplug nicht bestätigt | `l0-override-bridge.log` | s4 K3: OTG ab, dann Override |
| L1 REPLUG 4 KiB ×3 | **PASS** · 524288 B / 128 cmd · live ~8,3 s · identity_ok · sg p50 **5,0 ms** | `l1-4k-r*` | Q10-Kandidat: **4 KiB** (Feld-ähnlich) |
| L1 REPLUG 16 KiB ×3 | **PASS** · 33 cmd · live ~8,4 s · sg p50 5,25 ms | `l1-16k-r*` | Trace: 4 Callbacks/Kommando erwartbar |
| L1 REPLUG 64 KiB ×3 | **PASS** · 9 cmd · live ~8,3 s · sg p50 ~5,2 ms | `l1-64k-r*` | Trace: 16 Callbacks/Kommando |
| L2 Dump 48k (lab/play) | **PASS** · hörbar ~**8,25 s** Live 22,05 kHz mono, dann Stille 44,1 kHz | `l2c-48k.bin`, `l2c-48k-silence.txt` | PC-Fenster = Ringmodell; HU 5–6 s = Anlauf/Format (R25) |
| L2 Dump via Body-Read-Trigger | **FAIL** · `play.reject plug_window/prefetch` → nur Stille | `l2-48k.*` | Play-Detect: nicht „mittig antippen“ |
| L3 Q12 | **GEKLÄRT** · Reject `not_from_head` (+ prefetch); GW PASS after RST / no-RST | `l3-*-events.json` | Mitte-Reads starten keinen Stream |
| L4 200 USB-Zyklen | **nicht gelaufen** (Zeit/Autorize-Risiko) | — | vor s4 optional |
| L5 Langlauf | **nicht gelaufen** | — | Nacht optional |

**s3 Live-Window (Nachrechnung):** fav2-Episoden ~**8,26–8,41 s** Live @48k — siehe `feld-s3-prep/s3-…/live-window/`.

Reboots: 0 in L0–L3.  
Offene Blocker vor s4: L4 Versorgung optional; Name-Override nur mit OTG-ab.  
**Freigabe der Werkzeuge für s4: JA** (L0 PASS).

## Kurzfazit

Lab bestätigt das s3-Muster bytegenau: Ring voll → Replug-Read liefert **~8,2 s** Live, danach Stille; Formatwechsel 22,05 mono → 44,1 stereo sichtbar. Play-Detect lehnt Mid-File ab (`not_from_head`). Stall weiter Freeze.
