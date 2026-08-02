from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from fastmcp.client import Client

from wiki_api.access import public_key_text
from wiki_api.access.bans import FileBans
from wiki_api.access.issuing import create_issuer, issue, withdraw
from wiki_api.access.paths import banned_path, revoked_path
from wiki_api.config import Settings
from wiki_api.serve import create_combined
from wiki_api.surfaces.http import create_app
from wiki_api.surfaces.mcp import create_server
from wiki_api.surfaces.mcp.guarding import keys_for

if TYPE_CHECKING:
    from collections.abc import Iterator

ORIGINS = ("https://wiki.example.test",)
SCIMITAR = "/v1/entities/item/4587"


@pytest.fixture
def issuer(tmp_path: Path) -> Any:
    return create_issuer(tmp_path / "keys")


@pytest.fixture
def token(issuer: Any) -> str:
    minted, _ = issue(issuer, "the wiki")
    return minted


@pytest.fixture
def guarded_settings(http_settings: Settings, issuer: Any) -> Settings:
    return http_settings.model_copy(
        update={
            "auth_mode": "required",
            "auth_public_key": public_key_text(issuer.public_key),
            "auth_revoked_file": revoked_path(issuer.directory),
            "ban_file": banned_path(issuer.directory),
            "cors_origins": ORIGINS,
        }
    )


@pytest.fixture
def guarded(guarded_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(guarded_settings)) as connected:
        yield connected


def _bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


# only holders of an issued key are answered


def test_a_holder_of_an_issued_key_is_answered(guarded: TestClient, token: str) -> None:
    assert guarded.get(SCIMITAR, headers=_bearer(token)).status_code == 200


def test_a_caller_with_no_key_is_not_answered(guarded: TestClient) -> None:
    response = guarded.get(SCIMITAR)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_every_way_of_being_refused_looks_the_same(
    guarded: TestClient, token: str, tmp_path: Path
) -> None:
    stranger = Ed25519PrivateKey.generate()
    from wiki_api.access.issuing import Issuer

    theirs, _ = issue(Issuer(private_key=stranger, directory=tmp_path), "somebody")
    bodies = {
        guarded.get(SCIMITAR).text,
        guarded.get(SCIMITAR, headers=_bearer("nonsense")).text,
        guarded.get(SCIMITAR, headers=_bearer(theirs)).text,
        guarded.get(SCIMITAR, headers=_bearer(f"{token}x")).text,
    }
    assert len(bodies) == 1


def test_a_withdrawn_key_stops_being_answered(
    http_settings: Settings, issuer: Any
) -> None:
    token, kid = issue(issuer, "the wiki")
    withdraw(issuer.directory, kid)
    settings = http_settings.model_copy(
        update={
            "auth_mode": "required",
            "auth_public_key": public_key_text(issuer.public_key),
            "auth_revoked_file": revoked_path(issuer.directory),
            "ban_file": banned_path(issuer.directory),
            "cors_origins": ORIGINS,
        }
    )
    with TestClient(create_app(settings)) as client:
        assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 401


def test_a_health_check_is_answered_without_a_key(guarded: TestClient) -> None:
    assert guarded.get("/health").status_code == 200


def test_everything_else_needs_a_key(guarded: TestClient) -> None:
    for path in ("/v1/about", "/v1/types", "/v1/search?q=dragon", SCIMITAR):
        assert guarded.get(path).status_code == 401


# an unguarded deployment is exactly what it was before


def test_an_unguarded_deployment_answers_everyone(open_client: TestClient) -> None:
    assert open_client.get(SCIMITAR).status_code == 200


def test_an_unguarded_answer_may_still_be_held_by_a_shared_cache(
    open_client: TestClient,
) -> None:
    assert "public" in open_client.get(SCIMITAR).headers["cache-control"]


def test_a_guarded_answer_is_never_held_by_a_shared_cache(
    guarded: TestClient, token: str
) -> None:
    held = guarded.get(SCIMITAR, headers=_bearer(token)).headers["cache-control"]
    assert "private" in held
    assert "public" not in held


def test_a_guarded_answer_can_still_be_validated_rather_than_resent(
    guarded: TestClient, token: str
) -> None:
    first = guarded.get(SCIMITAR, headers=_bearer(token))
    again = guarded.get(
        SCIMITAR, headers={**_bearer(token), "if-none-match": first.headers["etag"]}
    )
    assert again.status_code == 304


# too much asking, and too much guessing


def test_a_caller_past_its_share_is_told_when_to_come_back(
    guarded_settings: Settings, token: str
) -> None:
    settings = guarded_settings.model_copy(
        update={"rate_per_second": 0.001, "rate_burst": 2}
    )
    with TestClient(create_app(settings)) as client:
        for _ in range(2):
            assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 200
        response = client.get(SCIMITAR, headers=_bearer(token))
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1


def test_an_address_that_keeps_guessing_is_shut_out(
    guarded_settings: Settings, token: str
) -> None:
    settings = guarded_settings.model_copy(update={"max_refusals": 3})
    with TestClient(create_app(settings)) as client:
        for _ in range(3):
            assert client.get(SCIMITAR, headers=_bearer("nonsense")).status_code == 401
        response = client.get(SCIMITAR, headers=_bearer(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "blocked"


def test_a_ban_outlives_the_process_that_made_it(
    guarded_settings: Settings, token: str, issuer: Any
) -> None:
    settings = guarded_settings.model_copy(update={"max_refusals": 2})
    with TestClient(create_app(settings)) as client:
        for _ in range(2):
            client.get(SCIMITAR, headers=_bearer("nonsense"))
        assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 403
    with TestClient(create_app(settings)) as started_again:
        assert started_again.get(SCIMITAR, headers=_bearer(token)).status_code == 403


def test_who_is_shut_out_is_written_where_a_person_can_read_it(
    guarded_settings: Settings, issuer: Any
) -> None:
    settings = guarded_settings.model_copy(update={"max_refusals": 2})
    with TestClient(create_app(settings)) as client:
        for _ in range(2):
            client.get(SCIMITAR, headers=_bearer("nonsense"))
    written = json.loads(banned_path(issuer.directory).read_text(encoding="utf-8"))
    assert [ban["caller"] for ban in written["banned"]] == ["testclient"]


def test_a_ban_lifted_by_hand_is_honoured_by_a_running_service(
    guarded_settings: Settings, token: str, issuer: Any
) -> None:
    settings = guarded_settings.model_copy(update={"max_refusals": 2})
    with TestClient(create_app(settings)) as client:
        for _ in range(2):
            client.get(SCIMITAR, headers=_bearer("nonsense"))
        assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 403
        FileBans(banned_path(issuer.directory)).lift("testclient")
        assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 200


def test_a_forwarded_address_is_ignored_unless_a_proxy_was_named(
    guarded_settings: Settings, token: str
) -> None:
    settings = guarded_settings.model_copy(update={"max_refusals": 2})
    with TestClient(create_app(settings)) as client:
        for hop in ("9.9.9.9", "8.8.8.8"):
            client.get(
                SCIMITAR,
                headers={**_bearer("nonsense"), "x-forwarded-for": hop},
            )
        response = client.get(SCIMITAR, headers=_bearer(token))
    assert response.status_code == 403


# the contract says a key is expected


def test_a_guarded_contract_publishes_the_key_it_expects(
    guarded_settings: Settings,
) -> None:
    document: dict[str, Any] = create_app(guarded_settings).openapi()
    assert "issued_key" in document["components"]["securitySchemes"]
    assert document["paths"][SCIMITAR.replace("item/4587", "{entity_type}/{ref}")][
        "get"
    ]["security"] == [{"issued_key": []}]


def test_an_unguarded_contract_says_nothing_about_keys(
    open_settings: Settings,
) -> None:
    document: dict[str, Any] = create_app(open_settings).openapi()
    assert "securitySchemes" not in document.get("components", {})


# one check, reached from both surfaces


def test_the_same_key_is_accepted_by_both_surfaces(
    guarded_settings: Settings, token: str
) -> None:
    settings = guarded_settings.model_copy(update={"mcp_transport": "http"})
    verifier = keys_for(settings, mounted=False)
    assert verifier is not None
    assert anyio.run(verifier.verify_token, token) is not None
    with TestClient(create_app(settings)) as client:
        assert client.get(SCIMITAR, headers=_bearer(token)).status_code == 200


def test_the_same_refusal_is_made_by_both_surfaces(
    guarded_settings: Settings,
) -> None:
    settings = guarded_settings.model_copy(update={"mcp_transport": "http"})
    verifier = keys_for(settings, mounted=False)
    assert verifier is not None
    assert anyio.run(verifier.verify_token, "nonsense") is None
    with TestClient(create_app(settings)) as client:
        assert client.get(SCIMITAR, headers=_bearer("nonsense")).status_code == 401


def test_a_local_client_over_its_own_pipe_is_never_challenged(
    guarded_settings: Settings,
) -> None:
    assert keys_for(guarded_settings, mounted=False) is None


def test_the_tools_still_answer_when_nothing_guards_them(
    http_settings: Settings,
) -> None:
    async def call() -> Any:
        async with Client(create_server(http_settings)) as client:
            return await client.call_tool("about", {})

    answered = anyio.run(call)
    assert answered.structured_content is not None


# both surfaces from one process


def test_both_surfaces_answer_on_one_port(
    http_settings: Settings, bearer: dict[str, str]
) -> None:
    with TestClient(create_combined(http_settings), headers=bearer) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/mcp/", json={}).status_code in {400, 406, 415}


def test_mounted_tools_are_behind_the_same_guard(
    guarded_settings: Settings,
) -> None:
    with TestClient(create_combined(guarded_settings)) as client:
        assert client.post("/mcp/", json={}).status_code == 401


def test_a_deployment_written_in_a_file_is_the_one_that_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    written = tmp_path / "deploy.json"
    written.write_text('{"surfaces": "mcp", "near_limit": 3}', encoding="utf-8")
    monkeypatch.setenv("WIKI_API_CONFIG_FILE", str(written))
    for key in ("WIKI_API_SURFACES", "WIKI_API_NEAR_LIMIT"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.surfaces == "mcp"
    assert settings.near_limit == 3


def test_the_example_deployment_is_one_this_service_can_read() -> None:
    written = Path(__file__).parent.parent.parent / "deploy.example.json"
    given = json.loads(written.read_text(encoding="utf-8"))
    assert set(given) <= set(Settings.model_fields)
    assert Settings(**given).surfaces == "both"
