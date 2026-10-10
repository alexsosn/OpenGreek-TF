"""A bounded, reversible research graph of every typed JSONL source field.

Node/edge representation is TF-independent; the single-source probe below
conserves this graph as native TF nodes, features, and has_fact edges.
This is NOT the production corpus writer or final schema (#33).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias, cast

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

from .record_stream import Family, FieldArray, FieldObject, FieldValue, ParsedRecord
from .text_runs import segment_runs

FactKind: TypeAlias = Literal["object", "array", "str", "int", "bool"]
FactScalar: TypeAlias = str | int | bool
MAX_FACT_NODES = 100_000
MAX_FACT_DEPTH = 64


class FactGraphError(ValueError):
    """Source facts cannot be modeled or validated without loss."""


@dataclass(frozen=True, slots=True)
class FactNode:
    id: int
    parent_id: int | None
    position: int
    key: str | None
    index: int | None
    kind: FactKind
    value: FactScalar | None


@dataclass(frozen=True, slots=True)
class FactGraph:
    family: Family
    relative_file: str
    ordinal: int
    nodes: tuple[FactNode, ...]

    @property
    def occurrence_key(self) -> tuple[str, int]:
        return (self.relative_file, self.ordinal)


def build_fact_graph(record: ParsedRecord) -> FactGraph:
    """Construct preorder nodes; source key order and all scalar types survive."""
    nodes: list[FactNode] = []

    def visit(
        value: FieldValue, parent: int | None, position: int,
        key: str | None, index: int | None, depth: int,
    ) -> None:
        if depth > MAX_FACT_DEPTH:
            raise FactGraphError("source fact nesting exceeds bounded depth")
        if len(nodes) >= MAX_FACT_NODES:
            raise FactGraphError("source fact count exceeds bounded probe maximum")
        node_id = len(nodes) + 1
        if isinstance(value, FieldObject):
            kind: FactKind = "object"
            scalar: FactScalar | None = None
        elif isinstance(value, FieldArray):
            kind = "array"
            scalar = None
        elif type(value) is bool:
            kind = "bool"
            scalar = value
        elif type(value) is int:
            kind = "int"
            scalar = value
        elif type(value) is str:
            kind = "str"
            scalar = value
        else:
            raise FactGraphError(f"unsupported source fact value: {type(value).__name__}")
        nodes.append(FactNode(node_id, parent, position, key, index, kind, scalar))
        if isinstance(value, FieldObject):
            for i, (field, child) in enumerate(value.items):
                visit(child, node_id, i, field, None, depth + 1)
        elif isinstance(value, FieldArray):
            for i, child in enumerate(value.items):
                visit(child, node_id, i, None, i, depth + 1)

    visit(record.fields, None, 0, None, None, 0)
    result = FactGraph(record.family, record.relative_file, record.ordinal, tuple(nodes))
    if decode_fact_graph(result) != record.fields:
        raise FactGraphError("internal source graph construction failed reverse decode")
    return result


def decode_fact_graph(graph: FactGraph) -> FieldObject:
    """Reconstruct independently from parent edges and positions, fail closed.

    Does not assume preorder, writer traversal, or a sidecar copy of values.
    """
    if not graph.nodes or len(graph.nodes) > MAX_FACT_NODES:
        raise FactGraphError("invalid graph size")
    if graph.ordinal < 1 or not graph.relative_file.startswith("data/"):
        raise FactGraphError("invalid source occurrence")
    mapping: dict[int, FactNode] = {}
    children: dict[int, list[FactNode]] = defaultdict(list)
    roots: list[FactNode] = []
    for node in graph.nodes:
        if type(node.id) is not int or node.id < 1 or node.id in mapping:
            raise FactGraphError("duplicate or invalid fact id")
        mapping[node.id] = node
    if set(mapping) != set(range(1, len(mapping) + 1)):
        raise FactGraphError("missing or noncontiguous fact identity")
    for node in graph.nodes:
        if type(node.position) is not int or node.position < 0:
            raise FactGraphError("invalid sibling position")
        if node.parent_id is None:
            roots.append(node)
        elif type(node.parent_id) is not int or node.parent_id not in mapping:
            raise FactGraphError("orphan fact parent")
        else:
            children[node.parent_id].append(node)
    if len(roots) != 1 or roots[0].id != 1 or roots[0].kind != "object":
        raise FactGraphError("must have exactly one root source object")
    if roots[0].key is not None or roots[0].index is not None or roots[0].position != 0:
        raise FactGraphError("invalid root address")

    seen: set[int] = set()
    active: set[int] = set()

    def visit(node: FactNode, depth: int) -> FieldValue:
        if depth > MAX_FACT_DEPTH:
            raise FactGraphError("fact graph nesting exceeds bound")
        if node.id in seen or node.id in active:
            raise FactGraphError("shared or cyclic fact nodes")
        active.add(node.id)
        followers = sorted(children.get(node.id, []), key=lambda n: n.position)
        if [n.position for n in followers] != list(range(len(followers))):
            raise FactGraphError("missing, duplicate or reordered fact positions")
        if node.kind == "object":
            if node.value is not None:
                raise FactGraphError("object contains a scalar value")
            pairs: list[tuple[str, FieldValue]] = []
            keys: set[str] = set()
            for child in followers:
                if not isinstance(child.key, str) or child.index is not None:
                    raise FactGraphError("object child must have string key only")
                if child.key in keys:
                    raise FactGraphError("duplicate object key")
                keys.add(child.key)
                pairs.append((child.key, visit(child, depth + 1)))
            value: FieldValue = FieldObject(tuple(pairs))
        elif node.kind == "array":
            if node.value is not None:
                raise FactGraphError("array contains a scalar value")
            items: list[FieldValue] = []
            for child in followers:
                if child.key is not None or child.index != child.position:
                    raise FactGraphError("array child must use exact contiguous index")
                items.append(visit(child, depth + 1))
            value = FieldArray(tuple(items))
        else:
            if followers:
                raise FactGraphError("scalar may not own child facts")
            if node.kind == "str" and type(node.value) is str:
                value = node.value
            elif node.kind == "int" and type(node.value) is int:
                value = node.value
            elif node.kind == "bool" and type(node.value) is bool:
                value = node.value
            else:
                raise FactGraphError("missing or type-shifted scalar fact")
        active.remove(node.id)
        seen.add(node.id)
        return value

    root = visit(roots[0], 0)
    if len(seen) != len(graph.nodes):
        raise FactGraphError("disconnected source fact nodes")
    if not isinstance(root, FieldObject):
        raise FactGraphError("source root must be object")
    return root


_NODE_FEATURES = (
    "fact_id fact_kind fact_position fact_key fact_index "
    "fact_str fact_int fact_bool"
)
_PASSAGE_FEATURES = "source_family source_file source_ordinal passage_key"
_ALL_FEATURES = (
    _NODE_FEATURES + " " + _PASSAGE_FEATURES + " atom_kind form has_fact"
)
_INT_FEATURES = {"fact_id", "fact_position", "fact_index",
                 "fact_int", "fact_bool", "source_ordinal"}


def write_native_fact_probe(record: ParsedRecord, destination: str | Path) -> None:
    """Write a bounded real source-row atom + native fact tree, no semantic blobs."""
    graph = build_fact_graph(record)
    if any(n.kind == "str" and isinstance(n.value, str) and "\r" in n.value
           for n in graph.nodes):
        raise FactGraphError("carriage return (CR) cannot safely round-trip in TF 13.1")
    target = Path(destination)
    if target.exists():
        raise FactGraphError(f"refusing existing TF destination: {target}")

    def director(cv: CV) -> None:
        passage = cv.node("passage")
        cv.feature(
            passage, source_family=graph.family, source_file=graph.relative_file,
            source_ordinal=graph.ordinal,
            passage_key=f"{graph.relative_file}:{graph.ordinal}",
        )
        for run in segment_runs(record.text):
            slot = cv.slot()
            cv.feature(slot, atom_kind="text", form=run.value)
        handles: dict[int, object] = {}
        # All sourceFact nodes share a *real* source-record slot. Their
        # semantic tree is in has_fact, NOT falsely inferred from oslots.
        for fact in graph.nodes:
            handle = cv.node("sourceFact")
            handles[fact.id] = handle
            attrs: dict[str, str | int] = {
                "fact_id": fact.id, "fact_kind": fact.kind,
                "fact_position": fact.position,
            }
            if fact.key is not None:
                attrs["fact_key"] = fact.key
            if fact.index is not None:
                attrs["fact_index"] = fact.index
            if fact.kind == "str":
                assert type(fact.value) is str
                attrs["fact_str"] = fact.value
            if fact.kind == "int":
                assert type(fact.value) is int
                attrs["fact_int"] = fact.value
            if fact.kind == "bool":
                assert type(fact.value) is bool
                attrs["fact_bool"] = int(fact.value)
            cv.feature(handle, **attrs)
        row_atom = cv.slot()
        cv.feature(row_atom, atom_kind="source-row")
        for fact in reversed(graph.nodes):
            cv.terminate(handles[fact.id])
        for fact in graph.nodes:
            parent = passage if fact.parent_id is None else handles[fact.parent_id]
            cv.edge(parent, handles[fact.id], has_fact=None)
        cv.terminate(passage)

    # TF 13.1 rejects featureMeta/intFeatures entries for features absent
    # from *this* graph. Derive the declarations from actual native values.
    used = {
        "atom_kind", "source_family", "source_file", "source_ordinal",
        "passage_key", "fact_id", "fact_kind", "fact_position", "has_fact",
    }
    if record.text:
        used.add("form")
    for fact in graph.nodes:
        if fact.key is not None:
            used.add("fact_key")
        if fact.index is not None:
            used.add("fact_index")
        if fact.kind in ("str", "int", "bool"):
            used.add(f"fact_{fact.kind}")

    cv = CV(Fabric(locations=str(target), silent="deep"), silent="deep")
    success = cv.walk(
        director,
        slotType="atom",
        generic={"source": "Open Greek one-record fact graph experiment"},
        otext={
            "sectionTypes": "passage", "sectionFeatures": "passage_key",
            "fmt:text-orig-full": "{form}",
        },
        featureMeta={n: {"description": f"Native source fact graph {n}"}
                     for n in sorted(used)},
        intFeatures=_INT_FEATURES & used,
        warn=False,
    )
    if not success:
        raise FactGraphError("Text-Fabric rejected native source fact graph")


def read_native_fact_graph(destination: str | Path) -> FactGraph:
    """Independent native TF load: read every fact, parent edge, type, and order."""
    fabric = Fabric(locations=str(destination), silent="deep")
    catalog = fabric.explore(silent="deep")
    if not catalog:
        raise FactGraphError("cannot discover native TF source fact features")
    present = set(catalog["nodes"]) | set(catalog["edges"])
    required = {
        "atom_kind", "source_family", "source_file", "source_ordinal",
        "passage_key", "fact_id", "fact_kind", "fact_position", "has_fact",
    }
    if required - present:
        raise FactGraphError("native TF graph lacks required structural features")
    api = fabric.load(
        " ".join(n for n in _ALL_FEATURES.split() if n in present), silent="deep"
    )
    if not api:
        raise FactGraphError("cannot load native TF source fact graph")

    def read_feature(name: str, node: int) -> str | int | None:
        """Absent optional features differ from present empty/zero values."""
        if name not in present:
            return None
        return getattr(api.F, name).v(node)

    passages = api.F.otype.s("passage")
    if len(passages) != 1:
        raise FactGraphError("native fact probe must contain one passage")
    passage = passages[0]
    nodes = api.F.otype.s("sourceFact")
    # An independent reader must not trust that CV anchored the declared
    # facts on a genuine source-row slot rather than a text/phantom token.
    row_atoms = tuple(
        s for s in api.F.otype.s("atom")
        if api.F.atom_kind.v(s) == "source-row"
    )
    if len(row_atoms) != 1 or read_feature("form", row_atoms[0]) is not None:
        raise FactGraphError("fact graph requires one non-text source-row atom")
    source_atom = row_atoms[0]
    if source_atom not in api.E.oslots.s(passage):
        raise FactGraphError("source row is outside native passage")
    for handle in nodes:
        if set(api.E.oslots.s(handle)) != {source_atom}:
            raise FactGraphError("native source fact is not anchored to source row")
    by_handle: dict[int, int] = {}
    for handle in nodes:
        ident = read_feature("fact_id", handle)
        if type(ident) is not int or ident in by_handle.values():
            raise FactGraphError("native fact id missing or duplicated")
        by_handle[handle] = ident
    parent: dict[int, int | None] = {}
    for handle in (passage, *nodes):
        for child in api.E.has_fact.f(handle):
            if child not in by_handle:
                raise FactGraphError("has_fact points outside sourceFact nodes")
            if child in parent:
                raise FactGraphError("fact has multiple parents")
            parent[child] = None if handle == passage else by_handle[handle]
    if len(parent) != len(nodes):
        raise FactGraphError("native fact lost source parent edge")

    result: list[FactNode] = []
    for handle, ident in by_handle.items():
        kind_raw = read_feature("fact_kind", handle)
        if kind_raw not in ("object", "array", "str", "int", "bool"):
            raise FactGraphError("unknown native fact kind")
        kind = cast(FactKind, kind_raw)
        present = [("str", read_feature("fact_str", handle)),
                   ("int", read_feature("fact_int", handle)),
                   ("bool", read_feature("fact_bool", handle))]
        nonempty = [(name, val) for name, val in present if val is not None]
        if kind in ("object", "array"):
            if nonempty:
                raise FactGraphError("container has unexpected scalar feature")
            value: FactScalar | None = None
        else:
            if len(nonempty) != 1 or nonempty[0][0] != kind:
                raise FactGraphError("native scalar discriminant mismatch")
            scalar = nonempty[0][1]
            if kind == "bool":
                if scalar not in (0, 1) or type(scalar) is not int:
                    raise FactGraphError("native boolean must be 0 or 1")
                value = bool(scalar)
            elif kind == "int":
                if type(scalar) is not int:
                    raise FactGraphError("native integer was converted")
                value = scalar
            else:
                if type(scalar) is not str:
                    raise FactGraphError("native string was converted")
                value = scalar
        pos = read_feature("fact_position", handle)
        key = read_feature("fact_key", handle)
        index = read_feature("fact_index", handle)
        if type(pos) is not int:
            raise FactGraphError("invalid native fact position")
        if key is not None and type(key) is not str:
            raise FactGraphError("invalid native fact key")
        if index is not None and type(index) is not int:
            raise FactGraphError("invalid native fact array index")
        result.append(
            FactNode(
                id=cast(int, ident), parent_id=parent.get(handle),
                position=cast(int, pos),
                key=cast(str | None, key), index=cast(int | None, index),
                kind=kind, value=value,
            )
        )
    family = read_feature("source_family", passage)
    relative_file = read_feature("source_file", passage)
    ordinal = read_feature("source_ordinal", passage)
    if family not in ("primary", "secondary", "paratext"):
        raise FactGraphError("invalid native source family")
    if type(relative_file) is not str or type(ordinal) is not int:
        raise FactGraphError("invalid native source occurrence")
    graph = FactGraph(
        family=cast(Family, family),
        relative_file=cast(str, relative_file),
        ordinal=cast(int, ordinal),
        nodes=tuple(result),
    )
    decode_fact_graph(graph)
    return graph
