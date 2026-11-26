"""Lossless, strictly typed streaming parser for the three audited JSONL families.

This module models source facts as immutable values; it does not infer citation
equivalence or decide the final Text-Fabric graph topology. Nested objects and
arrays remain inspectable typed values, never serialized feature blobs.
"""

from __future__ import annotations

import json
import math
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


FieldValue: TypeAlias = str | int | float | bool | None | FieldArray | FieldObject


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


@dataclass(frozen=True, slots=True)
class ChoiceSpec:
    """Mutually exclusive source-observed nested object keysets."""

    options: tuple[ObjectSpec, ...]


@dataclass(frozen=True, slots=True)
class ScalarChoiceSpec:
    """Explicit union of scalar source types, never Python numeric coercion."""

    options: tuple[type[str] | type[int] | type[float], ...]


SchemaSpec: TypeAlias = (
    type[str] | type[int] | type[float] | type[bool] | None
    | ArraySpec | ObjectSpec | NullableSpec | ChoiceSpec | ScalarChoiceSpec
)


def _array(item: SchemaSpec) -> ArraySpec:
    return ArraySpec(item)


def _obj(**fields: SchemaSpec) -> ObjectSpec:
    return ObjectSpec(fields)


def _nullable(item: SchemaSpec) -> NullableSpec:
    return NullableSpec(item)


def _choice(*options: ObjectSpec) -> ChoiceSpec:
    return ChoiceSpec(options)


def _scalar_choice(*options: type[str] | type[int] | type[float]) -> ScalarChoiceSpec:
    return ScalarChoiceSpec(options)


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
    book=_nullable(_scalar_choice(str, int)),
    greek_column=str,
    duplicate_scan=bool,
)

# Original November secondary witnesses: preserve their declared authority,
# duplicate history, source-image crop coordinates, and former-primary facts
# as typed native sourceFacts. Keysets are based on ALL 338,245 tagged rows.
_NOVEMBER_CROP_PAGE = _obj(
    crop_size=_array(int), id=str, max_side=int, path=str,
    pixel_box=_array(int), printed_column=int, region=_array(float),
    sha256=str, source=str, source_page=int,
)
_NOVEMBER_TARGET = _obj(slug=str, path=str, locus=str)
_NOVEMBER_ORIGINAL_ROW = _obj(
    urn=str, edition=str, locus=str, source=str, license=str,
    text=str, text_lines=_array(str),
)
_NOVEMBER_SECONDARY_FIELDS: dict[str, SchemaSpec] = {
    "source_page": _choice(_NOVEMBER_MEIBOM_PAGE, _NOVEMBER_CROP_PAGE),
    "evidence": str,
    "original_locus": str,
    "original_work": str,
    "original_edition": str,
    "original_urn": str,
    "original_row": _NOVEMBER_ORIGINAL_ROW,
    "source_char_range": _array(int),
    "source_pdf_page": int,
    "source_role": str,
    "source_role_evidence": str,
    "witness_group": str,
    "dubner_source_scope": _obj(authority=str),
    "source_location": _obj(volume=str, marker_page=str, start_line=str),
    "current_target": _NOVEMBER_TARGET,
    "reviewed_duplicate_witness": _obj(authority=str, key=str),
    "pindar_duplicate_review": _obj(authority=str),
    "canonical_target": _NOVEMBER_TARGET,
    "independent_witness": bool,
    "model": str,
    "revision": str,
    "vote_group": str,
    "merged_read": _MERGED_READ,
}
_NOVEMBER_MEIBOM_KEYS = frozenset(_NOVEMBER_MEIBOM_PAGE.fields)
_NOVEMBER_CROP_KEYS = frozenset(_NOVEMBER_CROP_PAGE.fields)


# Complete November primary census: 1,913,683 rows, 42 top-level keysets.
# Editorial projections and token offsets are source facts, not TF slot alignment.
_NOV_NUM = _scalar_choice(int, float)
_NOV_LINE = _choice(_obj(n=str), _obj(n=str, **{"break": str}))
_NOV_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_NOV_TEXTPART = _choice(
    _obj(tag=str, attributes=_choice(_obj(n=str, subtype=str, type=str))),
    _obj(tag=str, id=str, attributes=_choice(
        _obj(n=str, subtype=str, type=str, **{_NOV_XML_ID: str}),
        _obj(n=str, subtype=str, type=str, corresp=str, **{_NOV_XML_ID: str}),
    )),
)
_NOV_TEXTPARTS = _array(_NOV_TEXTPART)
_NOV_CUSTODY = _array(_choice(_obj(
    attributes=_choice(_obj(corresp=str, type=str, **{"from": str, "to": str})),
    references=_array(_choice(_obj(url=str))),
)))
_NOV_PHYSICAL = _choice(
    _obj(column=str, edition=str, license=str, printed_page=int, region=_array(float),
         scan_page=int, sha256=str, url=str),
    _obj(custody_events=_NOV_CUSTODY, dclp=str, document=str,
         line_attributes=_NOV_LINE, textparts=_NOV_TEXTPARTS),
    _obj(edition=str, printed_page=int, region=_array(float), scan_page=int, scan_sha256=str),
    _obj(edition=str, printed_page=int, scan_page=int, scan_sha256=str),
    _obj(line_attributes=_NOV_LINE, printed_page=int, scan_page=int,
         textparts=_NOV_TEXTPARTS, verse=int),
    _obj(line_attributes=_NOV_LINE, textparts=_NOV_TEXTPARTS),
    _obj(mime=str, printed_page=int, region=_array(float), scan_page=int, verses=str),
    _obj(printed_page=int, region=_array(float), scan_page=int, sha256=str, url=str),
)
_NOV_EBOOK: dict[str, SchemaSpec] = dict(
    ebook_id=int, edition_qualification=str, source_path=str, source_sha256=str, url=str,
)
_NOV_PROVENANCE = _choice(
    _obj(**_NOV_EBOOK, attribution_readings=_array(_choice(
        _obj(author=str, evidence=str, status=str),
    )), attribution_status=str, identity_evidence=_array(str)),
    _obj(commit=str, glaux_id=str, source_repo=str),
    _obj(consolidated_from=_array(str), method=str, source=str),
    _obj(dropped_gap=int, glaux_id=str, method=str, repo=str, source=str),
    _obj(**_NOV_EBOOK),
    _obj(fetched=str, note=str, page=str, url=str),
    _obj(fetched=str, page=str, url=str),
    _obj(glaux_id=str, method=str, source=str),
    _obj(license_url=str, method=str, page_sha256=str, url=str),
)
_NOV_TOKEN: dict[str, SchemaSpec] = dict(
    end=int, form=str, lexical_eligible=bool, start=int, status=_array(str),
)
_NOV_TOKENS = _array(_choice(
    _obj(**_NOV_TOKEN, analysis=None, id=str, lemma=None, span_ids=_array(str)),
    _obj(**_NOV_TOKEN, reading_ids=_array(str)),
    _obj(**_NOV_TOKEN, reading_ids=_array(str), numeral_ids=_array(str)),
))
_NOV_SCAN = _choice(_obj(height=int, label=str, sha256=str, url=str, width=int))
_NOV_REGION: dict[str, SchemaSpec] = dict(
    box=_array(int), column=str, printed_page=int, source_id=str,
)
_NOV_READING: dict[str, SchemaSpec] = dict(
    display=str, end=int, id=str, interpretation=str, kind=str, lexical_eligible=bool,
    normalized_reading=None, preferred=bool, printed_reading_verified=bool,
    source_regions=_array(_choice(_obj(**_NOV_REGION, apparatus_line=int))),
    start=int, witness=str,
)
_NOV_READINGS = _array(_choice(
    _obj(**_NOV_READING, baseline_text=str, raised_letter=_choice(_obj(
        anchor=_choice(_obj(base_character=str, base_codepoint_index=int, placement=str)),
        linearized_boundary=None, text=str,
    ))),
    _obj(**_NOV_READING, comparison_lemma=str, graphemes=_array(_choice(
        _obj(accent=str, breathing=str, letter=str),
        _obj(baseline=str, letter=str, placement=str),
    ))),
))
_NOV_NUMERALS = _array(_choice(_obj(
    base_letter=str, display=str, end=int, expanded_word=None, id=str, kind=str,
    lexical_eligible=bool, normalized_reading=None,
    overbar=_choice(_obj(codepoint=str, mark=str, placement=str)),
    printed_reading_verified=bool,
    source_regions=_array(_choice(_obj(**_NOV_REGION, apparatus_line=str))),
    start=int, value=int,
)))
_NOV_CRITICAL = _choice(
    _obj(schema=str),
    _obj(schema=str, source_path=str, source_sha256=str),
    _obj(display_convention=str, numerals=_NOV_NUMERALS, printed_page=int,
         reader_path=str, readings=_NOV_READINGS, schema=str,
         sources=_choice(_obj(bsb=_NOV_SCAN, toronto=_NOV_SCAN))),
)
_NOVEMBER_PRIMARY_FIELDS: dict[str, SchemaSpec] = {
    "analysis_segments": _array(str),
    "analysis_text": str,
    "chapter": int,
    "contextual_eligible": bool,
    "critical_markup": _NOV_CRITICAL,
    "gap_boundary_policy": str,
    "lang": str,
    "language": str,
    "line_attributes": _NOV_LINE,
    "original_edition": str,
    "original_locus": str,
    "original_work": str,
    "physical_refs": _NOV_PHYSICAL,
    "printed_page": int,
    "provenance": _NOV_PROVENANCE,
    "reading_text": str,
    "source_citation": _choice(_obj(scheme=str, locus=str)),
    "source_location": _choice(
        _obj(historical_missing_key=str, id=str, max_side=int, region=_array(_NOV_NUM),
             scan_page=int, source=str),
        _obj(marker_page=str, start_line=str, volume=str),
    ),
    "source_note": str,
    "source_pdf_page": int,
    "source_printed_columns": _array(int),
    "source_printed_page": _nullable(int),
    "source_scan": _choice(_obj(region=_array(_NOV_NUM), scan_page=int, sha256=str, url=str)),
    "source_url": str,
    "text_role": str,
    "textparts": _NOV_TEXTPARTS,
    "tokens": _NOV_TOKENS,
    "word_continuations": _choice(_obj(from_previous_line=bool, to_next_line=bool)),
}


_NOVEMBER_GUTENBERG: dict[str, SchemaSpec] = {
    "locus": str, "source": str, "source_sha256": str, "text": str,
}


def _decode(value: object, spec: SchemaSpec, *, field: str, context: str) -> FieldValue:
    if spec is None:
        if value is not None:
            raise RecordParseError(f"{context}: {field}: expected original null")
        return None
    if isinstance(spec, ScalarChoiceSpec):
        for option in spec.options:
            if type(value) is option:
                return _decode(value, option, field=field, context=context)
        expected = " or ".join(option.__name__ for option in spec.options)
        raise RecordParseError(f"{context}: {field}: expected {expected} source scalar")
    if isinstance(spec, ChoiceSpec):
        if not isinstance(value, dict):
            raise RecordParseError(f"{context}: {field}: expected object variant")
        known = set().union(*(option.fields.keys() for option in spec.options))
        unexpected = sorted(set(value) - known)
        if unexpected:
            raise RecordParseError(
                f"{context}: {field}.{unexpected[0]}: unknown source field"
            )
        matched = [option for option in spec.options if set(value) == set(option.fields)]
        if len(matched) != 1:
            raise RecordParseError(f"{context}: {field}: unsupported source object keyset")
        return _decode(value, matched[0], field=field, context=context)
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
    if type(value) is float:
        if not math.isfinite(value):
            raise RecordParseError(f"{context}: {field}: nonfinite original float")
        return value
    # Exact runtime type checks prevent treating booleans as integers.
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
        november = identity.tag == NOVEMBER_RELEASE.tag
        dubner = fields.get("dubner_source_scope")
        pindar = fields.get("pindar_duplicate_review")
        reviewed = fields.get("reviewed_duplicate_witness")
        tagged_source_page = isinstance(source_page, FieldObject)
        alternative = november and (
            tagged_source_page or dubner is not None
            or pindar is not None or reviewed is not None
        )
        if november:
            if evidence is not None and source_page is None and reviewed is None:
                raise RecordParseError(
                    f"{context}: source_page is required for Meibom evidence"
                )
            if source_page is not None:
                if not isinstance(source_page, FieldObject):
                    raise RecordParseError(f"{context}: source_page must be an object")
                keys = {key for key, _ in source_page.items}
                if keys == _NOVEMBER_MEIBOM_KEYS:
                    if not isinstance(evidence, str):
                        raise RecordParseError(f"{context}: evidence required for source_page")
                    if any(value is not None for value in (rank, reason, displacement)):
                        raise RecordParseError(
                            f"{context}: Meibom source_page cannot claim rank/displacement"
                        )
                elif keys == _NOVEMBER_CROP_KEYS:
                    crop = source_page.require("region")
                    crop_size = source_page.require("crop_size")
                    pixels = source_page.require("pixel_box")
                    if (
                        not isinstance(crop, FieldArray) or len(crop.items) != 4
                        or not isinstance(crop_size, FieldArray)
                        or len(crop_size.items) != 2
                        or not isinstance(pixels, FieldArray)
                        or len(pixels.items) != 4
                    ):
                        raise RecordParseError(
                            f"{context}: source_page.region/crop_size/pixel_box lengths"
                        )
                    required_crop = (
                        "source_role", "current_target", "model",
                        "revision", "vote_group",
                    )
                    for name in required_crop:
                        if fields.get(name) is None:
                            raise RecordParseError(f"{context}: missing cropped source {name}")
                    if evidence is not None or any(
                        value is not None for value in (rank, reason, displacement)
                    ):
                        raise RecordParseError(
                            f"{context}: cropped source_page cannot claim rank/evidence"
                        )
                else:
                    raise RecordParseError(f"{context}: unsupported source_page variant")
            if dubner is not None:
                required_dubner = (
                    "original_locus", "original_work", "original_edition",
                    "source_char_range", "source_pdf_page", "source_role",
                    "source_role_evidence", "witness_group",
                )
                for name in required_dubner:
                    if fields.get(name) is None:
                        raise RecordParseError(f"{context}: missing Dubner {name}")
                char_range = fields.require("source_char_range")
                if not isinstance(char_range, FieldArray) or len(char_range.items) != 2:
                    raise RecordParseError(f"{context}: source_char_range must be two ints")
                begin, finish = char_range.items
                if (
                    type(begin) is not int or type(finish) is not int
                    or begin < 0 or finish < begin
                ):
                    raise RecordParseError(f"{context}: invalid source_char_range")
            if reviewed is not None:
                for name in (
                    "current_target", "source_role", "source_role_evidence",
                ):
                    if fields.get(name) is None:
                        raise RecordParseError(f"{context}: reviewed witness needs {name}")
            if pindar is not None:
                for name in (
                    "canonical_target", "original_row", "original_urn",
                    "original_locus", "original_edition", "source_role",
                ):
                    if fields.get(name) is None:
                        raise RecordParseError(f"{context}: Pindar needs {name}")
                if type(fields.get("independent_witness")) is not bool:
                    raise RecordParseError(
                        f"{context}: Pindar independent_witness must be boolean"
                    )
                former = fields.require("original_row")
                if not isinstance(former, FieldObject):
                    raise RecordParseError(f"{context}: original_row must be an object")
                required_original = {
                    "urn", "edition", "locus", "source", "license", "text",
                }
                keys = {key for key, _ in former.items}
                if keys not in (required_original, required_original | {"text_lines"}):
                    raise RecordParseError(
                        f"{context}: original_row incomplete or unrecognized"
                    )
            merged_read = fields.get("merged_read")
            if merged_read is not None:
                if not isinstance(merged_read, FieldObject):
                    raise RecordParseError(f"{context}: invalid merged_read")
                if {key for key, _ in merged_read.items} not in (
                    {"guessed", "substituted", "with"},
                    {"guesses", "note", "of"},
                ):
                    raise RecordParseError(
                        f"{context}: merged_read not an audited complete variant"
                    )
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
        elif rank is None and reason is None and alternative:
            pass  # Genuine non-ranked former primary, cropped, review or scope.
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
        if family == "primary":
            fields_schema = {**fields_schema, **_NOVEMBER_PRIMARY_FIELDS}
        elif family == "secondary":
            fields_schema = {**fields_schema, **_NOVEMBER_SECONDARY_FIELDS}
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
