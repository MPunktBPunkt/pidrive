# Methodik: MSC-Wahrheit (ab 2026-10-17)

## Problem

Linux `read()` / `dd` auf `/dev/sda` kann aus dem **Page-Cache** bedienen:

- Host sieht z. B. 8 KiB „Daten“
- ESP `bytesRead` / MessCapture: **Δ = 0**

Belegt in `artifacts-2026-10-16-lab/id3-chain-20261017T065304Z/` (erster Versuch vs. SG_IO).

## Regel

| Erlaubt als Beweis | Nicht als MSC-Beweis |
|--------------------|----------------------|
| SG_IO auf `/dev/sg0` (`tools/sgio_read10.py`) | `read()` / `pread` / `dd` ohne ESP-Korrelation |
| O_DIRECT mit Alignment | „Host hexdump sieht ID3“ allein |
| ESP MessCapture `op=40` + Δbytes | |

## Folge für ältere Lab-Artefakte

Ergebnisse, die nur Host-`dd`/`read()` ohne ESP-Δbytes dokumentieren, tragen einen **methodischen Warnhinweis** — sie widerlegen keine Feld-HU-Fakten, dürfen aber keine neuen HU-Parameter begründen (siehe B4 / 64er-`pread`).
