"""Isolated native primary writer (#56), intentionally RED-first scaffold."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PrimaryBuildError(ValueError):
    """Isolated native primary build could not be completed."""


def run_isolated_primary_build(
    root: Path,
    relative_files: tuple[str, ...],
    destination: Path,
) -> dict[str, Any]:
    raise NotImplementedError("RED gate: isolated native primary composer")
