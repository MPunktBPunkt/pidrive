#!/usr/bin/env bash
# Collect technology signals from a target repo (evidence for INVENTORY updates).
# Usage: bash tools/audit_scan.sh /path/to/repo [output.json]
set -euo pipefail

TARGET="${1:?usage: audit_scan.sh /path/to/repo [out.json]}"
OUT="${2:-}"

if [[ ! -d "$TARGET" ]]; then
  echo "not a directory: $TARGET" >&2
  exit 1
fi

# Patterns: category|label|regex
PATTERNS=(
  'bt-media|NimBLE|NimBLE|'
  'bt-media|Heart Rate|180[Dd]|0x180[Dd]'
  'bt-peripheral|GATT Server|createServer|NimBLEServer'
  'web-ui|SSE|/events|text/event-stream'
  'web-ui|HTTP API|/api/|AsyncWebServer'
  'network|WiFiManager|WiFiManager|'
  'network|Hub|HubClient|esp-hub'
  'storage|LittleFS|LittleFS|'
  'embedded|PlatformIO|platformio\.ini|platformio.ini'
  'embedded|ArduinoJson|ArduinoJson|'
  'ci-test|GitHub Actions|\.github/workflows|'
)

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

hits=()
while IFS='|' read -r cat label file_pat content_pat; do
  [[ -z "$content_pat" ]] && content_pat="$file_pat"
  if [[ "$file_pat" == *'/'* ]] || [[ "$file_pat" == *'.'* ]]; then
    mapfile -t files < <(find "$TARGET" -path '*/.git/*' -prune -o -type f -name "$file_pat" -print 2>/dev/null | head -20)
  else
    mapfile -t files < <(rg -l --glob '!.git' "$content_pat" "$TARGET" 2>/dev/null | head -20 || true)
  fi
  count=${#files[@]}
  if [[ "$count" -gt 0 ]]; then
    sample=$(printf '%s;' "${files[@]}" | sed 's;'"$TARGET"'/;;g' | head -c 500)
    hits+=("{\"category\":\"$cat\",\"technology\":\"$label\",\"file_count\":$count,\"sample\":\"$sample\"}")
  fi
done < <(printf '%s\n' "${PATTERNS[@]}")

payload="{\"target\":\"$TARGET\",\"signals\":[$(IFS=,; echo "${hits[*]}")]}"

if [[ -n "$OUT" ]]; then
  printf '%s\n' "$payload" > "$OUT"
  echo "wrote $OUT (${#hits[@]} signals)"
else
  printf '%s\n' "$payload" | python3 -m json.tool
fi
