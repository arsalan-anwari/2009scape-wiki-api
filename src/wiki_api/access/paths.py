"""Name the files this service keeps, under one layout on every platform.

`WIKI_API_CONFIG_DIR` overrides the directory, so a container can point it elsewhere.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from wiki_api.access.errors import AccessMisconfigured

if TYPE_CHECKING:
    from collections.abc import Mapping

APPLICATION: Final = "scape2009-wiki-api"
CONFIG_DIR_VARIABLE: Final = "WIKI_API_CONFIG_DIR"
XDG_VARIABLE: Final = "XDG_CONFIG_HOME"

ISSUER_KEY_FILE: Final = "issuer.key"
ISSUER_PUBLIC_FILE: Final = "issuer.pub"
REVOKED_FILE: Final = "revoked.json"
BANNED_FILE: Final = "banned.json"
DEPLOY_FILE: Final = "deploy.json"
TOKENS_DIR: Final = "tokens"
TOKEN_SUFFIX: Final = ".json"

DIRECTORY_MODE: Final = 0o700
PRIVATE_MODE: Final = 0o600

SEPARATOR: Final = re.compile(r"[^a-z0-9]+")
NOT_A_NAME: Final = ("/", "\\", "..")


def config_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Resolve the config directory: `WIKI_API_CONFIG_DIR`, else `XDG_CONFIG_HOME`,
    else `~/.config`.
    """
    read = environ if environ is not None else os.environ
    named = read.get(CONFIG_DIR_VARIABLE)
    if named:
        return Path(named)
    shared = read.get(XDG_VARIABLE)
    if shared:
        return Path(shared) / APPLICATION
    return Path.home() / ".config" / APPLICATION


def issuer_key_path(directory: Path) -> Path:
    """Name the signing key file, which no server is ever given."""
    return directory / ISSUER_KEY_FILE


def issuer_public_path(directory: Path) -> Path:
    """Name the signature-checking key file, which every server is given."""
    return directory / ISSUER_PUBLIC_FILE


def revoked_path(directory: Path) -> Path:
    """Name the file listing keys that are no longer answered."""
    return directory / REVOKED_FILE


def banned_path(directory: Path) -> Path:
    """Name the file listing addresses that are not being answered."""
    return directory / BANNED_FILE


def deploy_path(directory: Path) -> Path:
    """Name the settings file a deployment may keep beside its keys."""
    return directory / DEPLOY_FILE


def tokens_dir(directory: Path) -> Path:
    """Name the directory holding a copy of each issued token."""
    return directory / TOKENS_DIR


def token_file_name(label: str) -> str:
    """Fold a label into the name its token is filed under, hyphenating anything that
    is not a letter or a digit.

    Raises rather than rewriting a label that leaves nothing, or one carrying `/`,
    `\\` or `..`.
    """
    said = label.strip().lower()
    if any(part in said for part in NOT_A_NAME):
        raise AccessMisconfigured(f"{label!r} is not a name a token can be filed under")
    named = SEPARATOR.sub("-", said).strip("-")
    if not named:
        raise AccessMisconfigured(f"{label!r} leaves nothing to name a token file with")
    return named


def token_path(directory: Path, label: str) -> Path:
    """Name the file the token issued to this label is kept in."""
    return tokens_dir(directory) / f"{token_file_name(label)}{TOKEN_SUFFIX}"


def find_token(directory: Path, label: str) -> Path | None:
    """Find the kept token for this label, falling back to the older extensionless
    name.
    """
    canonical = token_path(directory, label)
    if canonical.is_file():
        return canonical
    older = tokens_dir(directory) / token_file_name(label)
    return older if older.is_file() else None


# test cases


def test_the_environment_can_name_the_directory_outright() -> None:
    assert config_dir({CONFIG_DIR_VARIABLE: "/srv/keys"}) == Path("/srv/keys")


def test_the_desktop_convention_is_honoured_when_it_is_set() -> None:
    assert config_dir({XDG_VARIABLE: "/home/who/.config"}) == Path(
        f"/home/who/.config/{APPLICATION}"
    )


def test_an_outright_name_outranks_the_convention() -> None:
    given = {CONFIG_DIR_VARIABLE: "/srv/keys", XDG_VARIABLE: "/home/who/.config"}
    assert config_dir(given) == Path("/srv/keys")


def test_the_same_place_is_used_on_every_platform() -> None:
    resolved = config_dir({})
    assert resolved.parts[-2:] == (".config", APPLICATION)
    assert resolved.is_absolute()


def test_an_empty_variable_counts_as_unset() -> None:
    assert config_dir({CONFIG_DIR_VARIABLE: ""}) == config_dir({})


def test_everything_this_service_keeps_lives_in_one_place() -> None:
    directory = Path("/srv/keys")
    kept = (
        issuer_key_path(directory),
        issuer_public_path(directory),
        revoked_path(directory),
        banned_path(directory),
        deploy_path(directory),
    )
    assert all(path.parent == directory for path in kept)
    assert len({path.name for path in kept}) == len(kept)


def test_the_signing_key_is_never_the_file_a_server_is_given() -> None:
    directory = Path("/srv/keys")
    assert issuer_key_path(directory) != issuer_public_path(directory)


def test_a_label_becomes_a_name_a_file_system_will_take() -> None:
    assert token_file_name("some label") == "some-label"
    assert token_file_name("Test Cases") == "test-cases"
    assert token_file_name("  The Wiki!  ") == "the-wiki"


def test_a_label_that_could_point_somewhere_else_is_refused() -> None:
    import pytest

    for said in ("../escape", "keys/demos", "back\\slash"):
        with pytest.raises(AccessMisconfigured):
            token_file_name(said)


def test_a_label_that_names_nothing_is_refused() -> None:
    import pytest

    for said in ("", "   ", "!!!"):
        with pytest.raises(AccessMisconfigured):
            token_file_name(said)


def test_every_token_is_filed_under_the_keys_it_was_signed_with() -> None:
    directory = Path("/srv/keys")
    assert token_path(directory, "demos") == directory / TOKENS_DIR / "demos.json"
    assert tokens_dir(directory).parent == directory


def test_a_token_is_found_under_the_name_it_was_written_with(tmp_path: Path) -> None:
    kept = tokens_dir(tmp_path)
    kept.mkdir(parents=True)
    assert find_token(tmp_path, "demos") is None
    older = kept / "demos"
    older.write_text("{}", encoding="utf-8")
    assert find_token(tmp_path, "demos") == older
    canonical = kept / "demos.json"
    canonical.write_text("{}", encoding="utf-8")
    assert find_token(tmp_path, "demos") == canonical
