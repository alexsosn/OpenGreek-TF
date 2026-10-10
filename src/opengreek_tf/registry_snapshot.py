"""Full identity-*ledger* native Text-Fabric batch, not the broader catalog (#20)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LedgerSnapshotStats:
    authors: int
    works: int
    retired_authors: int
    retired_works: int
    former_slug_facts: int
    source_atoms: int


def write_full_registry_snapshot(source_root: Path, destination: Path) -> LedgerSnapshotStats:
    """Emit all source-declared author/work ID-ledger entries; fail closed."""
    raise NotImplementedError


def validate_full_registry_snapshot(
    source_root: Path, destination: Path,
) -> LedgerSnapshotStats:
    """Compare independent source JSON against loaded native TF, exhaustively."""
    raise NotImplementedError
