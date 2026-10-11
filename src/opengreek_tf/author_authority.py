"""All TLG author authority entries as typed, ordered, native Text-Fabric facts.

An authority record atom is genuinely present in the pinned source. Neither
a Greek word nor an OGA identity/crosswalk is inferred from its TLG key.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

AuthorityValue: TypeAlias = str | int | tuple[str, ...]
_SOURCE = "data/author_authority.json"
_ID = re.compile(r"tlg[0-9]{4}\Z")
_INT_KEYS = frozenset({"birth", "death", "floruit"})
_STR_KEYS = frozenset({"gnd", "isni", "viaf", "wikidata"})
_ARRAY_KEYS = frozenset({"_multi"})


class AuthorityError(ValueError):
    """Source data or loaded TF violates authority conservation."""


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    key: str
    ordinal: int
    fields: tuple[tuple[str, AuthorityValue], ...]


@dataclass(frozen=True, slots=True)
class AuthorityStats:
    records: int
    fields: int
    array_items: int
    source_atoms: int


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityError(f"duplicate source JSON key: {key}")
        result[key] = value
    return result


def parse_author_authority(source_root: Path) -> tuple[AuthorityRecord, ...]:
    """Parse the source JSON without losing key order, integer type or arrays."""
    try:
        payload = json.loads(
            (source_root / _SOURCE).read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityError(f"cannot read valid authority JSON: {_SOURCE}") from exc
    if not isinstance(payload, dict) or not payload:
        raise AuthorityError("author authority must be a nonempty JSON object")
    records: list[AuthorityRecord] = []
    for ordinal, (identifier, raw) in enumerate(payload.items(), 1):
        if not isinstance(identifier, str) or _ID.fullmatch(identifier) is None:
            raise AuthorityError(f"invalid TLG authority ID: {identifier!r}")
        if not isinstance(raw, dict) or not raw:
            raise AuthorityError(f"empty or non-object TLG authority entry: {identifier}")
        fields: list[tuple[str, AuthorityValue]] = []
        for key, value in raw.items():
            if key in _INT_KEYS and type(value) is int:
                fields.append((key, value))
            elif key in _STR_KEYS and type(value) is str and "\r" not in value:
                fields.append((key, value))
            elif (
                key in _ARRAY_KEYS
                and isinstance(value, list)
                and all(type(item) is str and "\r" not in item for item in value)
            ):
                fields.append((key, tuple(value)))
            else:
                raise AuthorityError(
                    f"unsupported authority field or scalar type: {identifier}.{key}"
                )
        if "wikidata" not in raw or not raw["wikidata"]:
            raise AuthorityError(f"missing source-declared wikidata identity: {identifier}")
        records.append(AuthorityRecord(identifier, ordinal, tuple(fields)))
    return tuple(records)


def _stats(rows: tuple[AuthorityRecord, ...]) -> AuthorityStats:
    return AuthorityStats(
        records=len(rows),
        fields=sum(len(row.fields) for row in rows),
        array_items=sum(
            len(value)
            for row in rows
            for _key, value in row.fields
            if isinstance(value, tuple)
        ),
        source_atoms=len(rows),
    )


def write_author_authority_tf(source_root: Path, destination: Path) -> AuthorityStats:
    """Materialize *all* real author records with no fake text or sidecars."""
    if destination.exists() or destination.is_symlink():
        raise AuthorityError("authority TF output destination already exists")
    records = parse_author_authority(source_root)
    has_ints = any(type(v) is int for r in records for _k, v in r.fields)
    has_items = any(
        isinstance(v, tuple) and bool(v)
        for r in records
        for _k, v in r.fields
    )
    metadata: dict[str, dict[str, str]] = {
        "atom_kind": {"description": "Authentic metadata source-record atom"},
        "source_file": {"description": "Exact author authority source filename"},
        "source_record_id": {"description": "Exact four-digit TLG authority key"},
        "source_ordinal": {"description": "One-based source JSON member order"},
        "authority_id": {"description": "Source authority TLG ID, not OGA"},
        "authority_key": {"description": "Source-declared property name"},
        "authority_position": {"description": "Zero-based JSON property order"},
        "authority_kind": {"description": "Typed string/int/array field"},
        "authority_text": {"description": "Exact source string value"},
        "has_authority_field": {"description": "Author to source property edge"},
    }
    int_features = {"source_ordinal", "authority_position"}
    if has_ints:
        metadata["authority_int"] = {"description": "Signed source integer value"}
        int_features.add("authority_int")
    if has_items:
        metadata.update({
            "authority_item_position": {
                "description": "Zero-based source array item order"
            },
            "has_authority_item": {
                "description": "Array field to item edge"
            },
        })
        int_features.add("authority_item_position")

    def director(cv: CV) -> None:
        for record in records:
            author = cv.node("authorAuthority")
            atom = cv.slot()
            cv.feature(
                atom,
                atom_kind="authority-record",
                source_file=_SOURCE,
                source_record_id=record.key,
                source_ordinal=record.ordinal,
            )
            cv.feature(author, authority_id=record.key)
            cv.terminate(author)
            for position, (key, value) in enumerate(record.fields):
                field = cv.node("authorityField", slots=[atom[1]])
                kind = "array" if isinstance(value, tuple) else (
                    "int" if type(value) is int else "str"
                )
                cv.feature(
                    field,
                    authority_key=key,
                    authority_position=position,
                    authority_kind=kind,
                )
                if type(value) is int:
                    cv.feature(field, authority_int=value)
                elif type(value) is str:
                    cv.feature(field, authority_text=value)
                elif isinstance(value, tuple):
                    for item_index, item_text in enumerate(value):
                        item = cv.node("authorityArrayItem", slots=[atom[1]])
                        cv.feature(
                            item,
                            authority_item_position=item_index,
                            authority_text=item_text,
                        )
                        cv.edge(field, item, has_authority_item=None)
                        cv.terminate(item)
                cv.edge(author, field, has_authority_field=None)
                cv.terminate(field)

    converter = CV(Fabric(locations=str(destination), silent="deep"), silent="auto")
    if not converter.walk(
        director,
        slotType="atom",
        generic={"source": "Pinned Open Greek TLG author authority research"},
        otext={
            "sectionTypes": "",
            "sectionFeatures": "",
            "fmt:text-orig-full": "{source_record_id}",
            "fmt:metadata-id": "{source_record_id}",
        },
        intFeatures=int_features,
        featureMeta=metadata,
        warn=False,
    ):
        raise AuthorityError("Text-Fabric rejected the author authority graph")
    return validate_author_authority_tf(source_root, destination)


def read_author_authority_tf(destination: Path) -> tuple[AuthorityRecord, ...]:
    """Independently reconstruct every record from loaded TF F/E, never JSON."""
    has_ints = (destination / "authority_int.tf").is_file()
    has_items = (destination / "authority_item_position.tf").is_file()
    required = (
        "atom_kind source_file source_record_id source_ordinal authority_id "
        "authority_key authority_position authority_kind authority_text "
        "has_authority_field"
    )
    if has_ints:
        required += " authority_int"
    if has_items:
        required += " authority_item_position has_authority_item"
    api = Fabric(locations=str(destination), silent="deep").load(
        required, silent="deep"
    )
    if not api:
        raise AuthorityError("native TF author authority could not load")
    if (destination / "form.tf").exists():
        raise AuthorityError("metadata-only source invented a lexical form")
    if api.F.otype.s("word") or api.F.otype.s("passage"):
        raise AuthorityError("metadata-only source invented textual nodes")
    atoms = set(api.F.otype.s("atom"))
    field_nodes = set(api.F.otype.s("authorityField"))
    item_nodes = set(api.F.otype.s("authorityArrayItem"))
    used_atoms: set[int] = set()
    used_fields: set[int] = set()
    used_items: set[int] = set()
    used_ids: set[str] = set()
    rows: list[AuthorityRecord] = []
    for author in api.F.otype.s("authorAuthority"):
        identifier = api.F.authority_id.v(author)
        if (
            not isinstance(identifier, str)
            or _ID.fullmatch(identifier) is None
            or identifier in used_ids
        ):
            raise AuthorityError("duplicate or malformed native TLG authority")
        used_ids.add(identifier)
        slots = tuple(api.E.oslots.s(author))
        if len(slots) != 1 or slots[0] not in atoms or slots[0] in used_atoms:
            raise AuthorityError("author authority must have one exclusive real atom")
        slot = slots[0]
        used_atoms.add(slot)
        if (
            api.F.atom_kind.v(slot) != "authority-record"
            or api.F.source_file.v(slot) != _SOURCE
            or api.F.source_record_id.v(slot) != identifier
        ):
            raise AuthorityError("source authority atom provenance mismatch")
        ordinal = api.F.source_ordinal.v(slot)
        if type(ordinal) is not int or ordinal < 1:
            raise AuthorityError("invalid authority physical source ordinal")
        fields: dict[int, tuple[str, AuthorityValue]] = {}
        for field in api.E.has_authority_field.f(author):
            if (
                field not in field_nodes
                or field in used_fields
                or tuple(api.E.oslots.s(field)) != slots
            ):
                raise AuthorityError("missing, shared or wrong-atom authority field")
            used_fields.add(field)
            index = api.F.authority_position.v(field)
            key = api.F.authority_key.v(field)
            kind = api.F.authority_kind.v(field)
            if (
                type(index) is not int
                or index < 0
                or index in fields
                or not isinstance(key, str)
                or key not in (_INT_KEYS | _STR_KEYS | _ARRAY_KEYS)
            ):
                raise AuthorityError("invalid source field name/order")
            children = (
                tuple(api.E.has_authority_item.f(field))
                if has_items else ()
            )
            if kind == "int" and key in _INT_KEYS and has_ints and not children:
                value: AuthorityValue = api.F.authority_int.v(field)
                if type(value) is not int:
                    raise AuthorityError("missing integer authority value")
            elif kind == "str" and key in _STR_KEYS and not children:
                value = api.F.authority_text.v(field)
                if type(value) is not str:
                    raise AuthorityError("missing string authority value")
            elif kind == "array" and key in _ARRAY_KEYS:
                items: dict[int, str] = {}
                for child in children:
                    if (
                        child not in item_nodes
                        or child in used_items
                        or tuple(api.E.oslots.s(child)) != slots
                    ):
                        raise AuthorityError("orphan, shared or wrong-atom array item")
                    used_items.add(child)
                    item_pos = api.F.authority_item_position.v(child)
                    text = api.F.authority_text.v(child)
                    if (
                        type(item_pos) is not int
                        or item_pos < 0
                        or item_pos in items
                        or type(text) is not str
                    ):
                        raise AuthorityError("invalid authority array index/value")
                    items[item_pos] = text
                if set(items) != set(range(len(items))):
                    raise AuthorityError("gapped or repeated array positions")
                value = tuple(items[i] for i in range(len(items)))
            else:
                raise AuthorityError("source authority field changed scalar type")
            fields[index] = (key, value)
        if set(fields) != set(range(len(fields))):
            raise AuthorityError("missing/duplicate source field positions")
        field_entries = tuple(fields[i] for i in range(len(fields)))
        if len({name for name, _value in field_entries}) != len(field_entries):
            raise AuthorityError("duplicate native authority field key")
        rows.append(AuthorityRecord(identifier, ordinal, field_entries))
    if used_atoms != atoms or used_fields != field_nodes or used_items != item_nodes:
        raise AuthorityError("unaccounted native source authority node")
    if len({row.ordinal for row in rows}) != len(rows):
        raise AuthorityError("duplicate physical authority entry ordinal")
    if set(row.ordinal for row in rows) != set(range(1, len(rows) + 1)):
        raise AuthorityError("missing physical source authority member")
    return tuple(sorted(rows, key=lambda row: row.ordinal))


def validate_author_authority_tf(
    source_root: Path, destination: Path,
) -> AuthorityStats:
    """Compare all source JSON objects to independently loaded native TF."""
    source = parse_author_authority(source_root)
    observed = read_author_authority_tf(destination)
    if source != observed:
        raise AuthorityError(
            f"author authority semantic conservation failed: "
            f"{len(source)} source vs {len(observed)} TF records"
        )
    return _stats(observed)
