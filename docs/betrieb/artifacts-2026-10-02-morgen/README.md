# Artefakte 2026-10-02 Morgen — Auto OTA 0.4.36 + Lab-Nacharbeit

**Feldbericht:** [FELDTEST §11.8](../FELDTEST-ESP-MSC-BMW-2026-09-28.md)


## Feld (Auto `.89`, abgebrochen / unterwegs)

| Beobachtung (Ohr) | Lesart |
|-------------------|--------|
| **Rock Antenne (`fav0`)**: Ton **sofort** + ID3-Cover | Live-Pfad + Cover ok nach Replug `PD0018` |
| **Rock Antenne Bayern (`fav1`)**: Ton erst **Mitte** | frühe Reads Silence/Stub; Live erst später im Slot |
| ~2 s Spot wiederholt sich | HU-Kurzloop / Underrun-Fill, kein Endlos-Live |
| Hotspot gleiche SSID | ESP am Handy-LAN, **nicht** `192.168.178.89` vom Heimnetz |

OTA: `0.4.34` → **`0.4.36-dev`**. Bridge hing auf Lab `.88`, umgestellt auf `.89`; `pump.play_replay` wirkte.

## Pi-Logs (gesichert)

- `bridge-session-20261002.txt` / `bridge-session-compact.txt` — Session ab Bridge-Start 07:26
- `pidrive_msc_reads.jsonl` — MSC-Read-Events
- `esp89-*-*.json` — Status/Events Snapshots

SlotMap Snapshot (~07:28, vor Replug): `fav0` maxSeq≈356 KiB / `fav1` maxSeq≈168 KiB — Bayern deutlich weniger sequentiell vom Head.

## Lab `.88` (Proxmox `sg0`, Bridge auf `.88`)

Suite `20261002-080518`:

| Scenario | Overall | Hinweis |
|----------|---------|---------|
| sequential_past_head | **PASS** | live_ratio=1.0 |
| burst_then_quiet | WARN | |
| head_reread_after_quiet | WARN | streamΔ=0 |
| prefetch_then_warm | **FAIL** | Suite-Race: Stream nicht auf `fav2` armed → streamΔ=0 |

**Rerun armed** (`prefetch_then_warm__rerun__20261002`): **WARN** wie Baseline B6 — `preΔ=0`, `streamΔ=180224`, `live_ratio≈0.22` (Underrun-Silence; Ring-Prefill nächster Hebel).

Paced `fav0` vs `fav1`: siehe `nbt-lab88/paced-fav0-fav1.json` / `paced-compare.log`.

## Nächster Code-/Lab-Hebel

1. Ring vor Burst füllen → `live_ratio` → 1.0 (klärt Mitte-Ton + 2 s-Loop mit)
2. Suite: vor `prefetch_then_warm` hart auf Ziel-UID armed warten (heutiger False-FAIL)
3. Feld daheim: Sync-Marker + Replug + Ohr `fav0`/`fav1`/`fav2` getrennt

## Guard-Fix Lab (~10:31)

- Bridge `started_at` Debounce deployed — `lab_guard_switch_test.log` **PASS** (`switch … age=9s`, `ignore rapid … age=2.3s<4s`)
- Prefetch nach Fix: `prefetch_then_warm__guardfix__20261002.summary.json`
