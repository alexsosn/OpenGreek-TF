"""Full source registry to generic native TF adapter (RED scaffold)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .native_composer import NativeRecord, NativeStats


def iter_native_registry(root: Path) -> Iterator[NativeRecord]:
    raise NotImplementedError("RED gate: complete native source registry adapter")
    yield  # pragma: no cover


def materialize_registry(root: Path, destination: Path) -> NativeStats:
    raise NotImplementedError("RED gate: full-registry native TF materializer")
