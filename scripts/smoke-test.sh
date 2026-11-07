#!/usr/bin/env bash
# Smoke-test a built image: dependencies import, CLI runs, privileges drop, webhook handshake works.
# Usage: scripts/smoke-test.sh <image>
set -euo pipefail
IMAGE=${1:?image}
NAME=aria-smoke-$$
PORT=${SMOKE_PORT:-18099}
DATA=$(mktemp -d)
chmod 777 "$DATA"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$DATA"; }
trap cleanup EXIT
fail() { echo "FAIL: $*"; docker logs "$NAME" 2>&1 | tail -30 || true; exit 1; }

echo "== imports and CLI"
docker run --rm --entrypoint python "$IMAGE" -c "import garminconnect, curl_cffi, cryptography, google.auth, google_auth_oauthlib; print('imports ok')"
docker run --rm "$IMAGE" --help >/dev/null

echo "== container start"
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8080" \
  -e ARIA_SYNC_WEBHOOK_PATH=/hook/smoke -e "ARIA_SYNC_WEBHOOK_SECRET=Bearer smoke" \
  -v "$DATA:/data" "$IMAGE" >/dev/null
for _ in $(seq 1 30); do
  docker logs "$NAME" 2>&1 | grep -q "Webhook receiver listening" && break
  sleep 1
done
docker logs "$NAME" 2>&1 | grep -q "Webhook receiver listening" || fail "receiver did not start"

echo "== runs as 99:100"
docker exec "$NAME" grep -qE '^Uid:\s+99\s' /proc/1/status || fail "main process is not uid 99"
[ "$(stat -c %u "$DATA/state.db")" = 99 ] || fail "state.db not owned by 99"

echo "== webhook handshake"
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
[ "$(code -X POST -H 'Authorization: Bearer smoke' -d '{"type":"verification"}' "http://127.0.0.1:$PORT/hook/smoke")" = 200 ] || fail "handshake with secret"
[ "$(code -X POST -d '{"type":"verification"}' "http://127.0.0.1:$PORT/hook/smoke")" = 401 ] || fail "handshake without secret"
[ "$(code "http://127.0.0.1:$PORT/")" = 404 ] || fail "root path should 404"

echo "== sync loop survives missing tokens"
sleep 2
docker inspect -f '{{.State.Running}}' "$NAME" | grep -q true || fail "container exited"
docker logs "$NAME" 2>&1 | grep -q "No Google token" || fail "expected a handled 'No Google token' failure"

echo "== graceful stop"
start=$(date +%s); docker stop -t 20 "$NAME" >/dev/null
[ $(( $(date +%s) - start )) -lt 10 ] || fail "stop took too long"
docker logs "$NAME" 2>&1 | grep -q "Stopped" || fail "did not log clean shutdown"

echo "SMOKE TEST PASSED"
