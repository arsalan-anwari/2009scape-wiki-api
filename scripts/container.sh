#!/usr/bin/env bash
#
# Build, run, check and stop the image, with everything a first start needs done
# for you: a dataset for it to serve, the public half of your issuer key where the
# image reads it, a directory the guard can write its bans into, and a token to
# call it with.
#
# Usage:
#   scripts/container.sh prepare   fill run/data and run/config, start nothing
#   scripts/container.sh up        prepare, build the image, start it
#   scripts/container.sh check     ask it the questions a deployment has to answer
#   scripts/container.sh logs      what the container has said so far
#   scripts/container.sh token     print the token to call it with
#   scripts/container.sh down      stop and remove it
#
# `up` and `prepare` take flags for how the start differs, and `check` asks after
# whichever one was used, so the same questions are asked of every way of starting:
#   --fixture    serve the test fixture instead of fetching the published dataset
#   --compose    start through compose.yaml instead of a plain `docker run`
#   --open       answer everyone rather than only key holders
#
# `up` fetches unless told to use the fixture, so the container serves what everyone
# else can fetch and never a local build. Which dataset and which build of it are
# settings:
#   WIKI_API_HF_REPO_ID=someone/else scripts/container.sh up
#   WIKI_API_HF_REVISION=<commit>    scripts/container.sh up
#
# Nothing here is needed to deploy: it is the same `docker run` a person would
# write, with the four preparation steps that are easy to get wrong done first.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

IMAGE="scape2009-wiki-api:local"
NAME="wiki"
SERVICE="wiki-api"
PORT="${WIKI_API_CONTAINER_PORT:-8000}"
HOST="127.0.0.1"
LABEL="docker"
RUN_DIR="$REPO_ROOT/run"
DATA_DIR="$RUN_DIR/data"
CONFIG_DIR="$RUN_DIR/config"
# How the running container was started, so `check` knows which contract to hold it
# to and `down` knows what it is tearing down. Written by `up`, read by both.
STATE="$RUN_DIR/started"
ARTIFACT="${WIKI_API_ARTIFACT_FILENAME:-knowledge.sqlite3}"
FIXTURE="$REPO_ROOT/tests/fixtures/knowledge"

SOURCE="published"
STARTED="plain"
GUARD="required"

# Two things podman needs and docker does not. It labels every bind mount and then
# refuses the container access to all of them unless told not to, and it builds in the
# OCI image format, which has nowhere to put the HEALTHCHECK this image declares and
# says so twice per build. Neither flag is understood by docker, so neither is passed
# to it.
BUILDING=()
RUNNING=()
if docker --version 2>/dev/null | grep -qi podman; then
  BUILDING=(--format docker --security-opt label=disable)
  RUNNING=(--security-opt label=disable)
fi

say() { printf '  %s\n' "$*"; }

flags() {
  for arg in "$@"; do
    case "$arg" in
      --fixture) SOURCE="fixture" ;;
      --compose) STARTED="compose" ;;
      --open) GUARD="off" ;;
      *)
        echo "container: unknown option '$arg'" >&2
        exit 2
        ;;
    esac
  done
  if [[ "$STARTED" == "compose" ]]; then
    # Asked before anything is fetched or built, so a machine without it says so in
    # one line rather than after a download and an image build.
    if ! docker compose version >/dev/null 2>&1; then
      echo "container: --compose needs \`docker compose\`, which is not installed" >&2
      echo "  podman users want the podman-compose package" >&2
      exit 2
    fi
    if [[ "$GUARD" == "off" ]]; then
      # compose.yaml writes down one deployment, and that deployment answers key
      # holders. Answering everyone is a change to that file, not a flag here.
      echo "container: --open is not a thing --compose can be asked for" >&2
      exit 2
    fi
    # The published port is written down in compose.yaml, so it is not ours to move.
    PORT=8000
  fi
}

remember() { printf '%s %s %s\n' "$SOURCE" "$STARTED" "$GUARD" >"$STATE"; }

recall() {
  if [[ -f "$STATE" ]]; then
    read -r SOURCE STARTED GUARD <"$STATE"
  fi
  if [[ "$STARTED" == "compose" ]]; then
    PORT=8000
  fi
}

token_of() {
  uv run --quiet python - "$LABEL" <<'PY'
import sys
from wiki_api.access import credential_from_file, find_token
from wiki_api.access.paths import config_dir, tokens_dir
kept = find_token(config_dir(), sys.argv[1])
if kept is None:
    raise SystemExit(
        f"no token issued to {sys.argv[1]!r} in {tokens_dir(config_dir())}"
    )
print(credential_from_file(kept).access_token)
PY
}

dataset() {
  # Emptied first, so what the container serves is the dataset as it stands now
  # and never a file left behind by an older start. This directory belongs to
  # this script: nothing else writes here, so nothing else is lost with it.
  rm -rf "$DATA_DIR"
  mkdir -p "$DATA_DIR"
  if [[ "$SOURCE" == "fixture" ]]; then
    # Built rather than fetched, for a check that has to hold with no network and
    # no dataset to reach. It answers the same questions about far less.
    uv run poe build-artifact "$FIXTURE" \
      --destination "$DATA_DIR/$ARTIFACT" \
      --data-version container-check >/dev/null
    say "the test fixture is built into $DATA_DIR"
    return
  fi
  bash scripts/download_data.sh --into "$DATA_DIR" "$ARTIFACT"
}

credentials() {
  local public="$HOME/.config/scape2009-wiki-api/issuer.pub"
  if [[ -n "${WIKI_API_CONFIG_DIR:-}" ]]; then
    public="$WIKI_API_CONFIG_DIR/issuer.pub"
  fi
  if [[ ! -f "$public" ]]; then
    echo "no issuer key yet: run \`uv run poe keys init\` first" >&2
    exit 1
  fi
  # Only the public half is given to the container. The signing key and the issued
  # token stay on this side, as they would on an administrator's machine.
  cp "$public" "$CONFIG_DIR/issuer.pub"

  if ! token_of >/dev/null 2>&1; then
    say "no token issued to $LABEL yet, issuing one"
    uv run poe keys issue --label "$LABEL" >/dev/null
  fi
}

prepare() {
  mkdir -p "$RUN_DIR" "$CONFIG_DIR"
  dataset
  credentials
  # The image runs as a user of its own and the guard writes the addresses it is
  # refusing into this directory, which it cannot do while the directory is ours.
  chmod 0777 "$CONFIG_DIR"
  remember
  say "dataset, public key and a token are ready in $RUN_DIR"
}

answering() {
  local waited="$1"
  for _ in $(seq 1 "$waited"); do
    if curl -fsS "http://$HOST:$PORT/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "the container did not answer in time. What it said:" >&2
  logs >&2 || true
  return 1
}

start() {
  # Built here for both ways of starting, rather than letting compose build its own.
  # compose.yaml names this same tag, so it finds the image already made and starts
  # it: what compose is being asked to prove is its wiring, not a second build. It
  # also keeps the one build in the one place that can pass podman the flags it needs,
  # which no compose file can carry.
  say "building $IMAGE"
  docker build "${BUILDING[@]}" -t "$IMAGE" . >/dev/null

  if [[ "$STARTED" == "compose" ]]; then
    say "starting the compose service"
    docker compose up -d >/dev/null
    return
  fi

  docker rm -f "$NAME" >/dev/null 2>&1 || true
  # A deployment that answers everyone needs no key, so it is given no /config at all:
  # that this works is part of what is being checked.
  local mounts=(-v "$DATA_DIR:/data:ro")
  local guarding=()
  if [[ "$GUARD" == "off" ]]; then
    guarding=(-e WIKI_API_AUTH_MODE=off -e 'WIKI_API_CORS_ORIGINS=["*"]')
  else
    mounts+=(-v "$CONFIG_DIR:/config")
  fi
  docker run -d --name "$NAME" "${RUNNING[@]}" \
    -p "$PORT:8000" \
    -e WIKI_API_SURFACES=both \
    "${guarding[@]}" \
    "${mounts[@]}" \
    "$IMAGE" >/dev/null
}

up() {
  prepare
  start
  answering 60 || exit 1
  if [[ "$GUARD" == "off" ]]; then
    say "answering on http://$HOST:$PORT, both surfaces, everyone"
  else
    say "answering on http://$HOST:$PORT, both surfaces, key holders only"
  fi
  say "check it with: scripts/container.sh check"
}

asked() {
  local what="$1" expected="$2" code
  shift 2
  code="$(curl -sL -o /dev/null -w '%{http_code}' "$@")"
  if [[ "$code" == "$expected" ]]; then
    printf '  WORKED  %-34s %s\n' "$what" "$code"
    return 0
  fi
  printf '  FAILED  %-34s %s, wanted %s\n' "$what" "$code" "$expected"
  return 1
}

check() {
  recall
  local token accept initialise failed=0
  accept='accept: application/json, text/event-stream'
  initialise='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"1"}}}'
  # localhost is ::1 on some machines and the container is listening on ipv4, so
  # every address here is written out rather than resolved.
  asked "health, asked by anyone" 200 "http://$HOST:$PORT/health" || failed=1

  if [[ "$GUARD" == "off" ]]; then
    # The same two questions, of a deployment that was asked to answer everyone.
    # A key nobody has to hold is the whole difference, so no token is fetched.
    asked "the api, with no key" 200 "http://$HOST:$PORT/v1/about" || failed=1
    asked "the tools, with no key" 200 -X POST "http://$HOST:$PORT/mcp" \
      -H 'content-type: application/json' -H "$accept" -d "$initialise" || failed=1
    echo
    say "answering everyone, as this deployment asked to"
    return "$failed"
  fi

  token="$(token_of)"
  asked "the api, with no key" 401 "http://$HOST:$PORT/v1/about" || failed=1
  asked "the api, with the issued key" 200 \
    -H "authorization: Bearer $token" "http://$HOST:$PORT/v1/about" || failed=1
  asked "the tools, with no key" 401 -X POST "http://$HOST:$PORT/mcp" \
    -H 'content-type: application/json' -H "$accept" -d "$initialise" || failed=1
  asked "the tools, with the issued key" 200 -X POST "http://$HOST:$PORT/mcp" \
    -H "authorization: Bearer $token" -H 'content-type: application/json' \
    -H "$accept" -d "$initialise" || failed=1
  echo
  say "what it answers, misspelling and all:"
  curl -s -H "authorization: Bearer $token" \
    "http://$HOST:$PORT/v1/near-names?name=dragon%20scimtar&type=item" | head -c 200
  echo
  return "$failed"
}

logs() {
  recall
  if [[ "$STARTED" == "compose" ]]; then
    docker compose logs "$SERVICE"
  else
    docker logs "$NAME"
  fi
}

down() {
  recall
  if [[ "$STARTED" == "compose" ]]; then
    docker compose down --remove-orphans >/dev/null 2>&1 && say "the service is stopped and gone"
  else
    docker rm -f "$NAME" >/dev/null 2>&1 && say "$NAME is stopped and gone"
  fi
  rm -f "$STATE"
}

verb="${1:-}"
shift || true
case "$verb" in
  prepare)
    flags "$@"
    prepare
    ;;
  up)
    flags "$@"
    up
    ;;
  check) check ;;
  logs) logs ;;
  token) token_of ;;
  down) down ;;
  *)
    sed -n '3,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
