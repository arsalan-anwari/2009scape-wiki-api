"""Check the tokens already on this machine against a running deployment.

Reads what `poe keys issue` left in the config directory, and is skipped where there
are no keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from tests.conftest import MACHINE_CONFIG, ORIGINS
from wiki_api.access import (
    Accepted,
    credential_from_file,
    public_key_from_file,
    verify,
)
from wiki_api.access.paths import issuer_public_path, tokens_dir
from wiki_api.config import Settings
from wiki_api.surfaces.http import create_app

if TYPE_CHECKING:
    from pathlib import Path

SCIMITAR = "/v1/entities/item/4587"
ISSUER = issuer_public_path(MACHINE_CONFIG)
KEPT = tokens_dir(MACHINE_CONFIG)


def _tokens() -> list[Path]:
    if not ISSUER.is_file() or not KEPT.is_dir():
        return []
    return sorted(path for path in KEPT.iterdir() if path.is_file())


def _named() -> list[str]:
    return [path.name for path in _tokens()]


needs_keys = pytest.mark.skipif(
    not _tokens(), reason=f"this machine has no issued tokens in {KEPT}"
)


@needs_keys
def test_every_token_kept_here_reads_back_as_a_credential() -> None:
    for path in _tokens():
        held = credential_from_file(path)
        assert held.kid
        assert held.access_token.startswith("wk1.")
        assert held.header["Authorization"].startswith("Bearer ")


@needs_keys
@pytest.mark.parametrize("name", _named() or [""])
def test_every_token_kept_here_is_answered_by_the_key_beside_it(name: str) -> None:
    held = credential_from_file(KEPT / name)
    verdict = verify(held.access_token, public_key=public_key_from_file(ISSUER))
    assert isinstance(verdict, Accepted), f"{name} is not answered by {ISSUER}"
    assert verdict.kid == held.kid


@needs_keys
@pytest.mark.parametrize("name", _named() or [""])
def test_a_deployment_holding_only_the_public_half_answers_these_tokens(
    name: str, fixture_artifact: Path
) -> None:
    held = credential_from_file(KEPT / name)
    settings = Settings(
        data_dir=fixture_artifact.parent,
        artifact_filename=fixture_artifact.name,
        auth_public_key_file=ISSUER,
        cors_origins=ORIGINS,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get(SCIMITAR).status_code == 401
        answered = client.get(SCIMITAR, headers=held.header)
    assert answered.status_code == 200
