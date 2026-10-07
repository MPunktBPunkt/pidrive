#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/f1-stick"
DEST="${1:?Usage: $0 /mnt/stick}"
test -d "$SRC" || { echo "kein f1-stick/; erst make-f1-stick.sh"; exit 1; }
mkdir -p "$DEST"
cp -av "$SRC"/F1-*.mp3 "$SRC"/F1-INDEX.json "$SRC"/F1-STICK.md "$DEST"/
sync
ls -lah "$DEST"/F1-*
echo "OK → $DEST"
