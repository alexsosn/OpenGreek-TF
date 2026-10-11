"""Pinned author authority JSON → native TF, research batch for issue #20."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AuthorityValue = str | int | tuple[str, ...]


class AuthorityError(ValueError):
    """Source data or loaded TF violates authority conservation."""


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    key: str
    ordinal: int
    fields: tuple[tuple[str, AuthorityValue], ...]


@dataclass(frozen=True, slots=True)
class AuthorityStats:
    records: int
    fields: int
    array_items: int
    source_atoms: int


def parse_author_authority(source_root: Path) -> tuple[AuthorityRecord, ...]:
    raise NotImplementedError


def write_author_authority_tf(source_root: Path, destination: Path) -> AuthorityStats:
    raise NotImplementedError


def read_author_authority_tf(destination: Path) -> tuple[AuthorityRecord, ...]:
    raise NotImplementedError


def validate_author_authority_tf(
    source_root: Path, destination: Path,
) -> AuthorityStats:
    raise NotImplementedError
