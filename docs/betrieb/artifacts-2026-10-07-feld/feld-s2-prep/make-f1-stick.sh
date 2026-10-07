#!/usr/bin/env bash
# F1-MP3s auf Stick/Ordner bauen (Protokoll Teil E).
set -euo pipefail
cd /home/martin/projects/pidrive
OUT="${1:-$PWD/docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/f1-stick}"
SIZES="${SIZES:-5mb,100mb}"
mkdir -p "$OUT"
if ! command -v espeak-ng >/dev/null && ! command -v espeak >/dev/null; then
  echo "Warnung: kein espeak-ng — Beep-Fallback. Auf dem Pi: sudo apt-get install -y espeak-ng" >&2
fi
# BR=128k: 100MB-Datei in 1,8 h statt 4,8 h, ~0,35 GB statt ~0,9 GB Temp-WAVs
extra=()
[[ -n "${TMP_DIR:-}" ]] && extra+=(--tmp-dir "$TMP_DIR")
exec python3 tools/feld_f1_make_stick.py --out-dir "$OUT" --sizes "$SIZES" --br "${BR:-48k}" "${extra[@]}"
