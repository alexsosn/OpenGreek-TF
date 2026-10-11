"""Complete grouped TLG work-authority source as typed native Text-Fabric facts.

This research writer models genuine source records, not Greek word occurrences.
No inferred QID uniqueness or crosswalk to OGA/OGC is introduced.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

WorkFieldValue: TypeAlias = str | int | tuple[str, ...]
_SOURCE = "data/work_authority.json"
_GROUP = re.compile(r"tlg[0-9]{4}\Z")
_TEXT_KEYS = frozenset({"label", "qid", "la", "el", "grc"})
_INT_KEYS = frozenset({"year"})
_ARRAY_KEYS = frozenset({"alts", "langs", "genres"})
_ALL_KEYS = _TEXT_KEYS | _INT_KEYS | _ARRAY_KEYS


class WorkAuthorityError(ValueError):
    """Source or loaded native TF violates grouped-work fact conservation."""


@dataclass(frozen=True, slots=True)
class WorkEntry:
    index: int
    fields: tuple[tuple[str, WorkFieldValue], ...]


@dataclass(frozen=True, slots=True)
class WorkGroup:
    key: str
    ordinal: int
    works: tuple[WorkEntry, ...]


@dataclass(frozen=True, slots=True)
class WorkAuthorityStats:
    groups: int
    works: int
    fields: int
    array_items: int
    source_atoms: int


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkAuthorityError(f"duplicate work authority JSON key {key!r}")
        result[key] = value
    return result


def parse_work_authority(source_root: Path) -> tuple[WorkGroup, ...]:
    """Reject lossy JSON and preserve parent, work, field, and item order."""
    try:
        source = json.loads(
            (source_root / _SOURCE).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkAuthorityError("cannot read valid pinned work authority JSON") from exc
    if not isinstance(source, dict) or not source:
        raise WorkAuthorityError("work authority source must be a nonempty object")
    result: list[WorkGroup] = []
    for ordinal, (group_key, children) in enumerate(source.items(), 1):
        if (
            not isinstance(group_key, str)
            or _GROUP.fullmatch(group_key) is None
            or not isinstance(children, list)
        ):
            raise WorkAuthorityError(f"invalid work authority TLG group {group_key!r}")
        works: list[WorkEntry] = []
        for index, raw in enumerate(children):
            if not isinstance(raw, dict) or set(raw) - _ALL_KEYS:
                raise WorkAuthorityError(
                    f"unknown or invalid work authority entry: {group_key}:{index}"
                )
            if (
                type(raw.get("label")) is not str
                or not raw["label"]
                or type(raw.get("qid")) is not str
                or not raw["qid"]
            ):
                raise WorkAuthorityError(f"missing source label/qid: {group_key}:{index}")
            fields: list[tuple[str, WorkFieldValue]] = []
            for name, value in raw.items():
                if name in _TEXT_KEYS and type(value) is str and "\r" not in value:
                    fields.append((name, value))
                elif name in _INT_KEYS and type(value) is int:
                    fields.append((name, value))
                elif (
                    name in _ARRAY_KEYS
                    and isinstance(value, list)
                    and all(type(v) is str and "\r" not in v for v in value)
                ):
                    fields.append((name, tuple(value)))
                else:
                    raise WorkAuthorityError(
                        f"invalid source field/type: {group_key}:{index}.{name}"
                    )
            works.append(WorkEntry(index, tuple(fields)))
        result.append(WorkGroup(group_key, ordinal, tuple(works)))
    return tuple(result)


def _stats(groups: tuple[WorkGroup, ...]) -> WorkAuthorityStats:
    nworks = sum(len(group.works) for group in groups)
    return WorkAuthorityStats(
        groups=len(groups),
        works=nworks,
        fields=sum(len(work.fields) for group in groups for work in group.works),
        array_items=sum(
            len(value)
            for group in groups for work in group.works
            for _name, value in work.fields
            if isinstance(value, tuple)
        ),
        source_atoms=len(groups) + nworks,
    )


def write_work_authority_tf(source_root: Path, destination: Path) -> WorkAuthorityStats:
    """Write all real TLG groups/works and source-declared typed property facts."""
    if destination.exists() or destination.is_symlink():
        raise WorkAuthorityError("work authority destination already exists")
    groups = parse_work_authority(source_root)
    has_works = any(group.works for group in groups)
    has_ints = any(
        type(value) is int
        for group in groups for work in group.works for _name, value in work.fields
    )
    has_items = any(
        isinstance(value, tuple) and bool(value)
        for group in groups for work in group.works for _name, value in work.fields
    )
    meta: dict[str, dict[str, str]] = {
        "atom_kind": {"description": "Actual group/work source-record atom"},
        "source_file": {"description": "Pinned work authority source filename"},
        "source_record_id": {"description": "Physical source record key"},
        "source_ordinal": {"description": "One-based physical source ordinal"},
        "authority_group_id": {"description": "Source TLG group key, not OGA identity"},
    }
    int_features = {"source_ordinal"}
    if has_works:
        meta.update({
            "authority_work_index": {"description": "Zero-based index within group"},
            "authority_key": {"description": "Source work property key"},
            "authority_position": {"description": "Source field order"},
            "authority_kind": {"description": "str, int or array"},
            "authority_text": {"description": "Exact literal source string"},
            "has_authority_work": {"description": "Source group to work-record edge"},
            "has_authority_field": {"description": "Work to typed property edge"},
        })
        int_features.update({"authority_work_index", "authority_position"})
    if has_ints:
        meta["authority_int"] = {"description": "Signed literal source integer"}
        int_features.add("authority_int")
    if has_items:
        meta.update({
            "authority_item_position": {"description": "Source array item index"},
            "has_authority_item": {"description": "Array field to item edge"},
        })
        int_features.add("authority_item_position")

    def director(cv: CV) -> None:
        for group in groups:
            group_node = cv.node("workAuthorityGroup")
            group_slot = cv.slot()
            cv.feature(
                group_slot,
                atom_kind="work-authority-group", source_file=_SOURCE,
                source_record_id=group.key, source_ordinal=group.ordinal,
            )
            cv.feature(group_node, authority_group_id=group.key)
            cv.terminate(group_node)
            for work in group.works:
                work_node = cv.node("workAuthority")
                work_slot = cv.slot()
                cv.feature(
                    work_slot,
                    atom_kind="work-authority-record", source_file=_SOURCE,
                    source_record_id=f"{group.key}:{work.index}",
                    source_ordinal=work.index + 1,
                )
                cv.feature(work_node, authority_work_index=work.index)
                cv.terminate(work_node)
                cv.edge(group_node, work_node, has_authority_work=None)
                for index, (key, value) in enumerate(work.fields):
                    field = cv.node("workAuthorityField", slots=[work_slot[1]])
                    kind = (
                        "array" if isinstance(value, tuple)
                        else "int" if type(value) is int else "str"
                    )
                    cv.feature(
                        field, authority_key=key,
                        authority_position=index, authority_kind=kind,
                    )
                    if type(value) is int:
                        cv.feature(field, authority_int=value)
                    elif type(value) is str:
                        cv.feature(field, authority_text=value)
                    elif isinstance(value, tuple):
                        for item_index, text in enumerate(value):
                            item = cv.node("workAuthorityItem", slots=[work_slot[1]])
                            cv.feature(
                                item, authority_item_position=item_index,
                                authority_text=text,
                            )
                            cv.edge(field, item, has_authority_item=None)
                            cv.terminate(item)
                    cv.edge(work_node, field, has_authority_field=None)
                    cv.terminate(field)

    cv = CV(Fabric(locations=str(destination), silent="deep"), silent="auto")
    if not cv.walk(
        director,
        slotType="atom",
        generic={"source": "Immutable Open Greek grouped TLG work authority research"},
        otext={
            "sectionTypes": "", "sectionFeatures": "",
            "fmt:text-orig-full": "{source_record_id}",
            "fmt:metadata-id": "{source_record_id}",
        },
        intFeatures=int_features,
        featureMeta=meta,
        warn=False,
    ):
        raise WorkAuthorityError("Text-Fabric refused native grouped work graph")
    return validate_work_authority_tf(source_root, destination)


def read_work_authority_tf(destination: Path) -> tuple[WorkGroup, ...]:
    """Reconstruct every parent/child/field/item exclusively from native Fabric.load."""
    has_works = (destination / "authority_work_index.tf").is_file()
    has_ints = (destination / "authority_int.tf").is_file()
    has_items = (destination / "authority_item_position.tf").is_file()
    wanted = (
        "atom_kind source_file source_record_id source_ordinal authority_group_id"
    )
    if has_works:
        wanted += (
            " authority_work_index authority_key authority_position "
            "authority_kind authority_text has_authority_work has_authority_field"
        )
    if has_ints:
        wanted += " authority_int"
    if has_items:
        wanted += " authority_item_position has_authority_item"
    api = Fabric(locations=str(destination), silent="deep").load(
        wanted, silent="deep"
    )
    if not api:
        raise WorkAuthorityError("Text-Fabric work authority did not load")
    if (destination / "form.tf").exists() or api.F.otype.s("word") or api.F.otype.s("passage"):
        raise WorkAuthorityError("work authority invented Greek textual nodes")

    atoms = set(api.F.otype.s("atom"))
    group_nodes = set(api.F.otype.s("workAuthorityGroup"))
    work_nodes = set(api.F.otype.s("workAuthority"))
    field_nodes = set(api.F.otype.s("workAuthorityField"))
    item_nodes = set(api.F.otype.s("workAuthorityItem"))
    used_atoms: set[int] = set()
    used_works: set[int] = set()
    used_fields: set[int] = set()
    used_items: set[int] = set()
    used_groups: set[str] = set()
    results: list[WorkGroup] = []

    def unique_slot(node: int, expected_kind: str, expected_id: str) -> tuple[int, int]:
        slots = tuple(api.E.oslots.s(node))
        if len(slots) != 1 or slots[0] not in atoms or slots[0] in used_atoms:
            raise WorkAuthorityError("missing, multiply owned or shared source atom")
        slot = slots[0]
        used_atoms.add(slot)
        if (
            api.F.atom_kind.v(slot) != expected_kind
            or api.F.source_file.v(slot) != _SOURCE
            or api.F.source_record_id.v(slot) != expected_id
        ):
            raise WorkAuthorityError("native work/group source provenance mismatch")
        ordinal = api.F.source_ordinal.v(slot)
        if type(ordinal) is not int or ordinal < 1:
            raise WorkAuthorityError("bad physical source ordinal")
        return slot, ordinal

    for group in group_nodes:
        key = api.F.authority_group_id.v(group)
        if (
            not isinstance(key, str) or _GROUP.fullmatch(key) is None
            or key in used_groups
        ):
            raise WorkAuthorityError("duplicate or malformed native TLG group")
        used_groups.add(key)
        _slot, ordinal = unique_slot(group, "work-authority-group", key)
        works_by_index: dict[int, WorkEntry] = {}
        children = tuple(api.E.has_authority_work.f(group)) if has_works else ()
        for work in children:
            if work not in work_nodes or work in used_works:
                raise WorkAuthorityError("missing or multiply parented work record")
            used_works.add(work)
            work_index = api.F.authority_work_index.v(work)
            if (
                type(work_index) is not int or work_index < 0
                or work_index in works_by_index
            ):
                raise WorkAuthorityError("duplicate or invalid work list index")
            work_slot, work_ordinal = unique_slot(
                work, "work-authority-record", f"{key}:{work_index}"
            )
            if work_ordinal != work_index + 1:
                raise WorkAuthorityError("physical work-list ordinal differs from index")
            fields: dict[int, tuple[str, WorkFieldValue]] = {}
            for field in api.E.has_authority_field.f(work):
                if (
                    field not in field_nodes or field in used_fields
                    or tuple(api.E.oslots.s(field)) != (work_slot,)
                ):
                    raise WorkAuthorityError("orphan, reused or wrong-atom work field")
                used_fields.add(field)
                position = api.F.authority_position.v(field)
                field_key = api.F.authority_key.v(field)
                field_kind = api.F.authority_kind.v(field)
                if (
                    type(position) is not int or position < 0 or position in fields
                    or field_key not in _ALL_KEYS
                ):
                    raise WorkAuthorityError("invalid or duplicated work property")
                linked_items = (
                    tuple(api.E.has_authority_item.f(field)) if has_items else ()
                )
                if field_kind == "str" and field_key in _TEXT_KEYS and not linked_items:
                    value: WorkFieldValue = api.F.authority_text.v(field)
                    if type(value) is not str or "\r" in value:
                        raise WorkAuthorityError("invalid native source string value")
                elif field_kind == "int" and field_key in _INT_KEYS and has_ints and not linked_items:
                    value = api.F.authority_int.v(field)
                    if type(value) is not int:
                        raise WorkAuthorityError("missing native integer year")
                elif field_kind == "array" and field_key in _ARRAY_KEYS:
                    values: dict[int, str] = {}
                    for item in linked_items:
                        if (
                            item not in item_nodes or item in used_items
                            or tuple(api.E.oslots.s(item)) != (work_slot,)
                        ):
                            raise WorkAuthorityError("orphan/multiparent array item")
                        used_items.add(item)
                        item_index = api.F.authority_item_position.v(item)
                        item_value = api.F.authority_text.v(item)
                        if (
                            type(item_index) is not int or item_index < 0
                            or item_index in values or type(item_value) is not str
                            or "\r" in item_value
                        ):
                            raise WorkAuthorityError("invalid native array value/index")
                        values[item_index] = item_value
                    if set(values) != set(range(len(values))):
                        raise WorkAuthorityError("missing/duplicated work array item")
                    value = tuple(values[i] for i in range(len(values)))
                else:
                    raise WorkAuthorityError("wrong native work field type")
                fields[position] = (field_key, value)
            if set(fields) != set(range(len(fields))):
                raise WorkAuthorityError("missing or repeated field position")
            ordered_fields = tuple(fields[i] for i in range(len(fields)))
            if len({name for name, _value in ordered_fields}) != len(ordered_fields):
                raise WorkAuthorityError("duplicate work property key")
            required_keys = dict(ordered_fields)
            if not all(
                type(required_keys.get(k)) is str and bool(required_keys[k])
                for k in ("label", "qid")
            ):
                raise WorkAuthorityError("native work has no source label/qid")
            works_by_index[work_index] = WorkEntry(work_index, ordered_fields)
        if set(works_by_index) != set(range(len(works_by_index))):
            raise WorkAuthorityError("missing/duplicated ordered work in group")
        results.append(
            WorkGroup(
                key, ordinal,
                tuple(works_by_index[i] for i in range(len(works_by_index))),
            )
        )

    if (
        used_atoms != atoms or used_works != work_nodes
        or used_fields != field_nodes or used_items != item_nodes
        or len(results) != len(group_nodes)
    ):
        raise WorkAuthorityError("orphan native TLG work/field/item/source atom")
    if set(g.ordinal for g in results) != set(range(1, len(results) + 1)):
        raise WorkAuthorityError("missing or duplicate physical TLG group")
    return tuple(sorted(results, key=lambda group: group.ordinal))


def validate_work_authority_tf(
    source_root: Path, destination: Path,
) -> WorkAuthorityStats:
    """Independently compare every source field and array item to reloaded TF."""
    expected = parse_work_authority(source_root)
    observed = read_work_authority_tf(destination)
    if expected != observed:
        raise WorkAuthorityError(
            f"complete work authority conservation failed: "
            f"{len(expected)} source groups, {len(observed)} native groups"
        )
    return _stats(observed)
