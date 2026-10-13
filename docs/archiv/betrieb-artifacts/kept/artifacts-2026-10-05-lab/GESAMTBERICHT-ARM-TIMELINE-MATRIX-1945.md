# Lab Arm-Timeline Matrix · 2026-10-05 ~19:45 (.88)

**Tool:** `tools/m3_lab_arm_timeline.py` (ab e1a8ab2 + Bridge-Mimic)  
**FW:** `0.4.45-dev` · Serial PD0062→… · Seed aus · Freeze hält

## Kernbefund

**`hostAbs=253952` ist reproduzierbar als Underrun-Zähler**, nicht als persistierter Cursor:

| | Feld 18:07 | Lab `1945-empty248` |
|--|------------|---------------------|
| hostAbsCursor | 253952 | **253952** |
| streamBytes | 253952 | **253952** |
| underruns | 253952 | **253952** |
| liveBytes | 0 | **0** |
| Arm-Start | (unbekannt) | `hostAbs=4096`, `absBase=0` |

Ablauf Lab: soft_rst → Head-Tip → **bridge-mimic `audio_start`** (Ring leer) → 248 KiB Post-Head-Reads = **62×4096**.

Ohne `audio_start` bleibt `streamBytes=0` / `cursorArmed=false` (Läufe 1938–1940) — Detect allein öffnet den Live-Pfad nicht (Feld: Bridge startet ffmpeg nach `play_uid`).

## Matrix (Bridge-Mimic)

| Out | Label | Prep | Arm-Übergang host/absBase | End host / live | Notiz |
|-----|-------|------|---------------------------|-----------------|--------|
| `1945-empty248` | empty_bridge_248k | soft_rst | **4096 / 0** | **253952 / 0** | **Feld-253952 1:1** |
| `1946-prefill` | prefill96_bridge | soft_rst+96KiB | 52736 / 49152 in_window | 126464 / 49664 | Prefill: Arm im Fenster |
| `1947-C` | versuch_C_bridge | soft_rst+prod 5s | 44544 / 40960 in_window | 118272 / 49664 | Versuch C: Arm ≈ absBase |
| `1948-mid` | mid256_bridge | soft_rst+mid 256 | 4096 / 0 | 65536 / 0 | Mid vor Tip ändert Cursor-Start nicht (Arm bei 0) |
| `1949-remount` | remount_after_prior | usb_remount | (verschmutzt) | — | Remount ohne RST: Zustand von Vorlauf bleibt (vgl. 1936) |
| `1950-rst-remount` | rst_remount_bridge | rst_remount | 4096 / 0 | 65536 / 0 | wie empty, kürzerer Post-Head |

Frühere Läufe ohne Bridge-Mimic (`1936`–`1940`, `1845`): Remount erhält Cursor; Head ohne `audio_start` → kein Live-Pfad.

## Folgerung

1. **GPT-Mechanik bestätigt** im Lab: Arm auf `absBase` → Cursor++ bei Underrun → 253952 = Byte-Zähler.  
2. **Mistral „alter Cursor“** für 253952 **verworfen**.  
3. Feld 18:07-Geometrie (Fenster voraus) entsteht, wenn Producer **nach** frühem Arm weiterläuft — nächster Schritt: Prefill-/Pace-Timing, kein Snap-Blindfix.  
4. Lab-Host ≠ NBT: RST→Head der **HU** bleibt Feld-Stichprobe; Lab mimt Head-Reads gezielt.

## Nächstes

- Bridge/Prefill: Arm erst, wenn Ring gefüllt **oder** Host-Pace ≤ Producer (kein FW-Snap ohne Abstimmung).  
- Optional Feld: dense Correlate ab `audio_start` (Timeline wie 1945).  
- Freeze hält.
