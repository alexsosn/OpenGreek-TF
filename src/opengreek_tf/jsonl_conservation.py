"""Independent native TF conservation against *original* JSONL source bytes.

Uses the stock JSON decoder and the independently loaded Text-Fabric F/E graph.
Deliberately never invokes the source typed parser or any materializer/writer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .native_composer import read_native_records
from .record_stream import FieldArray, FieldObject, FieldValue

_KINDS = {
    "corpus": ("primary-passage", "primary"),
    "corpus_secondary": ("secondary-witness", "secondary"),
    "paratext": ("paratext-record", "paratext"),
}


class JsonlConservationError(ValueError):
    """Original physical source rows differ from independently loaded native TF."""


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


def _distinct_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonlConservationError(f"duplicate original JSON object key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise JsonlConservationError(f"nonstandard JSON numeric constant: {value}")


def _exact_original(original: Any, restored: FieldValue) -> bool:
    """Match scalar *runtime type*, ordered arrays and original JSON member order."""
    if type(original) is dict:
        if type(restored) is not FieldObject:
            return False
        assert isinstance(restored, FieldObject)
        if len(original) != len(restored.items):
            return False
        return all(
            key == loaded_key and _exact_original(value, loaded_value)
            for (key, value), (loaded_key, loaded_value) in zip(
                original.items(), restored.items, strict=True,
            )
        )
    if type(original) is list:
        if type(restored) is not FieldArray:
            return False
        assert isinstance(restored, FieldArray)
        return len(original) == len(restored.items) and all(
            _exact_original(value, loaded_value)
            for value, loaded_value in zip(original, restored.items, strict=True)
        )
    return (
        type(original) in (str, int, bool, type(None))
        and type(original) is type(restored)
        and original == restored
    )


def _source_fact_count(value: Any) -> int:
    """Count every original container/scalar, not the writer's FactGraph."""
    if type(value) is dict:
        return 1 + sum(_source_fact_count(x) for x in value.values())
    if type(value) is list:
        return 1 + sum(_source_fact_count(x) for x in value)
    return 1


def validate_native_jsonl_sources(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> JsonlConservationReport:
    """Read source bytes and reload native Text-Fabric to verify every occurrence.

    Verifies selected source family/order/physical row and exact nested JSON
    types, not merely counts, hashes or values compared using Python equality.
    No sidecar is used for semantic queries, and no source facts are rewritten.
    """
    if not relative_files:
        raise JsonlConservationError("no original JSONL source files selected")

    source_root = root.resolve()
    physical_ids: set[tuple[int, int]] = set()
    checked_files: list[tuple[str, Path, str]] = []
    for relative in relative_files:
        if type(relative) is not str:
            raise JsonlConservationError("source path must be a string")
        path = Path(relative)
        if (
            path.is_absolute()
            or path.as_posix() != relative
            or len(path.parts) != 3
            or path.parts[0] != "data"
            or path.parts[1] not in _KINDS
            or path.suffix != ".jsonl"
        ):
            raise JsonlConservationError(f"invalid original JSONL source path: {relative}")
        try:
            original = (root / relative).resolve(strict=True)
            if not original.is_relative_to(source_root) or not original.is_file():
                raise JsonlConservationError(f"source path escapes root or is not a file: {relative}")
            identity = original.stat()
        except (OSError, RuntimeError) as exc:
            raise JsonlConservationError(f"missing or inaccessible original source: {relative}") from exc
        physical = (identity.st_dev, identity.st_ino)
        if physical in physical_ids:
            raise JsonlConservationError(f"duplicate physical original source file: {relative}")
        physical_ids.add(physical)
        checked_files.append((relative, original, _KINDS[path.parts[1]][0]))

    # This loader derives source fields and identities directly from native
    # Fabric F/E, checking every fact edge, digest, text slot and node census.
    loaded = iter(read_native_records(destination))
    digest = hashlib.sha256()
    counts = {"primary-passage": 0, "secondary-witness": 0, "paratext-record": 0}
    fact_count = 0
    codepoints = 0
    n = 0
    for relative, source_path, expected_kind in checked_files:
        encoded_name = relative.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        with source_path.open("rb") as source:
            for ordinal, raw in enumerate(source, 1):
                digest.update(len(raw).to_bytes(8, "big"))
                digest.update(raw)
                context = f"{relative}:{ordinal}"
                if not raw.strip():
                    raise JsonlConservationError(f"{context}: blank original source row")
                try:
                    original: Any = json.loads(
                        raw.decode("utf-8"),
                        object_pairs_hook=_distinct_pairs,
                        parse_constant=_invalid_constant,
                    )
                except (UnicodeError, ValueError, TypeError) as exc:
                    raise JsonlConservationError(
                        f"{context}: invalid original JSONL source: {exc}"
                    ) from exc
                if type(original) is not dict or type(original.get("text")) is not str:
                    raise JsonlConservationError(
                        f"{context}: missing original object or text string"
                    )
                try:
                    record = next(loaded)
                except StopIteration as exc:
                    raise JsonlConservationError(
                        f"{context}: missing original source occurrence in native TF"
                    ) from exc
                if (
                    record.source_file != relative
                    or record.ordinal != ordinal
                    or record.source_record_id != context
                    or record.record_kind != expected_kind
                    or (record.text != original["text"] if expected_kind == "primary-passage"
                        else record.text is not None)
                    or not _exact_original(original, record.fields)
                ):
                    raise JsonlConservationError(
                        f"{context}: native TF source facts, kind, order or text differ"
                    )
                counts[expected_kind] += 1
                fact_count += _source_fact_count(original)
                codepoints += len(original["text"])
                n += 1
    if next(loaded, None) is not None:
        raise JsonlConservationError("extra original source occurrences in native TF")
    if not n:
        raise JsonlConservationError("no original source records found")
    return JsonlConservationReport(
        source_files=len(checked_files),
        records=n,
        primary_passages=counts["primary-passage"],
        secondary_witnesses=counts["secondary-witness"],
        paratext_records=counts["paratext-record"],
        source_fact_nodes=fact_count,
        source_unicode_codepoints=codepoints,
        original_source_sha256=digest.hexdigest(),
    )
