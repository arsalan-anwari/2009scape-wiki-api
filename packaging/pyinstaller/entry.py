"""Send the one packaged executable to whichever console script was named first."""

from __future__ import annotations

import multiprocessing
import sys

COMMANDS = ("serve", "mcp", "keys")

USAGE = f"""usage: scape2009-wiki-api <{"|".join(COMMANDS)}> [arguments]

  serve   the http contract, the tools, or both, as the settings ask
  mcp     the tools alone, over stdio or http
  keys    make an issuer key, issue a token, withdraw one

Every setting is a WIKI_API_ environment variable or a line of deploy.json.
"""


def main() -> int:
    """Run the named command with the remaining arguments, or explain the names."""
    named = sys.argv[1] if len(sys.argv) > 1 else ""
    if named not in COMMANDS:
        stream = sys.stderr if named else sys.stdout
        print(USAGE, file=stream)
        return 2 if named else 0
    del sys.argv[1]
    return _ran(named)


def _ran(command: str) -> int:
    """Import only the command being run, so starting the tools costs no more than it
    has to.
    """
    if command == "keys":
        from wiki_api.access.cli import main as keys

        return keys()
    if command == "mcp":
        from wiki_api.surfaces.mcp.server import main as tools

        tools()
        return 0
    from wiki_api.serve import main as served

    served()
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
