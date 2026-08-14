"""Reduce a place's name to what two sources spelling it differently still share."""

from __future__ import annotations

import re

NOISE = re.compile(r"[^a-z0-9]+")


def folded(name: str) -> str:
    """Reduce a name to what survives one person typing it and another correcting it."""
    return NOISE.sub("", name.lower())


# test cases


def test_case_and_punctuation_do_not_separate_two_spellings_of_a_name() -> None:
    assert folded("Al Kharid") == folded("al-kharid") == "alkharid"


def test_a_name_of_nothing_but_noise_folds_away_to_nothing() -> None:
    assert folded(" -- ") == ""


def test_two_different_places_stay_apart() -> None:
    assert folded("Varrock") != folded("Falador")
