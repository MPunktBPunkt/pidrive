#!/usr/bin/env bash
# Eine Identity-Dimension rotieren (Feld, HTTP). Nie mischen.
# Usage:
#   ./f0-identity.sh status
#   ./f0-identity.sh serial|label|volume-id
#   ./f0-identity.sh verify <before.json> <after.json> <serial|label|volume-id>
set -euo pipefail
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
ROOT="$(cd "$(dirname "$0")" && pwd)"
CMD="${1:-status}"

identity_json() {
  curl -s -m 4 "$ESP/api/status" | python3 -c '
import json,sys
d=json.load(sys.stdin)
m=d.get("msc") or {}
print(json.dumps({
  "usbSerial": m.get("usbSerial"),
  "productRevision": m.get("productRevision"),
  "bpbVolumeId": m.get("bpbVolumeId"),
  "bpbLabel": m.get("bpbLabel"),
  "rootLabel": m.get("rootLabel"),
}, ensure_ascii=False))
'
}

case "$CMD" in
  status)
    identity_json | python3 -m json.tool
    ;;
  serial|label|volume-id)
    DIM="$CMD"
    BEFORE="$ROOT/identity-before-${DIM}.json"
    AFTER="$ROOT/identity-after-${DIM}.json"
    identity_json > "$BEFORE"
    python3 - "$ESP" "$DIM" "$BEFORE" "$AFTER" <<'PY'
import json, sys, urllib.request

esp, dim, before_path, after_path = sys.argv[1:5]

def http(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        esp.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        raw = r.read()
        return json.loads(raw.decode() or "{}")

before = json.load(open(before_path, encoding="utf-8"))
label = str(before.get("bpbLabel") or "PIDRIVE")[:11]
vid = int(before.get("bpbVolumeId") or 0)

if dim == "volume-id":
    target_id = vid ^ 1
    if target_id == 0:
        target_id = 1
    target_label = label
    keep = True
elif dim == "label":
    target_id = vid
    target_label = (label[:10] + "X") if label else "PIDRIVEX"
    if target_label == label:
        target_label = "PIDRIVEY"
    keep = True
else:  # serial
    target_id = vid
    target_label = label
    keep = False

http("POST", "/api/config", {"volumeLabel": target_label, "fatVolumeId": target_id})
http(
    "POST",
    "/api/lab/remount",
    {
        "keepIdentity": keep,
        "volumeLabel": target_label,
        "fatVolumeId": target_id,
    },
)
print(json.dumps({
    "dimension": dim,
    "target_label": target_label,
    "target_id": target_id,
    "keepIdentity": keep,
}, ensure_ascii=False))
PY
    sleep 2
    identity_json > "$AFTER"
    echo "BEFORE $BEFORE"
    echo "AFTER  $AFTER"
    "$0" verify "$BEFORE" "$AFTER" "$DIM"
    ;;
  verify)
    BEFORE="${2:?}"; AFTER="${3:?}"; DIM="${4:?}"
    python3 - "$BEFORE" "$AFTER" "$DIM" <<'PY'
import json, sys
before = json.load(open(sys.argv[1], encoding="utf-8"))
after = json.load(open(sys.argv[2], encoding="utf-8"))
dim = sys.argv[3]
expected = {
    "volume-id": ["bpbVolumeId"],
    "label": ["bpbLabel", "rootLabel"],
    "serial": ["productRevision", "usbSerial"],
}[dim]
diffs = sorted(k for k in before if before.get(k) != after.get(k))
ok = diffs == expected
print(json.dumps({
    "dimension": dim,
    "before": before,
    "after": after,
    "changed_fields": diffs,
    "expected_changed_fields": expected,
    "isolation_pass": ok,
}, ensure_ascii=False, indent=2))
sys.exit(0 if ok else 1)
PY
    ;;
  *)
    echo "Usage: $0 status|serial|label|volume-id|verify <before> <after> <dim>" >&2
    exit 1
    ;;
esac
