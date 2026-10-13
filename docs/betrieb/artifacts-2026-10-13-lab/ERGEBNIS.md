# Lab D-Startgate / HU-A1 · 2026-10-13

**Host:** DebianCursor `192.168.178.187`  
**ESP Lab:** `.88` · FW **`0.4.51-dev`**  
**OTG:** `/dev/sda` + `/dev/sg0` · UART: **nicht angeschlossen**  
**Repos:** `pidrive` (`lab_d_campaign.py` / `nbt_hu_sim.prep_lab`) + `esp32.pidrive` soft-remount Phase-Fix

## Überblick Analyse (Eingang)

| Quelle | Kern |
|--------|------|
| `ANALYSE-D-RESUME-IDENTITY-2026-10-13.md` | Rock-stumm ≠ monokausal Resume-P; Silence-Prefetch-Cache ist starke Inferenz |
| Audits 2026-10-13 (technology-audit) | NBT-Index liefert keinen Live-Cache-Beweis; HU-A1 zuerst |
| Runbook `LAB-D-STARTGATE-RUNBOOK.md` | Lab = Mechanik; NBT entscheidet Resume/Cache |

## Firmware-Fixes heute

| Version | Inhalt |
|---------|--------|
| **0.4.50** | `ConfigStore.fatVolumeId` (Upload `35fa1b1` war unvollständig); BPB-ID/Label in Status |
| **0.4.51** | Soft-Remount setzt `phase=Idle` + cleared stall/playGuess — sonst bleibt `phase=Play`, Quiet feuert nie, `indexSettled` bleibt false → dauernd `play.reject plug_window` |

Lab-Tooling: Stream stoppen vor Remount; Prefetch ohne TCP-Producer; vor Head-Tip `lab/stop`; Quiet-Settle nach Remount.

## Preflight

| Check | 0.4.49 | 0.4.50+ |
|-------|--------|---------|
| SG + OTG + Serial stabil | ok | ok |
| `no_reboot_observed` (`uptimeMs`) | FAIL | **PASS** (`preflight-050/`) |
| UART | skipped | skipped |

## HU-A1 Replay

Gemeinsames Prefetch-Muster:

| Prefetch fav0 | Wert |
|---------------|------|
| Bytes | 8 294 400 |
| Coverage | **98,877 %** (S6: 98,88 %) |
| Klassen | **ID3:1 · SILENCE:2024** |

### Auf 0.4.51 (kanonisch)

| Selection | PASS | gate_green | stall_armed | Artefakt |
|-----------|------|------------|-------------|----------|
| `no-read` | ✅ | false | false | `a1-no-read-051/` |
| `mid` | ✅ | false | false | `a1-mid-051/` |
| `head` | ✅ | **true** | **true** | `a1-head-051/` |

Head-Events: `play.guess fav0` → `msc.stall_armed fav0`; cold_body `set=1`.

Frühere Läufe (`a1-*-r3`, `a1-*-050*`): Prefetch/Klassen ok, aber ohne 0.4.51 kein Lab-`gate_green` (Remount-Phase-Deadlock).

## Identity-Smoke (0.4.50, vor 0.4.51)

| Dimension | PASS | nur deklarierte Drift |
|-----------|------|------------------------|
| `volume-id` | ✅ | ✅ |
| `label` | ✅ | ✅ (BPB+Root gemeinsam) |
| `serial` | ✅ | ✅ |

Artefakte: `identity-volume-id/`, `identity-label/`, `identity-serial/`

## Freeze

`stallEnable=false` auf `.88`.

## Nächste Schritte

1. UART physisch → `lab_uart_reset_log.py`
2. Kurzes NBT-F0: Cache-/Resume-Wirkung der Identity-Dimensionen
3. Danach D1–D3 Fixed-Huge-Leiter
