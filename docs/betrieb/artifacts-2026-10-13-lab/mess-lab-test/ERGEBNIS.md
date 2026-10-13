# ERGEBNIS — Mess-FW Lab-Test (2026-10-13)

**ESP:** `192.168.178.88` · FW `0.4.52-mess` · `mess.build=mess`

## Verdict

| Test | Ergebnis |
|------|----------|
| Controlled READ10 → `blocks` | **PASS** (512 / 4 KiB / 16 KiB / 64 KiB) |
| Soft-USB `usb_cycle` API | **PASS** (detach→auto-attach, Capture füllt sich) |
| `media_remount` Situation | **PASS** (API ok; Medium kurz not-ready) |
| Host sieht Soft-USB-Disconnect | **PASS (Bus)** — nach `usb_cycle` war `/dev/sg0` kurz `ENXIO`, dann wieder da; **kein VBUS-Power-Zyklus** |

## Controlled READ10 (Q10-Kalibrierung)

Host SG forderte bekannte Größen; Mess-FW meldete exakt:

| Mark | want blocks | got | chunks | dur_us |
|------|------------:|----:|-------:|-------:|
| `r4k` | 8 | 8 | 1 | 3864 |
| `r4k_b` | 8 | 8 | 1 | 3871 |
| `r16k` | 32 | 32 | 4 | 16540 |
| `r64k` | 128 | 128 | 16 | 77311 |
| `r512` | 1 | 1 | 1 | 686 |

`all_pass=True` — Datei: `controlled-read10-summary.json`

## Morgen HU

Mess-FW ist lab-validiert für Kommandogröße. Am Auto: gleiche FW auf Feld-ESP, Bridge an, `mess_hu_capture.py q10` (ggf. mit physischem Replug zusätzlich zu Soft-Cycle).
