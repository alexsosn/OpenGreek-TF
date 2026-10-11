"""Pinned Open Greek TLG crosswalk: ordered native Text-Fabric source facts (#7).

RED-phase API scaffold. The real writer must not infer one-to-one CTS/TLG
mappings, invent Greek word slots, or collapse absent versus empty strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class CrosswalkError(ValueError):
    """Source crosswalk or native TF fails lossless conservation."""


@dataclass(frozen=True, slots=True)
class CrosswalkRecord:
    identifier: str
    ordinal: int
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CrosswalkStats:
    records: int
    fields: int
    empty_values: int
    source_atoms: int


def parse_tlg_crosswalk(source_root: Path) -> tuple[CrosswalkRecord, ...]:
    raise NotImplementedError("RED gate: full crosswalk parser not implemented")


def write_tlg_crosswalk_tf(
    source_root: Path, destination: Path,
) -> CrosswalkStats:
    raise NotImplementedError("RED gate: native TF writer not implemented")


def read_tlg_crosswalk_tf(destination: Path) -> tuple[CrosswalkRecord, ...]:
    raise NotImplementedError("RED gate: independent TF reader not implemented")


def validate_tlg_crosswalk_tf(
    source_root: Path, destination: Path,
) -> CrosswalkStats:
    raise NotImplementedError("RED gate: conservation validator not implemented")
