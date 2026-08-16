"""Send the one packaged executable to whichever command was named first."""

from __future__ import annotations

import multiprocessing
import sys

from wiki_api.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
