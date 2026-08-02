"""Run one demonstration by the name of its folder.

Each starts at a `main.py`, which this runs in a process of its own, handing it the
rest of the command line.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parent
ROOT = DEMOS.parent
ENTRY = "main.py"


def named() -> list[str]:
    """Every demonstration that can be run, under the name you ask for it by."""
    if not DEMOS.is_dir():
        return []
    return sorted(path.name for path in DEMOS.iterdir() if (path / ENTRY).is_file())


def offered() -> str:
    """The names above, one per line, for a reader who guessed wrong."""
    return "\n".join(f"  {name}" for name in named()) or "  (none)"


def blocked(wanted: str) -> str | None:
    """Whatever stands between a name and a demonstration to run."""
    if not wanted:
        return f"name a demonstration to run:\n{offered()}"
    if wanted not in named():
        return f"there is no demonstration called {wanted!r}. There is:\n{offered()}"
    return None


def main() -> None:
    """Run the named demonstration, passing anything else straight through to it."""
    wanted, *arguments = sys.argv[1:] or [""]
    stopped = blocked(wanted)
    if stopped is not None:
        print(stopped)
        raise SystemExit(2)
    script = DEMOS / wanted / ENTRY
    print(f"running {script.relative_to(ROOT)}\n", flush=True)
    ran = subprocess.run([sys.executable, str(script), *arguments], check=False)
    raise SystemExit(ran.returncode)


if __name__ == "__main__":
    main()
