#!/usr/bin/env bash
# End-to-end smoke test against a running stack (web on :9090):
# health, register, activity import, feed, version.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="http://localhost:9090/api/v1"

echo "Waiting for the API to become healthy..."
healthy=""
for _ in $(seq 1 90); do
    if curl -fsS "$BASE/health" | grep -q '"status":"ok"'; then
        healthy=1
        break
    fi
    sleep 1
done
[ -n "$healthy" ] || { echo "error: API did not become healthy within 90s" >&2; exit 1; }

echo "Health: ok"
VERSION="$(curl -fsS "$BASE/health" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
echo "API version: $VERSION"

# Log in with a throwaway account, registering it on a first run.
echo "Authenticating..."
TOKEN="$(curl -s -X POST "$BASE/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"smoke@example.com","password":"supersecret1"}' \
    | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("token", ""))
except Exception:
    pass' || true)"
if [ -z "$TOKEN" ]; then
    TOKEN="$(curl -fsS -X POST "$BASE/auth/register" \
        -H 'Content-Type: application/json' \
        -d '{"first_name":"Smoke","last_name":"Test","email":"smoke@example.com","password":"supersecret1"}' \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
fi

echo "Importing a sample GPX activity..."
curl -fsS -X POST "$BASE/activities" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@api/tests/fixtures/run_sample.gpx;type=application/octet-stream" \
    > /dev/null

echo "Checking the feed..."
curl -fsS "$BASE/activities" -H "Authorization: Bearer $TOKEN" \
    | python3 -c 'import json,sys; data = json.load(sys.stdin); assert data["total"] >= 1, data'

echo "Smoke test passed."
