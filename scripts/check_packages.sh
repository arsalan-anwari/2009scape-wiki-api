#!/usr/bin/env bash
#
# Install each package in a clean container of the distribution it is meant for, and ask
# the installed commands the questions a user will ask first. Nothing here touches this
# machine: the packages are only ever installed inside a container that is thrown away.
#
# Usage:
#   scripts/check_packages.sh          all three
#   scripts/check_packages.sh deb      one of deb, rpm, arch
#   scripts/check_packages.sh --keep   leave the containers running to look at
#

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DIST="$REPO_ROOT/dist"
KEEP=0
WANTED=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    deb|rpm|arch) WANTED+=("$1") ;;
    --keep) KEEP=1 ;;
    -h|--help)
      sed -n '3,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "check_packages: unknown option '$1'" >&2
      exit 2
      ;;
  esac
  shift
done
[[ ${#WANTED[@]} -eq 0 ]] && WANTED=(deb rpm arch)

command -v docker >/dev/null 2>&1 || {
  echo "check_packages: no docker or podman, and every check runs in a container" >&2
  exit 1
}

RUNNING=()
if docker --version 2>/dev/null | grep -qi podman; then
  RUNNING=(--security-opt label=disable)
fi

say() { printf '  %s\n' "$*"; }

# Which image, which package, and how that distribution installs a file.
image_for() {
  case "$1" in
    deb) echo "docker.io/library/ubuntu:24.04" ;;
    rpm) echo "registry.fedoraproject.org/fedora:41" ;;
    arch) echo "docker.io/library/archlinux:base" ;;
  esac
}

package_for() {
  case "$1" in
    deb) compgen -G "$DIST/scape2009-wiki-api_*_amd64.deb" | head -1 ;;
    rpm) compgen -G "$DIST/scape2009-wiki-api-*.x86_64.rpm" | head -1 ;;
    arch) compgen -G "$DIST/scape2009-wiki-api-*-x86_64.pkg.tar.zst" | head -1 ;;
  esac
}

install_with() {
  case "$1" in
    deb) echo 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$PACKAGE"' ;;
    rpm) echo 'dnf install -y "$PACKAGE"' ;;
    arch) echo 'pacman -U --noconfirm "$PACKAGE"' ;;
  esac
}

# The questions, run inside the container once the package is on. Written once and used
# by all three, so no distribution is held to an easier standard than the others.
read -r -d '' ASKED <<'SCRIPT' || true
set -u
failed=0
asked() {
  if [ "$2" = "$3" ]; then
    printf '  WORKED  %-46s %s\n' "$1" "$2"
  else
    printf '  FAILED  %-46s %s, wanted %s\n' "$1" "$2" "$3"
    failed=1
  fi
}

[ -f /usr/share/scape2009-wiki-api/knowledge.sqlite3 ] && dataset=yes || dataset=no
asked "the dataset came with it" "$dataset" "yes"

id scape2009-wiki >/dev/null 2>&1 && account=yes || account=no
asked "the service account was made" "$account" "yes"

answer=$({
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"check","version":"1"}}}'
  sleep 3
  printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}'
  printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_thing","arguments":{"name":"dragon scimitar","type":"item"}}}'
  sleep 8
} | scape2009-wiki-mcp 2>/dev/null | grep '"id":2' | grep -c 'Dragon scimitar')
asked "the tools over stdio, no key, no port" "$answer" "1"

http_code() {
  exec 3<>/dev/tcp/127.0.0.1/8300 || return 1
  printf 'GET %s HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n' "$1" >&3
  read -r _ code _ <&3
  exec 3<&-
  printf '%s' "$code"
}

WIKI_API_AUTH_MODE=off WIKI_API_CORS_ORIGINS='["*"]' WIKI_API_HTTP_PORT=8300 \
  scape2009-wiki-serve >/tmp/serve.log 2>&1 &
waited=0
while [ "$waited" -lt 90 ]; do
  [ "$(http_code /health 2>/dev/null)" = "200" ] && break
  sleep 1
  waited=$((waited + 1))
done
asked "health, asked by anyone" "$(http_code /health)" "200"
asked "an item over http, answering everyone" \
  "$(http_code /v1/entities/item/dragon-scimitar)" "200"

if scape2009-wiki-serve >/tmp/guarded.log 2>&1; then
  refused=started
else
  refused=stopped
fi
asked "no key, so it stops rather than starts" "$refused" "stopped"

exit "$failed"
SCRIPT

printf '\n'
overall=0
for target in "${WANTED[@]}"; do
  package="$(package_for "$target")"
  if [[ -z "$package" ]]; then
    printf '== %s\n' "$target"
    say "no package built for this. Run scripts/build_binary.sh first"
    overall=1
    continue
  fi

  printf '== %s, in %s\n' "$(basename "$package")" "$(image_for "$target")"
  name="check-packages-$target"
  docker rm -f "$name" >/dev/null 2>&1
  keeping=(--rm)
  [[ "$KEEP" -eq 1 ]] && keeping=()

  if docker run "${keeping[@]}" --name "$name" "${RUNNING[@]}" \
      -v "$DIST:/pkg:ro" \
      -e "PACKAGE=/pkg/$(basename "$package")" \
      "$(image_for "$target")" \
      bash -c "set -e; $(install_with "$target") >/dev/null 2>&1; $ASKED"; then
    say "$target is good"
  else
    say "$target answered something wrong, see above"
    overall=1
  fi
  printf '\n'
done

if [[ "$KEEP" -eq 1 ]]; then
  say "the containers are still there: docker exec -it check-packages-deb bash"
fi
if [[ "$overall" -eq 0 ]]; then
  say "every package installs and answers"
else
  say "something is wrong, and it is written above"
fi
exit "$overall"
