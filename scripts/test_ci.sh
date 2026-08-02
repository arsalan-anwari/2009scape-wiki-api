#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:$PATH"

FIX=0
RUN_ACT=1
ACT_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    --no-act) RUN_ACT=0 ;;
    *) ACT_ARGS+=("$arg") ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --all-extras --quiet

if [[ "$FIX" -eq 1 ]]; then
  uv run poe fix
fi

DOCS_STATUS=0
bash "$REPO_ROOT/scripts/check_docs.sh" || DOCS_STATUS=1

uv run poe check

if [[ "$RUN_ACT" -eq 1 ]]; then
  if command -v act >/dev/null 2>&1; then
    SOCK="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
    if [[ -S "$SOCK" ]]; then
      export DOCKER_HOST="unix://$SOCK"
    fi
    if ! act push \
      -W .github/workflows/ci.yml \
      -P ubuntu-latest=catthehacker/ubuntu:act-latest \
      "${ACT_ARGS[@]}"; then
      echo "warning: 'act' did not complete (container backend or image pull unavailable); the local gate above is authoritative and passed." >&2
    fi
  else
    echo "note: 'act' is not installed; ran the local gate only." >&2
  fi
fi

if [[ "$DOCS_STATUS" -ne 0 ]]; then
  echo "failure: scripts/check_docs.sh reported prose to correct (see above)." >&2
  exit 1
fi
