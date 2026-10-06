#!/usr/bin/env bash
# Build and push the multi-arch release image from `git archive vX.Y.Z` (docs/PLAN.md §11.9).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/image_common.sh
V_FILE="$(tr -d '[:space:]' < VERSION)"
REF="v$V_FILE"
git rev-parse -q --verify "refs/tags/$REF" >/dev/null || { echo "tag $REF does not exist" >&2; exit 1; }
image_args "$REF"
if docker buildx imagetools inspect "$IMAGE:$V" >/dev/null 2>&1; then
  echo "$IMAGE:$V already exists on Docker Hub; released versions are never overwritten." >&2
  exit 1
fi
echo "Building and pushing $IMAGE:$V (linux/amd64, linux/arm64) from $REF…"
git archive --format=tar "$REF" | docker buildx build "${ARGS[@]}" \
  --platform linux/amd64,linux/arm64 --provenance=mode=min --sbom=false \
  -t "$IMAGE:$V" -t "$IMAGE:${V%.*}" -t "$IMAGE:latest" --push -
echo "Pushed $IMAGE:$V, :${V%.*} and :latest."
