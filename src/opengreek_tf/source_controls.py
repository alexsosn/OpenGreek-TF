"""Lossless, bounded-memory provenance of CR controls in typed source records.

Diagnostic only: this does not normalize source strings or encode them into TF.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .record_stream import Family, FieldArray, FieldObject, FieldValue, ParsedRecord


@dataclass(frozen=True, slots=True)
class CarriageReturnHit:
    """Physical source location and typed nested field path containing U+000D."""

    family: Family
    relative_file: str
    ordinal: int
    field_path: str
    count: int


def iter_carriage_returns(row: ParsedRecord) -> Iterator[CarriageReturnHit]:
    """Yield all CR-containing typed source strings, never copying text content."""

    def visit(value: FieldValue, path: str) -> Iterator[CarriageReturnHit]:
        if isinstance(value, str):
            count = value.count("\r")
            if count:
                yield CarriageReturnHit(
                    family=row.family,
                    relative_file=row.relative_file,
                    ordinal=row.ordinal,
                    field_path=path,
                    count=count,
                )
        elif isinstance(value, FieldObject):
            for key, nested in value.items:
                child_path = f"{path}.{key}" if path else key
                yield from visit(nested, child_path)
        elif isinstance(value, FieldArray):
            for index, nested in enumerate(value.items):
                yield from visit(nested, f"{path}[{index}]")

    yield from visit(row.fields, "")
