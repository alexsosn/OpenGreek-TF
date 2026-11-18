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

from .release import NOVEMBER_RELEASE, SUPPORTED_RELEASE, ReleaseIdentity

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
        """Get field value. For nullable schemas, inspect .items to distinguish absent."""
        for found, value in self.items:
            if found == key:
                return value
        return None

    def require(self, key: str) -> FieldValue:
        """Return a present typed member (including explicit null), else KeyError."""
        for found, value in self.items:
            if found == key:
                return value
        raise KeyError(key)


FieldValue: TypeAlias = str | int | bool | None | FieldArray | FieldObject


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


@dataclass(frozen=True, slots=True)
class NullableSpec:
    item: SchemaSpec


SchemaSpec: TypeAlias = (
    type[str] | type[int] | type[bool] | ArraySpec | ObjectSpec | NullableSpec
)


def _array(item: SchemaSpec) -> ArraySpec:
    return ArraySpec(item)


def _obj(**fields: SchemaSpec) -> ObjectSpec:
    return ObjectSpec(fields)


def _nullable(item: SchemaSpec) -> NullableSpec:
    return NullableSpec(item)


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

# A *bounded, source-observed* November grammar extension. The 2026-11-17
# pinned corpus adds Meibom secondary source_page/evidence and a distinct
# source-hashed Gutenberg note family. Other new nested OCR/citation formats
# remain deliberately unsupported until their typed schema/TF proof exists.
_NOVEMBER_MEIBOM_PAGE = _obj(
    work=str,
    scan_page=int,
    printed_page=int,
    book=_nullable(str),
    greek_column=str,
    duplicate_scan=bool,
)
_NOVEMBER_GUTENBERG = {
    "locus": str, "source": str, "source_sha256": str, "text": str,
}


def _decode(value: object, spec: SchemaSpec, *, field: str, context: str) -> FieldValue:
    if isinstance(spec, NullableSpec):
        if value is None:
            return None
        return _decode(value, spec.item, field=field, context=context)
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


def _family_for(
    relative_file: str, *, identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> Family:
    path = Path(relative_file)
    if path.as_posix() != relative_file:
        raise RecordParseError(f"noncanonical source path: {relative_file!r}")
    parts = path.parts
    ordinary = len(parts) == 3 and parts[1] in DIR_FAMILY
    november_gutenberg = (
        identity.tag == NOVEMBER_RELEASE.tag
        and len(parts) == 4
        and parts[1:3] == ("paratext", "gutenberg")
    )
    if (
        path.is_absolute()
        or not parts
        or parts[0] != "data"
        or not (ordinary or november_gutenberg)
        or any(part in {".", ".."} for part in parts)
        or path.suffix != ".jsonl"
    ):
        raise RecordParseError(f"unsupported source JSONL path: {relative_file!r}")
    return DIR_FAMILY[parts[1]]



def _validate_record_variants(
    family: Family, fields: FieldObject, *, context: str,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> None:
    """Enforce source-declared tagged field groups established by the audit."""
    if family == "secondary":
        displacement = fields.get("displaced_by")
        rank = fields.get("rank")
        reason = fields.get("secondary_reason")
        source_page = fields.get("source_page")
        evidence = fields.get("evidence")
        if identity.tag == NOVEMBER_RELEASE.tag and (
            source_page is not None or evidence is not None
        ):
            if not isinstance(source_page, FieldObject):
                raise RecordParseError(f"{context}: source_page is required")
            if not isinstance(evidence, str):
                raise RecordParseError(f"{context}: evidence is required")
            if {key for key, _ in source_page.items} != {
                "work", "scan_page", "printed_page", "book",
                "greek_column", "duplicate_scan",
            }:
                raise RecordParseError(f"{context}: incomplete source_page fields")
            if rank is not None or reason is not None or displacement is not None:
                raise RecordParseError(
                    f"{context}: Meibom source_page must not claim alignment/rank"
                )
            return
        if displacement is not None:
            if rank is not None or reason is not None:
                raise RecordParseError(
                    f"{context}: displaced_by cannot coexist with rank/secondary_reason"
                )
            if not isinstance(displacement, FieldObject):
                raise AssertionError("internal parser invariant: displaced_by object")
            if {name for name, _ in displacement.items} != {"date", "pass", "reason"}:
                raise RecordParseError(
                    f"{context}: displaced_by must have date, pass and reason"
                )
        elif rank is None or reason is None:
            missing = "rank" if rank is None else "secondary_reason"
            raise RecordParseError(
                f"{context}: secondary row missing {missing} or displaced_by"
            )

    if family == "primary":
        merged = fields.get("merged_read")
        if merged is not None:
            if not isinstance(merged, FieldObject):
                raise AssertionError("internal parser invariant: merged_read object")
            keys = {name for name, _ in merged.items}
            if keys not in (
                {"guessed", "substituted", "with"},
                {"guesses", "note", "of"},
            ):
                raise RecordParseError(
                    f"{context}: merged_read must use one complete audited variant"
                )


def parse_file(
    root: Path, relative_file: str, *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> Iterator[ParsedRecord]:
    """Lazily parse exactly one audited-family JSONL file.

    Yields one record at a time, keeps original field order, and identifies a
    source occurrence by physical row number (including validation of blanks).
    """
    family = _family_for(relative_file, identity=identity)
    file_path = Path(root) / relative_file
    fields_schema = SCHEMAS[family]
    required = REQUIRED[family]
    if identity.tag == NOVEMBER_RELEASE.tag:
        if family == "secondary":
            fields_schema = {
                **fields_schema, "source_page": _NOVEMBER_MEIBOM_PAGE,
                "evidence": str,
            }
        elif (
            family == "paratext"
            and Path(relative_file).parts[2] == "gutenberg"
        ):
            fields_schema = _NOVEMBER_GUTENBERG
            required = frozenset(fields_schema)

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
                checked_fields = FieldObject(tuple(fields))
                _validate_record_variants(
                    family, checked_fields, context=context, identity=identity,
                )
                yield ParsedRecord(
                    family=family,
                    relative_file=relative_file,
                    ordinal=ordinal,
                    fields=checked_fields,
                )
    except (OSError, UnicodeError) as exc:
        raise RecordParseError(f"cannot read {relative_file}: {exc}") from exc


def iter_family(
    root: Path, family: Family, *,
    identity: ReleaseIdentity = SUPPORTED_RELEASE,
) -> Iterator[ParsedRecord]:
    """Yield all source rows in deterministic filename/physical-row order."""
    if family not in FAMILY_DIR:
        raise RecordParseError(f"unsupported source family: {family!r}")
    directory = Path(root) / "data" / FAMILY_DIR[family]
    if not directory.is_dir():
        raise RecordParseError(f"missing audited source directory: {directory}")
    if identity.tag == NOVEMBER_RELEASE.tag and family == "paratext":
        files = sorted(directory.rglob("*.jsonl"))
    else:
        files = sorted(directory.glob("*.jsonl"), key=lambda path: path.name)
    if not files:
        raise RecordParseError(f"empty audited source family: {directory}")
    for file in files:
        yield from parse_file(
            root, file.relative_to(root).as_posix(), identity=identity,
        )
