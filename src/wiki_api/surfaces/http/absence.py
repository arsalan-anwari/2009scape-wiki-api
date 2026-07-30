"""The one place the core's answers become transport.

The core says found, moved, hidden or missing. Only this module decides that those are
a body, a redirect and two flavours of 404. The core says "here is a link to the new
place" and this module says "go there".
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from wiki_api.core import Found, Hidden, Missing, Moved
from wiki_api.surfaces.http.errors import ContractError, Redirect
from wiki_api.surfaces.http.schemas import ErrorCode

if TYPE_CHECKING:
    from collections.abc import Callable

    from wiki_api.core import Absent
    from wiki_api.domain.identity import Link

MISSING_MESSAGE = "no such entity"
HIDDEN_MESSAGE = "that entity exists but is not published"


def delivered[T](resolution: Found[T] | Absent, moved_to: Callable[[Link], str]) -> T:
    """The answer, or the reason a caller is not getting one."""
    if isinstance(resolution, Found):
        return resolution.value
    if isinstance(resolution, Moved):
        raise Redirect(moved_to(resolution.target))
    raise _refused(resolution)


def _refused(resolution: Hidden | Missing) -> ContractError:
    if isinstance(resolution, Hidden):
        return ContractError(
            HTTPStatus.NOT_FOUND, ErrorCode.NOT_PUBLISHED, HIDDEN_MESSAGE
        )
    return ContractError(HTTPStatus.NOT_FOUND, ErrorCode.NOT_FOUND, MISSING_MESSAGE)


# test cases


def _link() -> Link:
    from wiki_api.domain.identity import EntityType
    from wiki_api.domain.identity import Link as EntityLink

    return EntityLink(
        type=EntityType.ITEM, id=4587, slug="dragon-scimitar", label="Dragon scimitar"
    )


def test_an_answer_is_handed_straight_back() -> None:
    from wiki_api.surfaces.http.addressing import entity_path

    assert delivered(Found[int](value=7), entity_path) == 7


def test_a_renamed_thing_sends_the_caller_to_where_it_lives_now() -> None:
    import pytest

    from wiki_api.surfaces.http.addressing import entity_path

    with pytest.raises(Redirect) as raised:
        delivered(Moved(target=_link()), entity_path)
    assert raised.value.path == "/v1/entities/item/4587"


def test_a_redirect_points_at_whichever_resource_was_asked_for() -> None:
    import pytest

    from wiki_api.surfaces.http.addressing import tooltip_path

    with pytest.raises(Redirect) as raised:
        delivered(Moved(target=_link()), tooltip_path)
    assert raised.value.path == "/v1/entities/item/4587/tooltip"


def test_nothing_at_all_is_a_plain_absence() -> None:
    import pytest

    from wiki_api.surfaces.http.addressing import entity_path

    with pytest.raises(ContractError) as raised:
        delivered(Missing(reference="item:1"), entity_path)
    assert raised.value.status is HTTPStatus.NOT_FOUND
    assert raised.value.code is ErrorCode.NOT_FOUND


def test_an_unpublished_thing_is_absent_but_says_so_differently() -> None:
    import pytest

    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.surfaces.http.addressing import entity_path

    with pytest.raises(ContractError) as raised:
        delivered(
            Hidden(key=EntityKey(type=EntityType.NPC, id=3089)),
            entity_path,
        )
    assert raised.value.status is HTTPStatus.NOT_FOUND
    assert raised.value.code is ErrorCode.NOT_PUBLISHED


def test_a_reader_is_never_told_which_id_was_withheld() -> None:
    import pytest

    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.surfaces.http.addressing import entity_path

    with pytest.raises(ContractError) as raised:
        delivered(Hidden(key=EntityKey(type=EntityType.NPC, id=3089)), entity_path)
    assert "3089" not in raised.value.message
