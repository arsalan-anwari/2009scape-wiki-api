#!/usr/bin/env bash
#
# Flags prose that reads as machine-written: unconventional characters and
# filler phrases in Python comments, docstrings and description strings, in the
# prose values of JSON files, and in README.md outside its code blocks.
#
# It never stops at the first failure. Every offending line in every file is
# reported, then the script exits 1 if anything was found.
#
# Usage:
#   scripts/check_docs.sh [PATH ...]   check these paths
#                                      (default: src tests demos scripts README.md)
#   scripts/check_docs.sh --rules      print what is checked and exit
#
# A line carrying the marker "docs-check: ignore" is left alone.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DEFAULT_PATHS=(src tests demos scripts README.md)
EXCLUDE_GLOBS=(
  './.venv/*'
  './.git/*'
  './game_data/*'
  './node_modules/*'
  './*cache*/*'
  './.*_cache/*'
)

PATHS=()
SHOW_RULES=0
for arg in "$@"; do
  case "$arg" in
    --rules) SHOW_RULES=1 ;;
    -h|--help)
      sed -n '3,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "check_docs: unknown option '$arg'" >&2
      exit 2
      ;;
    *) PATHS+=("$arg") ;;
  esac
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=("${DEFAULT_PATHS[@]}")
fi

if command -v python3 >/dev/null 2>&1; then
  PY=(python3)
elif command -v uv >/dev/null 2>&1; then
  PY=(uv run --no-project python)
else
  echo "check_docs: needs python3 (or uv) on PATH" >&2
  exit 2
fi

collect_files() {
  local root
  for root in "${PATHS[@]}"; do
    [[ -e "$root" ]] || continue
    if [[ -f "$root" ]]; then
      printf '%s\n' "$root"
      continue
    fi
    local find_args=(
      find "$root" -type f \( -name '*.py' -o -name '*.json' -o -name 'README.md' \)
    )
    local glob
    for glob in "${EXCLUDE_GLOBS[@]}"; do
      find_args+=(-not -path "$glob")
    done
    "${find_args[@]}"
  done | sed 's|^\./||' | sort -u
}

CHECKER="$(mktemp -t check_docs.XXXXXX.py)"
trap 'rm -f "$CHECKER"' EXIT
cat >"$CHECKER" <<'PYCHECK'
"""Reads file paths on stdin, reports unconventional prose, exits 1 on findings."""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
import unicodedata
from pathlib import Path

IGNORE_MARKER = "docs-check: ignore"

# Characters no hand-written comment in this repository needs. Anything outside
# ASCII is reported; these get a name so the report says what to type instead.
NAMED_CHARACTERS = {
    "—": ("em dash", "use a comma, a colon, or two sentences"),
    "–": ("en dash", "use a hyphen, or 'to' for ranges"),
    "‒": ("figure dash", "use a hyphen"),
    "―": ("horizontal bar", "use a hyphen"),
    "→": ("rightwards arrow", "use '->'"),
    "←": ("leftwards arrow", "use '<-'"),
    "↔": ("left-right arrow", "use '<->'"),
    "⇒": ("double arrow", "use '=>'"),
    "‘": ("left single quote", "use '"),
    "’": ("right single quote", "use '"),
    "“": ("left double quote", 'use "'),
    "”": ("right double quote", 'use "'),
    "…": ("ellipsis", "use three dots"),
    "•": ("bullet", "use '-'"),
    "·": ("middle dot", "use '-'"),
    " ": ("non-breaking space", "use a normal space"),
    "​": ("zero-width space", "delete it"),
    "﻿": ("byte order mark", "delete it"),
    "≥": ("greater-or-equal sign", "use '>='"),
    "≤": ("less-or-equal sign", "use '<='"),
    "≠": ("not-equal sign", "use '!='"),
    "×": ("multiplication sign", "use 'x'"),
    "✓": ("check mark", "say it in words"),
    "✗": ("ballot x", "say it in words"),
    "": ("line separator", "use a newline"),
    "": ("paragraph separator", "use a newline"),
}

# Filler that reads as generated rather than written. Each entry is a pattern
# and the reason it is worth rewriting.
PHRASES: list[tuple[str, str]] = [
    (r"\bdelv(?:e|es|ed|ing)\s+into\b", "filler opener"),
    (r"\bit(?:'s| is)\s+(?:worth|important)\s+(?:noting|to note)\b", "filler hedge"),
    (r"\bplease\s+note\s+that\b", "filler hedge"),
    (r"\bnote\s+that\s+this\s+(?:function|method|class|module)\b", "filler hedge"),
    (r"\bthis\s+(?:function|method|class|module)\s+is\s+responsible\s+for\b",
     "say what it does, not that it is responsible"),
    (r"\bin\s+(?:today|this\s+day\s+and\s+age)\b", "marketing opener"),
    (r"\bseamless(?:ly)?\b", "marketing adjective"),
    (r"\bleverag(?:e|es|ed|ing)\b", "say 'use'"),
    (r"\butiliz(?:e|es|ed|ing)\b", "say 'use'"),
    (r"\bfacilitat(?:e|es|ed|ing)\b", "say what actually happens"),
    (r"\bstreamlin(?:e|es|ed|ing)\b", "marketing verb"),
    (r"\bempower(?:s|ed|ing)?\b", "marketing verb"),
    (r"\brobust\s+(?:solution|implementation|system|approach)\b", "marketing phrase"),
    (r"\bcutting[- ]edge\b", "marketing phrase"),
    (r"\bstate[- ]of[- ]the[- ]art\b", "marketing phrase"),
    (r"\bgame[- ]chang(?:er|ing)\b", "marketing phrase"),
    (r"\b(?:unlock|harness)\s+the\s+(?:power|potential|full)\b", "marketing phrase"),
    (r"\belevate\s+your\b", "marketing phrase"),
    (r"\b(?:let(?:'s| us)\s+)?dive\s+(?:in|into)\b", "filler opener"),
    (r"\ba\s+testament\s+to\b", "marketing phrase"),
    (r"\bplays\s+an?\s+(?:crucial|vital|pivotal|key|important)\s+role\b", "filler"),
    (r"\bin\s+the\s+realm\s+of\b", "filler"),
    (r"\bnavigat(?:e|es|ing)\s+the\b", "filler"),
    (r"\bmeticulous(?:ly)?\b", "filler adjective"),
    (r"\bcomprehensive\s+(?:guide|solution|overview|suite|set)\b", "filler adjective"),
    (r"\bwide\s+(?:range|variety)\s+of\b", "filler"),
    (r"\befficiently\s+and\s+effectively\b", "filler pair"),
    (r"\bbest\s+practices\b", "say which practice"),
    (r"\bfirst\s+and\s+foremost\b", "filler connector"),
    (r"\b(?:furthermore|moreover|additionally)\b", "filler connector"),
    (r"\bin\s+(?:conclusion|summary)\b", "filler connector"),
    (r"\bit(?:'s| is)\s+not\s+just\b", "the not-just-but construction"),
    (r"\bisn't\s+just\b", "the not-just-but construction"),
    (r"\bnot\s+only\s+.{1,60}\bbut\s+also\b", "the not-only-but-also construction"),
    (r"\bas\s+an\s+AI\b", "assistant voice"),
    (r"\b(?:I\s+hope\s+this\s+helps|great\s+question|certainly!)", "assistant voice"),
    (r"\bhere(?:'s| is)\s+(?:a|the)\s+(?:breakdown|summary|overview)\b",
     "assistant voice"),
    (r"\bcertainly,\s", "assistant voice"),
    (r"\b(?:significantly|greatly)\s+(?:improve|enhance|reduce)\w*\b",
     "unquantified claim"),
    (r"!{2,}", "shouting punctuation"),
    (r"\bTODO:\s*(?:implement\s+(?:this|logic)|add\s+more)\b", "placeholder text"),
    (r"\byour\s+(?:code|application|project)\s+here\b", "placeholder text"),
]

# Keyword arguments whose string value is prose a reader will see.
PROSE_KWARGS = {
    "description",
    "summary",
    "title",
    "detail",
    "help",
    "doc",
    "docstring",
    "note",
    "message",
    "instructions",
    "label",
}

# Assignment targets whose string value is prose a reader will see.
PROSE_NAME_SUFFIXES = (
    "DESCRIPTION",
    "SUMMARY",
    "TITLE",
    "DOC",
    "DOCSTRING",
    "HELP",
    "NOTE",
    "MESSAGE",
    "INSTRUCTIONS",
    "TEXT",
)

# JSON keys whose string value is prose rather than data.
PROSE_JSON_KEYS = {
    "description",
    "summary",
    "title",
    "detail",
    "docstring",
    "comment",
    "note",
    "message",
    "help",
    "instructions",
    "text",
}

COMPILED_PHRASES = [(re.compile(p, re.IGNORECASE), why) for p, why in PHRASES]

JSON_PAIR = re.compile(
    r'"(?P<key>(?:[^"\\]|\\.)*)"\s*:\s*"(?P<val>(?:[^"\\]|\\.)*)"',
    re.DOTALL,
)

FENCE = re.compile(r"(```|~~~)")
CODE_SPAN = re.compile(r"`[^`]*`")


class Finding:
    def __init__(
        self, path: str, line: int, column: int, code: str, message: str, excerpt: str
    ) -> None:
        self.path = path
        self.line = line
        self.column = column
        self.code = code
        self.message = message
        self.excerpt = excerpt

    def sort_key(self) -> tuple[str, int, int]:
        return (self.path, self.line, self.column)


def describe_character(char: str) -> tuple[str, str]:
    if char in NAMED_CHARACTERS:
        return NAMED_CHARACTERS[char]
    try:
        name = unicodedata.name(char).lower()
    except ValueError:
        name = "unnamed character"
    return (name, "use a plain ASCII equivalent")


def inspect_text(
    path: str, line: int, column: int, text: str, excerpt: str
) -> list[Finding]:
    """Applies every rule to one run of prose sitting on one line."""
    findings: list[Finding] = []
    for offset, char in enumerate(text):
        if ord(char) < 128:
            continue
        name, advice = describe_character(char)
        findings.append(
            Finding(
                path,
                line,
                column + offset + 1,
                "CHAR",
                f"{name} (U+{ord(char):04X}); {advice}",
                excerpt,
            )
        )
    for pattern, why in COMPILED_PHRASES:
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    path,
                    line,
                    column + match.start() + 1,
                    "PHRASE",
                    f"{match.group(0).strip()!r}: {why}",
                    excerpt,
                )
            )
    return findings


class ProseRegions:
    """The parts of each line that are prose rather than code."""

    def __init__(self) -> None:
        self._regions: dict[int, list[tuple[int, int | None]]] = {}

    def add_span(
        self, start_line: int, start_col: int, end_line: int, end_col: int
    ) -> None:
        for line in range(start_line, end_line + 1):
            begin = start_col if line == start_line else 0
            finish = end_col if line == end_line else None
            self._regions.setdefault(line, []).append((begin, finish))

    def add_node(self, node: ast.AST) -> None:
        end_lineno = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)
        if end_lineno is None or end_col is None:
            return
        self.add_span(node.lineno, node.col_offset, end_lineno, end_col)

    def items(self) -> list[tuple[int, list[tuple[int, int | None]]]]:
        return sorted(self._regions.items())


def collect_python_regions(tree: ast.Module) -> ProseRegions:
    regions = ProseRegions()

    docstring_owners = (
        ast.Module,
        ast.ClassDef,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
    )
    for node in ast.walk(tree):
        if isinstance(node, docstring_owners):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    regions.add_node(value)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in PROSE_KWARGS and _is_stringish(keyword.value):
                    regions.add_node(keyword.value)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            if _is_stringish(node.value) and _targets_prose_name(node):
                regions.add_node(node.value)
    return regions


def _is_stringish(node: ast.AST | None) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    return isinstance(node, ast.JoinedStr)


def _targets_prose_name(node: ast.Assign | ast.AnnAssign) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        name = getattr(target, "id", None) or getattr(target, "attr", None)
        if name and name.upper().endswith(PROSE_NAME_SUFFIXES):
            return True
    return False


def check_python(path: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        return [
            Finding(
                path,
                error.lineno or 1,
                error.offset or 1,
                "PARSE",
                f"could not parse the file: {error.msg}",
                "",
            )
        ]

    regions = collect_python_regions(tree)

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                regions.add_span(
                    token.start[0], token.start[1], token.start[0], token.end[1]
                )
    except (tokenize.TokenError, IndentationError) as error:
        findings.append(
            Finding(path, 1, 1, "PARSE", f"could not tokenize the file: {error}", "")
        )

    for line_number, spans in regions.items():
        if line_number > len(lines):
            continue
        line = lines[line_number - 1]
        if IGNORE_MARKER in line:
            continue
        for start, end in spans:
            fragment = line[start:end] if end is not None else line[start:]
            findings.extend(
                inspect_text(path, line_number, start, fragment, line.strip())
            )
    return findings


def check_json(path: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        json.loads(source)
    except json.JSONDecodeError as error:
        return [
            Finding(
                path, error.lineno, error.colno, "PARSE",
                f"could not parse the file: {error.msg}", "",
            )
        ]

    line_starts = [0]
    for index, char in enumerate(source):
        if char == "\n":
            line_starts.append(index + 1)
    lines = source.splitlines()

    def position(offset: int) -> tuple[int, int]:
        low, high = 0, len(line_starts) - 1
        while low < high:
            middle = (low + high + 1) // 2
            if line_starts[middle] <= offset:
                low = middle
            else:
                high = middle - 1
        return (low + 1, offset - line_starts[low] + 1)

    for match in JSON_PAIR.finditer(source):
        key = match.group("key").lower()
        if key not in PROSE_JSON_KEYS:
            continue
        try:
            value = json.loads(f'"{match.group("val")}"')
        except json.JSONDecodeError:
            continue
        line, column = position(match.start("val"))
        if line <= len(lines) and IGNORE_MARKER in lines[line - 1]:
            continue
        excerpt = lines[line - 1].strip() if line <= len(lines) else ""
        for finding in inspect_text(path, line, column - 1, value, excerpt):
            finding.column = column
            findings.append(finding)
    return findings


def check_markdown(path: str, source: str) -> list[Finding]:
    """Every line is prose, except fenced code blocks and inline code spans."""
    findings: list[Finding] = []
    fence: str | None = None

    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        opening = FENCE.match(stripped)
        if opening is not None:
            fence = opening.group(1)[:3]
            continue
        if IGNORE_MARKER in line:
            continue
        findings.extend(inspect_text(path, number, 0, _mask_code(line), line.strip()))
    return findings


def _mask_code(line: str) -> str:
    """Blanks out inline code spans, keeping every column where it was."""
    return CODE_SPAN.sub(lambda match: " " * len(match.group(0)), line)


def print_rules() -> None:
    print("check_docs rules")
    print()
    print("CHAR   any non-ASCII character in a comment, docstring, description")
    print("       string, or JSON prose value. Named cases:")
    for char, (name, advice) in NAMED_CHARACTERS.items():
        print(f"         U+{ord(char):04X}  {name}: {advice}")
    print()
    print("PHRASE filler and marketing wording that reads as generated:")
    for pattern, why in PHRASES:
        print(f"         {pattern}   ({why})")
    print()
    print(f"Lines carrying {IGNORE_MARKER!r} are skipped.")


def main() -> int:
    if "--rules" in sys.argv[1:]:
        print_rules()
        return 0

    paths = [line.strip() for line in sys.stdin if line.strip()]
    findings: list[Finding] = []
    checked = 0

    for raw_path in paths:
        path = Path(raw_path)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            findings.append(
                Finding(raw_path, 1, 1, "READ", f"could not read the file: {error}", "")
            )
            continue
        checked += 1
        if path.suffix == ".py":
            findings.extend(check_python(raw_path, source))
        elif path.suffix == ".json":
            findings.extend(check_json(raw_path, source))
        elif path.suffix == ".md":
            findings.extend(check_markdown(raw_path, source))

    findings.sort(key=Finding.sort_key)

    current_file = None
    for finding in findings:
        if finding.path != current_file:
            current_file = finding.path
            print(f"\n{current_file}")
        print(f"  {finding.line}:{finding.column}  {finding.code}  {finding.message}")
        if finding.excerpt:
            print(f"      | {finding.excerpt}")

    print()
    if findings:
        files_affected = len({finding.path for finding in findings})
        print(
            f"check_docs: {len(findings)} finding(s) in {files_affected} file(s) "
            f"out of {checked} checked."
        )
        return 1

    print(f"check_docs: {checked} file(s) checked, nothing to correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYCHECK

if [[ "$SHOW_RULES" -eq 1 ]]; then
  "${PY[@]}" "$CHECKER" --rules
  exit 0
fi

FILES="$(collect_files)"
if [[ -z "$FILES" ]]; then
  echo "check_docs: no Python or JSON files under: ${PATHS[*]}" >&2
  exit 0
fi

printf '%s\n' "$FILES" | "${PY[@]}" "$CHECKER"
