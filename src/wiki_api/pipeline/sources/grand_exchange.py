"""Fetching the weekly Grand Exchange price snapshots."""

from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Final
from urllib.parse import unquote, urljoin

import httpx
from pydantic import BaseModel, ConfigDict

from wiki_api.config import Settings, get_settings

if TYPE_CHECKING:
    from pathlib import Path

SNAPSHOT_NAME: Final = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
SNAPSHOT_SUFFIX: Final = ".json"
PARTIAL_SUFFIX: Final = ".partial"
TIMEOUT: Final = 30.0


class SnapshotRef(BaseModel):
    """One weekly price snapshot, named by the day it covers and parsed to a date here
    so nothing downstream reads the filename again.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_date: date

    @property
    def filename(self) -> str:
        return f"{self.snapshot_date.isoformat()}{SNAPSHOT_SUFFIX}"

    def __str__(self) -> str:
        return self.filename


class SnapshotHarvest(BaseModel):
    """What one fetch did, split into what it downloaded and what was already there."""

    model_config = ConfigDict(frozen=True)

    fetched: tuple[SnapshotRef, ...] = ()
    skipped: tuple[SnapshotRef, ...] = ()

    @property
    def available(self) -> int:
        return len(self.fetched) + len(self.skipped)

    @property
    def latest(self) -> SnapshotRef | None:
        seen = self.fetched + self.skipped
        if not seen:
            return None
        return max(seen, key=lambda ref: ref.snapshot_date)


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


def snapshot_refs(listing: str) -> tuple[SnapshotRef, ...]:
    """Pick the dated snapshots out of a directory listing."""
    collector = _LinkCollector()
    collector.feed(listing)
    names = {unquote(href.rsplit("/", 1)[-1]) for href in collector.hrefs}
    matched = (SNAPSHOT_NAME.match(name) for name in names)
    refs = {
        SnapshotRef(snapshot_date=date.fromisoformat(match.group(1)))
        for match in matched
        if match is not None
    }
    return tuple(sorted(refs, key=lambda ref: ref.snapshot_date))


def as_directory_url(base_url: str) -> str:
    """Make sure a base url ends the way relative names expect."""
    return base_url if base_url.endswith("/") else f"{base_url}/"


def download_snapshots(
    client: httpx.Client, base_url: str, destination: Path
) -> SnapshotHarvest:
    """Download every snapshot not already on disk, writing each one atomically."""
    directory = as_directory_url(base_url)
    listing = client.get(directory)
    listing.raise_for_status()
    destination.mkdir(parents=True, exist_ok=True)
    fetched: list[SnapshotRef] = []
    skipped: list[SnapshotRef] = []
    for ref in snapshot_refs(listing.text):
        target = destination / ref.filename
        if target.is_file():
            skipped.append(ref)
            continue
        response = client.get(urljoin(directory, ref.filename))
        response.raise_for_status()
        partial = destination / f"{ref.filename}{PARTIAL_SUFFIX}"
        partial.write_bytes(response.content)
        partial.replace(target)
        fetched.append(ref)
    return SnapshotHarvest(fetched=tuple(fetched), skipped=tuple(skipped))


def fetch_snapshots(settings: Settings | None = None) -> SnapshotHarvest:
    """Download the snapshots to wherever the settings point."""
    resolved = settings if settings is not None else get_settings()
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        return download_snapshots(
            client, resolved.ge_data_url, resolved.ge_snapshot_dir
        )


def main() -> None:
    """Fetch the snapshots and say what happened."""
    settings = get_settings()
    harvest = fetch_snapshots(settings)
    print(
        f"grand exchange: {len(harvest.fetched)} new, "
        f"{len(harvest.skipped)} already present, "
        f"{harvest.available} snapshots in {settings.ge_snapshot_dir}"
    )


# test cases

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
    assert [ref.snapshot_date for ref in snapshot_refs(_LISTING)] == [
        date(2024, 6, 8),
        date(2026, 7, 25),
    ]


def test_a_snapshot_is_identified_by_its_day_not_its_filename() -> None:
    first = snapshot_refs(_LISTING)[0]
    assert first.snapshot_date == date(2024, 6, 8)
    assert first.filename == "2024-06-08.json"
    assert SnapshotRef(snapshot_date=date(2024, 6, 8)) == first


def test_the_rolling_latest_file_is_never_a_snapshot() -> None:
    assert SNAPSHOT_NAME.match("latest.json") is None


def test_percent_encoded_names_are_decoded() -> None:
    listing = '<a href="/gedata/2024-06-08.json">x</a>'
    assert snapshot_refs(listing) == (SnapshotRef(snapshot_date=date(2024, 6, 8)),)


def test_a_listing_without_snapshots_yields_nothing() -> None:
    assert snapshot_refs("<html><body>nothing here</body></html>") == ()


def test_the_newest_snapshot_is_found_by_date() -> None:
    harvest = SnapshotHarvest(
        fetched=(SnapshotRef(snapshot_date=date(2024, 6, 8)),),
        skipped=(SnapshotRef(snapshot_date=date(2026, 7, 25)),),
    )
    assert harvest.latest == SnapshotRef(snapshot_date=date(2026, 7, 25))
    assert SnapshotHarvest().latest is None


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
    assert [ref.filename for ref in harvest.fetched] == [
        "2024-06-08.json",
        "2026-07-25.json",
    ]
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
    assert [ref.filename for ref in again.skipped] == [
        "2024-06-08.json",
        "2026-07-25.json",
    ]
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
