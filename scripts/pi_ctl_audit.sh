#!/bin/bash
# PiDrive pidrivectl + WebUI audit — auf dem Pi ausführen
set -u
PASS=0; WARN=0; FAIL=0; SKIP=0
log() { echo "$@"; }

run_cmd() {
  local name="$1"; shift
  local timeout="${1:-15}"; shift
  local out rc lines
  out=$(timeout "$timeout" "$@" 2>&1) || rc=$?
  rc=${rc:-0}
  lines=$(echo "$out" | wc -l)
  if [ "$rc" -eq 124 ]; then
    echo "TIMEOUT  $name"
    ((WARN++)) || true
    return
  fi
  if [ "$rc" -ne 0 ]; then
    echo "FAIL($rc) $name"
    echo "$out" | head -3
    ((FAIL++)) || true
    return
  fi
  if [ -z "$(echo "$out" | tr -d '[:space:]')" ]; then
    echo "EMPTY    $name"
    ((WARN++)) || true
    return
  fi
  if [ "$lines" -lt 1 ]; then
    echo "THIN     $name (${lines} lines)"
    ((WARN++)) || true
  else
    echo "OK       $name (${lines} lines)"
    ((PASS++)) || true
  fi
  echo "$out" | head -2 | sed 's/^/  | /'
}

echo "======== PiDrive Audit $(date) ========"
echo "Version: $(pidrivectl version 2>/dev/null || echo '?')"
echo ""

echo "=== STATUS ==="
run_cmd "status" 10 pidrivectl status
run_cmd "now" 10 pidrivectl now
run_cmd "quick" 10 pidrivectl quick
run_cmd "version" 5 pidrivectl version
run_cmd "status --json" 10 pidrivectl --json status

echo ""
echo "=== STATION LISTS ==="
run_cmd "station list web" 15 pidrivectl station list web
run_cmd "station list dab" 15 pidrivectl station list dab
run_cmd "station list fm" 15 pidrivectl station list fm

echo ""
echo "=== FAVORITES ==="
run_cmd "favorites list" 10 pidrivectl favorites list

echo ""
echo "=== AUDIO / VOLUME ==="
run_cmd "audio status" 10 pidrivectl audio status
run_cmd "volume (show)" 10 pidrivectl volume
run_cmd "ppm status" 10 pidrivectl ppm status

echo ""
echo "=== DAB ==="
run_cmd "dab status" 10 pidrivectl dab status
run_cmd "dab live 2s" 5 timeout 3 pidrivectl dab live

echo ""
echo "=== BT (read-only) ==="
run_cmd "bt status" 15 pidrivectl bt status
run_cmd "bt known" 15 pidrivectl bt known
run_cmd "bt devices" 15 pidrivectl bt devices

echo ""
echo "=== SYSTEM ==="
run_cmd "system" 15 pidrivectl system
run_cmd "system info" 15 pidrivectl system info
run_cmd "system resources" 20 pidrivectl system resources

echo ""
echo "=== PLAYLIST / LOG ==="
run_cmd "playlist" 10 pidrivectl playlist
run_cmd "log" 15 pidrivectl log

echo ""
echo "=== DEBUG ==="
run_cmd "debug state" 10 pidrivectl debug state
run_cmd "debug dab" 10 pidrivectl debug dab
run_cmd "debug audio" 10 pidrivectl debug audio
run_cmd "debug source-state" 10 pidrivectl debug source-state

echo ""
echo "=== AVRCP (read-only) ==="
run_cmd "avrcp status" 10 pidrivectl avrcp status
run_cmd "avrcp events" 10 pidrivectl avrcp events

echo ""
echo "=== PLAY (short) ==="
run_cmd "play web 1" 25 pidrivectl play web 1
sleep 8
run_cmd "now after web" 10 pidrivectl now
run_cmd "stop" 15 pidrivectl stop

echo ""
echo "=== SCANNER (stop only) ==="
run_cmd "scanner stop" 10 pidrivectl scanner stop

echo ""
echo "=== WEB UI ==="
WEB=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://127.0.0.1:8080/ 2>/dev/null || echo "000")
echo "HTTP /     -> $WEB"
if [ "$WEB" = "200" ]; then ((PASS++)); else ((FAIL++)); fi
for ep in /api/ping /api/state /api/core /api/runtime; do
  code=$(curl -s -o /tmp/_pi_api.json -w '%{http_code}' --connect-timeout 3 "http://127.0.0.1:8080${ep}" 2>/dev/null || echo "000")
  bytes=$(wc -c < /tmp/_pi_api.json 2>/dev/null || echo 0)
  if [ "$code" = "200" ] && [ "$bytes" -gt 10 ]; then
    echo "OK       GET ${ep} (${bytes} bytes)"
    ((PASS++)) || true
  else
    echo "FAIL     GET ${ep} code=$code bytes=$bytes"
    ((FAIL++)) || true
  fi
done

echo ""
echo "======== SUMMARY: OK=$PASS WARN=$WARN FAIL=$FAIL ========"
