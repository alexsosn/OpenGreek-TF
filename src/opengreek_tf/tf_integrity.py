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


_DATE = re.compile(rb"@dateWritten=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\+00:00)?Z")


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


# Buffer only feature headers; malformed oversized headers fail closed.
_HEADER_READ_BYTES = 64 * 1024
_MAX_HEADER_BYTES = 1024 * 1024
_BODY_READ_BYTES = 1024 * 1024


def _feature_hashes(path: Path) -> tuple[int, bytes, bytes]:
    """Hash an actual TF feature in bounded memory, preserving both digests."""
    raw = hashlib.sha256()
    canonical = hashlib.sha256()
    with path.open("rb") as source:
        first = bytearray()
        while True:
            chunk = source.read(_HEADER_READ_BYTES)
            if not chunk:
                raise NativeTfIntegrityError(f"{path.name}: incomplete TF header")
            first.extend(chunk)
            delimiter_at = first.find(b"\n\n")
            if delimiter_at >= 0:
                if delimiter_at + 2 > _MAX_HEADER_BYTES:
                    raise NativeTfIntegrityError(f"{path.name}: oversized TF header")
                break
            if len(first) >= _MAX_HEADER_BYTES:
                raise NativeTfIntegrityError(f"{path.name}: oversized TF header")

        first_bytes = bytes(first)
        canonical_first = _canonical_payload(path.name, first_bytes)
        raw.update(first_bytes)
        canonical.update(canonical_first)
        size = len(first_bytes)
        del first, first_bytes, canonical_first

        while chunk := source.read(_BODY_READ_BYTES):
            raw.update(chunk)
            canonical.update(chunk)
            size += len(chunk)

    return size, raw.digest(), canonical.digest()


def native_tf_manifest(destination: Path) -> NativeTfManifest:
    """Compute exact native TF digests by reading each feature once, in chunks.

    Text-Fabric's cache directory is not a feature file. Canonical hashes
    exclude only the validated volatile @dateWritten header, not source facts.
    """
    files = sorted(path for path in destination.glob("*.tf") if path.is_file())
    if not files:
        raise NativeTfIntegrityError("no native .tf feature files")
    raw_digest = hashlib.sha256()
    canonical_digest = hashlib.sha256()
    size = 0
    for path in files:
        feature_bytes, raw_hash, canonical_hash = _feature_hashes(path)
        size += feature_bytes
        prefix = path.name.encode("utf-8") + b"\0"
        raw_digest.update(prefix)
        raw_digest.update(raw_hash)
        canonical_digest.update(prefix)
        canonical_digest.update(canonical_hash)
    return NativeTfManifest(
        tf_file_count=len(files),
        output_bytes=size,
        raw_sha256=raw_digest.hexdigest(),
        canonical_sha256=canonical_digest.hexdigest(),
    )
