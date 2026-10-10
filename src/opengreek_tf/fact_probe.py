"""Bounded source-fact → native TF proof, independently loadable as a graph.

Uses genuine source-row and text atoms; not a production corpus writer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

from .fact_graph import (
    FactGraph,
    FactGraphError,
    FactNode,
    build_fact_graph,
    restore_fact_fields,
)
from .record_stream import ParsedRecord
from .text_runs import segment_runs


def write_fact_probe(record: ParsedRecord, destination: str | Path) -> None:
    """Emit all real typed facts of one source row as native TF nodes/edges."""

    graph = build_fact_graph(record)
    if restore_fact_fields(graph) != record.fields:
        raise FactGraphError("source fact graph failed pre-write conservation")
    output = Path(destination)
    if output.exists():
        raise FactGraphError(f"TF output already exists: {output}")

    for node in graph.nodes:
        if (
            (isinstance(node.value, str) and "\r" in node.value)
            or (node.key is not None and "\r" in node.key)
        ):
            raise FactGraphError("carriage return in source fact cannot round-trip")
    if "\r" in record.relative_file:
        raise FactGraphError("carriage return in physical source identifier")

    def director(cv: CV) -> None:
        passage = cv.node("passage")
        cv.feature(
            passage,
            passage_key=f"{record.relative_file}:{record.ordinal}",
            source_file=record.relative_file,
            source_ordinal=record.ordinal,
            fact_count=graph.declared_size,
            fact_digest=graph.digest,
        )
        for run in segment_runs(record.text):
            atom = cv.slot()
            cv.feature(atom, atom_kind="text", form=run.value)
        source_atom = cv.slot()
        cv.feature(source_atom, atom_kind="source-row")

        handles: dict[int, Any] = {}
        for fact in graph.nodes:
            handle = cv.node("sourceFact", slots=[source_atom[1]])
            handles[fact.node_id] = handle
            typed: dict[str, str | int] = {
                "fact_kind": fact.kind,
                "fact_id": fact.node_id,
                "fact_position": fact.position,
            }
            if fact.key is not None:
                typed["fact_key"] = fact.key
            if fact.kind == "str":
                if not isinstance(fact.value, str):
                    raise FactGraphError("string source fact has no string value")
                typed["fact_text"] = fact.value
            elif fact.kind in {"int", "bool"}:
                if type(fact.value) not in (int, bool):
                    raise FactGraphError("numeric source fact has no typed value")
                typed["fact_int"] = int(fact.value)
            cv.feature(handle, **typed)
        for fact in graph.nodes:
            if fact.parent_id is not None:
                cv.edge(handles[fact.parent_id], handles[fact.node_id], has_fact=None)
        cv.edge(passage, handles[0], has_fact=None)
        cv.terminate(passage)

    # TF 13.1 refuses metadata declarations for node features that do not
    # actually occur. Keep the source model honest: never fabricate values
    # merely to satisfy a feature declaration.
    available = {
        "atom_kind", "passage_key", "source_file", "source_ordinal",
        "fact_count", "fact_digest", "fact_kind", "fact_id", "fact_position",
        "has_fact",
    }
    if any(fact.key is not None for fact in graph.nodes):
        available.add("fact_key")
    if any(fact.kind == "str" for fact in graph.nodes):
        available.add("fact_text")
    if any(fact.kind in {"int", "bool"} for fact in graph.nodes):
        available.add("fact_int")
    if record.text:
        available.add("form")
    integer_features = {"source_ordinal", "fact_count", "fact_id", "fact_position"}
    if "fact_int" in available:
        integer_features.add("fact_int")

    cv = CV(Fabric(locations=str(output), silent="deep"), silent="deep")
    result = cv.walk(
        director,
        slotType="atom",
        generic={"source": "Open Greek native typed source-fact experiment"},
        otext={
            "sectionTypes": "passage",
            "sectionFeatures": "passage_key",
            "fmt:text-orig-full": "{form}",
        },
        featureMeta={
            name: {"description": f"Native source fact {name}"}
            for name in sorted(available)
        },
        intFeatures=integer_features,
        warn=False,
    )
    if not result:
        raise FactGraphError("Text-Fabric refused source-fact graph")


def read_fact_probe(destination: str | Path) -> FactGraph:
    """Reconstruct the fact graph from *loaded native TF*, never original rows."""

    fabric = Fabric(locations=str(destination), silent="deep")
    discovered = fabric.explore(silent="deep")
    if not discovered:
        raise FactGraphError("cannot discover native TF source-fact features")
    required = {
        "source_file", "source_ordinal", "fact_count", "fact_digest",
        "atom_kind", "fact_id", "fact_kind", "fact_position", "has_fact",
    }
    optional = {"fact_key", "fact_text", "fact_int"}
    declared = set(discovered["nodes"]) | set(discovered["edges"])
    if not required.issubset(declared):
        raise FactGraphError("missing mandatory native source-fact features")
    api = fabric.load(" ".join(sorted(required | (optional & declared))), silent="deep")
    if not api:
        raise FactGraphError("cannot load native source-fact dataset")
    passages = api.F.otype.s("passage")
    if len(passages) != 1:
        raise FactGraphError("expected one physical source passage")
    passage = passages[0]
    physical_file = api.F.source_file.v(passage)
    physical_ordinal = api.F.source_ordinal.v(passage)
    if not isinstance(physical_file, str) or type(physical_ordinal) is not int:
        raise FactGraphError("loaded passage lost physical occurrence identity")

    fact_handles = api.F.otype.s("sourceFact")
    by_local_id: dict[int, int] = {}
    for handle in fact_handles:
        local_id = api.F.fact_id.v(handle)
        if type(local_id) is not int or local_id in by_local_id:
            raise FactGraphError("missing or duplicated native source fact ID")
        by_local_id[local_id] = handle
    if set(by_local_id) != set(range(len(fact_handles))):
        raise FactGraphError("native fact ID sequence has gaps")

    roots = tuple(api.E.has_fact.f(passage))
    if roots != (by_local_id[0],):
        raise FactGraphError("passage has missing or ambiguous source fact root")

    parent_by_handle: dict[int, int] = {}
    for source_id, source_handle in by_local_id.items():
        for child_handle in api.E.has_fact.f(source_handle):
            if child_handle not in fact_handles or child_handle in parent_by_handle:
                raise FactGraphError("unknown or multiply parented native source fact")
            parent_by_handle[child_handle] = source_id

    nodes: list[FactNode] = []
    for local_id in range(len(fact_handles)):
        handle = by_local_id[local_id]
        kind = api.F.fact_kind.v(handle)
        if kind not in ("str", "int", "bool", "array", "object"):
            raise FactGraphError("unknown native source fact kind")
        if kind == "str":
            value: str | int | bool | None = api.F.fact_text.v(handle)
        elif kind in ("int", "bool"):
            number = api.F.fact_int.v(handle)
            if type(number) is not int or (kind == "bool" and number not in (0, 1)):
                raise FactGraphError("invalid native numeric or boolean fact")
            value = bool(number) if kind == "bool" else number
        else:
            value = None
        position = api.F.fact_position.v(handle)
        key = api.F.fact_key.v(handle)
        nodes.append(
            FactNode(
                node_id=local_id,
                parent_id=parent_by_handle.get(handle),
                position=position,
                key=key,
                kind=kind,
                value=value,
            )
        )
    count = api.F.fact_count.v(passage)
    digest = api.F.fact_digest.v(passage)
    if type(count) is not int or not isinstance(digest, str):
        raise FactGraphError("loaded passage lost source fact conservation seal")
    graph = FactGraph(
        occurrence_key=(physical_file, physical_ordinal),
        nodes=tuple(nodes),
        declared_size=count,
        digest=digest,
    )
    restore_fact_fields(graph)
    # All nodes are truly associated with this source row, not other texts.
    row_atoms = {
        slot
        for slot in api.E.oslots.s(passage)
        if api.F.atom_kind.v(slot) == "source-row"
    }
    if len(row_atoms) != 1:
        raise FactGraphError("source passage must contain one authentic row atom")
    for handle in fact_handles:
        if set(api.E.oslots.s(handle)) != row_atoms:
            raise FactGraphError("fact node not anchored to the correct source row")
    return graph
