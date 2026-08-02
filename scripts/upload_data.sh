#!/usr/bin/env bash
#
# Send what is in data/ to the Hugging Face dataset this deployment reads from,
# and take away anything there that is no longer here, so the dataset is a copy
# of the directory rather than everything that has ever been in it.
#
# Usage:
#   scripts/upload_data.sh               sync data/ to the dataset
#   scripts/upload_data.sh --dry-run     say what would be sent and removed
#   scripts/upload_data.sh -m "message"  name the commit yourself
#
# Where it uploads to is this project's own setting, so a different dataset is
# named the way everything else names one:
#   WIKI_API_HF_REPO_ID=someone/else scripts/upload_data.sh
#
# The dataset's own README.md and .gitattributes are never removed: they describe
# the dataset and are not built from data/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

DRY_RUN=0
MESSAGE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -m|--message)
      shift
      [[ $# -gt 0 ]] || { echo "-m wants a message after it" >&2; exit 2; }
      MESSAGE="$1"
      ;;
    -h|--help)
      sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

uv run --quiet python - "$DRY_RUN" "$MESSAGE" <<'PY'
import sys
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError, RepositoryNotFoundError
from huggingface_hub.utils import LocalTokenNotFoundError

from wiki_api.config import Settings

# What sqlite leaves beside a database while it is open, and the usual editor and
# operating system litter. None of them are the dataset, and half of a database
# would be worse than none of it.
IGNORED = ("*-wal", "*-shm", "*-journal", "*.tmp", "*.part", ".*", "**/.*")

# Written by hand on the dataset side, not built from data/, so a sync leaves them be.
KEPT = ("README.md", ".gitattributes", ".gitignore")

dry_run = sys.argv[1] == "1"
message = sys.argv[2]

# Uploading never answers a request, so it has no use for a key to check callers
# against, and asking for one would stop a machine that only builds the data.
settings = Settings(auth_mode="off")
data_dir = Path(settings.data_dir)
if not data_dir.is_dir():
    raise SystemExit(f"nothing to upload: {data_dir} is not a directory")

api = HfApi()
try:
    who = api.whoami()["name"]
except (LocalTokenNotFoundError, HfHubHTTPError) as error:
    raise SystemExit(
        f"not signed in to Hugging Face ({type(error).__name__}): run `hf auth login`, "
        "or set HF_TOKEN to a token that may write to the dataset"
    ) from error

repo_id = settings.hf_repo_id
revision = settings.hf_revision
try:
    api.repo_info(repo_id, repo_type="dataset", revision=revision)
except RepositoryNotFoundError as error:
    raise SystemExit(
        f"{who} cannot see a dataset called {repo_id}: create it first, or name "
        "another one with WIKI_API_HF_REPO_ID"
    ) from error


def ignored(relative: Path) -> bool:
    parts = (relative, *relative.parents)
    return any(part.match(pattern) for part in parts for pattern in IGNORED)


here = sorted(
    path.relative_to(data_dir).as_posix()
    for path in data_dir.rglob("*")
    if path.is_file() and not ignored(path.relative_to(data_dir))
)
if not here:
    raise SystemExit(f"nothing to upload: {data_dir} holds no files worth sending")

# A README.md here becomes the dataset's card, which is the page every visitor reads
# first and the only place the dataset says what it is. Sending an empty one would
# replace that page with nothing, which nobody means to do.
card = data_dir / "README.md"
if "README.md" in here and card.stat().st_size == 0:
    raise SystemExit(
        f"{card} is empty and would blank the dataset's card: write it, or take it "
        "away and let the card on the dataset stand"
    )

there = set(api.list_repo_files(repo_id, repo_type="dataset", revision=revision))
stale = sorted(there - set(here) - set(KEPT))

print(f"  {who} -> {repo_id} ({revision}), from {data_dir}/")
for name in here:
    print(f"  send    {name}")
for name in stale:
    print(f"  remove  {name}")

if dry_run:
    print("  dry run: nothing was sent")
    raise SystemExit(0)

commit = api.upload_folder(
    folder_path=str(data_dir),
    repo_id=repo_id,
    repo_type="dataset",
    revision=revision,
    ignore_patterns=list(IGNORED),
    # An exact path is a pattern that matches itself, so this takes away what is no
    # longer here without reaching anything the sync is not answerable for.
    delete_patterns=stale or None,
    commit_message=message or f"Sync {data_dir}/ ({len(here)} files)",
)
print(f"  done: {commit.commit_url}")
PY
