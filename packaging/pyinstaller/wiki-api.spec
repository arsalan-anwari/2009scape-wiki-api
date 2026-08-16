# One executable carrying the runtime, for the machines that have no Python on them.
# Built by scripts/build_binary.sh, which is where the paths and the flags are decided.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

DISTRIBUTION = "scape2009-wiki-api"
NAME = "scape2009-wiki-api"

ROOT = Path(os.environ["WIKI_API_REPO_ROOT"]).resolve()
ENTRY = ROOT / "packaging" / "pyinstaller" / "entry.py"

datas = collect_data_files("wiki_api", includes=["**/*.sql"])
datas += copy_metadata(DISTRIBUTION)

hiddenimports = []
binaries = []

# Every command line these three ship is a package of its own, built on typer and
# click, which nothing that serves installs. Walking into one stops the build.
UNSERVED = ("cli", "__main__")


def served(name):
    return not any(part in UNSERVED for part in name.split("."))


for package in ("fastmcp", "mcp", "uvicorn"):
    found_datas, found_binaries, found_hidden = collect_all(
        package, filter_submodules=served, on_error="ignore"
    )
    datas += found_datas
    binaries += found_binaries
    hiddenimports += found_hidden

excludes = [
    "wiki_api.pipeline",
    "lxml",
    "huggingface_hub",
    "tkinter",
    "pytest",
    "mypy",
    "IPython",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NAME,
)
