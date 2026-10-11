"""Faithful multi-file primary Greek passage adapter for native Text-Fabric.

This is a thin typed-source adapter, not an alternative TF converter.
The shared generic native composer conserves all ordered typed fields.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats, write_native_records
from .record_stream import parse_file


def _check_files(root: Path, relative_files: tuple[str, ...]) -> None:
    """Reject duplicate, nonprimary and source-escaping selections before output."""
    if not relative_files:
        raise ValueError("no primary JSONL source files selected")
    visited: set[str] = set()
    physical_files: set[Path] = set()
    source_root = root.resolve()
    for relative in relative_files:
        if type(relative) is not str:
            raise ValueError("primary source path must be a string")
        path = Path(relative)
        if (
            path.is_absolute()
            or path.as_posix() != relative
            or len(path.parts) != 3
            or path.parts[:2] != ("data", "corpus")
            or path.suffix != ".jsonl"
        ):
            raise ValueError(f"not a canonical primary source path: {relative!r}")
        if relative in visited:
            raise ValueError(f"duplicate selected primary source file: {relative}")
        visited.add(relative)
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(source_root):
            raise ValueError(f"primary source file escapes source root: {relative}")
        if resolved in physical_files:
            raise ValueError(f"duplicate selected physical primary source file: {relative}")
        physical_files.add(resolved)


def iter_native_primary(
    root: Path, relative_files: tuple[str, ...],
) -> Iterator[NativeRecord]:
    """Preserve caller file order, then 1-based physical JSONL row order.

    A source occurrence key is a technical, physically verifiable identity;
    it is *not* an inferred CTS/work/edition equivalence.
    """
    _check_files(root, relative_files)
    for relative in relative_files:
        for row in parse_file(root, relative):
            if row.family != "primary":
                raise ValueError("nonprimary source record selected")
            yield NativeRecord(
                source_file=row.relative_file,
                ordinal=row.ordinal,
                source_record_id=f"{row.relative_file}:{row.ordinal}",
                record_kind="primary-passage",
                fields=row.fields,
                text=row.text,
            )


def materialize_primary(
    root: Path,
    relative_files: tuple[str, ...],
    destination: Path,
    *,
    on_phase: Callable[[str], None] | None = None,
) -> NativeStats:
    """Write the complete selected primary sample as one native TF graph.

    Parsing and schema validation finish before creating the output, so a
    malformed record in the final file cannot leave a partial successful TF.
    This API remains all-at-once; it is *not* streaming in bounded memory.
    """
    source_records = tuple(iter_native_primary(root, relative_files))
    if on_phase is not None:
        on_phase("source-input-loaded")
    return write_native_records(source_records, destination, on_phase=on_phase)
