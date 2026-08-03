#!/usr/bin/env bash
#
# Send what is in data/ to the Hugging Face dataset this deployment reads from,
# and take away anything there that is no longer here.
#
# Usage:
#   scripts/upload_data.sh               sync data/ to the dataset
#   scripts/upload_data.sh -m "message"  name the commit yourself
#   scripts/upload_data.sh --create-pr   send it as a pull request instead
#
# Where it uploads to is read from the environment the way the server reads it,
# with this project's own setting as the default:
#   WIKI_API_HF_REPO_ID=someone/else scripts/upload_data.sh
#
# Writing needs a key: sign in with `hf auth login`, or set HF_TOKEN to a token
# that may write to the dataset.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPO="${WIKI_API_HF_REPO_ID:-arsalan-anwari/2009scape-wiki-api-data}"
REVISION="${WIKI_API_HF_REVISION:-main}"
DATA_DIR="${WIKI_API_DATA_DIR:-data}"

MESSAGE="Sync $DATA_DIR/ $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
REST=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message)
      shift
      [[ $# -gt 0 ]] || { echo "-m wants a message after it" >&2; exit 2; }
      MESSAGE="$1"
      ;;
    -h|--help)
      sed -n '3,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) REST+=("$1") ;;
  esac
  shift
done

[[ -d "$DATA_DIR" ]] || { echo "nothing to upload: $DATA_DIR is not a directory" >&2; exit 1; }

if [[ -f "$DATA_DIR/README.md" && ! -s "$DATA_DIR/README.md" ]]; then
  echo "$DATA_DIR/README.md is empty and would blank the dataset's card: write it," \
    "or take it away and let the card on the dataset stand" >&2
  exit 1
fi

HF=(hf)
command -v hf >/dev/null 2>&1 || HF=(uv run --quiet hf)

echo "  $DATA_DIR/ -> $REPO ($REVISION)"
exec "${HF[@]}" upload "$REPO" "$DATA_DIR" . ${REST[@]+"${REST[@]}"} \
  --repo-type dataset \
  --revision "$REVISION" \
  --commit-message "$MESSAGE" \
  --delete "*" \
  --exclude "*-wal" --exclude "*-shm" --exclude "*-journal" \
  --exclude "*.tmp" --exclude "*.part" \
  --exclude ".*" --exclude "**/.*"
