"""Whole pinned grouped TLG work-authority graph in native Text-Fabric (#20)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

WorkFieldValue: TypeAlias = str | int | tuple[str, ...]


class WorkAuthorityError(ValueError):
    """Source or TF violates grouped-work authority conservation."""


@dataclass(frozen=True, slots=True)
class WorkEntry:
    index: int
    fields: tuple[tuple[str, WorkFieldValue], ...]


@dataclass(frozen=True, slots=True)
class WorkGroup:
    key: str
    ordinal: int
    works: tuple[WorkEntry, ...]


@dataclass(frozen=True, slots=True)
class WorkAuthorityStats:
    groups: int
    works: int
    fields: int
    array_items: int
    source_atoms: int


def parse_work_authority(source_root: Path) -> tuple[WorkGroup, ...]:
    raise NotImplementedError


def write_work_authority_tf(source_root: Path, destination: Path) -> WorkAuthorityStats:
    raise NotImplementedError


def read_work_authority_tf(destination: Path) -> tuple[WorkGroup, ...]:
    raise NotImplementedError


def validate_work_authority_tf(
    source_root: Path, destination: Path,
) -> WorkAuthorityStats:
    raise NotImplementedError
