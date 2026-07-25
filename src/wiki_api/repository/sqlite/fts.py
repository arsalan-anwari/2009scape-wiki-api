from __future__ import annotations

import re
import unicodedata

_TOKENS = re.compile(r"[0-9A-Za-z]+")


def to_match_query(query: str) -> str | None:
    folded = unicodedata.normalize("NFKD", query)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    tokens = _TOKENS.findall(ascii_only)
    if not tokens:
        return None
    return " ".join(f'"{token}"*' for token in tokens)


def test_each_token_becomes_a_quoted_prefix_term() -> None:
    assert to_match_query("dragon scimitar") == '"dragon"* "scimitar"*'


def test_a_single_prefix_is_enough_for_a_type_ahead_box() -> None:
    assert to_match_query("drag") == '"drag"*'


def test_punctuation_and_fts_operators_are_neutralised() -> None:
    assert to_match_query('dragon" OR *') == '"dragon"* "OR"*'
    assert to_match_query("d'hide (green)") == '"d"* "hide"* "green"*'
    assert to_match_query("NEAR/2") == '"NEAR"* "2"*'


def test_accents_are_folded_to_match_the_index() -> None:
    assert to_match_query("café") == '"cafe"*'


def test_a_query_with_nothing_searchable_has_no_match_expression() -> None:
    assert to_match_query("") is None
    assert to_match_query("   ") is None
    assert to_match_query("!!!") is None
