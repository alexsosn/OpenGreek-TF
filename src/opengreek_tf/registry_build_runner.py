"""Isolated native source registry build runner (RED scaffold)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class RegistryBuildError(ValueError):
    """Isolated native registry build failed."""


def run_isolated_registry_build(root: Path, destination: Path) -> dict[str, Any]:
    raise NotImplementedError("RED: registry build child-process isolation")
