"""Independent original-source scale profile, not a Text-Fabric serializer.

Reads one physical JSONL row at a time using the standard JSON decoder.
Counts source codepoints, exact layout-run slot bounds and physical anchors
independently of the source typed parser and generic TF writer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    object_value: dict[str, Any] = {}
    for key, value in pairs:
        if key in object_value:
            raise PrimarySourceProfileError(f"duplicate source JSON member: {key}")
        object_value[key] = value
    return object_value


def _reject_constant(value: str) -> None:
    raise PrimarySourceProfileError(f"nonstandard JSON numeric constant: {value}")


def _layout_runs(text: str) -> int:
    """Count maximal Unicode whitespace/nonspace runs without making tokens."""
    if not text:
        return 0
    previous_space = text[0].isspace()
    count = 1
    for char in text[1:]:
        space = char.isspace()
        if space != previous_space:
            count += 1
        previous_space = space
    return count


def _checked_paths(
    root: Path, relative_files: tuple[str, ...],
) -> tuple[tuple[str, Path], ...]:
    if not relative_files:
        raise PrimarySourceProfileError("empty original primary source file selection")
    source_root = root.resolve()
    physical: set[tuple[int, int]] = set()
    selected: list[tuple[str, Path]] = []
    for relative in relative_files:
        if type(relative) is not str:
            raise PrimarySourceProfileError("original primary path must be a string")
        path = Path(relative)
        if (
            path.is_absolute()
            or path.as_posix() != relative
            or len(path.parts) != 3
            or path.parts[:2] != ("data", "corpus")
            or path.suffix != ".jsonl"
        ):
            raise PrimarySourceProfileError(
                f"invalid original primary source path: {relative}"
            )
        try:
            absolute = (root / relative).resolve(strict=True)
            if not absolute.is_relative_to(source_root) or not absolute.is_file():
                raise PrimarySourceProfileError(
                    f"original primary source escapes root or is not a file: {relative}"
                )
            stats = absolute.stat()
        except (OSError, RuntimeError) as exc:
            raise PrimarySourceProfileError(
                f"missing original primary source file: {relative}"
            ) from exc
        identity = (stats.st_dev, stats.st_ino)
        if identity in physical:
            raise PrimarySourceProfileError(
                f"duplicate original primary source file: {relative}"
            )
        physical.add(identity)
        selected.append((relative, absolute))
    return tuple(selected)


def profile_primary_sources(
    root: Path, relative_files: tuple[str, ...],
) -> PrimarySourceProfile:
    """Audit exact original bytes before running a large TF compilation.

    Returns data-independent aggregate metrics only; the source text itself
    never becomes a semantic sidecar, and no Text-Fabric output is read here.
    """
    paths = _checked_paths(root, relative_files)
    digest = hashlib.sha256()
    file_counts: list[int] = []
    records = 0
    codepoints = 0
    layout_atoms = 0
    max_codepoints = 0
    max_layout = 0
    source_bytes = 0

    for relative, absolute in paths:
        name = relative.encode("utf-8")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        file_rows = 0
        with absolute.open("rb") as stream:
            for ordinal, raw in enumerate(stream, 1):
                context = f"{relative}:{ordinal}"
                source_bytes += len(raw)
                digest.update(len(raw).to_bytes(8, "big"))
                digest.update(raw)
                if not raw.strip():
                    raise PrimarySourceProfileError(
                        f"{context}: blank original JSONL record"
                    )
                try:
                    original: Any = json.loads(
                        raw.decode("utf-8", errors="strict"),
                        object_pairs_hook=_unique_members,
                        parse_constant=_reject_constant,
                    )
                except UnicodeDecodeError as exc:
                    raise PrimarySourceProfileError(
                        f"{context}: invalid UTF-8 source"
                    ) from exc
                except (ValueError, TypeError) as exc:
                    raise PrimarySourceProfileError(
                        f"{context}: invalid original JSONL record: {exc}"
                    ) from exc
                if type(original) is not dict or type(original.get("text")) is not str:
                    raise PrimarySourceProfileError(
                        f"{context}: source text must be a literal string"
                    )
                text: str = original["text"]
                if "\r" in text:
                    raise PrimarySourceProfileError(
                        f"{context}: carriage return unsupported by native T.text"
                    )
                length = len(text)
                runs = _layout_runs(text)
                max_codepoints = max(max_codepoints, length)
                max_layout = max(max_layout, runs)
                codepoints += length
                layout_atoms += runs
                records += 1
                file_rows += 1
        if not file_rows:
            raise PrimarySourceProfileError(
                f"empty original source file: {relative}"
            )
        file_counts.append(file_rows)

    return PrimarySourceProfile(
        source_files=len(paths),
        file_records=tuple(file_counts),
        records=records,
        original_codepoints=codepoints,
        text_layout_atoms=layout_atoms,
        source_anchor_atoms=records,
        total_atoms=layout_atoms + records,
        max_passage_codepoints=max_codepoints,
        max_layout_atoms=max_layout,
        source_bytes=source_bytes,
        source_sha256=digest.hexdigest(),
    )
