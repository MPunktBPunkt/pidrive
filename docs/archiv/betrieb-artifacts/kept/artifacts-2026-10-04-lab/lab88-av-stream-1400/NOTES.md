# Lab AV metrics — 2026-10-04T14:06:41

## 1. bufferMs is dead telemetry

In `esp32.pidrive` `App.h` / `App.cpp`, `bufferMs` is only initialized to 0 and exported in `/api/status`.
There are **no assignments** elsewhere in the firmware tree.

**Lab proof:** during `lab/play fav1` + ffmpeg, StreamBuffer `size` grew to 49152 (full) while `bufferMs` remained 0 every second.

→ Stop using `bufferMs=0` as evidence of empty audio path.

## 2. Real AV metric: streamBytes vs underruns

| Case | streamBytes | underruns | live≈ |
|------|-------------|-----------|-------|
| Field PD0058 fav1 play | 311296 | 311296 | **0** |
| Lab play, ring filling, no host dd | 57344 (stale/cum) | 0 | n/a (no new serve) |

Field PD0058: Detect+ffmpeg OK, but host got **underrun silence only**.

## 3. Poll (lab, no host read)

```
t=1 play=fav1 und=0 sb=57344 size=6144 buf=0 live=57344
t=2 play=fav1 und=0 sb=57344 size=16168 buf=0 live=57344
t=3 play=fav1 und=0 sb=57344 size=26192 buf=0 live=57344
t=4 play=fav1 und=0 sb=57344 size=35192 buf=0 live=57344
t=5 play=fav1 und=0 sb=57344 size=46024 buf=0 live=57344
t=6 play=fav1 und=0 sb=57344 size=49152 buf=0 live=57344
t=7 play=fav1 und=0 sb=57344 size=49152 buf=0 live=57344
t=8 play=fav1 und=0 sb=57344 size=49152 buf=0 live=57344

```
