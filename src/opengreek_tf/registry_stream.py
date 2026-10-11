"""Typed source-registry reader, pending RED-first implementation (#5)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .record_stream import FieldObject

Kind = Literal["author", "work"]


class RegistryError(ValueError):
    """Pinned source registry violates declared semantic schema."""


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    kind: Kind
    slug: str
    ordinal: int
    fields: FieldObject
    relative_file: str = "data/source_registry.json"

    @property
    def occurrence_key(self) -> tuple[str, int]:
        return (f"{self.relative_file}#{self.kind}s", self.ordinal)


def iter_registry(source_root: Path) -> Iterator[RegistryRecord]:
    raise NotImplementedError("RED gate: registry source parser not implemented")
    yield  # pragma: no cover
