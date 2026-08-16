#!/bin/sh
#
# Make the account the service runs as, before any file is owned by it.

set -e

if ! getent group scape2009-wiki >/dev/null 2>&1; then
  groupadd --system scape2009-wiki
fi

if ! getent passwd scape2009-wiki >/dev/null 2>&1; then
  useradd --system --gid scape2009-wiki \
    --home-dir /var/lib/scape2009-wiki-api \
    --no-create-home --shell /usr/sbin/nologin scape2009-wiki
fi
