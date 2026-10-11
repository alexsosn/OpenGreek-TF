"""Complete TLG crosswalk as native nonlexical source facts (#7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

_SOURCE = "data/tlg_crosswalk.json"
_KEYS = frozenset({"cts", "tlg", "author_slug", "title", "pta", "note"})


class CrosswalkError(ValueError):
    """Source or loaded TF violates crosswalk data conservation."""


@dataclass(frozen=True, slots=True)
class CrosswalkRecord:
    identifier: str
    ordinal: int
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CrosswalkStats:
    records: int
    fields: int
    empty_values: int
    source_atoms: int


def _unique_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CrosswalkError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def parse_tlg_crosswalk(root: Path) -> tuple[CrosswalkRecord, ...]:
    """Read exact physical member/field order, distinguishing missing from blank."""
    try:
        payload = json.loads(
            (root / _SOURCE).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CrosswalkError(f"cannot read valid JSON {_SOURCE}") from exc
    if not isinstance(payload, dict) or not payload:
        raise CrosswalkError("crosswalk root must be a nonempty object")
    result: list[CrosswalkRecord] = []
    for ordinal, (identifier, raw) in enumerate(payload.items(), 1):
        if (
            type(identifier) is not str or not identifier or "\r" in identifier
            or not isinstance(raw, dict) or not raw
            or set(raw) - _KEYS
            or "author_slug" not in raw or "title" not in raw
        ):
            raise CrosswalkError(f"invalid crosswalk entry {identifier!r}")
        fields: list[tuple[str, str]] = []
        for key, value in raw.items():
            if type(value) is not str or "\r" in value:
                raise CrosswalkError(f"invalid field {identifier}.{key}")
            fields.append((key, value))
        result.append(CrosswalkRecord(identifier, ordinal, tuple(fields)))
    return tuple(result)


def _stats(rows: tuple[CrosswalkRecord, ...]) -> CrosswalkStats:
    return CrosswalkStats(
        records=len(rows),
        fields=sum(len(row.fields) for row in rows),
        empty_values=sum(value == "" for row in rows for _, value in row.fields),
        source_atoms=len(rows),
    )


def write_tlg_crosswalk_tf(root: Path, destination: Path) -> CrosswalkStats:
    """Emit one genuine metadata source atom per row, no Greek word/passage."""
    if destination.exists() or destination.is_symlink():
        raise CrosswalkError("crosswalk output already exists")
    rows = parse_tlg_crosswalk(root)
    has_values = any(value for row in rows for _, value in row.fields)
    meta = {
        "atom_kind": {"description": "Genuine crosswalk source-record atom"},
        "source_file": {"description": "Exact pinned crosswalk source file"},
        "source_record_id": {"description": "Exact source key, not canonical OGC/OGA"},
        "source_ordinal": {"description": "One-based physical source member order"},
        "crosswalk_id": {"description": "Literal source record identifier"},
        "crosswalk_key": {"description": "Source-declared field name"},
        "crosswalk_position": {"description": "Zero-based physical field position"},
        "crosswalk_kind": {"description": "Literal str or empty-string value kind"},
        "has_crosswalk_field": {"description": "Source row to present source fact"},
    }
    if has_values:
        meta["crosswalk_value"] = {"description": "Exact nonempty source string"}

    def director(cv: CV) -> None:
        for record in rows:
            entry = cv.node("crosswalkRecord")
            atom = cv.slot()
            cv.feature(
                atom, atom_kind="tlg-crosswalk-record", source_file=_SOURCE,
                source_record_id=record.identifier, source_ordinal=record.ordinal,
            )
            cv.feature(entry, crosswalk_id=record.identifier)
            cv.terminate(entry)
            for pos, (key, value) in enumerate(record.fields):
                field = cv.node("crosswalkField", slots=[atom[1]])
                cv.feature(
                    field, crosswalk_key=key, crosswalk_position=pos,
                    crosswalk_kind="str" if value else "empty",
                )
                if value:
                    cv.feature(field, crosswalk_value=value)
                cv.edge(entry, field, has_crosswalk_field=None)
                cv.terminate(field)

    if not CV(Fabric(locations=str(destination), silent="deep"), silent="auto").walk(
        director,
        slotType="atom",
        generic={"source": "Immutable pinned Open Greek TLG crosswalk"},
        otext={
            "sectionTypes": "", "sectionFeatures": "",
            "fmt:text-orig-full": "{source_record_id}",
            "fmt:metadata-id": "{source_record_id}",
        },
        intFeatures={"source_ordinal", "crosswalk_position"},
        featureMeta=meta,
        warn=False,
    ):
        raise CrosswalkError("Text-Fabric refused crosswalk graph")
    return validate_tlg_crosswalk_tf(root, destination)


def read_tlg_crosswalk_tf(destination: Path) -> tuple[CrosswalkRecord, ...]:
    """Reconstruct all source facts exclusively from loaded F/E native features."""
    has_values = (destination / "crosswalk_value.tf").is_file()
    feature_names = (
        "atom_kind source_file source_record_id source_ordinal "
        "crosswalk_id crosswalk_key crosswalk_position crosswalk_kind "
        "has_crosswalk_field"
    )
    if has_values:
        feature_names += " crosswalk_value"
    api = Fabric(locations=str(destination), silent="deep").load(
        feature_names, silent="deep",
    )
    if not api:
        raise CrosswalkError("could not load native TF crosswalk")
    if (
        (destination / "form.tf").exists()
        or api.F.otype.s("word")
        or api.F.otype.s("passage")
    ):
        raise CrosswalkError("crosswalk invented Greek textual content")
    atoms = set(api.F.otype.s("atom"))
    fields = set(api.F.otype.s("crosswalkField"))
    used_atoms: set[int] = set()
    used_fields: set[int] = set()
    used_keys: set[str] = set()
    rows: list[CrosswalkRecord] = []
    for entry in api.F.otype.s("crosswalkRecord"):
        identifier = api.F.crosswalk_id.v(entry)
        if (
            type(identifier) is not str or not identifier
            or "\r" in identifier or identifier in used_keys
        ):
            raise CrosswalkError("missing, invalid or repeated crosswalk source key")
        used_keys.add(identifier)
        slots = tuple(api.E.oslots.s(entry))
        if len(slots) != 1 or slots[0] not in atoms or slots[0] in used_atoms:
            raise CrosswalkError("absent, reused or multiply owned crosswalk atom")
        atom = slots[0]
        used_atoms.add(atom)
        if (
            api.F.atom_kind.v(atom) != "tlg-crosswalk-record"
            or api.F.source_file.v(atom) != _SOURCE
            or api.F.source_record_id.v(atom) != identifier
        ):
            raise CrosswalkError("crosswalk atom provenance mismatch")
        ordinal = api.F.source_ordinal.v(atom)
        if type(ordinal) is not int or ordinal < 1:
            raise CrosswalkError("invalid physical member order")
        ordered: dict[int, tuple[str, str]] = {}
        for field in api.E.has_crosswalk_field.f(entry):
            if (
                field not in fields or field in used_fields
                or tuple(api.E.oslots.s(field)) != slots
            ):
                raise CrosswalkError("shared, orphan or wrong-atom field")
            used_fields.add(field)
            pos = api.F.crosswalk_position.v(field)
            key = api.F.crosswalk_key.v(field)
            kind = api.F.crosswalk_kind.v(field)
            if (
                type(pos) is not int or pos < 0 or pos in ordered
                or type(key) is not str or key not in _KEYS
            ):
                raise CrosswalkError("wrong field key/position")
            observed = api.F.crosswalk_value.v(field) if has_values else None
            if kind == "empty" and observed is None:
                value = ""
            elif kind == "str" and type(observed) is str and observed and "\r" not in observed:
                value = observed
            else:
                raise CrosswalkError("changed source field kind/string")
            ordered[pos] = (key, value)
        if set(ordered) != set(range(len(ordered))):
            raise CrosswalkError("gapped or duplicate field positions")
        values = tuple(ordered[i] for i in range(len(ordered)))
        if (
            len({k for k, _ in values}) != len(values)
            or "author_slug" not in dict(values)
            or "title" not in dict(values)
        ):
            raise CrosswalkError("missing or repeated required source fact")
        rows.append(CrosswalkRecord(identifier, ordinal, values))
    if atoms != used_atoms or fields != used_fields:
        raise CrosswalkError("unaccounted source atom or mapping fact")
    if {row.ordinal for row in rows} != set(range(1, len(rows) + 1)):
        raise CrosswalkError("missing or repeated source member position")
    return tuple(sorted(rows, key=lambda row: row.ordinal))


def validate_tlg_crosswalk_tf(root: Path, destination: Path) -> CrosswalkStats:
    """Independently compare every literal source JSON fact to loaded TF."""
    source = parse_tlg_crosswalk(root)
    observed = read_tlg_crosswalk_tf(destination)
    if source != observed:
        raise CrosswalkError(
            f"full crosswalk conservation failed: {len(source)} vs {len(observed)}"
        )
    return _stats(observed)
