#!/usr/bin/env bash
# Verify the pushed image: both architectures, matching tags, smoke probes, private scan.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/image_common.sh
V="$(tr -d '[:space:]' < VERSION)"
platforms="$(docker buildx imagetools inspect --raw "$IMAGE:$V" \
  | jq -r '.manifests[].platform | select(.os == "linux") | .os + "/" + .architecture' | sort | tr '\n' ' ')"
[ "$platforms" = "linux/amd64 linux/arm64 " ] || { echo "unexpected platforms: $platforms" >&2; exit 1; }
digest() { docker buildx imagetools inspect "$1" --format '{{json .Manifest}}' | jq -r .digest; }
D="$(digest "$IMAGE:$V")"
for tag in "${V%.*}" latest; do
  [ "$(digest "$IMAGE:$tag")" = "$D" ] || { echo "$IMAGE:$tag does not point at $D" >&2; exit 1; }
done
docker pull --quiet --platform linux/amd64 "$IMAGE@$D" >/dev/null
NAME="dinnerbell-verify"
PORT=18081
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm "$NAME" >/dev/null 2>&1 || true' EXIT
docker volume create "$NAME" >/dev/null
docker run -d --name "$NAME" --platform linux/amd64 -p "127.0.0.1:$PORT:8080" -v "$NAME:/data" \
  -e APP_BASE_URL="http://localhost:$PORT" -e APP_SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n')" \
  -e APP_PASSWORD=smoke-password-0000 -e TZ=Etc/UTC "$IMAGE@$D" >/dev/null
wait_healthy "$NAME" 90
probe "$PORT" "$V"
uv run --quiet --no-project --python 3.14 scripts/private_scan.py image "$IMAGE@$D"
echo "Verified $IMAGE:$V ($D): amd64 + arm64, tags agree, probes pass, private scan clean."
