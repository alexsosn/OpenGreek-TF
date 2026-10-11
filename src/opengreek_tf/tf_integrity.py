"""Native TF feature integrity manifest (RED-first scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class NativeTfIntegrityError(ValueError):
    """Malformed or unverifiable native Text-Fabric feature files."""


@dataclass(frozen=True, slots=True)
class NativeTfManifest:
    tf_file_count: int
    output_bytes: int
    raw_sha256: str
    canonical_sha256: str


def native_tf_manifest(destination: Path) -> NativeTfManifest:
    raise NotImplementedError("RED gate: semantic feature manifest unavailable")
