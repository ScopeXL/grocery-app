# Shared by smoke_image.sh, image_build.sh and image_verify.sh (sourced, not run).
# Docker comes from OrbStack; its CLI may not be on PATH in every shell.
export PATH="$HOME/.orbstack/bin:$PATH"
IMAGE="scopexl/dinner-bell"
BUILDER="orbstack"

# image_args REF: sets V (version at REF) and ARGS (buildx arguments) from the commit itself.
image_args() {
  local ref="$1"
  V="$(git show "$ref:VERSION" | tr -d '[:space:]')"
  local rev epoch created
  rev="$(git rev-parse "$ref^{commit}")"
  epoch="$(git log -1 --format=%ct "$ref")"
  created="$(TZ=UTC git log -1 --date=format-local:%Y-%m-%dT%H:%M:%SZ --format=%cd "$ref")"
  ARGS=(--builder "$BUILDER" --build-arg "VERSION=$V" --build-arg "REVISION=$rev"
        --build-arg "CREATED=$created" --build-arg "SOURCE_DATE_EPOCH=$epoch")
}

# wait_healthy NAME SECONDS: wait for the container's HEALTHCHECK to pass.
wait_healthy() {
  local name="$1" limit="$2" status
  for _ in $(seq 1 "$limit"); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo missing)"
    [ "$status" = "healthy" ] && return 0
    [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = "false" ] && break
    sleep 1
  done
  echo "container $name did not become healthy (status: $status)" >&2
  docker logs --tail 40 "$name" >&2 || true
  return 1
}

# probe PORT VERSION: the checks every image must pass.
probe() {
  local base="http://127.0.0.1:$1" version="$2"
  curl -fsS "$base/api/health" | grep -q '"ok"'
  [ "$(curl -fsS "$base/api/version" | jq -r .version)" = "$version" ]
  curl -fsS "$base/some/deep/link" | grep -q 'id="root"'
  [ "$(curl -so /dev/null -w '%{http_code}' "$base/api/nope")" = 404 ]
  [ "$(curl -so /dev/null -w '%{http_code}' "$base/assets/missing-123.js")" = 404 ]
  curl -fsS -D - -o /dev/null "$base/" | grep -qi 'content-security-policy'
}
