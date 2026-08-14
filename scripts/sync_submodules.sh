#!/usr/bin/env bash
#
# Check out the game project's own repositories into game_data/ and move each
# one to the latest commit on the branch it tracks.
#
# Usage:
#   scripts/sync_submodules.sh                 check out what is missing, update everything
#   scripts/sync_submodules.sh 2009scape       one of them, by name or by path
#   scripts/sync_submodules.sh --init-only     check out what is missing, pull nothing
#   scripts/sync_submodules.sh --status        say what is there, and how far behind
#   scripts/sync_submodules.sh --shallow       a first checkout keeps the latest commit only
#   scripts/sync_submodules.sh --dry-run       say what would be run, run none of it

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INIT_ONLY=0
STATUS_ONLY=0
SHALLOW=0
DRY_RUN=0
ONLY=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --init-only) INIT_ONLY=1 ;;
    --status) STATUS_ONLY=1 ;;
    --shallow) SHALLOW=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '3,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "sync_submodules: unknown option '$1'" >&2
      exit 2
      ;;
    *) ONLY+=("$1") ;;
  esac
  shift
done

if [[ ! -f .gitmodules ]]; then
  echo "sync_submodules: no .gitmodules here, so there is nothing to check out" >&2
  exit 1
fi

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  would run: %s\n' "$*"
    return 0
  fi
  "$@"
}

wanted() {
  local path="$1" name
  if [[ ${#ONLY[@]} -eq 0 ]]; then
    return 0
  fi
  for name in "${ONLY[@]}"; do
    if [[ "$path" == "$name" || "${path##*/}" == "$name" || "$path" == "${name%/}" ]]; then
      return 0
    fi
  done
  return 1
}

declared() {
  git config --file .gitmodules --get "submodule.$1.$2" 2>/dev/null || true
}

# In the index a submodule is a gitlink, mode 160000. Anything else at that
# path, or nothing at all, means it was never registered here.
is_registered() {
  [[ "$(git ls-files --stage -- "$1" 2>/dev/null | cut -c1-6)" == "160000" ]]
}

is_checked_out() {
  [[ -e "$1/.git" ]]
}

is_shallow() {
  [[ "$(git -C "$1" rev-parse --is-shallow-repository 2>/dev/null)" == "true" ]]
}

is_dirty() {
  [[ -n "$(git -C "$1" status --porcelain 2>/dev/null)" ]]
}

FAILED=()
MATCHED=0

PATHS=()
while read -r key value; do
  [[ -n "$value" ]] || continue
  PATHS+=("$value")
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' || true)

if [[ ${#PATHS[@]} -eq 0 ]]; then
  echo "sync_submodules: .gitmodules declares no submodules" >&2
  exit 1
fi

for path in "${PATHS[@]}"; do
  wanted "$path" || continue
  MATCHED=$((MATCHED + 1))

  name="$path"
  url="$(declared "$name" url)"
  branch="$(declared "$name" branch)"
  branch="${branch:-HEAD}"

  printf '%s\n' "$path"

  if [[ -z "$url" ]]; then
    printf '  no url in .gitmodules, skipped\n'
    FAILED+=("$path")
    continue
  fi

  # A repository that was cloned here by hand before anyone thought of
  # submodules is worth keeping, but only if it is the same one.
  if is_checked_out "$path"; then
    have="$(git -C "$path" remote get-url origin 2>/dev/null || true)"
    if [[ -n "$have" && "$have" != "$url" ]]; then
      printf '  origin is %s, .gitmodules says %s, skipped\n' "$have" "$url"
      FAILED+=("$path")
      continue
    fi
  fi

  if [[ "$STATUS_ONLY" -eq 1 ]]; then
    if ! is_registered "$path"; then
      printf '  not registered as a submodule yet\n'
    fi
    if ! is_checked_out "$path"; then
      printf '  not checked out, tracks %s\n' "$branch"
      continue
    fi
    head="$(git -C "$path" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    on="$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    [[ "$on" == "HEAD" ]] && on="detached"
    behind="$(git -C "$path" rev-list --count "HEAD..origin/$branch" 2>/dev/null || echo '?')"
    printf '  at %s on %s, %s commit(s) behind origin/%s%s%s\n' \
      "$head" "$on" "$behind" "$branch" \
      "$(is_shallow "$path" && printf ', shallow' || true)" \
      "$(is_dirty "$path" && printf ', uncommitted work' || true)"
    continue
  fi

  # Three states, each with the one step that moves it forward: never
  # registered, registered but absent, and present.
  if ! is_registered "$path"; then
    printf '  registering and checking out from %s\n' "$url"
    add=(git submodule add -b "$branch")
    [[ "$SHALLOW" -eq 1 ]] && add+=(--depth 1)
    add+=(-- "$url" "$path")
    if ! run "${add[@]}"; then
      printf '  could not register it\n'
      FAILED+=("$path")
      continue
    fi
    if [[ "$DRY_RUN" -eq 0 ]]; then
      printf '  registered, so .gitmodules and %s are staged for you to commit\n' "$path"
    fi
  elif ! is_checked_out "$path"; then
    printf '  checking out at the commit this repository points at\n'
    update=(git submodule update --init)
    [[ "$SHALLOW" -eq 1 ]] && update+=(--depth 1)
    update+=(-- "$path")
    if ! run "${update[@]}"; then
      printf '  could not check it out\n'
      FAILED+=("$path")
      continue
    fi
  fi

  if [[ "$INIT_ONLY" -eq 1 ]]; then
    printf '  checked out, left where it is\n'
    continue
  fi

  if [[ "$DRY_RUN" -eq 1 ]] && ! is_checked_out "$path"; then
    printf '  would then fetch origin/%s and fast-forward to it\n' "$branch"
    continue
  fi

  # Deepening a shallow clone would undo the point of asking for one, so a
  # repository that came down shallow is fetched shallow from here on.
  fetch=(git -C "$path" fetch --prune origin)
  if is_shallow "$path"; then
    fetch+=(--depth 1)
  fi
  fetch+=("$branch")
  if ! run "${fetch[@]}"; then
    printf '  could not reach %s\n' "$url"
    FAILED+=("$path")
    continue
  fi

  if is_dirty "$path"; then
    printf '  has uncommitted work, left where it is\n'
    continue
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  would fast-forward %s to origin/%s\n' "$branch" "$branch"
    continue
  fi

  if git -C "$path" rev-parse --verify --quiet "refs/heads/$branch" >/dev/null; then
    run git -C "$path" checkout --quiet "$branch"
    if ! run git -C "$path" merge --ff-only --quiet "origin/$branch"; then
      printf '  %s has moved apart from origin/%s, resolve it in the submodule\n' "$branch" "$branch"
      FAILED+=("$path")
      continue
    fi
  else
    # A fresh `submodule update` leaves a detached HEAD. Put the branch back so
    # that whoever is here to contribute can commit without thinking about it.
    if ! run git -C "$path" checkout --quiet -b "$branch" --track "origin/$branch"; then
      printf '  could not follow origin/%s\n' "$branch"
      FAILED+=("$path")
      continue
    fi
  fi

  printf '  on %s at %s\n' "$branch" "$(git -C "$path" rev-parse --short HEAD)"
done

if [[ "$MATCHED" -eq 0 ]]; then
  printf 'nothing in .gitmodules matched: %s\n' "${ONLY[*]}" >&2
  printf 'it declares: %s\n' "${PATHS[*]}" >&2
  exit 2
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  printf '\nleft as it was: %s\n' "${FAILED[*]}" >&2
  exit 1
fi
