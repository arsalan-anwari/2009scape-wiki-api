#!/usr/bin/env bash
#
# Flags prose that reads as machine-written: unconventional characters and
# filler phrases in Python comments, docstrings and description strings, in the
# prose values of JSON files, and in README.md outside its code blocks.
#
# The rules and the reading are in tools/check_docs.py. This says what to read.
#
# Usage:
#   scripts/check_docs.sh [PATH ...]   check these paths
#   scripts/check_docs.sh --rules      print what is checked and exit
#
# A line carrying the marker "docs-check: ignore" is left alone.

set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PATHS=(src tests demos scripts tools README.md)
EXCLUDES=(
  --exclude .venv
  --exclude .git
  --exclude game_data
  --exclude node_modules
  --exclude '*cache*'
)

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      sed -n '3,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

# The checker asks for nothing but the standard library, so any python3 runs it
# and only a machine without one needs the project's own.
if command -v python3 >/dev/null 2>&1; then
  PY=(python3)
elif command -v uv >/dev/null 2>&1; then
  PY=(uv run --no-project python)
else
  echo "check_docs: needs python3 (or uv) on PATH" >&2
  exit 2
fi

ARGS=("$@")
[[ ${#ARGS[@]} -eq 0 ]] && ARGS=("${PATHS[@]}")

exec "${PY[@]}" -m tools.check_docs "${ARGS[@]}" "${EXCLUDES[@]}"
