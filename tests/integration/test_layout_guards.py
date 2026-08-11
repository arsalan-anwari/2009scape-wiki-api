from __future__ import annotations

import re
from pathlib import Path

import wiki_api

MARKER = "\n# test cases\n"
PACKAGE = Path(str(wiki_api.__path__[0]))
TEST_FUNCTION = re.compile(r"^def test_", re.MULTILINE)
MODULE_PYTEST = re.compile(r"^(import pytest|from pytest\b)", re.MULTILINE)


def _modules() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def _split(path: Path) -> tuple[str, str]:
    source = path.read_text(encoding="utf-8")
    code, _, cases = source.partition(MARKER)
    return code, cases


# the convention three guards already read a file by


def test_every_module_with_test_cases_declares_where_they_start() -> None:
    missing = [
        str(path.relative_to(PACKAGE))
        for path in _modules()
        if TEST_FUNCTION.search(path.read_text(encoding="utf-8"))
        and MARKER not in path.read_text(encoding="utf-8")
    ]
    assert not missing, f"test cases outside a marked section: {missing}"


def test_no_test_case_hides_above_the_marker() -> None:
    early = [
        str(path.relative_to(PACKAGE))
        for path in _modules()
        if TEST_FUNCTION.search(_split(path)[0])
    ]
    assert not early, f"test cases above the marker: {early}"


def test_the_marker_appears_once_so_a_guard_reads_the_whole_file() -> None:
    repeated = [
        str(path.relative_to(PACKAGE))
        for path in _modules()
        if path.read_text(encoding="utf-8").count(MARKER) > 1
    ]
    assert not repeated, f"more than one marker: {repeated}"


# a test library stays a development dependency


def test_nothing_shipped_imports_a_test_library_at_module_level() -> None:
    reaching = [
        str(path.relative_to(PACKAGE))
        for path in _modules()
        if MODULE_PYTEST.search(path.read_text(encoding="utf-8"))
    ]
    assert not reaching, f"pytest imported at module level: {reaching}"


def test_the_guard_would_notice_a_test_case_written_above_the_marker(
    tmp_path: Path,
) -> None:
    stray = tmp_path / "stray.py"
    stray.write_text(f"def test_early() -> None:\n    pass\n{MARKER}", encoding="utf-8")
    assert TEST_FUNCTION.search(_split(stray)[0])
