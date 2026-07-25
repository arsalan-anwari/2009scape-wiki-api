from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.alias import AliasKind
from wiki_api.domain.entity import VariantKind, Visibility
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.pipeline.artifact.errors import OverlaySchemaMismatch

if TYPE_CHECKING:
    pass

OVERLAY_SCHEMA: Final = 1


class OverlayMode(StrEnum):
    DEFINE = "define"
    PATCH = "patch"


class OverlayEntity(BaseModel):
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
    hidden_reason: str | None = None
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
    model_config = ConfigDict(frozen=True, extra="forbid")

    src: str
    rel: RelationshipType
    dst: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    discriminator: str = ""
    order_key: int = 0
    source_ref: str | None = None

    @property
    def src_key(self) -> EntityKey:
        return EntityKey.parse(self.src)

    @property
    def dst_key(self) -> EntityKey:
        return EntityKey.parse(self.dst)


class OverlayAlias(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: EntityType
    slug: str = Field(min_length=1)
    id: int = Field(ge=0)
    kind: AliasKind = AliasKind.ALTERNATE_NAME

    @property
    def key(self) -> EntityKey:
        return EntityKey(type=self.type, id=self.id)


class OverlayPrice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: int = Field(ge=0)
    snapshot_date: str
    value: int = Field(ge=0)


class OverlayDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schema")
    source: str = Field(min_length=1)
    game_version: str = Field(min_length=1)
    precedence: int = 0
    entities: tuple[OverlayEntity, ...] = ()
    edges: tuple[OverlayEdge, ...] = ()
    aliases: tuple[OverlayAlias, ...] = ()
    prices: tuple[OverlayPrice, ...] = ()


class OverlaySource(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin: str
    document: OverlayDocument

    @property
    def sort_key(self) -> tuple[int, str]:
        return (self.document.precedence, self.origin)


def load_document(path: Path) -> OverlaySource:
    payload = json.loads(path.read_text(encoding="utf-8"))
    document = OverlayDocument.model_validate(payload)
    if document.schema_version != OVERLAY_SCHEMA:
        raise OverlaySchemaMismatch(path.name, document.schema_version, OVERLAY_SCHEMA)
    return OverlaySource(origin=path.name, document=document)


def load_documents(directory: Path) -> tuple[OverlaySource, ...]:
    sources = [load_document(path) for path in sorted(directory.rglob("*.json"))]
    return tuple(sorted(sources, key=lambda source: source.sort_key))


def _document(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": OVERLAY_SCHEMA,
        "source": "fixture",
        "game_version": "test",
    }
    payload.update(overrides)
    return payload


def test_a_document_declares_its_schema_source_and_game_version() -> None:
    document = OverlayDocument.model_validate(_document())
    assert document.schema_version == OVERLAY_SCHEMA
    assert document.entities == ()
    assert document.precedence == 0


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
    assert edge.src_key == EntityKey(type=EntityType.NPC, id=50)
    assert edge.dst_key == EntityKey(type=EntityType.ITEM, id=536)


def test_unknown_keys_in_a_document_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        OverlayDocument.model_validate(_document(entites=[]))


def test_documents_load_in_precedence_then_name_order(tmp_path: Path) -> None:
    (tmp_path / "b_source.json").write_text(json.dumps(_document()), encoding="utf-8")
    (tmp_path / "a_source.json").write_text(json.dumps(_document()), encoding="utf-8")
    (tmp_path / "correction.json").write_text(
        json.dumps(_document(precedence=10, source="overlay")), encoding="utf-8"
    )
    origins = [source.origin for source in load_documents(tmp_path)]
    assert origins == ["a_source.json", "b_source.json", "correction.json"]


def test_a_document_from_another_overlay_schema_is_rejected(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "future.json"
    path.write_text(
        json.dumps(_document(schema=OVERLAY_SCHEMA + 1)),
        encoding="utf-8",
    )
    with pytest.raises(OverlaySchemaMismatch):
        load_document(path)
