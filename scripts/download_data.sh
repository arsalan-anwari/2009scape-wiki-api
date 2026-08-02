#!/usr/bin/env bash
#
# Fetch the published dataset from Hugging Face and put it where a server reads
# it, overwriting whatever is there. This is the other half of upload_data.sh:
# that one sends a build out, this one brings the published build back.
#
# Usage:
#   scripts/download_data.sh                 the whole dataset into data/
#   scripts/download_data.sh --into run/data somewhere else
#   scripts/download_data.sh knowledge.sqlite3   only the files you name
#   scripts/download_data.sh --dry-run       say what would be written
#
# Which dataset, and which build of it, are this project's own settings, so a
# fork or an older build is named the way everything else names one:
#   WIKI_API_HF_REPO_ID=someone/else scripts/download_data.sh
#   WIKI_API_HF_REVISION=<commit>    scripts/download_data.sh
#
# The dataset is public, so this needs no key. Files are copied out of the local
# cache as ordinary files, never as links into it, so a container can mount them.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

DRY_RUN=0
INTO=""
WANTED=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --into)
      shift
      [[ $# -gt 0 ]] || { echo "--into wants a directory after it" >&2; exit 2; }
      INTO="$1"
      ;;
    -h|--help)
      sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
    *) WANTED+=("$1") ;;
  esac
  shift
done

uv run --quiet python - "$DRY_RUN" "$INTO" ${WANTED[@]+"${WANTED[@]}"} <<'PY'
import shutil
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import (
    EntryNotFoundError,
    HfHubHTTPError,
    LocalEntryNotFoundError,
    RepositoryNotFoundError,
)

from wiki_api.config import Settings

# Git's own bookkeeping on the dataset side. It says how the hub stores large
# files, which means nothing once the files are sitting in a directory.
SKIPPED = (".gitattributes", ".gitignore")

dry_run = sys.argv[1] == "1"
into = sys.argv[2]
wanted = sys.argv[3:]

# Downloading answers no request, so it needs no key to check callers against,
# and asking for one would stop a machine that only fetches the data.
settings = Settings(auth_mode="off")
destination = Path(into) if into else Path(settings.data_dir)
repo_id = settings.hf_repo_id
revision = settings.hf_revision

api = HfApi()
try:
    built = api.repo_info(repo_id, repo_type="dataset", revision=revision)
    there = sorted(api.list_repo_files(repo_id, repo_type="dataset", revision=revision))
except RepositoryNotFoundError as error:
    raise SystemExit(
        f"no dataset called {repo_id} at {revision}: name another one with "
        "WIKI_API_HF_REPO_ID, or sign in with `hf auth login` if it is private"
    ) from error
except HfHubHTTPError as error:
    raise SystemExit(f"could not reach the dataset {repo_id}: {error}") from error

files = list(wanted) if wanted else [name for name in there if name not in SKIPPED]
unknown = [name for name in files if name not in there]
if unknown:
    raise SystemExit(
        f"{repo_id} at {revision} holds no {', '.join(unknown)}. It holds: "
        + ", ".join(there)
    )
if not files:
    raise SystemExit(f"{repo_id} at {revision} holds nothing worth fetching")


def sized(path: Path) -> str:
    size = float(path.stat().st_size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


print(f"  {repo_id} ({revision}, {built.sha[:8]}) -> {destination}/")
if dry_run:
    for name in files:
        print(f"  fetch   {name}")
    print("  dry run: nothing was written")
    raise SystemExit(0)

for name in files:
    try:
        cached = hf_hub_download(repo_id, name, repo_type="dataset", revision=revision)
    except (EntryNotFoundError, LocalEntryNotFoundError, HfHubHTTPError) as error:
        raise SystemExit(f"could not fetch {name} from {repo_id}: {error}") from error
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    # copyfile reads through the cache's link and writes real bytes, so what
    # lands here survives the cache being cleared and can be mounted read-only.
    shutil.copyfile(cached, target)
    print(f"  wrote   {name}  ({sized(target)})")

served = destination / settings.artifact_filename
if not served.is_file():
    print(
        f"  note: nothing at {served}, which is what a server opens. "
        "Fetch it by name, or set WIKI_API_ARTIFACT_FILENAME to what you did fetch"
    )
PY
