"""Primary served source to generic native TF adapter (RED scaffold)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats


def iter_native_primary(
    root: Path, relative_files: tuple[str, ...],
) -> Iterator[NativeRecord]:
    raise NotImplementedError("RED primary source adapter")
    yield  # pragma: no cover


def materialize_primary(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> NativeStats:
    raise NotImplementedError("RED multi-file native TF composer")
