"""Pinned Open Greek source acquisition and identity verification."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .release import SUPPORTED_RELEASE, ReleaseIdentity

FULL_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class SourceAcquisitionError(RuntimeError):
    """Raised when an Open Greek source checkout cannot be acquired or verified."""


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Identity of a verified local Open Greek source checkout."""

    path: Path
    revision: str


def _run_git(
    args: list[str], *, capture_output: bool = False
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            check=True,
            capture_output=capture_output,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SourceAcquisitionError(f"git command failed: {' '.join(args)}") from exc


def validate_revision(revision: str) -> str:
    """Return a normalized immutable Git commit id or reject the revision."""
    if not FULL_COMMIT_RE.fullmatch(revision):
        raise SourceAcquisitionError(
            "source revision must be a full 40-hex immutable Git commit id"
        )
    return revision.lower()


def _canonical_repository(url: str) -> str:
    """Normalize supported GitHub transport spellings to one repository identity."""
    value = url.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]

    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.removeprefix("ssh://git@github.com/")

    prefix = "https://github.com/"
    if not value.startswith(prefix):
        return value.lower()
    owner_repo = value.removeprefix(prefix)
    return f"github.com/{owner_repo}".lower()


def resolve_revision(source: Path) -> str:
    """Return the exact HEAD revision of a local Git checkout."""
    result = _run_git(["-C", str(source), "rev-parse", "HEAD"], capture_output=True)
    revision = result.stdout.strip()
    if not revision:
        raise SourceAcquisitionError(f"could not resolve source revision: {source}")
    try:
        return validate_revision(revision)
    except SourceAcquisitionError as exc:
        raise SourceAcquisitionError(
            f"git returned a non-commit source revision for {source}: {revision!r}"
        ) from exc


def _resolve_origin(source: Path) -> str:
    result = _run_git(
        ["-C", str(source), "remote", "get-url", "origin"],
        capture_output=True,
    )
    origin = result.stdout.strip()
    if not origin:
        raise SourceAcquisitionError(f"source checkout has no origin URL: {source}")
    return origin


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _verify_release_manifest(path: Path, identity: ReleaseIdentity) -> None:
    manifest_path = path / "data" / "corpus_release.json"
    if not manifest_path.is_file():
        raise SourceAcquisitionError(
            f"release manifest is missing: {manifest_path}"
        )

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceAcquisitionError(
            f"invalid release manifest: {manifest_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise SourceAcquisitionError(
            f"invalid release manifest root: expected object in {manifest_path}"
        )

    checks: tuple[tuple[str, Any, Any], ...] = (
        ("release id", payload.get("release_id"), identity.release_id),
        (
            "corpus hash",
            _nested(payload, "pin", "corpus_sha256"),
            identity.corpus_sha256,
        ),
        (
            "catalog hash",
            _nested(payload, "pin", "catalog_sha256"),
            identity.catalog_sha256,
        ),
        ("work count", _nested(payload, "corpus", "works"), identity.works),
        (
            "passage count",
            _nested(payload, "corpus", "passages"),
            identity.passages,
        ),
        (
            "token count",
            _nested(payload, "corpus", "tokens"),
            identity.greek_tokens,
        ),
        (
            "generated-from",
            _nested(payload, "generated_from", "commit"),
            identity.generated_from_commit,
        ),
    )
    for label, actual, expected in checks:
        if actual != expected:
            raise SourceAcquisitionError(
                f"release manifest {label} mismatch: expected {expected!r}, "
                f"found {actual!r}"
            )


def verify_source(
    source: str | Path,
    *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> SourceSnapshot:
    """Verify a clean local checkout against the complete supported release identity."""
    path = Path(source).resolve()
    if not path.is_dir():
        raise SourceAcquisitionError(f"source directory does not exist: {path}")

    expected_revision = validate_revision(identity.commit)
    resolved_revision = resolve_revision(path)
    if resolved_revision != expected_revision:
        raise SourceAcquisitionError(
            f"source revision mismatch: expected {expected_revision}, "
            f"resolved {resolved_revision}"
        )

    expected_repo = _canonical_repository(identity.repository)
    resolved_repo = _canonical_repository(_resolve_origin(path))
    if resolved_repo != expected_repo:
        raise SourceAcquisitionError(
            f"source repository mismatch: expected {expected_repo}, found {resolved_repo}"
        )

    status = _run_git(
        [
            "-C",
            str(path),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        capture_output=True,
    ).stdout
    if status.strip():
        raise SourceAcquisitionError(f"source checkout is dirty: {path}")

    _verify_release_manifest(path, identity)
    return SourceSnapshot(path=path, revision=resolved_revision)


def fetch_source(
    destination: str | Path,
    *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> SourceSnapshot:
    """Fetch and atomically install the exact supported Open Greek checkout."""
    revision = validate_revision(identity.commit)
    target = Path(destination)
    target_preexisted = target.exists()

    if target_preexisted:
        if target.is_symlink():
            raise SourceAcquisitionError(f"destination must not be a symlink: {target}")
        if not target.is_dir():
            raise SourceAcquisitionError(
                f"destination exists and is not a directory: {target}"
            )
        if any(target.iterdir()):
            raise SourceAcquisitionError(f"destination is not empty: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.opengreek-tf-",
            dir=target.parent,
        )
    )

    try:
        _run_git(["-C", str(staging), "init", "--quiet"])
        _run_git(
            ["-C", str(staging), "remote", "add", "origin", identity.repository]
        )
        _run_git(
            [
                "-C",
                str(staging),
                "fetch",
                "--depth",
                "1",
                "origin",
                revision,
            ]
        )
        _run_git(["-C", str(staging), "checkout", "--detach", "FETCH_HEAD"])

        verified = verify_source(staging, identity=identity)

        if target_preexisted:
            target.rmdir()
        staging.replace(target)
        return SourceSnapshot(path=target.resolve(), revision=verified.revision)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if target_preexisted and not target.exists():
            target.mkdir(parents=False, exist_ok=True)
        raise
