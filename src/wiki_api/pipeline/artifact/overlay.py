"""Read the overlay documents a build takes, converting every raw game encoding here.

Nothing above this layer sees an ordinal, a packed string or a date written as text.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Final, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from wiki_api.domain.alias import AliasKind
from wiki_api.domain.entity import VariantKind, Visibility
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.provenance import GameVersion
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import GameEnum, HiddenReason, SourceKind
from wiki_api.pipeline.artifact.errors import (
    InvalidOverlayDocument,
    OverlaySchemaMismatch,
)

OVERLAY_SCHEMA: Final = 1


def coerce_entity_key(value: Any) -> Any:
    """Turn the compact form an overlay writes into to a real key."""
    if isinstance(value, str):
        return EntityKey.parse(value)
    return value


EntityRef = Annotated[EntityKey, BeforeValidator(coerce_entity_key)]


class OverlayMode(GameEnum):
    """Whether a document defines an entity or corrects one already defined."""

    DEFINE = "define"
    PATCH = "patch"


class OverlayEntity(BaseModel):
    """One entity as a document declares it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: EntityType
    id: int = Field(ge=0)
    mode: OverlayMode = OverlayMode.DEFINE
    name: str | None = None
    description: str | None = None
    source_key: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    canonical_id: int | None = Field(default=None, ge=0)
    variant_kind: VariantKind | None = None
    visibility: Visibility | None = None
    hidden_reason: HiddenReason | None = None
    searchable: bool | None = None
    icon_ref: str | None = None
    source_ref: str | None = None

    @model_validator(mode="after")
    def _definitions_need_a_name(self) -> Self:
        if self.mode is OverlayMode.DEFINE and self.name is None:
            raise ValueError(f"{self.type.value}:{self.id} is defined without a name")
        return self

    @property
    def key(self) -> EntityKey:
        return EntityKey(type=self.type, id=self.id)


class OverlayEdge(BaseModel):
    """One relationship as a document declares it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    src: EntityRef
    rel: RelationshipType
    dst: EntityRef
    attributes: dict[str, Any] = Field(default_factory=dict)
    order_key: int = 0
    source_ref: str | None = None

    def __str__(self) -> str:
        return f"{self.src} {self.rel.value} {self.dst}"


class OverlayAlias(BaseModel):
    """One alias as a document declares it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: EntityType
    slug: str = Field(min_length=1)
    id: int = Field(ge=0)
    kind: AliasKind = AliasKind.ALTERNATE_NAME

    @property
    def key(self) -> EntityKey:
        return EntityKey(type=self.type, id=self.id)


class OverlayPrice(BaseModel):
    """One price as a document declares it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: int = Field(ge=0)
    snapshot_date: date
    value: int = Field(ge=0)


class OverlayDocument(BaseModel):
    """One document, with the source and game version everything in it inherits."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schema")
    source: SourceKind
    game_version: GameVersion
    source_file: str | None = None
    precedence: int = 0
    entities: tuple[OverlayEntity, ...] = ()
    edges: tuple[OverlayEdge, ...] = ()
    aliases: tuple[OverlayAlias, ...] = ()
    prices: tuple[OverlayPrice, ...] = ()


class OverlaySource(BaseModel):
    """A document together with the file it was read from."""

    model_config = ConfigDict(frozen=True)

    origin: str
    document: OverlayDocument

    @property
    def sort_key(self) -> tuple[int, str]:
        return (self.document.precedence, self.origin)


def load_document(path: Path) -> OverlaySource:
    """Read and validate one document, naming the file if it is malformed."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        document = OverlayDocument.model_validate(payload)
    except ValidationError as error:
        raise InvalidOverlayDocument(path.name, _first_problem(error)) from error
    if document.schema_version != OVERLAY_SCHEMA:
        raise OverlaySchemaMismatch(path.name, document.schema_version, OVERLAY_SCHEMA)
    return OverlaySource(origin=path.name, document=document)


def _first_problem(error: ValidationError) -> str:
    errors = error.errors()
    if not errors:
        return str(error)
    first = errors[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}" if location else str(first["msg"])


def load_documents(directory: Path) -> tuple[OverlaySource, ...]:
    """Read every document in a directory, ordered by precedence and then by name."""
    sources = [load_document(path) for path in sorted(directory.rglob("*.json"))]
    return tuple(sorted(sources, key=lambda source: source.sort_key))


# test cases


def _document(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": OVERLAY_SCHEMA,
        "source": "fixture",
        "game_version": "test",
    }
    payload.update(overrides)
    return payload


def _write(path: Path, **overrides: Any) -> Path:
    path.write_text(json.dumps(_document(**overrides)), encoding="utf-8")
    return path


def test_a_document_declares_its_schema_source_and_game_version() -> None:
    document = OverlayDocument.model_validate(_document())
    assert document.schema_version == OVERLAY_SCHEMA
    assert document.source is SourceKind.FIXTURE
    assert document.entities == ()
    assert document.precedence == 0


def test_a_document_names_the_kind_of_source_and_the_file_behind_it() -> None:
    document = OverlayDocument.model_validate(
        _document(source="game_config", source_file="item_configs.json")
    )
    assert document.source is SourceKind.GAME_CONFIG
    assert document.source_file == "item_configs.json"


def test_a_source_outside_the_vocabulary_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayDocument.model_validate(_document(source="item_configs.json"))


def test_an_entity_definition_needs_a_name() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayEntity.model_validate({"type": "item", "id": 4587})


def test_a_patch_may_omit_the_name() -> None:
    patch = OverlayEntity.model_validate(
        {"type": "item", "id": 4587, "mode": "patch", "description": "corrected"}
    )
    assert patch.name is None
    assert patch.mode is OverlayMode.PATCH


def test_edges_reference_entities_by_compact_key() -> None:
    edge = OverlayEdge.model_validate(
        {"src": "npc:50", "rel": "drops", "dst": "item:536"}
    )
    assert edge.src == EntityKey(type=EntityType.NPC, id=50)
    assert edge.dst == EntityKey(type=EntityType.ITEM, id=536)


def test_an_edge_no_longer_authors_its_own_key() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayEdge.model_validate(
            {"src": "npc:50", "rel": "drops", "dst": "item:536", "discriminator": "x"}
        )


def test_a_price_arrives_as_a_date_rather_than_text() -> None:
    price = OverlayPrice.model_validate(
        {"item_id": 4587, "snapshot_date": "2024-06-08", "value": 106049}
    )
    assert price.snapshot_date == date(2024, 6, 8)


def test_a_price_that_is_not_a_date_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayPrice.model_validate(
            {"item_id": 4587, "snapshot_date": "last tuesday", "value": 1}
        )


def test_unknown_keys_in_a_document_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayDocument.model_validate(_document(entites=[]))


def test_documents_load_in_precedence_then_name_order(tmp_path: Path) -> None:
    _write(tmp_path / "b_source.json")
    _write(tmp_path / "a_source.json")
    _write(tmp_path / "correction.json", precedence=10, source="overlay")
    origins = [source.origin for source in load_documents(tmp_path)]
    assert origins == ["a_source.json", "b_source.json", "correction.json"]


def test_a_document_from_another_overlay_schema_is_rejected(tmp_path: Path) -> None:
    import pytest

    path = _write(tmp_path / "future.json", schema=OVERLAY_SCHEMA + 1)
    with pytest.raises(OverlaySchemaMismatch):
        load_document(path)


def test_a_malformed_entity_key_fails_on_load_naming_the_file(tmp_path: Path) -> None:
    import pytest

    path = _write(
        tmp_path / "edges.json",
        entities=[{"type": "npc", "id": 50, "name": "King Black Dragon"}],
        edges=[{"src": "banana", "rel": "drops", "dst": "item:536"}],
    )
    with pytest.raises(InvalidOverlayDocument) as caught:
        load_document(path)
    assert caught.value.origin == "edges.json"
    assert "edges.0.src" in str(caught.value)


def test_a_malformed_price_fails_on_load_rather_than_during_the_merge(
    tmp_path: Path,
) -> None:
    import pytest

    path = _write(
        tmp_path / "prices.json",
        prices=[{"item_id": 4587, "snapshot_date": "not-a-date", "value": 1}],
    )
    with pytest.raises(InvalidOverlayDocument) as caught:
        load_document(path)
    assert "prices.0.snapshot_date" in str(caught.value)
