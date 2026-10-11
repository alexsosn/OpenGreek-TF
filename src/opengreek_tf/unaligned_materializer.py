"""Thin unaligned secondary/paratext source adapter (RED scaffold)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats


def iter_native_unaligned(
    root: Path, relative_files: tuple[str, ...],
) -> Iterator[NativeRecord]:
    raise NotImplementedError("RED: unaligned source adapter")
    yield  # pragma: no cover


def materialize_unaligned(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> NativeStats:
    raise NotImplementedError("RED: native secondary/paratext source materializer")
