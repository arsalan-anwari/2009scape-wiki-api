#!/bin/sh
#
# Tell systemd the unit is there, and say what is still missing.

set -e

chown -R scape2009-wiki:scape2009-wiki /var/lib/scape2009-wiki-api 2>/dev/null || true

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload >/dev/null 2>&1 || true
fi

if [ ! -f /etc/scape2009-wiki-api/issuer.pub ]; then
  cat <<'MESSAGE'

  scape2009-wiki-api is installed. Two things before it will answer:

    sudo scape2009-wiki-keys init            the key this machine answers
    sudo scape2009-wiki-keys issue --label me   one token to call it with

  Then start it:

    sudo systemctl enable --now scape2009-wiki-api

  Or run the tools over stdio with no key and no port: scape2009-wiki-mcp

MESSAGE
fi
