"""Materialize a complete source registry through the *generic* native TF composer.

This module is only a typed source-family adapter, not a separate TF writer.
One source occurrence yields one nonlexical metadataRecord and its source facts.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats, write_native_records
from .registry_stream import iter_registry


def iter_native_registry(root: Path) -> Iterator[NativeRecord]:
    """Yield every pinned registry occurrence in author-then-work source order."""
    for row in iter_registry(root):
        yield NativeRecord(
            source_file=row.occurrence_key[0],
            ordinal=row.ordinal,
            source_record_id=row.slug,
            record_kind=f"registry-{row.kind}",
            fields=row.fields,
            text=None,
        )


def materialize_registry(root: Path, destination: Path) -> NativeStats:
    """Convert all source members in a single native TF graph.

    Materialize and validate the input *before* opening a TF destination so a
    malformed later work record cannot leave an apparently complete partial TF.
    The generic composer writes/loads and validates all native source facts.
    """
    records = tuple(iter_native_registry(root))
    return write_native_records(records, destination)
