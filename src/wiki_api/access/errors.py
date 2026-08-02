"""What can go wrong before a single request is answered."""

from __future__ import annotations


class AccessError(Exception):
    """Something about who may be answered is wrong."""


class AccessMisconfigured(AccessError):
    """This deployment cannot decide who to answer, so it will not answer anyone."""


class IssuerExists(AccessError):
    """There is already a key here, and overwriting it would refuse every token ever
    issued from it.
    """


# test cases


def test_every_way_this_fails_is_one_family() -> None:
    assert issubclass(AccessMisconfigured, AccessError)
    assert issubclass(IssuerExists, AccessError)


def test_a_misconfiguration_reads_as_a_sentence() -> None:
    assert str(AccessMisconfigured("no public key was configured")) == (
        "no public key was configured"
    )
