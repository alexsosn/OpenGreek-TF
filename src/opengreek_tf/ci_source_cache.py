"""A verified, reusable Git-object cache for pinned text-family CI (#34).

Caches are untrusted performance hints. Each run creates a fresh .git config,
index and sparse spec, then revalidates a detached immutable source checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .release import SUPPORTED_RELEASE, ReleaseIdentity
from .source import SourceAcquisitionError, validate_revision, verify_source

TEXT_FAMILY_PATTERNS: tuple[str, ...] = (
    "/data/corpus_release.json",
    "/data/corpus/",
    "/data/corpus_secondary/",
    "/data/paratext/",
)
_HEX = re.compile(r"[0-9a-f]{40}\Z")
_LOOSE = re.compile(r"[0-9a-f]{38}\Z")
_PACK = re.compile(r"pack-[0-9a-f]{40,64}\.(?:pack|idx|rev|promisor|bitmap|mtimes)\Z")
_PLATFORM = re.compile(r"[A-Za-z0-9_-]+\Z")


class PinnedCacheError(RuntimeError):
    """Object cache or immutable acquisition could not be safely verified."""


@dataclass(frozen=True, slots=True)
class SourceTiming:
    acquisition_seconds: float
    verification_seconds: float
    object_bytes: int
    recovery_attempted: bool


def _patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    if not patterns or len(set(patterns)) != len(patterns):
        raise PinnedCacheError("empty or duplicate sparse source scope")
    for pattern in patterns:
        if (
            not pattern.startswith("/")
            or ".." in pattern
            or "\\" in pattern
            or any(c in pattern for c in ("*", "?", "[", "]", "\n", "\r"))
            or not (pattern.endswith("/") or pattern.endswith(".json"))
        ):
            raise PinnedCacheError(f"untrusted sparse pattern {pattern!r}")
    return tuple(sorted(patterns))


def cache_key(
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
    *,
    platform: str = "Linux",
) -> str:
    if not _PLATFORM.fullmatch(platform):
        raise PinnedCacheError("invalid cache platform")
    try:
        revision = validate_revision(identity.commit)
    except SourceAcquisitionError as exc:
        raise PinnedCacheError("cache requires a full immutable Git revision") from exc
    scope = _patterns(patterns)
    payload = json.dumps(
        {"repo": identity.repository.lower().removesuffix(".git"),
         "revision": revision, "scope": scope},
        sort_keys=True, separators=(",", ":"),
    )
    scope_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"opengreek-gitobjects-v1-{platform}-{revision}-{scope_id}"


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True,
            timeout=420,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PinnedCacheError(f"Git operation failed: {' '.join(args[:4])}") from exc
    return result.stdout.strip()


def _scope_path(root: Path) -> Path:
    return root / ".git" / "info" / "sparse-checkout"


def prepare_source(
    root: Path,
    *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
) -> str:
    """Initialize new checkout metadata, before a cache restores ONLY objects."""
    scope = _patterns(patterns)
    key = cache_key(identity, patterns)
    if root.exists() or root.is_symlink():
        raise PinnedCacheError(f"source checkout must not already exist: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git("init", "-q", str(root))
        _git("-C", str(root), "remote", "add", "origin", identity.repository)
        _git("-C", str(root), "sparse-checkout", "init", "--no-cone")
        _scope_path(root).write_text("\n".join(patterns) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    if set(_scope_path(root).read_text().splitlines()) != set(scope):
        raise PinnedCacheError("prepared sparse scope disagrees with cache key")
    return key


def check_cached_objects(root: Path) -> None:
    """Never hand Git object-cache symlinks, alternates or unknown files."""
    objects = root / ".git" / "objects"
    if objects.is_symlink() or not objects.is_dir():
        raise PinnedCacheError("Git object directory is absent or a symlink")
    for entry in objects.rglob("*"):
        if entry.is_symlink():
            raise PinnedCacheError("symbolic link in Git object cache")
        rel = entry.relative_to(objects).parts
        if entry.is_dir():
            if len(rel) != 1 or (
                rel[0] not in {"pack", "info"}
                and not re.fullmatch(r"[0-9a-f]{2}", rel[0])
            ):
                raise PinnedCacheError("unexpected Git object-cache directory")
            continue
        if not entry.is_file() or len(rel) != 2:
            raise PinnedCacheError("unexpected Git object-cache item")
        directory, name = rel
        if directory == "pack":
            valid = _PACK.fullmatch(name) is not None
        elif directory == "info":
            valid = name in {"packs", "commit-graph"}
        else:
            valid = bool(re.fullmatch(r"[0-9a-f]{2}", directory) and _LOOSE.fullmatch(name))
        if not valid:
            raise PinnedCacheError(f"untrusted Git object-cache item: {entry.name}")


def _reset_object_cache(root: Path) -> None:
    objects = root / ".git" / "objects"
    if objects.is_symlink():
        objects.unlink()
    elif objects.exists():
        shutil.rmtree(objects)
    (objects / "info").mkdir(parents=True, exist_ok=True)
    (objects / "pack").mkdir(parents=True, exist_ok=True)


def verify_checkout(
    root: Path,
    *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    expected_files: tuple[int, int, int] | None = (3909, 533, 5),
) -> None:
    """Check fresh Git tree, worktree integrity, origin and source manifest."""
    try:
        snapshot = verify_source(root, identity=identity)
        if snapshot.revision != validate_revision(identity.commit):
            raise PinnedCacheError("wrong pinned revision")
    except SourceAcquisitionError as exc:
        raise PinnedCacheError(f"verified source identity failed: {exc}") from exc
    _git("-C", str(root), "fsck", "--full", "--no-reflogs")
    if _git("-C", str(root), "diff", "--name-only", "HEAD", "--"):
        raise PinnedCacheError("pinned worktree content differs from HEAD")
    if expected_files is not None:
        actual = tuple(
            len(list((root / "data" / dirname).glob("*.jsonl")))
            for dirname in ("corpus", "corpus_secondary", "paratext")
        )
        if actual != expected_files:
            raise PinnedCacheError(
                f"pinned sparse scope incomplete: expected {expected_files}, got {actual}"
            )


def _object_bytes(root: Path) -> int:
    return sum(
        p.stat().st_size for p in (root / ".git" / "objects").rglob("*")
        if p.is_file() and not p.is_symlink()
    )


def checkout_source(
    root: Path,
    *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
    patterns: tuple[str, ...] = TEXT_FAMILY_PATTERNS,
    expected_files: tuple[int, int, int] | None = (3909, 533, 5),
) -> SourceTiming:
    """Bounded cache validation then exact SHA acquisition with one clean retry."""
    expected = set(_patterns(patterns))
    sparse = _scope_path(root)
    if root.is_symlink() or not sparse.is_file():
        raise PinnedCacheError("source checkout was not prepared")
    lines = sparse.read_text(encoding="utf-8").splitlines()
    if len(lines) != len(expected) or set(lines) != expected:
        raise PinnedCacheError("pinned sparse source scope changed")
    if _git("-C", str(root), "remote", "get-url", "origin") != identity.repository:
        raise PinnedCacheError("prepared source origin was changed")
    started = time.monotonic()
    recover = False
    verification_seconds = 0.0

    for attempt in range(2):
        try:
            check_cached_objects(root)
            _git(
                "-C", str(root), "fetch", "--depth", "1", "--filter=blob:none",
                "origin", validate_revision(identity.commit),
            )
            _git("-C", str(root), "checkout", "--force", "--detach", "FETCH_HEAD")
            verify_started = time.monotonic()
            verify_checkout(root, identity=identity, expected_files=expected_files)
            verification_seconds = time.monotonic() - verify_started
            return SourceTiming(
                acquisition_seconds=round(time.monotonic() - started, 3),
                verification_seconds=round(verification_seconds, 3),
                object_bytes=_object_bytes(root),
                recovery_attempted=recover,
            )
        except (PinnedCacheError, SourceAcquisitionError, OSError) as exc:
            if attempt == 1:
                raise PinnedCacheError(
                    "cached and clean pinned fetch/verification both failed"
                ) from exc
            recover = True
            _reset_object_cache(root)
    raise AssertionError("unreachable bounded checkout state")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "checkout"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--cache-hit", default="false")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            key = prepare_source(args.root)
            output = os.environ.get("GITHUB_OUTPUT")
            if output:
                with open(output, "a", encoding="utf-8") as stream:
                    stream.write(f"key={key}\n")
            print(json.dumps({"cache_key": key, "cache_scope": "text-families"}))
        else:
            result = checkout_source(args.root)
            measured = {
                "cache_hit": args.cache_hit == "true",
                "acquisition_seconds": result.acquisition_seconds,
                "verification_seconds": result.verification_seconds,
                "object_bytes": result.object_bytes,
                "recovered_from_corrupt_cache": result.recovery_attempted,
            }
            print(json.dumps(measured, sort_keys=True))
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as stream:
                    stream.write(
                        "\n## Immutable source checkout cache\n\n"
                        f"- Cache exact-key hit: **{measured['cache_hit']}**\n"
                        f"- Acquisition and verification: "
                        f"**{result.acquisition_seconds}s**\n"
                        f"- Verification: **{result.verification_seconds}s**\n"
                        f"- Git objects on disk: **{result.object_bytes} bytes**\n"
                        f"- Recovery required: **{result.recovery_attempted}**\n"
                    )
        return 0
    except (PinnedCacheError, OSError) as exc:
        print(f"pinned source cache: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
