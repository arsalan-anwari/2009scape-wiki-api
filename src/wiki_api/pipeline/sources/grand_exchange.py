from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Final
from urllib.parse import unquote, urljoin

import httpx
from pydantic import BaseModel, ConfigDict

from wiki_api.config import Settings, get_settings

if TYPE_CHECKING:
    from pathlib import Path

SNAPSHOT_NAME: Final = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
PARTIAL_SUFFIX: Final = ".partial"
TIMEOUT: Final = 30.0


class SnapshotHarvest(BaseModel):
    model_config = ConfigDict(frozen=True)

    fetched: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()

    @property
    def available(self) -> int:
        return len(self.fetched) + len(self.skipped)


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def snapshot_names(listing: str) -> tuple[str, ...]:
    collector = _LinkCollector()
    collector.feed(listing)
    names = {unquote(href.rsplit("/", 1)[-1]) for href in collector.hrefs}
    return tuple(sorted(name for name in names if SNAPSHOT_NAME.match(name)))


def as_directory_url(base_url: str) -> str:
    return base_url if base_url.endswith("/") else f"{base_url}/"


def download_snapshots(
    client: httpx.Client, base_url: str, destination: Path
) -> SnapshotHarvest:
    directory = as_directory_url(base_url)
    listing = client.get(directory)
    listing.raise_for_status()
    destination.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    skipped: list[str] = []
    for name in snapshot_names(listing.text):
        target = destination / name
        if target.is_file():
            skipped.append(name)
            continue
        response = client.get(urljoin(directory, name))
        response.raise_for_status()
        partial = destination / f"{name}{PARTIAL_SUFFIX}"
        partial.write_bytes(response.content)
        partial.replace(target)
        fetched.append(name)
    return SnapshotHarvest(fetched=tuple(fetched), skipped=tuple(skipped))


def fetch_snapshots(settings: Settings | None = None) -> SnapshotHarvest:
    resolved = settings if settings is not None else get_settings()
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        return download_snapshots(
            client, resolved.ge_data_url, resolved.ge_snapshot_dir
        )


def main() -> None:
    settings = get_settings()
    harvest = fetch_snapshots(settings)
    print(
        f"grand exchange: {len(harvest.fetched)} new, "
        f"{len(harvest.skipped)} already present, "
        f"{harvest.available} snapshots in {settings.ge_snapshot_dir}"
    )


_LISTING = """
<html><body>
<a href="../">../</a>
<a href="2024-06-08.json">2024-06-08.json</a>
<a href="2026-07-25.json">2026-07-25.json</a>
<a href="latest.json">latest.json</a>
<a href="readme.txt">readme.txt</a>
</body></html>
"""


def _client(listing: str = _LISTING) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/"):
            return httpx.Response(200, text=listing)
        return httpx.Response(200, json=[{"item_id": 4587, "value": 108590}])

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_only_dated_snapshots_are_listed() -> None:
    assert snapshot_names(_LISTING) == ("2024-06-08.json", "2026-07-25.json")


def test_the_rolling_latest_file_is_never_a_snapshot() -> None:
    assert "latest.json" not in snapshot_names(_LISTING)
    assert SNAPSHOT_NAME.match("latest.json") is None


def test_percent_encoded_names_are_decoded() -> None:
    listing = '<a href="/gedata/2024-06-08.json">x</a>'
    assert snapshot_names(listing) == ("2024-06-08.json",)


def test_a_listing_without_snapshots_yields_nothing() -> None:
    assert snapshot_names("<html><body>nothing here</body></html>") == ()


def test_a_base_url_without_a_trailing_slash_still_resolves() -> None:
    assert as_directory_url("https://example.test/gedata") == (
        "https://example.test/gedata/"
    )
    assert as_directory_url("https://example.test/gedata/") == (
        "https://example.test/gedata/"
    )


def test_snapshots_are_downloaded_into_the_destination(tmp_path: Path) -> None:
    with _client() as client:
        harvest = download_snapshots(client, "https://example.test/gedata", tmp_path)
    assert harvest.fetched == ("2024-06-08.json", "2026-07-25.json")
    assert harvest.skipped == ()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "2024-06-08.json",
        "2026-07-25.json",
    ]


def test_published_snapshots_are_never_downloaded_twice(tmp_path: Path) -> None:
    with _client() as client:
        download_snapshots(client, "https://example.test/gedata/", tmp_path)
        again = download_snapshots(client, "https://example.test/gedata/", tmp_path)
    assert again.fetched == ()
    assert again.skipped == ("2024-06-08.json", "2026-07-25.json")
    assert again.available == 2


def test_no_partial_files_are_left_behind(tmp_path: Path) -> None:
    with _client() as client:
        download_snapshots(client, "https://example.test/gedata/", tmp_path)
    assert not list(tmp_path.glob(f"*{PARTIAL_SUFFIX}"))


def test_a_failing_listing_is_not_swallowed(tmp_path: Path) -> None:
    import pytest

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with (
        httpx.Client(transport=httpx.MockTransport(handle)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        download_snapshots(client, "https://example.test/gedata/", tmp_path)


def test_the_destination_comes_from_settings(tmp_path: Path) -> None:
    settings = Settings(game_data_dir=tmp_path)
    assert settings.ge_snapshot_dir == tmp_path / "grand-exchange-data"
