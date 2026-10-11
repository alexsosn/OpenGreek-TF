"""Generic native Text-Fabric composer for typed source records (RED scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .record_stream import FieldObject


class NativeComposeError(ValueError):
    """Native TF source graph failed its conservation contract."""


@dataclass(frozen=True, slots=True)
class NativeRecord:
    source_file: str
    ordinal: int
    source_record_id: str
    record_kind: str
    fields: FieldObject
    text: str | None = None


@dataclass(frozen=True, slots=True)
class NativeStats:
    records: int
    metadata_records: int
    text_records: int
    source_atoms: int
    fact_nodes: int


def write_native_records(records: tuple[NativeRecord, ...], destination: Path) -> NativeStats:
    raise NotImplementedError("RED native generic composer gate")


def read_native_records(destination: Path) -> tuple[NativeRecord, ...]:
    raise NotImplementedError("RED native composer reader gate")


def validate_native_records(
    records: tuple[NativeRecord, ...], destination: Path,
) -> NativeStats:
    raise NotImplementedError("RED whole-graph conservation gate")
