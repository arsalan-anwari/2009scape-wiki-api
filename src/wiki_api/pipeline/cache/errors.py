"""Errors the cache decoders raise, each naming what it was reading and where."""

from __future__ import annotations

from wiki_api.domain.errors import KnowledgeError


class CacheError(KnowledgeError):
    """Base class for anything that stops the game cache being read."""


class CacheMissing(CacheError):
    """The cache files are not where the collector expects them."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"no game cache at {path}: check the submodules are checked out"
        )
        self.path = path


class IndexMissing(CacheError):
    """An index this build reads has no file in the cache directory."""

    def __init__(self, index: int, path: str) -> None:
        super().__init__(f"index {index} has no file at {path}")
        self.index = index
        self.path = path


class MalformedContainer(CacheError):
    """A container does not hold what its own header says it holds."""

    def __init__(self, index: int, container: int, detail: str) -> None:
        super().__init__(f"index {index} container {container} is malformed: {detail}")
        self.index = index
        self.container = container
        self.detail = detail


class ArchiveUnreadable(CacheError):
    """An archive is present but its bytes did not survive being unpacked."""

    def __init__(self, index: int, archive: int, detail: str) -> None:
        super().__init__(f"index {index} archive {archive} did not unpack: {detail}")
        self.index = index
        self.archive = archive
        self.detail = detail


class UnknownOpcode(CacheError):
    """A definition carries an opcode the game's own decoder does not declare."""

    def __init__(self, kind: str, identity: int, opcode: int, offset: int) -> None:
        super().__init__(
            f"{kind} {identity} carries opcode {opcode} at byte {offset}, "
            f"which is not in the table this decoder was transcribed from"
        )
        self.kind = kind
        self.identity = identity
        self.opcode = opcode
        self.offset = offset


class TruncatedDefinition(CacheError):
    """A definition ran out of bytes part way through a field."""

    def __init__(self, kind: str, identity: int, wanted: int, left: int) -> None:
        super().__init__(f"{kind} {identity} wanted {wanted} more bytes and had {left}")
        self.kind = kind
        self.identity = identity
        self.wanted = wanted
        self.left = left


# test cases


def test_every_cache_error_is_a_knowledge_error() -> None:
    errors = (
        CacheMissing("game_data/2009scape/Server/data/cache"),
        IndexMissing(19, "main_file_cache.idx19"),
        MalformedContainer(5, 1234, "sector points outside the data file"),
        ArchiveUnreadable(5, 1234, "no decryption key"),
        UnknownOpcode("item", 4587, 200, 41),
        TruncatedDefinition("item", 4587, 4, 1),
    )
    assert all(isinstance(error, CacheError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_an_unknown_opcode_names_the_definition_and_the_offset() -> None:
    error = UnknownOpcode("scenery", 1276, 201, 88)
    assert "scenery 1276" in str(error)
    assert "201" in str(error)
    assert "88" in str(error)
