"""Where a fact came from and which build of the game it reflects."""

from __future__ import annotations

from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from wiki_api.domain.vocabulary import SourceKind

VERSION_SEPARATOR = "@"


class GameVersion(BaseModel):
    """Which build of the game a fact reflects, written as repo@commit and parsed once;
    a bare label with no commit is valid.
    """

    model_config = ConfigDict(frozen=True)

    repo: str = Field(min_length=1)
    commit: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _parse(cls, data: Any) -> Any:
        if not isinstance(data, str):
            return data
        repo, separator, commit = data.partition(VERSION_SEPARATOR)
        if not repo.strip():
            raise ValueError(f"malformed game version: {data!r}")
        if separator and not commit.strip():
            raise ValueError(f"game version {data!r} declares an empty commit")
        return {"repo": repo, "commit": commit if separator else None}

    @model_serializer
    def _serialize(self) -> str:
        return str(self)

    def __str__(self) -> str:
        if self.commit is None:
            return self.repo
        return f"{self.repo}{VERSION_SEPARATOR}{self.commit}"


class Provenance(BaseModel):
    """Where one fact came from."""

    model_config = ConfigDict(frozen=True)

    source: Annotated[SourceKind, BeforeValidator(SourceKind.coerce)]
    game_version: GameVersion
    source_file: str | None = None
    source_ref: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.source_file is not None and not self.source_file.strip():
            raise ValueError("a source file must not be blank")
        return self


# test cases


def test_a_game_version_splits_into_a_repo_and_a_commit() -> None:
    version = GameVersion.model_validate("2009scape@1f4a2c9")
    assert version.repo == "2009scape"
    assert version.commit == "1f4a2c9"


def test_a_game_version_round_trips_through_its_string_form() -> None:
    for label in ("2009scape@1f4a2c9", "test"):
        assert str(GameVersion.model_validate(label)) == label


def test_a_bare_label_carries_no_commit() -> None:
    version = GameVersion.model_validate("test")
    assert version.commit is None


def test_a_game_version_serialises_as_the_string_the_sources_use() -> None:
    version = GameVersion.model_validate("2009scape@1f4a2c9")
    assert version.model_dump_json() == '"2009scape@1f4a2c9"'


def test_a_malformed_game_version_is_rejected() -> None:
    import pytest

    for malformed in ("", "   ", "@1f4a2c9", "2009scape@"):
        with pytest.raises(ValueError):
            GameVersion.model_validate(malformed)


def test_provenance_records_the_kind_of_source_and_the_file() -> None:
    provenance = Provenance.model_validate(
        {
            "source": "game_config",
            "source_file": "item_configs.json",
            "game_version": "2009scape@1f4a2c9",
            "source_ref": "item_configs.json#4587",
        }
    )
    assert provenance.source is SourceKind.GAME_CONFIG
    assert provenance.source_file == "item_configs.json"
    assert provenance.game_version.commit == "1f4a2c9"


def test_a_source_outside_the_vocabulary_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        Provenance.model_validate(
            {"source": "item_configs.json", "game_version": "test"}
        )


def test_a_source_and_game_version_are_mandatory() -> None:
    import pytest

    with pytest.raises(ValueError):
        Provenance.model_validate({"source": "", "game_version": "test"})
    with pytest.raises(ValueError):
        Provenance.model_validate({"source": "fixture", "game_version": ""})


def test_a_blank_source_file_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        Provenance.model_validate(
            {"source": "fixture", "game_version": "test", "source_file": "   "}
        )


def test_a_fact_need_not_name_a_file() -> None:
    provenance = Provenance.model_validate(
        {"source": "fixture", "game_version": "test"}
    )
    assert provenance.source_file is None
    assert provenance.source is SourceKind.FIXTURE
