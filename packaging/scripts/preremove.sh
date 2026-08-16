#!/bin/sh
#
# Stop the service before its files go.

set -e

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop scape2009-wiki-api.service >/dev/null 2>&1 || true
  systemctl disable scape2009-wiki-api.service >/dev/null 2>&1 || true
fi
