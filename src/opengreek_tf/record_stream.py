"""Lossless, strictly typed streaming parser for the three audited JSONL families.

This module models source facts as immutable values; it does not infer citation
equivalence or decide the final Text-Fabric graph topology. Nested objects and
arrays remain inspectable typed values, never serialized feature blobs.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

Family: TypeAlias = Literal["primary", "secondary", "paratext"]


class RecordParseError(ValueError):
    """Unrepresentable source shape, with source-file and physical-row context."""


@dataclass(frozen=True, slots=True)
class FieldArray:
    """Ordered, immutable, already type-checked array in the source record."""

    items: tuple[FieldValue, ...]


@dataclass(frozen=True, slots=True)
class FieldObject:
    """Ordered, immutable, already type-checked key/value fields."""

    items: tuple[tuple[str, FieldValue], ...]

    def get(self, key: str) -> FieldValue | None:
        """Get an audited field; None means absent (source null is disallowed)."""
        for found, value in self.items:
            if found == key:
                return value
        return None


FieldValue: TypeAlias = str | int | bool | FieldArray | FieldObject


@dataclass(frozen=True, slots=True)
class ParsedRecord:
    """One source record, distinguished by file and 1-based physical row."""

    family: Family
    relative_file: str
    ordinal: int
    fields: FieldObject

    @property
    def occurrence_key(self) -> tuple[str, int]:
        """Lossless source record identity independent of a potentially reused locus."""
        return (self.relative_file, self.ordinal)

    @property
    def text(self) -> str:
        """Exact source text, without whitespace/Unicode transformations."""
        value = self.fields.get("text")
        if not isinstance(value, str):
            raise AssertionError("internal parser invariant: text is a string")
        return value


@dataclass(frozen=True, slots=True)
class ArraySpec:
    item: SchemaSpec


@dataclass(frozen=True, slots=True)
class ObjectSpec:
    fields: dict[str, SchemaSpec]


SchemaSpec: TypeAlias = type[str] | type[int] | type[bool] | ArraySpec | ObjectSpec


def _array(item: SchemaSpec) -> ArraySpec:
    return ArraySpec(item)


def _obj(**fields: SchemaSpec) -> ObjectSpec:
    return ObjectSpec(fields)


# Exact observed field types from the complete pinned-release semantic audit.
# Deliberately no catch-all data fields or unknown nested keys.
_SOURCE_BASE: dict[str, SchemaSpec] = {
    "edition": str,
    "source": str,
    "license": str,
    "text": str,
}
_TEXT_BASE: dict[str, SchemaSpec] = {
    **_SOURCE_BASE,
    "urn": str,
    "locus": str,
}
_PROVENANCE = _obj(
    commit=str,
    consolidated_from=_array(str),
    dropped_gap=int,
    fetched=str,
    glaux_id=str,
    license_url=str,
    method=str,
    note=str,
    page=str,
    page_sha256=str,
    repo=str,
    source=str,
    source_repo=str,
    url=str,
)
_MERGED_READ = _obj(
    guessed=int,
    guesses=int,
    note=str,
    of=str,
    substituted=int,
    **{"with": _array(str)},
)
_DISPLACED_BY = _obj(date=str, **{"pass": str}, reason=str)

SCHEMAS: dict[Family, dict[str, SchemaSpec]] = {
    "primary": {
        **_TEXT_BASE,
        "base_locus": str,
        "bekker": _array(str),
        "book": str,
        "corrections": _array(str),
        "cts": str,
        "dfhg_flag": bool,
        "figure": str,
        "merged_read": _MERGED_READ,
        "ocr_dpi": int,
        "page": int,
        "provenance": _PROVENANCE,
        "row_part": str,
        "section": str,
        "text_lines": _array(str),
        "text_orig": str,
        "witness": str,
        "work": str,
    },
    "secondary": {
        **_TEXT_BASE,
        "corrections": _array(str),
        "cts": str,
        "dfhg_flag": bool,
        "displaced_by": _DISPLACED_BY,
        "ocr_dpi": int,
        "page": int,
        "rank": str,
        "secondary_reason": str,
        "text_lines": _array(str),
        "witness": str,
        "work": str,
    },
    "paratext": {
        **_SOURCE_BASE,
        "slug": str,
        "page": str,
        "lang": str,
        "class": str,
        "script": str,
        "greek_remaining_in_this_row": int,
        "why_not_served": str,
    },
}
REQUIRED: dict[Family, frozenset[str]] = {
    "primary": frozenset(_TEXT_BASE),
    "secondary": frozenset(_TEXT_BASE),
    "paratext": frozenset((*_SOURCE_BASE, "slug", "page", "lang")),
}
FAMILY_DIR: dict[Family, str] = {
    "primary": "corpus",
    "secondary": "corpus_secondary",
    "paratext": "paratext",
}
DIR_FAMILY: dict[str, Family] = {v: k for k, v in FAMILY_DIR.items()}


def _decode(value: object, spec: SchemaSpec, *, field: str, context: str) -> FieldValue:
    if isinstance(spec, ArraySpec):
        if not isinstance(value, list):
            raise RecordParseError(f"{context}: {field}: expected array")
        return FieldArray(
            tuple(
                _decode(item, spec.item, field=f"{field}[{i}]", context=context)
                for i, item in enumerate(value)
            )
        )
    if isinstance(spec, ObjectSpec):
        if not isinstance(value, dict):
            raise RecordParseError(f"{context}: {field}: expected object")
        fields: list[tuple[str, FieldValue]] = []
        for k, item in value.items():
            if not isinstance(k, str) or k not in spec.fields:
                raise RecordParseError(f"{context}: {field}.{k}: unknown source field")
            fields.append(
                (k, _decode(item, spec.fields[k], field=f"{field}.{k}", context=context))
            )
        return FieldObject(tuple(fields))

    if type(value) is not spec:
        raise RecordParseError(
            f"{context}: {field}: expected {spec.__name__}, found {type(value).__name__}"
        )
    # The exact runtime type check above narrows JSON scalars for mypy.
    if isinstance(value, (str, int, bool)):
        return value
    raise AssertionError("unreachable scalar schema type")


def _object_no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object fields rather than silently keeping last."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate source key {key!r}")
        result[key] = value
    return result


def _family_for(relative_file: str) -> Family:
    path = Path(relative_file)
    if path.as_posix() != relative_file:
        raise RecordParseError(f"noncanonical source path: {relative_file!r}")
    parts = path.parts
    if (
        path.is_absolute()
        or len(parts) != 3
        or parts[0] != "data"
        or parts[1] not in DIR_FAMILY
        or parts[2] in {"", ".", ".."}
        or path.suffix != ".jsonl"
    ):
        raise RecordParseError(f"unsupported source JSONL path: {relative_file!r}")
    return DIR_FAMILY[parts[1]]


def parse_file(root: Path, relative_file: str) -> Iterator[ParsedRecord]:
    """Lazily parse exactly one audited-family JSONL file.

    Yields one record at a time, keeps original field order, and identifies a
    source occurrence by physical row number (including validation of blanks).
    """
    family = _family_for(relative_file)
    file_path = Path(root) / relative_file
    fields_schema = SCHEMAS[family]
    required = REQUIRED[family]

    try:
        with file_path.open("rb") as source:
            for ordinal, raw_line in enumerate(source, start=1):
                context = f"{relative_file}:{ordinal}"
                try:
                    line = raw_line.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise RecordParseError(
                        f"{context}: invalid UTF-8 source line"
                    ) from exc
                if not line.strip():
                    raise RecordParseError(f"{context}: blank JSONL row")
                try:
                    raw: object = json.loads(
                        line, object_pairs_hook=_object_no_duplicate_keys
                    )
                except (ValueError, TypeError) as exc:
                    raise RecordParseError(f"{context}: {exc}") from exc
                if not isinstance(raw, dict):
                    raise RecordParseError(f"{context}: JSONL row must be an object")
                missing = sorted(required - raw.keys())
                if missing:
                    raise RecordParseError(
                        f"{context}: missing mandatory field {missing[0]}"
                    )
                fields: list[tuple[str, FieldValue]] = []
                for key, value in raw.items():
                    if not isinstance(key, str) or key not in fields_schema:
                        raise RecordParseError(f"{context}: {key}: unknown source field")
                    fields.append(
                        (
                            key,
                            _decode(
                                value, fields_schema[key], field=key, context=context
                            ),
                        )
                    )
                yield ParsedRecord(
                    family=family,
                    relative_file=relative_file,
                    ordinal=ordinal,
                    fields=FieldObject(tuple(fields)),
                )
    except (OSError, UnicodeError) as exc:
        raise RecordParseError(f"cannot read {relative_file}: {exc}") from exc


def iter_family(root: Path, family: Family) -> Iterator[ParsedRecord]:
    """Yield all source rows in deterministic filename/physical-row order."""
    if family not in FAMILY_DIR:
        raise RecordParseError(f"unsupported source family: {family!r}")
    directory = Path(root) / "data" / FAMILY_DIR[family]
    if not directory.is_dir():
        raise RecordParseError(f"missing audited source directory: {directory}")
    files = sorted(directory.glob("*.jsonl"), key=lambda path: path.name)
    if not files:
        raise RecordParseError(f"empty audited source family: {directory}")
    for file in files:
        yield from parse_file(root, file.relative_to(root).as_posix())
