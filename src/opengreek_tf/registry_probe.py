"""Native source-ledger TF atom research proof (issue #20, not a corpus writer)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RegistryKind = Literal["author", "work"]


class RegistryProbeError(ValueError):
    """An identity ledger or generated native TF graph violates the source contract."""


@dataclass(frozen=True, slots=True)
class LedgerRecord:
    kind: RegistryKind
    identifier: str
    source_file: str
    ordinal: int
    slug: str
    status: str
    former_slugs: tuple[str, ...]


def parse_ledger(root: Path, kind: RegistryKind) -> tuple[LedgerRecord, ...]:
    raise NotImplementedError


def write_registry_probe(
    source_root: Path,
    destination: Path,
    *,
    authors: tuple[str, ...],
    works: tuple[str, ...],
) -> None:
    raise NotImplementedError


def read_registry_probe(destination: Path) -> tuple[LedgerRecord, ...]:
    raise NotImplementedError
