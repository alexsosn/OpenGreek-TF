"""Original secondary witnesses and paratext as *unaligned* native TF.

A witness or paratext source occurrence is preserved with every original
typed fact but never made to look like primary Greek text or a witnessed
alignment. This is a thin adapter to the generic Text-Fabric composer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats, write_native_records
from .record_stream import parse_file

_SOURCE_KINDS = {
    "corpus_secondary": ("secondary", "secondary-witness"),
    "paratext": ("paratext", "paratext-record"),
}


def _check_files(root: Path, relative_files: tuple[str, ...]) -> None:
    """Prevalidate source file identities, forbidding duplicates or escapes."""
    if not relative_files:
        raise ValueError("no secondary or paratext source files selected")
    seen_files: set[str] = set()
    physical_files: set[Path] = set()
    source_root = root.resolve()
    for relative in relative_files:
        if type(relative) is not str:
            raise ValueError("unaligned source file must have a string path")
        path = Path(relative)
        if (
            path.is_absolute()
            or path.as_posix() != relative
            or len(path.parts) != 3
            or path.parts[0] != "data"
            or path.parts[1] not in _SOURCE_KINDS
            or path.suffix != ".jsonl"
        ):
            raise ValueError(f"unsupported canonical unaligned source path: {relative!r}")
        if relative in seen_files:
            raise ValueError(f"duplicate selected unaligned source file: {relative}")
        seen_files.add(relative)
        physical = (root / relative).resolve()
        if not physical.is_relative_to(source_root):
            raise ValueError(f"unaligned source file escapes source root: {relative}")
        if physical in physical_files:
            raise ValueError(f"duplicate physical unaligned source file: {relative}")
        physical_files.add(physical)


def iter_native_unaligned(
    root: Path, relative_files: tuple[str, ...],
) -> Iterator[NativeRecord]:
    """Read real witness/paratext records without asserting an alignment.

    File order is caller-given, then 1-based physical source-line order.
    Original "text" is an ordinary native string source fact: these are
    nonprimary metadata records with no Text-Fabric text-layout slots.
    """
    _check_files(root, relative_files)
    for relative in relative_files:
        family, record_kind = _SOURCE_KINDS[Path(relative).parts[1]]
        for row in parse_file(root, relative):
            if row.family != family:
                raise ValueError(f"unexpected source family for {relative}")
            yield NativeRecord(
                source_file=row.relative_file,
                ordinal=row.ordinal,
                source_record_id=f"{row.relative_file}:{row.ordinal}",
                record_kind=record_kind,
                fields=row.fields,
                text=None,
            )


def materialize_unaligned(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> NativeStats:
    """Store genuine unaligned data in one loadable metadata-only TF graph.

    Finish all strict source validation before emitting native TF. This proof
    is not bounded-memory streaming or a full corpus/ontology release.
    """
    source_records = tuple(iter_native_unaligned(root, relative_files))
    return write_native_records(source_records, destination)
