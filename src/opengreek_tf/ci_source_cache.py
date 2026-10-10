"""Bounded CI object-cache acquisition for immutable Open Greek sources (#34).

A cache supplies Git objects, never a Git checkout, origin or source authority.
All source identity checks are repeated on both cache hits and misses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .release import SUPPORTED_RELEASE, ReleaseIdentity

TEXT_FAMILY_PATTERNS: tuple[str, ...] = (
    "/data/corpus_release.json",
    "/data/corpus/",
    "/data/corpus_secondary/",
    "/data/paratext/",
)


class PinnedCacheError(RuntimeError):
    """Source cache or immutable acquisition could not be safely validated."""


@dataclass(frozen=True, slots=True)
class SourceTiming:
    acquisition_seconds: float
    verification_seconds: float
    object_bytes: int
    recovery_attempted: bool


def cache_key(
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
    *,
    platform: str = "Linux",
) -> str:
    raise NotImplementedError


def prepare_source(
    root: Path, *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
) -> str:
    raise NotImplementedError


def check_cached_objects(root: Path) -> None:
    raise NotImplementedError


def verify_checkout(
    root: Path, *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    expected_files: tuple[int, int, int] | None = (3909, 533, 5),
) -> None:
    raise NotImplementedError


def checkout_source(
    root: Path, *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
    expected_files: tuple[int, int, int] | None = (3909, 533, 5),
) -> SourceTiming:
    raise NotImplementedError


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
