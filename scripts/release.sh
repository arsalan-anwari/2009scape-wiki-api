#!/usr/bin/env bash
#
# Cut a release from the version CHANGELOG.md declares. That file is the only place a
# version is decided: this writes it into everything that names one, builds what each
# channel ships, and pushes it to PyPI, Docker Hub and GitHub.
#
# Usage:
#   scripts/release.sh version   the version CHANGELOG.md declares
#   scripts/release.sh notes     that version's section of CHANGELOG.md
#   scripts/release.sh sync      write it into pyproject.toml, uv.lock and nfpm.yaml
#   scripts/release.sh build     everything the release ships, into dist/
#   scripts/release.sh check     what is built, what is not, and what would be pushed
#   scripts/release.sh verify    install what was built and ask it what its users will
#   scripts/release.sh docs      build the documentation and put it on GitHub Pages
#   scripts/release.sh publish   push it, once --yes says to
#   scripts/release.sh all       build and publish in one go, once --yes says to
#
# Flags, read by build, check and publish:
#   --yes          push for real. Without it, publish only says what it would do
#   --no-pypi      leave the wheel and the sdist out
#   --no-docker    leave the image out
#   --no-github    leave the tag and the release out
#   --no-packages  leave the executable and the deb, rpm and arch packages out
#   --no-docs      leave the documentation site out
#   --no-data      build the image and the packages with no dataset inside them
#   --no-check     do not run `poe check` first, which publish otherwise refuses to skip
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

CHANGELOG="CHANGELOG.md"
DIST="$REPO_ROOT/dist"
PYTHON_DIST="$DIST/python"
IMAGE_REPO="${WIKI_API_IMAGE_REPO:-arsalananwari/2009scape-wiki-api}"
REGISTRY="${WIKI_API_REGISTRY:-docker.io}"
REGISTRY_USER="${WIKI_API_REGISTRY_USER:-${IMAGE_REPO%%/*}}"
GIT_REMOTE="${WIKI_API_GIT_REMOTE:-origin}"
MAIN_BRANCH="${WIKI_API_MAIN_BRANCH:-main}"
DOCS_BRANCH="${WIKI_API_DOCS_BRANCH:-gh-pages}"
DOCS_OUT="$REPO_ROOT/docs/out"
NAME="scape2009-wiki-api"

CONFIRMED=0
WANT_PYPI=1
WANT_DOCKER=1
WANT_GITHUB=1
WANT_PACKAGES=1
WANT_DOCS=1
WITH_DATA=1
RUN_CHECK=1

say() { printf '  %s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
die() { echo "release: $*" >&2; exit 1; }

flags() {
  for arg in "$@"; do
    case "$arg" in
      --yes) CONFIRMED=1 ;;
      --no-pypi) WANT_PYPI=0 ;;
      --no-docker) WANT_DOCKER=0 ;;
      --no-github) WANT_GITHUB=0 ;;
      --no-packages) WANT_PACKAGES=0 ;;
      --no-docs) WANT_DOCS=0 ;;
      --no-data) WITH_DATA=0 ;;
      --no-check) RUN_CHECK=0 ;;
      *)
        echo "release: unknown option '$arg'" >&2
        exit 2
        ;;
    esac
  done
}

# What the changelog says

declared() {
  local found
  found="$(grep -m1 -oE '^## +\[?[0-9]+\.[0-9]+\.[0-9]+[^]]*\]?' "$CHANGELOG" 2>/dev/null \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
  [[ -n "$found" ]] || die "$CHANGELOG declares no version. Add a '## [1.2.3] - date' heading"
  printf '%s\n' "$found"
}

notes() {
  local version="$1"
  awk -v want="$version" '
    /^## / {
      if (seen) { exit }
      if (index($0, want) > 0) { seen = 1; next }
    }
    seen && /^\[[^]]+\]: / { next }
    seen { print }
  ' "$CHANGELOG" | sed -e '/./,$!d' -e ':a' -e '/^\n*$/{$d;N;ba' -e '}'
}

# Writing it down

sync_version() {
  local version="$1"
  step "writing $version into every file that names one"

  awk -v version="$version" '
    /^\[/ { section = $0 }
    section == "[project]" && /^version *=/ { print "version = \"" version "\""; next }
    { print }
  ' pyproject.toml >pyproject.toml.new && mv pyproject.toml.new pyproject.toml
  say "pyproject.toml"

  sed -i -e "s/^version: .*/version: \"$version\"/" packaging/nfpm.yaml
  say "packaging/nfpm.yaml"

  # The lockfile records this package's own version, and CI installs with --locked.
  uv lock --quiet
  say "uv.lock"
}

synced() {
  local version="$1" written
  written="$(awk '/^\[/ { section = $0 } section == "[project]" && /^version *=/ { gsub(/[" ]/, "", $3); print $3; exit }' pyproject.toml)"
  [[ "$written" == "$version" ]]
}

# What each channel ships

image_tag() { printf '%s:%s\n' "$IMAGE_REPO" "$1"; }

asset_globs() {
  local version="$1"
  printf '%s\n' \
    "$DIST/${NAME}_${version}*_amd64.deb" \
    "$DIST/${NAME}-${version}*.x86_64.rpm" \
    "$DIST/${NAME}-${version}*-x86_64.pkg.tar.zst" \
    "$DIST/${NAME}-${version}-docker-amd64.tar.gz"
}

assets_present() {
  local pattern
  while read -r pattern; do
    compgen -G "$pattern" || true
  done < <(asset_globs "$1")
  [[ -f "$DIST/SHA256SUMS" ]] && printf '%s\n' "$DIST/SHA256SUMS"
  return 0
}

BUILDING=()
if command -v docker >/dev/null 2>&1 && docker --version 2>/dev/null | grep -qi podman; then
  BUILDING=(--format docker --security-opt label=disable)
fi

build() {
  local version="$1"
  mkdir -p "$DIST"

  if [[ "$RUN_CHECK" -eq 1 ]]; then
    step "the gate, before anything is built from this tree"
    uv run poe check
    bash scripts/check_docs.sh
  fi

  synced "$version" || die "pyproject.toml does not say $version. Run \`scripts/release.sh sync\` first"

  if [[ "$WANT_PYPI" -eq 1 ]]; then
    step "the wheel and the sdist"
    rm -rf "$PYTHON_DIST"
    uv build --out-dir "$PYTHON_DIST"
    ls -1 "$PYTHON_DIST" | sed 's/^/  /'
  fi

  if [[ "$WANT_PACKAGES" -eq 1 ]]; then
    step "the executable, and the deb, rpm and arch packages around it"
    local binary_flags=(--version "$version")
    [[ "$WITH_DATA" -eq 0 ]] && binary_flags+=(--no-data)
    bash scripts/build_binary.sh "${binary_flags[@]}"
  fi

  if [[ "$WANT_DOCKER" -eq 1 ]]; then
    build_image "$version"
  fi

  if [[ "$WANT_DOCS" -eq 1 ]]; then
    build_site
  fi

  step "a checksum for everything this release hands out"
  # Only this version's assets. dist/ keeps every build ever made, and a checksum file
  # naming files the release does not hand out is worse than no checksum file.
  rm -f "$DIST/SHA256SUMS"
  local shipping=()
  mapfile -t shipping < <(assets_present "$version")
  if [[ ${#shipping[@]} -gt 0 ]]; then
    ( cd "$DIST" && sha256sum "${shipping[@]##*/}" >SHA256SUMS )
    sed 's/^/  /' "$DIST/SHA256SUMS"
  fi

  printf '\n'
  say "built for $version. Nothing has been pushed"
  say "look it over with: scripts/release.sh check"
}

build_image() {
  local version="$1" dataset="embedded" saved
  [[ "$WITH_DATA" -eq 0 ]] && dataset="none"

  if [[ "$dataset" == "embedded" && ! -f "${WIKI_API_DATA_DIR:-data}/${WIKI_API_ARTIFACT_FILENAME:-knowledge.sqlite3}" ]]; then
    die "no dataset to bake into the image. Fetch one with \`uv run poe download-data\`, or pass --no-data"
  fi

  step "the image, with the dataset $([[ $dataset == embedded ]] && echo 'inside it' || echo 'left out')"
  docker build "${BUILDING[@]}" \
    --build-arg "VERSION=$version" \
    --build-arg "DATASET=$dataset" \
    -t "$(image_tag "$version")" \
    -t "$(image_tag latest)" \
    . >/dev/null
  say "$(image_tag "$version")"

  step "the image as a file, for a machine that cannot reach a registry"
  saved="$DIST/${NAME}-${version}-docker-amd64.tar.gz"
  docker save "$(image_tag "$version")" | gzip >"$saved"
  say "$(du -h "$saved" | cut -f1) in $(basename "$saved"), loaded with \`docker load -i\`"
}

build_site() {
  step "the documentation, with every warning treated as a failure"
  bash scripts/build_docs.sh --clean --strict
  say "$(find "$DOCS_OUT" -name '*.html' | wc -l | tr -d ' ') pages in docs/out"
}

repo_slug() {
  gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true
}

pages_url() {
  local slug found
  slug="$(repo_slug)"
  [[ -n "$slug" ]] || return 0
  found="$(gh api "repos/$slug/pages" -q .html_url 2>/dev/null)" || return 0
  printf '%s\n' "$found"
}

pages_state() {
  local url
  if ! command -v gh >/dev/null 2>&1; then
    printf 'unknown, no gh on this machine\n'
    return 0
  fi
  url="$(pages_url)"
  if [[ -n "$url" ]]; then
    printf '%s\n' "$url"
  else
    printf 'not created yet, publish makes it\n'
  fi
}

ensure_pages_site() {
  local slug url
  slug="$(repo_slug)"
  [[ -n "$slug" ]] || die "gh cannot say which repository this is"

  url="$(pages_url)"
  if [[ -n "$url" ]]; then
    say "the site is already there, at $url"
    return 0
  fi

  step "the GitHub Pages site, which $slug does not have yet"
  gh api --method POST "repos/$slug/pages" \
    -f "source[branch]=$DOCS_BRANCH" -f "source[path]=/" >/dev/null \
    || die "GitHub refused to create the Pages site for $slug"
  say "created, serving $DOCS_BRANCH at /"
}

publish_site() {
  local version="$1" staged url
  [[ -f "$DOCS_OUT/index.html" ]] \
    || die "no documentation in docs/out. Run \`scripts/release.sh build\`"

  step "the documentation, onto $DOCS_BRANCH"
  staged="$(mktemp -d)"
  cp -R "$DOCS_OUT/." "$staged/"
  rm -rf "$staged/.doctrees" "$staged/.buildinfo"
  touch "$staged/.nojekyll"
  git -C "$staged" init -q -b "$DOCS_BRANCH"
  git -C "$staged" add -A
  git -C "$staged" \
    -c "user.name=$(git config user.name || echo "$NAME")" \
    -c "user.email=$(git config user.email || echo "release@$NAME")" \
    commit -q -m "$NAME $version"
  git -C "$staged" push -q --force "$(git remote get-url "$GIT_REMOTE")" "$DOCS_BRANCH"
  rm -rf "$staged"
  say "$DOCS_BRANCH pushed to $GIT_REMOTE"

  ensure_pages_site
  url="$(pages_url)"
  [[ -n "$url" ]] && say "$url"
  return 0
}

deploy_docs() {
  local version="$1"

  build_site

  if [[ "$CONFIRMED" -eq 0 ]]; then
    printf '\n'
    say "this would force docs/out onto $DOCS_BRANCH at $GIT_REMOTE,"
    say "and create the Pages site if this repository has none"
    printf '\n'
    say "nothing was pushed. Add --yes when it is right"
    return 0
  fi

  preflight_gh
  publish_site "$version"
}

# Looking it over

check() {
  local version="$1"
  local tag="v$version"

  printf '\nversion\n'
  printf '  %-24s %s\n' "$CHANGELOG says" "$version"
  printf '  %-24s %s\n' "pyproject.toml says" \
    "$(awk '/^\[/ { s = $0 } s == "[project]" && /^version *=/ { gsub(/[" ]/, "", $3); print $3; exit }' pyproject.toml)"
  printf '  %-24s %s\n' "nfpm.yaml says" \
    "$(awk '/^version:/ { gsub(/[" ]/, "", $2); print $2; exit }' packaging/nfpm.yaml)"

  printf '\nthe tree\n'
  if [[ -z "$(git status --porcelain)" ]]; then
    printf '  %-24s %s\n' "uncommitted work" "none"
  else
    printf '  %-24s %s\n' "uncommitted work" "yes, and publish will refuse to run"
  fi
  printf '  %-24s %s\n' "branch" "$(git rev-parse --abbrev-ref HEAD)"
  if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
    printf '  %-24s %s\n' "$tag" "already made here"
  else
    printf '  %-24s %s\n' "$tag" "not made yet"
  fi

  printf '\nwhat is built\n'
  local built=0
  local pattern
  local candidate
  while read -r pattern; do
    if ! compgen -G "$pattern" >/dev/null; then
      printf '  %-52s %s\n' "$(basename "$pattern")" "missing"
      continue
    fi
    for candidate in $(compgen -G "$pattern"); do
      printf '  %-52s %s\n' "$(basename "$candidate")" "$(du -h "$candidate" | cut -f1)"
      built=1
    done
  done < <(asset_globs "$version")
  if [[ -d "$PYTHON_DIST" ]]; then
    for candidate in "$PYTHON_DIST"/*; do
      [[ -f "$candidate" ]] || continue
      printf '  %-52s %s\n' "python/$(basename "$candidate")" "$(du -h "$candidate" | cut -f1)"
    done
  else
    printf '  %-52s %s\n' "python/ (wheel and sdist)" "missing"
  fi
  [[ "$built" -eq 1 ]] || say "nothing is built yet: scripts/release.sh build"

  printf '\nthe documentation\n'
  if [[ -f "$DOCS_OUT/index.html" ]]; then
    printf '  %-24s %s\n' "docs/out" "built"
  else
    printf '  %-24s %s\n' "docs/out" "missing"
  fi
  printf '  %-24s %s\n' "the Pages site" "$(pages_state)"

  printf '\nwhat publish would push\n'
  [[ "$WANT_PYPI" -eq 1 ]] && printf '  %-24s %s\n' "PyPI" "$NAME $version"
  [[ "$WANT_DOCKER" -eq 1 ]] && printf '  %-24s %s\n' "Docker Hub" "$(image_tag "$version"), $(image_tag latest)"
  [[ "$WANT_GITHUB" -eq 1 ]] && printf '  %-24s %s\n' "GitHub" "tag $tag, a release, and every file above"
  [[ "$WANT_DOCS" -eq 1 ]] && printf '  %-24s %s\n' "GitHub Pages" "docs/out onto $DOCS_BRANCH"
  printf '\n'
}

# Pushing it

preflight_tree() {
  local version="$1"
  local tag="v$version"

  synced "$version" || die "pyproject.toml does not say $version. Run \`scripts/release.sh sync\`"
  [[ -z "$(git status --porcelain)" ]] || die "there is uncommitted work. Commit it, then publish"

  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  [[ "$branch" == "$MAIN_BRANCH" ]] || die "on branch '$branch', not '$MAIN_BRANCH'"

  git rev-parse -q --verify "refs/tags/$tag" >/dev/null \
    && die "$tag already exists here. Bump $CHANGELOG, or delete the tag"
  if git ls-remote --exit-code --tags "$GIT_REMOTE" "$tag" >/dev/null 2>&1; then
    die "$tag is already published. A released version is never rebuilt"
  fi

  if [[ "$WANT_PYPI" -eq 1 ]]; then
    [[ -n "${UV_PUBLISH_TOKEN:-}" ]] || die "UV_PUBLISH_TOKEN is not set, so PyPI would refuse this"
  fi
  if [[ "$WANT_GITHUB" -eq 1 || "$WANT_DOCS" -eq 1 ]]; then
    preflight_gh
  fi
  if [[ "$WANT_DOCKER" -eq 1 ]]; then
    signed_into_the_registry || sign_into_the_registry
  fi
}

preflight_gh() {
  command -v gh >/dev/null 2>&1 || die "no gh on this machine, and the release is made with it"
  gh auth status >/dev/null 2>&1 || die "gh is not signed in. Run \`gh auth login\`"
}

sign_into_the_registry() {
  [[ -n "${DOCKER_API_KEY:-}" ]] || die \
    "not signed in to $REGISTRY. Run \`docker login $REGISTRY\`, or set DOCKER_API_KEY"
  say "signing in to $REGISTRY as $REGISTRY_USER"
  printf '%s' "$DOCKER_API_KEY" \
    | docker login "$REGISTRY" --username "$REGISTRY_USER" --password-stdin >/dev/null \
    || die "DOCKER_API_KEY was refused by $REGISTRY as $REGISTRY_USER"
}

signed_into_the_registry() {
  # podman answers who is signed in; docker keeps it in a file and has no such question.
  if docker --version 2>/dev/null | grep -qi podman; then
    docker login --get-login "$REGISTRY" >/dev/null 2>&1
    return
  fi
  grep -q "$REGISTRY" "${DOCKER_CONFIG:-$HOME/.docker}/config.json" 2>/dev/null
}

# What only a build can satisfy.
preflight_artifacts() {
  local version="$1"
  if [[ "$WANT_PYPI" -eq 1 ]]; then
    compgen -G "$PYTHON_DIST/*.whl" >/dev/null \
      || die "no wheel in $PYTHON_DIST. Run \`scripts/release.sh build\`"
  fi
  if [[ "$WANT_DOCKER" -eq 1 ]]; then
    docker image inspect "$(image_tag "$version")" >/dev/null 2>&1 \
      || die "$(image_tag "$version") is not built. Run \`scripts/release.sh build\`"
  fi
  if [[ "$WANT_DOCS" -eq 1 ]]; then
    [[ -f "$DOCS_OUT/index.html" ]] \
      || die "no documentation in docs/out. Run \`scripts/release.sh build\`"
  fi
}

preflight() {
  local version="$1"
  preflight_tree "$version"
  preflight_artifacts "$version"
  if [[ "$RUN_CHECK" -eq 1 ]]; then
    step "the gate, on the tree about to be tagged"
    uv run poe check
    bash scripts/check_docs.sh
  fi
}

publish() {
  local version="$1"
  local tag="v$version"
  local written

  preflight "$version"

  if [[ "$CONFIRMED" -eq 0 ]]; then
    printf '\n'
    say "this would push $version:"
    [[ "$WANT_GITHUB" -eq 1 ]] && say "  $tag to $GIT_REMOTE, then a release carrying every file in dist/"
    [[ "$WANT_PYPI" -eq 1 ]] && say "  $(ls -1 "$PYTHON_DIST" 2>/dev/null | tr '\n' ' ')to PyPI"
    [[ "$WANT_DOCKER" -eq 1 ]] && say "  $(image_tag "$version") and $(image_tag latest) to Docker Hub"
    [[ "$WANT_DOCS" -eq 1 ]] && say "  docs/out to $DOCS_BRANCH, served by GitHub Pages"
    printf '\n'
    say "nothing was pushed. Add --yes when it is right"
    return 0
  fi

  if [[ "$WANT_GITHUB" -eq 1 ]]; then
    step "the tag"
    git tag -a "$tag" -m "$NAME $version"
    git push "$GIT_REMOTE" "$tag"
    say "$tag pushed"
  fi

  if [[ "$WANT_PYPI" -eq 1 ]]; then
    step "PyPI"
    uv publish "$PYTHON_DIST"/*
  fi

  if [[ "$WANT_DOCKER" -eq 1 ]]; then
    step "Docker Hub"
    docker push "$(image_tag "$version")"
    docker push "$(image_tag latest)"
  fi

  if [[ "$WANT_GITHUB" -eq 1 ]]; then
    step "the release"
    written="$(mktemp)"
    notes "$version" >"$written"
    # shellcheck disable=SC2046
    gh release create "$tag" \
      --title "$NAME $version" \
      --notes-file "$written" \
      $(assets_present "$version" | tr '\n' ' ')
    rm -f "$written"
  fi

  if [[ "$WANT_DOCS" -eq 1 ]]; then
    publish_site "$version"
  fi

  printf '\n'
  say "$version is out. Add the next '## [Unreleased]' heading to $CHANGELOG"
}

# Asking what was built the questions its users will

verify() {
  local version="$1"
  local failed=0

  preflight_artifacts "$version"

  if [[ "$WANT_PYPI" -eq 1 ]]; then
    step "the wheel, installed into an environment of its own"
    verify_wheel "$version" || failed=1
  fi
  if [[ "$WANT_DOCKER" -eq 1 ]]; then
    step "the image, with no network and nothing mounted"
    verify_image "$version" || failed=1
  fi
  if [[ "$WANT_PACKAGES" -eq 1 ]]; then
    step "the packages, each in its own distribution"
    bash scripts/check_packages.sh --version "$version" || failed=1
  fi

  printf '\n'
  if [[ "$failed" -eq 0 ]]; then
    say "everything this would publish answers. It is still all local"
    say "publish it with: scripts/release.sh all --yes"
  else
    say "something this would publish does not answer, and it is written above"
  fi
  return "$failed"
}

verify_wheel() {
  local version="$1"
  local venv="$DIST/verify-venv"
  local failed=0

  rm -rf "$venv"
  uv venv --quiet "$venv"
  VIRTUAL_ENV="$venv" uv pip install --quiet "$PYTHON_DIST"/*.whl

  local said
  said="$("$venv/bin/python" -c 'import wiki_api; print(wiki_api.__version__)')"
  answered "the version it reports" "$said" "$version" || failed=1

  local installed=0
  for command in scape2009-wiki-serve scape2009-wiki-mcp scape2009-wiki-keys; do
    [[ -x "$venv/bin/$command" ]] && installed=$(( installed + 1 ))
  done
  answered "the commands it installs" "$installed" "3" || failed=1

  # Asked over stdio, which is how anyone who pip installs it will use the tools.
  local answer
  answer="$(WIKI_API_DATA_DIR="${WIKI_API_DATA_DIR:-data}" \
    WIKI_API_CONFIG_DIR="$DIST/verify-config" WIKI_API_AUTH_MODE=off \
    asked_over_stdio "$venv/bin/scape2009-wiki-mcp")"
  answered "a real question over stdio" "$answer" "1" || failed=1

  rm -rf "$venv" "$DIST/verify-config"
  return "$failed"
}

verify_image() {
  local version="$1"
  local name="verify-image"
  local failed=0
  local running=()
  [[ ${#BUILDING[@]} -gt 0 ]] && running=(--security-opt label=disable)

  docker rm -f "$name" >/dev/null 2>&1
  # No volumes and no network at all: what an air-gapped deployment gets.
  docker run -d --name "$name" "${running[@]}" --network none \
    -e WIKI_API_AUTH_MODE=off -e 'WIKI_API_CORS_ORIGINS=["*"]' -e WIKI_API_SURFACES=both \
    "$(image_tag "$version")" >/dev/null

  local waited=0
  while (( waited < 60 )); do
    docker exec "$name" python -c \
      "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)" \
      >/dev/null 2>&1 && break
    sleep 1
    waited=$(( waited + 1 ))
  done

  local code
  for path in /health /v1/about /v1/entities/item/dragon-scimitar; do
    code="$(docker exec "$name" python -c \
      "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000$path',timeout=5).status)" \
      2>/dev/null || echo none)"
    answered "$path, with no network" "$code" "200" || failed=1
  done

  local carried
  carried="$(docker exec "$name" sh -c 'test -f /data/knowledge.sqlite3 && echo yes || echo no')"
  answered "the dataset travelled in the image" "$carried" "yes" || failed=1

  docker rm -f "$name" >/dev/null 2>&1
  return "$failed"
}

# One initialise, one tool call, counting whether the thing asked about came back.
asked_over_stdio() {
  {
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
    sleep 3
    printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_thing","arguments":{"name":"dragon scimitar","type":"item"}}}'
    sleep 8
  } | "$1" 2>/dev/null | grep '"id":2' | grep -c 'Dragon scimitar'
}

answered() {
  if [[ "$2" == "$3" ]]; then
    printf '  WORKED  %-46s %s\n' "$1" "$2"
    return 0
  fi
  printf '  FAILED  %-46s %s, wanted %s\n' "$1" "$2" "$3"
  return 1
}

everything() {
  local version="$1"

  step "what has to be true before any of this is worth building"
  preflight_tree "$version"
  say "the tree is clean, $MAIN_BRANCH is checked out, v$version is free, credentials are there"

  build "$version"

  RUN_CHECK=0
  publish "$version"
}

# What was asked for

verb="${1:-}"
shift || true
flags "$@"
VERSION="$(declared)"

case "$verb" in
  version) printf '%s\n' "$VERSION" ;;
  notes) notes "$VERSION" ;;
  sync) sync_version "$VERSION" ;;
  build) build "$VERSION" ;;
  verify) verify "$VERSION" ;;
  docs) deploy_docs "$VERSION" ;;
  all) everything "$VERSION" ;;
  check) check "$VERSION" ;;
  publish) publish "$VERSION" ;;
  *)
    sed -n '3,27p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
