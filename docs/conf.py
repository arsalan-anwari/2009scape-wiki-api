"""Sphinx configuration for the 2009scape wiki API documentation.

Built with `uv run poe docs`, which writes the site into `docs/out`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version

project = "2009scape wiki API"
author = "Arsalan Anwari"
copyright = "2026, Arsalan Anwari"

try:
    release = installed_version("scape2009-wiki-api")
except PackageNotFoundError:
    release = "1.1.0"
version = release

extensions: list[str] = []

source_suffix = {".rst": "restructuredtext"}
master_doc = "index"

exclude_patterns = ["out", "_build", "Thumbs.db", ".DS_Store"]

templates_path: list[str] = ["_templates"]
html_static_path: list[str] = []

html_theme = "2009scape"
html_title = "2009scape wiki API"
html_short_title = "wiki API"
html_copy_source = False
html_show_sourcelink = False

html_theme_options = {
    "logo_text": "2009scape wiki API",
    "logo_subtitle": "game sources as one queryable artifact",
    "github_url": "https://github.com/arsalan-anwari/2009scape-wiki-api",
    "source_repository": "https://github.com/arsalan-anwari/2009scape-wiki-api",
    "source_branch": "main",
    "source_directory": "docs",
    "footer_note": (
        "Apache-2.0. Not affiliated with Jagex. 2009scape game data belongs to the "
        "2009scape project."
    ),
    "nav_links": [
        {"title": "Install", "doc": "install"},
        {"title": "Architecture", "doc": "architecture"},
        {"title": "Extending", "doc": "extending"},
    ],
    "globaltoc_maxdepth": "2",
    "show_prev_next": "true",
    "show_breadcrumbs": "true",
}
