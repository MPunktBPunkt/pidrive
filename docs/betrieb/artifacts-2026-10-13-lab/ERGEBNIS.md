# Lab D-Startgate / HU-A1 · 2026-10-13

**Host:** DebianCursor `192.168.178.187`  
**ESP Lab:** `.88` · FW **`0.4.50-dev`** (ConfigStore-`fatVolumeId` + Analyse-OTA; gebaut aus `esp32.pidrive` L3)  
**OTG:** `/dev/sda` + `/dev/sg0` · UART: **nicht angeschlossen**  
**Repos:** `pidrive` + lokaler Fix in `tools/lab_d_campaign.py` (Producer vor Prefetch stoppen, `wait_esp`/Pump-Reconnect)

## Überblick Analyse (Eingang)

| Quelle | Kern |
|--------|------|
| `ANALYSE-D-RESUME-IDENTITY-2026-10-13.md` | Rock-stumm ≠ monokausal Resume-P; Silence-Prefetch-Cache ist starke Inferenz |
| Audits 2026-10-13 (technology-audit) | NBT-Index liefert keinen Live-Cache-Beweis; HU-A1 zuerst |
| Runbook `LAB-D-STARTGATE-RUNBOOK.md` | Lab = Mechanik; NBT entscheidet Resume/Cache |

## Preflight

| Check | 0.4.49 | 0.4.50 |
|-------|--------|--------|
| SG READ(10) + OTG stabil + USB-Serial gleich | ok | ok |
| `no_reboot_observed` (`uptimeMs`) | **FAIL** | **PASS** (`preflight-050/`) |
| UART-Logger | skipped | skipped — kein `/dev/ttyACM*` |

Artefakte: `preflight/` (alt), `preflight-050/`

## HU-A1 Replay (r3, getrennt)

Gemeinsames Prefetch-Muster in **allen** Läufen:

| Prefetch fav0 | Wert |
|---------------|------|
| Bytes | 8 294 400 |
| Coverage | **98,877 %** (S6: 98,88 %) |
| Klassen | **ID3:1 · SILENCE:2024** |

| Selection | PASS | observed | gate_green | Bemerkung |
|-----------|------|----------|------------|-----------|
| `no-read` | ✅ | no-read | false | keine Post-Select-Reads; erwartet |
| `mid` | ✅ | mid @1 MiB | false | LIVE nach fav0-Arm (Overlay) |
| `head` | ✅ | head | **false** | LIVE ja, aber **`stall.armed=false`** |

Artefakte: `a1-no-read-r3/`, `a1-mid-r3/`, `a1-head-r3/`  
(r1/r2: Prefetch schon belegt, Selection-Phase an TCP/HTTP-Timeouts gescheitert → Tool gehärtet)

### gate_green

Runbook: Lab-`gate_green` = Head-Read ∧ S7 armed ∧ LIVE.  
Hier: Head+LIVE ✅, S7-B armed ❌ (`skipNotArmed` steigt, `stall.cmds` bleibt alt).  
`playing_uid` im Final-Snap blieb `fav2` trotz `audio_start fav0` — Play-Guess/S7-Pfad greift in diesem Sim-Ablauf nicht wie am NBT. **Kein NBT-Resume-Beweis; kein D1-Go.**

## Media-/Identity

### Vorher (0.4.49)

- BPB Volume-ID fest `0x041ED56F`, BPB-Label **`PIDRIVE`**
- Root-Label **`PD0xxx`** → Identity unvollständig

### Fix + OTA 0.4.50

- `ConfigStore.fatVolumeId` ergänzt (Upload `35fa1b1` war ohne ConfigStore-Feld unvollständig)
- L3-Build `pidrive-s3-l3` → `dist/pidrive.0.4.50-dev.ota.esp32s3.bin` → OTA `.88`
- Status: `uptimeMs` / `resetReason` / `bpbVolumeId` / `bpbLabel`=`rootLabel` / `transportEpoch`

| Identity-Smoke | PASS | Drift nur deklarierte Dimension | Device↔Status |
|----------------|------|----------------------------------|---------------|
| `volume-id` | ✅ | ✅ (`bpbVolumeId` 0x…B4→B5) | ✅ |
| `label` | ✅ | ✅ (BPB+Root gemeinsam `PD0436X`) | ✅ |

Artefakte: `identity-volume-id/`, `identity-label/`, `identity-plan/`

## Freeze

Nach Kampagne und Identity-Smoke: `stallEnable=false`.

## Nächste Schritte

1. UART physisch verbinden → `lab_uart_reset_log.py`.
2. Head-Pfad so fahren, dass Play-Guess/S7 armed messbar wird → Lab-`gate_green`.
3. Identity `serial` + NBT-F0 nach reproduzierbarem Startmechanismus.
4. Commits: `esp32.pidrive` 0.4.50 + `pidrive` Lab-Artefakte/`lab_d_campaign.py`-Härtung (noch lokal).
