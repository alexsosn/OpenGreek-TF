"""Deterministic content manifest for native Text-Fabric feature payloads.

TF 13.1's writer emits a fresh @dateWritten UTC timestamp for *every*
serialized feature. The canonical digest ignores that header field only;
raw SHA-256 remains available for exact byte-level diagnostics.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


class NativeTfIntegrityError(ValueError):
    """Native TF payload is absent or the volatile header is malformed."""


@dataclass(frozen=True, slots=True)
class NativeTfManifest:
    tf_file_count: int
    output_bytes: int
    raw_sha256: str
    canonical_sha256: str


_DATE = re.compile(rb"@dateWritten=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _canonical_payload(name: str, payload: bytes) -> bytes:
    if not payload.startswith((b"@node\n", b"@edge\n", b"@config\n")):
        raise NativeTfIntegrityError(f"{name}: not a native TF feature header")
    header, delimiter, body = payload.partition(b"\n\n")
    if not delimiter:
        raise NativeTfIntegrityError(f"{name}: incomplete TF header")
    fields = header.split(b"\n")
    stamped = [field for field in fields if field.startswith(b"@dateWritten=")]
    if len(stamped) != 1 or not _DATE.fullmatch(stamped[0]):
        raise NativeTfIntegrityError(f"{name}: missing/invalid dateWritten header")
    # Parse and remove *only* the single volatile header field, never a
    # data body line or any other provenance metadata. Preserve all LF bytes.
    return b"\n".join(field for field in fields if field is not stamped[0]) + delimiter + body


def native_tf_manifest(destination: Path) -> NativeTfManifest:
    """Compute raw and normalized digests of real serialized .tf feature files.

    TF writes a `.tf/` cache directory, which `glob("*.tf")` also matches.
    Include only regular .tf feature files in their deterministic name order.
    The canonical digest excludes precisely one verified dateWritten header per
    feature, but hashes all remaining metadata, node/edge data and order.
    """
    files = sorted(path for path in destination.glob("*.tf") if path.is_file())
    if not files:
        raise NativeTfIntegrityError("no native .tf feature files")
    raw_digest = hashlib.sha256()
    canonical_digest = hashlib.sha256()
    size = 0
    for path in files:
        raw = path.read_bytes()
        canonical = _canonical_payload(path.name, raw)
        size += len(raw)
        prefix = path.name.encode("utf-8") + b"\0"
        raw_digest.update(prefix)
        raw_digest.update(hashlib.sha256(raw).digest())
        canonical_digest.update(prefix)
        canonical_digest.update(hashlib.sha256(canonical).digest())
    return NativeTfManifest(
        tf_file_count=len(files),
        output_bytes=size,
        raw_sha256=raw_digest.hexdigest(),
        canonical_sha256=canonical_digest.hexdigest(),
    )
