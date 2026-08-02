"""Fixtures the whole run gets, wherever its test cases were collected from."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.artifact import TEST_ARTIFACT, build_test_artifact

from wiki_api.access.issuing import Issuer, create_issuer, issue, write_token
from wiki_api.access.paths import CONFIG_DIR_VARIABLE, token_path
from wiki_api.access.tokens import credential_from_file

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

TEST_LABEL = "test cases"


@pytest.fixture(scope="session", autouse=True)
def suite_issuer(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Issuer]:
    """Mint the key this run answers, fresh for the whole session.

    Minted rather than read off the machine, so the suite says the same thing on a
    laptop with issued keys and on a build with none.
    """
    directory = tmp_path_factory.mktemp("config")
    made = create_issuer(directory)
    token, kid = issue(made, TEST_LABEL)
    write_token(directory, TEST_LABEL, token, kid)
    patched = pytest.MonkeyPatch()
    patched.setenv(CONFIG_DIR_VARIABLE, str(directory))
    try:
        yield made
    finally:
        patched.undo()


@pytest.fixture(scope="session")
def suite_token(suite_issuer: Issuer) -> str:
    """The token this run presents, read back from the file it was kept in."""
    return credential_from_file(
        token_path(suite_issuer.directory, TEST_LABEL)
    ).access_token


@pytest.fixture
def bearer(suite_token: str) -> dict[str, str]:
    """What a caller puts on a request to be answered."""
    return {"authorization": f"Bearer {suite_token}"}


@pytest.fixture(scope="session")
def fixture_artifact() -> Path:
    """Build the dataset every test reads, once a session."""
    build_test_artifact()
    return TEST_ARTIFACT
