#!/usr/bin/env bash
#
# Run the poe tasks that leave a demonstration with something to answer from: the
# real artifact at data/, built from the game's own sources, and the hand-made one
# at data/tests/, which the fixture demonstrations read.
#
# Usage:
#   scripts/build_artifacts.sh                 both artifacts, sources and all
#   scripts/build_artifacts.sh --fixture-only  only the hand-made one, no checkouts
#   scripts/build_artifacts.sh --no-fixture    only the real one
#   scripts/build_artifacts.sh --offline       no network: no checkout, no prices
#   scripts/build_artifacts.sh --update        move the checkouts to their branch heads
#   scripts/build_artifacts.sh --no-deps       trust the environment, do not sync it
#   scripts/build_artifacts.sh --dry-run       say what would be run, run none of it

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

DATA_DIR="${WIKI_API_DATA_DIR:-data}"
ARTIFACT="$DATA_DIR/${WIKI_API_ARTIFACT_FILENAME:-knowledge.sqlite3}"
FIXTURE_ARTIFACT="data/tests/knowledge.sqlite3"
GAME_DATA="${WIKI_API_GAME_DATA_DIR:-game_data}"

REAL=1
FIXTURE=1
NETWORK=1
UPDATE=0
DEPS=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fixture-only) REAL=0 ;;
    --no-fixture) FIXTURE=0 ;;
    --offline) NETWORK=0 ;;
    --update) UPDATE=1 ;;
    --no-deps) DEPS=0 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '3,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "build_artifacts: unknown option '$1'" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$REAL" -eq 0 && "$FIXTURE" -eq 0 ]]; then
  echo "build_artifacts: --fixture-only and --no-fixture leave nothing to build" >&2
  exit 2
fi
if [[ "$REAL" -eq 0 && "$UPDATE" -eq 1 ]]; then
  echo "build_artifacts: --update is for the checkouts, which --fixture-only skips" >&2
  exit 2
fi

say() { printf '  %s\n' "$*"; }

step() {
  printf '\n== %s\n' "$1"
  shift
  if [[ "$DRY_RUN" -eq 1 ]]; then
    say "would run: $*"
    return 0
  fi
  "$@"
}

poe() { uv run --quiet poe "$@"; }

if ! command -v uv >/dev/null 2>&1; then
  echo "build_artifacts: no uv on this machine. Install it from https://astral.sh/uv" >&2
  exit 1
fi

if [[ "$DEPS" -eq 1 ]]; then
  step "the environment this needs" uv sync --all-extras --quiet
fi

if [[ "$REAL" -eq 1 ]]; then
  if [[ "$NETWORK" -eq 1 ]]; then
    if [[ "$UPDATE" -eq 1 ]]; then
      step "the game's repositories, moved to their branch heads" poe sync-submodules
    else
      step "the game's repositories, whatever is missing" \
        poe sync-submodules --init-only
    fi
  elif [[ ! -d "$GAME_DATA/2009scape/.git" ]]; then
    echo "build_artifacts: --offline, but $GAME_DATA holds no checkout to read" >&2
    echo "  run without --offline once, or \`poe sync-submodules --init-only\`" >&2
    exit 1
  fi

  step "the sources, copied, decoded and extracted into data/source" poe stage-sources
  if [[ "$NETWORK" -eq 1 ]]; then
    step "the weekly grand exchange snapshots" poe stage-sources --only prices
  else
    say "leaving the grand exchange snapshots as they are, as --offline asked"
  fi

  step "a number for whatever the sources name but never number" poe allocate-ids --write
  step "the overlays a person finishes, where none is written yet" poe prefill-overlays
  step "data/source plus overlays plus identity -> $ARTIFACT" poe build-artifact
fi

if [[ "$FIXTURE" -eq 1 ]]; then
  step "the hand-made documents -> $FIXTURE_ARTIFACT" poe build-test-artifact
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '\n'
  say "nothing was run, as --dry-run asked"
  exit 0
fi

printf '\nwhat a demonstration can now be pointed at:\n'
built() {
  local path="$1" what="$2"
  if [[ -f "$path" ]]; then
    printf '  %-28s %-8s %s\n' "$path" "$(du -h "$path" | cut -f1)" "$what"
  else
    printf '  %-28s %s\n' "$path" "was not built"
  fi
}
[[ "$REAL" -eq 1 ]] && built "$ARTIFACT" "WIKI_API_DATA_DIR=$DATA_DIR"
[[ "$FIXTURE" -eq 1 ]] && built "$FIXTURE_ARTIFACT" "WIKI_API_DATA_DIR=data/tests"
printf '\n'
say "claude_complex_query reads the real one, the others the hand-made one"
say "each demonstration also wants a key: uv run poe keys issue --label demos"
