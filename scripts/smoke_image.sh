#!/usr/bin/env bash
# Build an amd64 image from `git archive REF`, run it, and probe it (docs/PLAN.md §11.9).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/image_common.sh
REF="${1:-HEAD}"
image_args "$REF"
TAG="dinner-bell:smoke"
NAME="dinnerbell-smoke"
PORT=18080
SECRET="$(openssl rand -base64 48 | tr -d '\n')"

cleanup() {
  docker rm -f "$NAME" "$NAME-root" "$NAME-novol" >/dev/null 2>&1 || true
  docker volume rm "$NAME" "$NAME-root" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "Building $TAG from $REF (version $V, linux/amd64)…"
git archive --format=tar "$REF" | docker buildx build "${ARGS[@]}" --platform linux/amd64 -t "$TAG" --load -

run_app() {
  local name="$1"; shift
  docker run -d --name "$name" --platform linux/amd64 "$@" \
    -e APP_BASE_URL="http://localhost:$PORT" -e APP_SECRET_KEY="$SECRET" \
    -e APP_PASSWORD=smoke-password-0000 -e KROGER_MODE=fake -e TZ=Etc/UTC "$TAG" >/dev/null
}

docker volume create "$NAME" >/dev/null
run_app "$NAME" -p "127.0.0.1:$PORT:8080" -v "$NAME:/data"
wait_healthy "$NAME" 90
probe "$PORT" "$V"
[ "$(docker exec "$NAME" id -u)" = 10001 ] || { echo "not running as uid 10001" >&2; exit 1; }

docker restart "$NAME" >/dev/null
wait_healthy "$NAME" 90
copies="$(docker exec "$NAME" sh -c 'ls /data/backups/pre-migrate 2>/dev/null | wc -l' | tr -d ' ')"
[ "$copies" = 0 ] || { echo "a restart took a new pre-migration backup" >&2; exit 1; }

# Negative cases: a root-owned volume and no volume at all must both refuse to start (exit 73).
docker volume create "$NAME-root" >/dev/null
docker run --rm --platform linux/amd64 --user 0 --entrypoint sh -v "$NAME-root:/data" "$TAG" \
  -c 'chown 0:0 /data && chmod 755 /data'
run_app "$NAME-root" -v "$NAME-root:/data"
[ "$(docker wait "$NAME-root")" = 73 ] || { echo "root-owned volume did not exit 73" >&2; exit 1; }
run_app "$NAME-novol"
[ "$(docker wait "$NAME-novol")" = 73 ] || { echo "missing volume did not exit 73" >&2; exit 1; }

echo "Smoke test passed for $V ($REF)."
