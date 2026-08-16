#!/usr/bin/env bash
#
# Freeze the serving half of the project into one executable, then wrap it in the
# packages a distribution installs. Nothing this produces needs Python, uv or a network
# on the machine it lands on.
#
# Usage:
#   scripts/build_binary.sh                the executable, then a deb, an rpm and an arch package
#   scripts/build_binary.sh --binary-only  stop after the executable
#   scripts/build_binary.sh --no-data      leave the dataset out and fetch one at run time
#   scripts/build_binary.sh --clean        throw away what an earlier run left first
#   scripts/build_binary.sh --native       freeze against this machine's own glibc
#   scripts/build_binary.sh --version 1.2.3   build a version the changelog does not declare
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"
export WIKI_API_REPO_ROOT="$REPO_ROOT"

DIST="$REPO_ROOT/dist"
STAGE="$DIST/stage"
FROZEN="$DIST/frozen"
TOOLS="$DIST/.tools"
SPEC="packaging/pyinstaller/wiki-api.spec"
NAME="scape2009-wiki-api"
DATA_DIR="${WIKI_API_DATA_DIR:-data}"
ARTIFACT="${WIKI_API_ARTIFACT_FILENAME:-knowledge.sqlite3}"
NFPM_VERSION="${NFPM_VERSION:-2.43.1}"

# Debian 12 carries glibc 2.36, so what is frozen there runs on Debian 12, Ubuntu 22.04,
# RHEL 9, and every Fedora and Arch since.
BUILDER_IMAGE="${WIKI_API_BUILDER_IMAGE:-ghcr.io/astral-sh/uv:python3.12-bookworm-slim}"
BUILDER_TAG="scape2009-wiki-api-builder:bookworm"

VERSION=""
BINARY_ONLY=0
WITH_DATA=1
CLEAN=0
NATIVE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary-only) BINARY_ONLY=1 ;;
    --no-data) WITH_DATA=0 ;;
    --clean) CLEAN=1 ;;
    --native) NATIVE=1 ;;
    --version)
      shift
      [[ $# -gt 0 ]] || { echo "--version wants a number after it" >&2; exit 2; }
      VERSION="$1"
      ;;
    -h|--help)
      sed -n '3,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "build_binary: unknown option '$1'" >&2
      exit 2
      ;;
  esac
  shift
done

say() { printf '  %s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }

[[ -n "$VERSION" ]] || VERSION="$(bash scripts/release.sh version)"

MACHINE="$(uname -m)"
case "$MACHINE" in
  x86_64) PACKAGE_ARCH="amd64" ;;
  aarch64|arm64) PACKAGE_ARCH="arm64" ;;
  *)
    echo "build_binary: no package is described for $MACHINE" >&2
    exit 1
    ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  echo "build_binary: no uv on this machine. Install it from https://astral.sh/uv" >&2
  exit 1
fi

if [[ "$CLEAN" -eq 1 ]]; then
  step "what an earlier run left"
  rm -rf "$FROZEN" "$STAGE" "$DIST/pyinstaller-work"
  rm -f "$DIST"/*.deb "$DIST"/*.rpm "$DIST"/*.pkg.tar.zst "$DIST/nfpm.yaml"
  say "gone"
fi

# The executable

# Two flags podman needs and docker does not understand.
RUNNING_SMOKE=()
BUILDING_BUILDER=()
if command -v docker >/dev/null 2>&1 && docker --version 2>/dev/null | grep -qi podman; then
  RUNNING_SMOKE=(--security-opt label=disable)
  BUILDING_BUILDER=(--format docker)
fi

PYINSTALLER=(pyinstaller "$SPEC" --noconfirm --log-level WARN)

freeze_here() {
  step "the environment this build needs"
  uv sync --all-extras --group release --quiet

  step "freezing the runtime against this machine's glibc"
  uv run --all-extras --group release --quiet "${PYINSTALLER[@]}" \
    --distpath "$FROZEN" \
    --workpath "$DIST/pyinstaller-work"
}

freeze_in_container() {
  local running=()
  command -v docker >/dev/null 2>&1 || {
    echo "build_binary: no docker or podman, and the release build freezes in a container" >&2
    echo "  pass --native to freeze against this machine's glibc instead" >&2
    exit 1
  }
  if docker --version 2>/dev/null | grep -qi podman; then
    # podman labels every bind mount and then refuses the container access to it.
    running=(--security-opt label=disable)
  else
    # Under docker the container is root and would leave root-owned files in dist/.
    running=(--user "$(id -u):$(id -g)")
  fi

  step "the image this freezes in"
  docker build "${BUILDING_BUILDER[@]}" -t "$BUILDER_TAG" - <<DOCKERFILE >/dev/null
FROM $BUILDER_IMAGE
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils \
 && rm -rf /var/lib/apt/lists/*
DOCKERFILE
  say "$BUILDER_TAG, on $BUILDER_IMAGE"

  step "freezing the runtime in $BUILDER_TAG"

  docker run --rm "${running[@]}" \
    -v "$REPO_ROOT:/repo" \
    -w /repo \
    -e HOME=/tmp \
    -e UV_CACHE_DIR=/tmp/uv-cache \
    -e UV_PROJECT_ENVIRONMENT=/tmp/venv \
    -e WIKI_API_REPO_ROOT=/repo \
    "$BUILDER_TAG" \
    sh -c "uv sync --group release --quiet \
      && uv run --group release --quiet ${PYINSTALLER[*]} \
        --distpath /repo/dist/frozen --workpath /repo/dist/pyinstaller-work"
}

mkdir -p "$DIST"
if [[ "$NATIVE" -eq 1 ]]; then
  freeze_here
else
  freeze_in_container
fi

BUILT="$FROZEN/$NAME/$NAME"
[[ -x "$BUILT" ]] || { echo "build_binary: pyinstaller wrote no executable at $BUILT" >&2; exit 1; }

step "asking the executable to answer for itself"

if [[ "$NATIVE" -eq 1 ]]; then
  (cd / && "$BUILT" >/dev/null)
else
  docker run --rm "${RUNNING_SMOKE[@]}" -v "$FROZEN:/frozen:ro" -w / "$BUILDER_TAG" \
    /frozen/scape2009-wiki-api/scape2009-wiki-api >/dev/null
fi
say "$(du -sh "$FROZEN/$NAME" | cut -f1) in $FROZEN/$NAME"

if [[ "$BINARY_ONLY" -eq 1 ]]; then
  printf '\n'
  say "the executable is at $BUILT"
  exit 0
fi

# The tree the packages install

step "staging the tree a package installs"
rm -rf "$STAGE"
install -d "$STAGE/usr/lib" "$STAGE/usr/bin" "$STAGE/usr/share/$NAME"
cp -a "$FROZEN/$NAME" "$STAGE/usr/lib/$NAME"
install -m 0755 packaging/linux/scape2009-wiki-serve "$STAGE/usr/bin/"
install -m 0755 packaging/linux/scape2009-wiki-mcp "$STAGE/usr/bin/"
install -m 0755 packaging/linux/scape2009-wiki-keys "$STAGE/usr/bin/"

NOTE="$STAGE/usr/share/$NAME/DATASET"
if [[ "$WITH_DATA" -eq 1 ]]; then
  if [[ ! -f "$DATA_DIR/$ARTIFACT" ]]; then
    echo "build_binary: no dataset at $DATA_DIR/$ARTIFACT to put in the package" >&2
    echo "  fetch one with \`uv run poe download-data\`, build one with" \
      "\`uv run poe build-artifacts\`, or pass --no-data" >&2
    exit 1
  fi
  install -m 0644 "$DATA_DIR/$ARTIFACT" "$STAGE/usr/share/$NAME/$ARTIFACT"
  {
    printf 'file    %s\n' "$ARTIFACT"
    printf 'bytes   %s\n' "$(stat -c '%s' "$DATA_DIR/$ARTIFACT")"
    printf 'sha256  %s\n' "$(sha256sum "$DATA_DIR/$ARTIFACT" | cut -d' ' -f1)"
    printf 'built   %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  } >"$NOTE"
  say "the dataset is in the package, so a machine with no network answers the same"
else
  {
    printf 'This package carries no dataset.\n\n'
    printf 'Put one here as %s, or point WIKI_API_DATA_DIR at one:\n' "$ARTIFACT"
    printf '  hf download arsalan-anwari/2009scape-wiki-api-data --repo-type dataset \\\n'
    printf '    --local-dir /usr/share/%s\n' "$NAME"
  } >"$NOTE"
  say "no dataset, as --no-data asked"
fi

# The packages

nfpm_command() {
  if command -v nfpm >/dev/null 2>&1; then
    echo "nfpm"
    return
  fi
  local kept="$TOOLS/nfpm"
  if [[ -x "$kept" ]]; then
    echo "$kept"
    return
  fi
  local machine="x86_64"
  [[ "$PACKAGE_ARCH" == "arm64" ]] && machine="arm64"
  local from="https://github.com/goreleaser/nfpm/releases/download/v${NFPM_VERSION}/nfpm_${NFPM_VERSION}_Linux_${machine}.tar.gz"
  mkdir -p "$TOOLS"
  say "fetching nfpm $NFPM_VERSION, which builds all three packages" >&2
  if ! curl -fsSL "$from" | tar -xz -C "$TOOLS" nfpm; then
    echo "build_binary: could not fetch nfpm from $from" >&2
    echo "  install it yourself and put it on PATH, or set NFPM_VERSION to one that exists" >&2
    exit 1
  fi
  chmod +x "$kept"
  echo "$kept"
}

step "the description all three packages are built from"
sed -e "s/^version: .*/version: \"$VERSION\"/" \
    -e "s/^arch: .*/arch: $PACKAGE_ARCH/" \
    packaging/nfpm.yaml >"$DIST/nfpm.yaml"
say "version $VERSION, $PACKAGE_ARCH"

NFPM="$(nfpm_command)"
for packager in deb rpm archlinux; do
  step "the $packager package"
  "$NFPM" package --config "$DIST/nfpm.yaml" --packager "$packager" --target "$DIST" \
    | sed 's/^/  /'
done

printf '\nwhat a machine with no Python can now install:\n'
for built in "$DIST"/*.deb "$DIST"/*.rpm "$DIST"/*.pkg.tar.zst; do
  [[ -f "$built" ]] || continue
  printf '  %-52s %s\n' "$(basename "$built")" "$(du -h "$built" | cut -f1)"
done
