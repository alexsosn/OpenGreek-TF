"""Writer-independent source JSONL ↔ native TF conservation (RED scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class JsonlConservationError(ValueError):
    """The original source and independently loaded native TF differ."""


@dataclass(frozen=True, slots=True)
class JsonlConservationReport:
    source_files: int
    records: int
    primary_passages: int
    secondary_witnesses: int
    paratext_records: int
    source_fact_nodes: int
    source_unicode_codepoints: int
    original_source_sha256: str


def validate_native_jsonl_sources(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> JsonlConservationReport:
    raise NotImplementedError("RED gate: independent mixed source verifier")
