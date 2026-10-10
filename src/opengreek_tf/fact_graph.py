"""Native-TF-ready graph of every ordered, typed source-record fact.

Independent of Text-Fabric: no JSON blobs, lexical inference or sidecars.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, TypeAlias

from .record_stream import FieldArray, FieldObject, FieldValue, ParsedRecord

FactKind: TypeAlias = Literal["object", "array", "str", "int", "bool"]


class FactGraphError(ValueError):
    """A source fact is unrepresentable or a graph invariant was violated."""


@dataclass(frozen=True, slots=True)
class FactNode:
    """One real source object, array or scalar at a source-local preorder ID."""

    node_id: int
    parent_id: int | None
    position: int
    key: str | None
    kind: FactKind
    value: str | int | bool | None = None


@dataclass(frozen=True, slots=True)
class FactGraph:
    """Source-local ordered typed graph with its physical occurrence identity."""

    occurrence_key: tuple[str, int]
    nodes: tuple[FactNode, ...]
    declared_size: int
    digest: str


def _digest(
    occurrence_key: tuple[str, int], nodes: tuple[FactNode, ...]
) -> str:
    """Hash complete typed graph semantics, including order and source identity."""
    h = hashlib.sha256()
    payloads: list[object] = [list(occurrence_key)]
    payloads.extend(
        [n.node_id, n.parent_id, n.position, n.key, n.kind, n.value]
        for n in nodes
    )
    for payload in payloads:
        h.update(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        h.update(b"\\n")
    return h.hexdigest()


def build_fact_graph(record: ParsedRecord) -> FactGraph:
    """Flatten typed source facts into immutable parent-indexed graph nodes."""

    nodes: list[FactNode] = []

    def visit(
        value: FieldValue,
        parent_id: int | None,
        position: int,
        key: str | None,
    ) -> int:
        if isinstance(value, FieldObject):
            kind: FactKind = "object"
            scalar: str | int | bool | None = None
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
            raise FactGraphError(f"unsupported typed source fact: {type(value)}")

        node_id = len(nodes)
        nodes.append(
            FactNode(
                node_id=node_id,
                parent_id=parent_id,
                position=position,
                key=key,
                kind=kind,
                value=scalar,
            )
        )
        if isinstance(value, FieldObject):
            for index, (field_key, field_value) in enumerate(value.items):
                visit(field_value, node_id, index, field_key)
        elif isinstance(value, FieldArray):
            for index, item in enumerate(value.items):
                visit(item, node_id, index, None)
        return node_id

    visit(record.fields, None, 0, None)
    result_nodes = tuple(nodes)
    return FactGraph(
        occurrence_key=record.occurrence_key,
        nodes=result_nodes,
        declared_size=len(result_nodes),
        digest=_digest(record.occurrence_key, result_nodes),
    )


def restore_fact_fields(graph: FactGraph) -> FieldObject:
    """Independently validate then restore all ordered typed source fields."""

    nodes = graph.nodes
    if type(graph.declared_size) is not int or graph.declared_size != len(nodes):
        raise FactGraphError("declared source fact node count mismatch")
    if _digest(graph.occurrence_key, nodes) != graph.digest:
        raise FactGraphError("source fact digest mismatch: source values or order changed")
    if not nodes:
        raise FactGraphError("missing root fact node")
    if len(graph.occurrence_key) != 2 or not graph.occurrence_key[0]:
        raise FactGraphError("missing physical source identity")
    if type(graph.occurrence_key[1]) is not int or graph.occurrence_key[1] < 1:
        raise FactGraphError("invalid physical source ordinal")

    children: dict[int, list[FactNode]] = {}
    for expected_id, node in enumerate(nodes):
        if node.node_id != expected_id:
            raise FactGraphError("missing, duplicate or out-of-order fact node ID")
        if expected_id == 0:
            if node.parent_id is not None or node.position != 0 or node.key is not None:
                raise FactGraphError("invalid source fact root")
            if node.kind != "object":
                raise FactGraphError("source record root must be an object")
        elif (
            node.parent_id is None
            or type(node.parent_id) is not int
            or not 0 <= node.parent_id < expected_id
        ):
            raise FactGraphError("fact parent must precede its child")
        if type(node.position) is not int or node.position < 0:
            raise FactGraphError("invalid child position")
        if node.kind in {"object", "array"}:
            if node.value is not None:
                raise FactGraphError("source container has a scalar value")
        elif node.kind == "str" and type(node.value) is not str:
            raise FactGraphError("expected exact string scalar")
        elif node.kind == "int" and type(node.value) is not int:
            raise FactGraphError("expected exact integer scalar")
        elif node.kind == "bool" and type(node.value) is not bool:
            raise FactGraphError("expected exact boolean scalar")
        elif node.kind not in {"str", "int", "bool", "object", "array"}:
            raise FactGraphError("unknown source fact kind")
        if node.parent_id is not None:
            children.setdefault(node.parent_id, []).append(node)

    def rebuild(node_id: int) -> FieldValue:
        node = nodes[node_id]
        successors = sorted(children.get(node_id, []), key=lambda child: child.position)
        if node.kind not in {"object", "array"}:
            if successors:
                raise FactGraphError("scalar source fact cannot have children")
            value = node.value
            if not isinstance(value, (str, int, bool)):
                raise FactGraphError("scalar source fact has invalid type")
            return value
        if [child.position for child in successors] != list(range(len(successors))):
            raise FactGraphError("missing, duplicated or reordered child positions")
        if node.kind == "array":
            if any(child.key is not None for child in successors):
                raise FactGraphError("array item cannot carry an object key")
            return FieldArray(tuple(rebuild(child.node_id) for child in successors))
        fields: list[tuple[str, FieldValue]] = []
        seen: set[str] = set()
        for child in successors:
            if not isinstance(child.key, str):
                raise FactGraphError("object member missing field key")
            if child.key in seen:
                raise FactGraphError("duplicate source object key")
            seen.add(child.key)
            fields.append((child.key, rebuild(child.node_id)))
        return FieldObject(tuple(fields))

    result = rebuild(0)
    if not isinstance(result, FieldObject):
        raise FactGraphError("root did not restore a source object")
    return result
