# Counter semantics (FW 0.4.36-dev source)

Verified in `esp32.pidrive` `UsbMscGadget.cpp` / `.h` / `StreamBuffer.h` on 2026-10-02.

## `msc.streamBytes` (= `streamBytesServed_`)
- Incremented **only** when a host MSC read hits the **active live stream slot** and data is served via `stream_->readAt(...)` (overlay path).
- Silence/Xing fills for non-live slots do **not** increment `streamBytes` (they may increment `preWarmHostBytes` when pending overlay UID matches).
- Reset to 0 on media plug (`streamBytesServed_ = 0` in plug path).
- **Not** equal to `sum(slotMap[].maxSeq)` or `sum(slotMap[].bytes)`. Those are independent scan/depth stats.

## `msc.readOverflow` (= `readOverflowCount_`)
- Incremented in `enqueuePendingRead` when the **telemetry pending queue** (`kPendingReads`) is full: oldest sample dropped, overflow++.
- Does **not** mean the USB/MSC data response failed — host still got sectors; only the **read-event log/export queue** lost a sample.
- Distinct from `ov` snapshot exported on each flush (`b.overflow = readOverflowCount_`).
- Flat during a quiet poll window only shows it did not keep rising *in that window* (hypothesis: burst-phase queue pressure) — not proof of when it was incremented without a time series through the burst.

## `live_ratio`
- **Not** an ESP status field. Computed in Lab harness/scripts as live-served bytes vs total read/silence mix (e.g. `paced_uid_compare.py`).

## `cursorArmed` / `hostAbsCursor`
- Live in `StreamBuffer`: armed on near-head / seek-back; then sequential host consumption advances `hostAbsCursor_`.
- Field Auto passes often showed `cursorArmed=false` while Lab paced showed true + advancing cursor.

## Lab re-read trigger already present
- `POST /api/lab/remount` — present since ~0.4.24; bumps serial/remountGen; used to force host re-enumeration.
- Play-detect knobs already runtime via `POST /api/config` (`playPlugWindowMs`, `playMinSeqBytes`, …).
- SoftAP lab: `/api/lab/play|stop|stream|overlay_read|listen|cover`.
- Host replay: `tools/nbt_suite.py` / `nbt_replay.py` (needs Proxmox `/dev/sg0`).

**Decision:** No separate probe-FW repo — instrumentation + remount/config APIs already cover HU analysis scaffolding; BMW cache questions remain Auto-only (B7/150s).

## `msc.readCount` / `msc.readsEmit` (M0 Lab 2026-10-03)

- `readCount`: SCSI-/Host-Read-Ereignisse; Reset nur an **USB-Plug-Kante** (`onUsbPlugged`), **nicht** bei Soft-`remountMedia`.
- `readsEmit`: Anzahl **Burst-Flushes** an den Pump-Client (`noteReadsEmitted` nach `flushReadBurst`); Aggregation `kBurstGapMs=50`, `kBurstMaxN=32`.
- Normative Fenster-Gleichung: **`ΔreadCount = Σ(burst.n) + ΔreadOverflow`**.
- Zusätzlich: **`ΔreadsEmit = Anzahl JSONL-Zeilen`** im gleichen Fenster (Lab PASS).
- Ohne verbundenen `pump_bridge`: `readsEmit` bleibt 0 und `/tmp/pidrive_msc_reads.jsonl` wächst nicht — trotz steigendem `readCount`.
