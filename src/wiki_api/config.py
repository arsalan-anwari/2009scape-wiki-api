"""Settings for the service, read from the environment."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from wiki_api.access.limits import (
    BAN_SECONDS,
    MAX_REFUSALS,
    RATE_BURST,
    RATE_PER_SECOND,
    REFUSAL_WINDOW,
    TRACKED_CALLERS,
)
from wiki_api.access.paths import config_dir, deploy_path, issuer_public_path
from wiki_api.core import BLOCK_PAGE_SIZE
from wiki_api.domain.page import MAX_PAGE_SIZE
from wiki_api.domain.search import (
    MOST_NEAR_LIMIT,
    NEAR_FLOOR,
    NEAR_KEEP,
    NEAR_LIMIT,
)

if TYPE_CHECKING:
    import pytest

ANY_ORIGIN = "*"
ANY_KEY = "WIKI_API_AUTH_PUBLIC_KEY"
DEPLOYMENT_FILE_VARIABLE = "WIKI_API_CONFIG_FILE"
PRICES_DIRNAME: Final = "grand-exchange"


def deployment_file() -> Path:
    """Locate the deployment file, beside the keys unless the environment says
    otherwise.
    """
    named = os.environ.get(DEPLOYMENT_FILE_VARIABLE)
    return Path(named) if named else deploy_path(config_dir())


class Settings(BaseSettings):
    """Runtime configuration, every field overridable with a WIKI_API_ prefixed
    environment variable.
    """

    model_config = SettingsConfigDict(
        env_prefix="WIKI_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order where a setting may come from, strongest first.

        The deployment file ranks last, so an environment variable overrides any line
        of it without the file being edited.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls, json_file=deployment_file()),
        )

    hf_repo_id: str = "arsalan-anwari/2009scape-wiki-api-data"
    hf_revision: str = "main"
    data_dir: Path = Path("data")
    artifact_filename: str = "knowledge.sqlite3"
    staged_dirname: str = "source"
    prices_dirname: str = PRICES_DIRNAME
    game_data_dir: Path = Path("game_data")
    overlay_dir: Path = Path("overlays")
    identity_dir: Path = Path("identity")
    ge_data_url: str = "https://cdn.2009scape.org/gedata/"
    cors_origins: tuple[str, ...] = ()
    cache_seconds: int = 300
    tooltip_cache_seconds: int = 3600
    block_rows: int = Field(default=60, ge=1, le=MAX_PAGE_SIZE)
    near_limit: int = Field(default=NEAR_LIMIT, ge=1, le=MOST_NEAR_LIMIT)
    near_keep: float = Field(default=NEAR_KEEP, ge=0.0, le=1.0)
    near_floor: float = Field(default=NEAR_FLOOR, ge=0.0, le=1.0)
    mcp_rows: int = Field(default=BLOCK_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    mcp_transport: Literal["stdio", "http"] = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8009, ge=1, le=65535)
    surfaces: Literal["http", "mcp", "both"] = "http"
    http_host: str = "127.0.0.1"
    http_port: int = Field(default=8000, ge=1, le=65535)
    auth_mode: Literal["off", "required"] = "required"
    auth_public_key: str = ""
    auth_public_key_file: Path | None = None
    auth_revoked_file: Path | None = None
    ban_file: Path | None = None
    rate_per_second: float = Field(default=RATE_PER_SECOND, gt=0.0)
    rate_burst: int = Field(default=RATE_BURST, ge=1)
    max_refusals: int = Field(default=MAX_REFUSALS, ge=1)
    refusal_window: float = Field(default=REFUSAL_WINDOW, gt=0.0)
    ban_seconds: float = Field(default=BAN_SECONDS, gt=0.0)
    guard_entries: int = Field(default=TRACKED_CALLERS, ge=1)
    trusted_proxies: tuple[str, ...] = ()

    @property
    def artifact_path(self) -> Path:
        return self.data_dir / self.artifact_filename

    @property
    def staged_dir(self) -> Path:
        return self.data_dir / self.staged_dirname

    @property
    def ge_snapshot_dir(self) -> Path:
        return self.staged_dir / self.prices_dirname

    @property
    def guarded(self) -> bool:
        return self.auth_mode != "off"

    @property
    def issuer_public_file(self) -> Path | None:
        """Find the key where `poe keys init` leaves it, when nobody named one.

        Never consulted by a deployment that names its own key.
        """
        found = issuer_public_path(config_dir())
        return found if found.is_file() else None

    @model_validator(mode="after")
    def _answerable(self) -> Settings:
        """Refuse to start when a key is demanded but none is configured, or demanded
        alongside `cors_origins=["*"]`.

        A browser cannot keep a key secret, so that pairing means the key is public.
        """
        if not self.guarded:
            return self
        named = self.auth_public_key or self.auth_public_key_file is not None
        if not named and self.issuer_public_file is None:
            raise ValueError(
                "answering only key holders needs an issuer public key to check them "
                f"against: run `uv run poe keys init`, or set {ANY_KEY} to a key you "
                "already have, or set WIKI_API_AUTH_MODE=off to answer everyone"
            )
        if ANY_ORIGIN in self.cors_origins:
            raise ValueError(
                "a guarded deployment cannot also allow every origin: name the origins "
                "that may read it"
            )
        return self


def get_settings() -> Settings:
    """Read the settings fresh from the environment."""
    return Settings()


# test cases


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("WIKI_API_HF_REPO_ID", "WIKI_API_HF_REVISION", "WIKI_API_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.hf_repo_id == "arsalan-anwari/2009scape-wiki-api-data"
    assert settings.hf_revision == "main"
    assert settings.data_dir == Path("data")


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKI_API_HF_REVISION", "abc123")
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    settings = Settings()
    assert settings.hf_revision == "abc123"
    assert settings.data_dir == Path("/srv/wiki")


def test_the_artifact_path_lives_under_the_data_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_ARTIFACT_FILENAME", raising=False)
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    assert Settings().artifact_path == Path("/srv/wiki/knowledge.sqlite3")


def test_the_artifact_filename_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    monkeypatch.setenv("WIKI_API_ARTIFACT_FILENAME", "knowledge-2026.sqlite3")
    assert Settings().artifact_path == Path("/srv/wiki/knowledge-2026.sqlite3")


def test_the_staged_sources_sit_beside_the_artifact_they_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("WIKI_API_STAGED_DIRNAME", "WIKI_API_PRICES_DIRNAME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    settings = Settings()
    assert settings.staged_dir == Path("/srv/wiki/source")
    assert settings.ge_snapshot_dir == Path("/srv/wiki/source/grand-exchange")
    assert settings.staged_dir in settings.ge_snapshot_dir.parents


def test_nothing_is_ever_written_into_the_checked_out_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_GAME_DATA_DIR", "/srv/raw")
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    settings = Settings()
    assert settings.game_data_dir not in settings.staged_dir.parents
    assert settings.game_data_dir not in settings.ge_snapshot_dir.parents


def test_the_hand_written_inputs_live_where_they_can_be_reviewed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("WIKI_API_OVERLAY_DIR", "WIKI_API_IDENTITY_DIR"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.overlay_dir == Path("overlays")
    assert settings.identity_dir == Path("identity")


def test_the_grand_exchange_host_is_not_hardcoded_in_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_GE_DATA_URL", "https://example.test/prices/")
    assert Settings().ge_data_url == "https://example.test/prices/"


def test_no_browser_is_invited_in_until_one_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_CORS_ORIGINS", raising=False)
    assert Settings().cors_origins == ()


def test_the_origins_allowed_in_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_CORS_ORIGINS", '["https://wiki.example.test"]')
    assert Settings().cors_origins == ("https://wiki.example.test",)


def test_a_hover_is_held_longer_than_a_page(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("WIKI_API_CACHE_SECONDS", "WIKI_API_TOOLTIP_CACHE_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.tooltip_cache_seconds > settings.cache_seconds


def test_a_page_shows_enough_rows_to_be_worth_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_BLOCK_ROWS", raising=False)
    assert Settings().block_rows == 60


def test_how_many_rows_a_page_shows_is_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_BLOCK_ROWS", "25")
    assert Settings().block_rows == 25


def test_a_page_can_never_be_configured_to_be_unbounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_BLOCK_ROWS", str(MAX_PAGE_SIZE + 1))
    with testing.raises(ValueError):
        Settings()


def test_a_reader_that_pays_per_word_gets_a_smaller_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("WIKI_API_BLOCK_ROWS", "WIKI_API_MCP_ROWS"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.mcp_rows == BLOCK_PAGE_SIZE
    assert settings.mcp_rows < settings.block_rows


def test_only_a_few_near_names_are_offered_and_only_close_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("WIKI_API_NEAR_LIMIT", "WIKI_API_NEAR_KEEP", "WIKI_API_NEAR_FLOOR"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.near_limit == NEAR_LIMIT
    assert settings.near_keep == NEAR_KEEP
    assert settings.near_floor == NEAR_FLOOR


def test_how_forgiving_a_near_name_answer_is_can_be_tuned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_NEAR_LIMIT", "3")
    monkeypatch.setenv("WIKI_API_NEAR_KEEP", "0.75")
    settings = Settings()
    assert settings.near_limit == 3
    assert settings.near_keep == 0.75


def test_a_near_name_answer_can_never_be_configured_to_be_a_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_NEAR_LIMIT", str(MOST_NEAR_LIMIT + 1))
    with testing.raises(ValueError):
        Settings()


def test_a_share_of_the_best_score_is_the_only_thing_keep_can_be(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_NEAR_KEEP", "1.5")
    with testing.raises(ValueError):
        Settings()


def test_the_transport_is_chosen_rather_than_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_MCP_TRANSPORT", raising=False)
    assert Settings().mcp_transport == "stdio"
    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", "http")
    assert Settings().mcp_transport == "http"


def test_a_transport_nobody_serves_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", "carrier-pigeon")
    with testing.raises(ValueError):
        Settings()


def test_a_service_answers_only_key_holders_until_it_is_told_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_AUTH_MODE", raising=False)
    settings = Settings()
    assert settings.auth_mode == "required"
    assert settings.guarded is True


def test_answering_everyone_is_something_a_deployment_has_to_ask_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "off")
    settings = Settings()
    assert settings.guarded is False


def test_answering_only_key_holders_needs_a_key_to_check_them_with(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    monkeypatch.setenv("WIKI_API_CONFIG_DIR", str(tmp_path / "nothing"))
    monkeypatch.delenv("WIKI_API_AUTH_PUBLIC_KEY", raising=False)
    with testing.raises(ValueError):
        Settings()


def test_the_key_made_here_is_the_one_used_when_nobody_names_another(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Written by hand rather than issued: nothing that serves may reach the module
    that mints keys, and this file is imported by everything that serves.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from wiki_api.access.keys import public_key_text

    directory = tmp_path / "keys"
    directory.mkdir()
    written = public_key_text(Ed25519PrivateKey.generate().public_key())
    (directory / "issuer.pub").write_text(f"{written}\n", encoding="utf-8")
    monkeypatch.setenv("WIKI_API_CONFIG_DIR", str(directory))
    monkeypatch.delenv("WIKI_API_AUTH_PUBLIC_KEY", raising=False)
    settings = Settings()
    assert settings.guarded is True
    assert settings.issuer_public_file == directory / "issuer.pub"


def test_a_guarded_service_may_not_also_invite_every_browser_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    monkeypatch.setenv("WIKI_API_AUTH_PUBLIC_KEY", "a" * 43)
    monkeypatch.setenv("WIKI_API_CORS_ORIGINS", '["*"]')
    with testing.raises(ValueError):
        Settings()


def test_a_guarded_service_names_the_origins_it_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    monkeypatch.setenv("WIKI_API_AUTH_PUBLIC_KEY", "a" * 43)
    monkeypatch.setenv("WIKI_API_CORS_ORIGINS", '["https://wiki.example.test"]')
    settings = Settings()
    assert settings.guarded is True
    assert ANY_ORIGIN not in settings.cors_origins


def test_a_key_may_be_kept_in_a_file_instead_of_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    monkeypatch.delenv("WIKI_API_AUTH_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("WIKI_API_AUTH_PUBLIC_KEY_FILE", "/run/secrets/issuer.pub")
    monkeypatch.setenv("WIKI_API_CORS_ORIGINS", '["https://wiki.example.test"]')
    assert Settings().auth_public_key_file == Path("/run/secrets/issuer.pub")


def test_how_much_one_caller_may_ask_for_is_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_RATE_PER_SECOND", "2.5")
    monkeypatch.setenv("WIKI_API_RATE_BURST", "5")
    settings = Settings()
    assert settings.rate_per_second == 2.5
    assert settings.rate_burst == 5


def test_a_caller_can_never_be_configured_to_get_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_RATE_PER_SECOND", "0")
    with testing.raises(ValueError):
        Settings()


def test_what_the_guard_remembers_is_always_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_GUARD_ENTRIES", raising=False)
    assert Settings().guard_entries == TRACKED_CALLERS


def test_no_proxy_is_believed_about_who_a_caller_is_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_TRUSTED_PROXIES", raising=False)
    assert Settings().trusted_proxies == ()


def test_which_surfaces_are_served_is_chosen_rather_than_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_SURFACES", raising=False)
    assert Settings().surfaces == "http"
    monkeypatch.setenv("WIKI_API_SURFACES", "both")
    assert Settings().surfaces == "both"


def test_a_surface_nobody_serves_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_SURFACES", "telepathy")
    with testing.raises(ValueError):
        Settings()


def test_a_deployment_can_be_written_down_in_a_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    written = tmp_path / "deploy.json"
    written.write_text('{"surfaces": "both", "block_rows": 12}', encoding="utf-8")
    monkeypatch.setenv(DEPLOYMENT_FILE_VARIABLE, str(written))
    for key in ("WIKI_API_SURFACES", "WIKI_API_BLOCK_ROWS"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.surfaces == "both"
    assert settings.block_rows == 12


def test_the_environment_outranks_the_file_it_was_written_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    written = tmp_path / "deploy.json"
    written.write_text('{"surfaces": "both"}', encoding="utf-8")
    monkeypatch.setenv(DEPLOYMENT_FILE_VARIABLE, str(written))
    monkeypatch.setenv("WIKI_API_SURFACES", "mcp")
    assert Settings().surfaces == "mcp"


def test_no_deployment_file_is_no_reason_to_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DEPLOYMENT_FILE_VARIABLE, str(tmp_path / "absent.json"))
    assert Settings().surfaces == "http"


def test_where_the_deployment_file_lives_is_never_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DEPLOYMENT_FILE_VARIABLE, "/srv/deploy.json")
    assert deployment_file() == Path("/srv/deploy.json")
    monkeypatch.delenv(DEPLOYMENT_FILE_VARIABLE)
    monkeypatch.setenv("WIKI_API_CONFIG_DIR", "/srv/keys")
    assert deployment_file() == Path("/srv/keys/deploy.json")
