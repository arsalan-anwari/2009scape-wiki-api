"""Read the saved community pages, which only a prefill ever opens.

This sits here rather than beside the staged sources a build reads, because the build
must not be able to reach a source it does not publish from.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from wiki_api.pipeline.wiki import WikiPage

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.pipeline.sources.staged import StagedSources
    from wiki_api.pipeline.staging.declared import DeclaredPages


def saved_pages(staged: StagedSources, declared: DeclaredPages) -> tuple[WikiPage, ...]:
    """Read one staged namespace of community pages, empty when none was staged."""
    if not staged.has_staged(declared.staged):
        return ()
    payload = json.loads(staged.path(declared.staged).read_text(encoding="utf-8"))
    return tuple(WikiPage.model_validate(page) for page in payload["pages"])


# test cases


def _staged(tmp_path: Path, pages: list[dict[str, object]]) -> StagedSources:
    from tests.sources import staged_from

    from wiki_api.pipeline.staging.declared import QUEST_PAGES

    return staged_from(
        tmp_path,
        {
            QUEST_PAGES.staged: json.dumps(
                {"namespace": QUEST_PAGES.namespace, "pages": pages}
            )
        },
    )


def _page(slug: str = "cooks_assistant") -> dict[str, object]:
    from wiki_api.pipeline.staging.declared import QUEST_PAGES

    return {
        "slug": slug,
        "namespace": QUEST_PAGES.namespace,
        "title": "Cook's Assistant",
        "sections": [],
    }


def test_a_staged_namespace_reads_back_as_pages(tmp_path: Path) -> None:
    from wiki_api.pipeline.staging.declared import QUEST_PAGES

    pages = saved_pages(_staged(tmp_path, [_page()]), QUEST_PAGES)
    assert [page.slug for page in pages] == ["cooks_assistant"]


def test_nothing_staged_reads_back_as_nothing(tmp_path: Path) -> None:
    from tests.sources import staged_from

    from wiki_api.pipeline.staging.declared import QUEST_PAGES

    assert saved_pages(staged_from(tmp_path, {}), QUEST_PAGES) == ()
