"""Independent source profile for primary Greek native scale (RED scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PrimarySourceProfileError(ValueError):
    """Original primary JSONL cannot be safely profiled."""


@dataclass(frozen=True, slots=True)
class PrimarySourceProfile:
    source_files: int
    file_records: tuple[int, ...]
    records: int
    original_codepoints: int
    text_layout_atoms: int
    source_anchor_atoms: int
    total_atoms: int
    max_passage_codepoints: int
    max_layout_atoms: int
    source_bytes: int
    source_sha256: str


def profile_primary_sources(
    root: Path, relative_files: tuple[str, ...],
) -> PrimarySourceProfile:
    raise NotImplementedError("RED: independently audit source bytes before scaling")
