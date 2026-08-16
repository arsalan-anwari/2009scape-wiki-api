#!/usr/bin/env bash
#
#
# Usage:
#   scripts/build_docs.sh              write docs/out
#   scripts/build_docs.sh --clean      throw away what an earlier build left first
#   scripts/build_docs.sh --strict     treat every warning as a failure, as CI does
#   scripts/build_docs.sh --serve      build, then serve docs/out on :8080
#   scripts/build_docs.sh --open       print the file to open when it is done

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SOURCE="docs"
OUTPUT="docs/out"
PORT="${DOCS_PORT:-8080}"

CLEAN=0
STRICT=0
SERVE=0
OPEN=0
PASSED=()

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      sed -n '3,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --clean) CLEAN=1 ;;
    --strict) STRICT=1 ;;
    --serve) SERVE=1 ;;
    --open) OPEN=1 ;;
    *) PASSED+=("$arg") ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "build_docs: needs uv on PATH" >&2
  exit 2
fi

if [[ $CLEAN -eq 1 && -d $OUTPUT ]]; then
  echo "removing $OUTPUT"
  rm -rf "$OUTPUT"
fi

ARGS=(-b html "$SOURCE" "$OUTPUT")
[[ $CLEAN -eq 1 ]] && ARGS=(-E -a "${ARGS[@]}")
[[ $STRICT -eq 1 ]] && ARGS=(-W --keep-going "${ARGS[@]}")
[[ ${#PASSED[@]} -gt 0 ]] && ARGS+=("${PASSED[@]}")

uv run --group docs --quiet sphinx-build "${ARGS[@]}"

echo "wrote $OUTPUT"
[[ $OPEN -eq 1 ]] && echo "open $PWD/$OUTPUT/index.html"

if [[ $SERVE -eq 1 ]]; then
  echo "serving $OUTPUT on http://127.0.0.1:$PORT"
  exec uv run --no-project python -m http.server "$PORT" --directory "$OUTPUT"
fi
