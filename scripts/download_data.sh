#!/usr/bin/env bash
#
# Fetch the published dataset from Hugging Face and put it where a server reads
# it, overwriting whatever is there. 
#
# Usage:
#   scripts/download_data.sh                     the whole dataset into data/
#   scripts/download_data.sh --into run/data     somewhere else
#   scripts/download_data.sh knowledge.sqlite3   only the files you name
#   scripts/download_data.sh --dry-run           say what would be written
#
# Which dataset, and which build of it, are read from the environment the way the
# server reads them, with this project's own settings as the default:
#   WIKI_API_HF_REPO_ID=someone/else scripts/download_data.sh
#   WIKI_API_HF_REVISION=<commit>    scripts/download_data.sh

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPO="${WIKI_API_HF_REPO_ID:-arsalan-anwari/2009scape-wiki-api-data}"
REVISION="${WIKI_API_HF_REVISION:-main}"
INTO="${WIKI_API_DATA_DIR:-data}"

REST=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --into)
      shift
      [[ $# -gt 0 ]] || { echo "--into wants a directory after it" >&2; exit 2; }
      INTO="$1"
      ;;
    -h|--help)
      sed -n '3,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) REST+=("$1") ;;
  esac
  shift
done

# The CLI comes with the huggingface-hub dependency
HF=(hf)
command -v hf >/dev/null 2>&1 || HF=(uv run --quiet hf)

echo "  $REPO ($REVISION) -> $INTO/"
# --local-dir writes ordinary files rather than links into the cache, so what
# lands here survives the cache being cleared and can be mounted read-only.
"${HF[@]}" download "$REPO" ${REST[@]+"${REST[@]}"} \
  --repo-type dataset \
  --revision "$REVISION" \
  --local-dir "$INTO"

# Remove the cache and git files that the CLI leaves behind.
rm -rf "$INTO/.cache/huggingface"
rmdir "$INTO/.cache" 2>/dev/null || true
rm -f "$INTO/.gitattributes" "$INTO/.gitignore"
