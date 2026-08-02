"""Check a caller's key on the way into the tools.

Holds no rule of its own: it asks `surfaces.guarding` and reports the answer in this
protocol's words. Installed only when this surface is served over HTTP on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from fastmcp.server.auth.auth import AccessToken, TokenVerifier

from wiki_api.surfaces.guarding import Access, access_from

if TYPE_CHECKING:
    from wiki_api.config import Settings

ISSUER: Final = "scape2009-wiki-api"


class IssuedKeys(TokenVerifier):
    """Answer only holders of a key this deployment's issuer signed."""

    def __init__(self, access: Access) -> None:
        super().__init__()
        self._access = access

    async def verify_token(self, token: str) -> AccessToken | None:
        held = self._access.holds(token)
        if held is None:
            return None
        return AccessToken(
            token=token, client_id=held.kid, scopes=[], claims={"label": held.label}
        )


def keys_for(settings: Settings, *, mounted: bool) -> IssuedKeys | None:
    """Build the check this server installs, or nothing when `mounted`.

    Mounted, the HTTP middleware has already decided, and checking twice would spend a
    caller's share twice for one request.
    """
    if mounted or settings.mcp_transport != "http":
        return None
    access = access_from(settings)
    return None if access is None else IssuedKeys(access)


# test cases


def _settings(**given: object) -> Settings:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from wiki_api.access import public_key_text
    from wiki_api.config import Settings as Configured

    public_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32))).public_key()
    return Configured(
        auth_mode="required",
        auth_public_key=public_key_text(public_key),
        cors_origins=("https://wiki.example.test",),
        **given,  # type: ignore[arg-type]
    )


def _token(kid: str = "abcd", label: str = "wiki") -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from wiki_api.access.tokens import assemble, claims, signed_bytes

    private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    payload = claims(kid, label)
    return assemble(payload, private_key.sign(signed_bytes(payload)))


def test_a_holder_of_an_issued_key_is_let_in() -> None:
    import anyio

    verifier = keys_for(_settings(mcp_transport="http"), mounted=False)
    assert verifier is not None
    held = anyio.run(verifier.verify_token, _token())
    assert held is not None
    assert held.client_id == "abcd"


def test_anyone_else_is_not_let_in() -> None:
    import anyio

    verifier = keys_for(_settings(mcp_transport="http"), mounted=False)
    assert verifier is not None
    assert anyio.run(verifier.verify_token, "nonsense") is None


def test_a_local_client_that_started_this_process_is_never_challenged() -> None:
    assert keys_for(_settings(mcp_transport="stdio"), mounted=False) is None


def test_the_check_is_never_made_twice_in_the_combined_application() -> None:
    assert keys_for(_settings(mcp_transport="http"), mounted=True) is None


def test_a_deployment_that_answers_everyone_installs_nothing() -> None:
    from wiki_api.config import Settings as Configured

    told = Configured(mcp_transport="http", auth_mode="off")
    assert keys_for(told, mounted=False) is None
