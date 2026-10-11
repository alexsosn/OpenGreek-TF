"""Generic mixed native Text-Fabric composer for ordered typed source facts.

Creates one authentic source-row atom per metadata or text record. Passage
text runs occupy separate atoms, and metadata records never become words.
The loader independently reconstructs every source graph from F/E.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
from .record_stream import FieldObject
from .text_runs import segment_runs


class NativeComposeError(ValueError):
    """Native TF source graph violates its conservation contract."""


@dataclass(frozen=True, slots=True)
class NativeRecord:
    source_file: str
    ordinal: int
    source_record_id: str
    record_kind: str
    fields: FieldObject
    text: str | None = None

    @property
    def occurrence_key(self) -> tuple[str, int]:
        return (self.source_file, self.ordinal)


@dataclass(frozen=True, slots=True)
class NativeStats:
    records: int
    metadata_records: int
    text_records: int
    source_atoms: int
    fact_nodes: int


def _preflight(records: tuple[NativeRecord, ...]) -> tuple[FactGraph, ...]:
    if not records:
        raise NativeComposeError("cannot compose empty source graph")
    identities: set[tuple[str, int]] = set()
    graphs: list[FactGraph] = []
    for record in records:
        if (
            type(record.source_file) is not str
            or not record.source_file
            or type(record.ordinal) is not int
            or record.ordinal < 1
            or type(record.source_record_id) is not str
            or not record.source_record_id
            or type(record.record_kind) is not str
            or not record.record_kind
        ):
            raise NativeComposeError("missing or malformed physical source identity")
        if (record.source_file, record.ordinal) in identities:
            raise NativeComposeError("duplicate physical source occurrence")
        identities.add((record.source_file, record.ordinal))
        for value in (record.source_file, record.source_record_id, record.record_kind):
            if "\r" in value:
                raise NativeComposeError("carriage return in source identity")
        if record.text is not None:
            if type(record.text) is not str or record.fields.require("text") != record.text:
                raise NativeComposeError("source passage text differs from typed fact")
            if "\r" in record.text:
                raise NativeComposeError("carriage return in source passage text")
        try:
            graph = build_fact_graph(record)
            if restore_fact_fields(graph) != record.fields:
                raise NativeComposeError("typed fact graph failed source conservation")
        except (FactGraphError, KeyError) as exc:
            raise NativeComposeError("invalid native source fact graph") from exc
        for node in graph.nodes:
            if (
                (node.key is not None and "\r" in node.key)
                or (isinstance(node.value, str) and "\r" in node.value)
            ):
                raise NativeComposeError("carriage return in native fact")
        graphs.append(graph)
    return tuple(graphs)


def _stats(records: tuple[NativeRecord, ...], graphs: tuple[FactGraph, ...]) -> NativeStats:
    text_count = sum(record.text is not None for record in records)
    return NativeStats(
        records=len(records),
        metadata_records=len(records) - text_count,
        text_records=text_count,
        source_atoms=len(records),
        fact_nodes=sum(graph.declared_size for graph in graphs),
    )


def write_native_records(
    records: tuple[NativeRecord, ...],
    destination: Path,
    *,
    on_phase: Callable[[str], None] | None = None,
) -> NativeStats:
    """Compose into native TF; optionally report validated phase boundaries.

    on_phase runs after successful preflight, native CV.walk, and independent
    Fabric.load conservation, respectively. The callback does not change data.
    """
    if destination.exists() or destination.is_symlink():
        raise NativeComposeError("native TF destination already exists")
    graphs = _preflight(records)
    if on_phase is not None:
        on_phase("preflight-complete")
    has_text = any(record.text is not None for record in records)
    # Avoid retaining a second 252k-element reference vector solely for
    # feature discovery: inspect each already validated fact in-place.
    def has_fact(predicate: Callable[[FactNode], bool]) -> bool:
        return any(predicate(node) for graph in graphs for node in graph.nodes)
    available = {
        "atom_kind", "source_file", "source_ordinal", "source_seq",
        "source_record_id", "record_kind", "fact_count", "fact_digest",
        "fact_kind", "fact_id", "fact_position", "has_fact",
    }
    if has_fact(lambda node: node.key is not None):
        available.add("fact_key")
    if has_fact(lambda node: node.kind == "str"):
        available.add("fact_text")
    if has_fact(lambda node: node.kind in {"int", "bool"}):
        available.add("fact_int")
    if has_text:
        available.add("form")
    ints = {"source_ordinal", "source_seq", "fact_count", "fact_id", "fact_position"}
    if "fact_int" in available:
        ints.add("fact_int")

    def director(cv: CV) -> None:
        for seq, (record, graph) in enumerate(zip(records, graphs, strict=True), 1):
            textual = record.text is not None
            owner = cv.node("passage" if textual else "metadataRecord")
            cv.feature(
                owner,
                source_file=record.source_file, source_ordinal=record.ordinal,
                source_seq=seq, source_record_id=record.source_record_id,
                record_kind=record.record_kind, fact_count=graph.declared_size,
                fact_digest=graph.digest,
            )
            if textual:
                assert record.text is not None
                for run in segment_runs(record.text):
                    text_atom = cv.slot()
                    cv.feature(text_atom, atom_kind="text", form=run.value)
            source_atom = cv.slot()
            cv.feature(
                source_atom,
                atom_kind="source-row" if textual else "metadata-record",
                source_file=record.source_file,
                source_record_id=record.source_record_id,
            )
            if textual and not record.text:
                cv.feature(source_atom, form="")
            cv.terminate(owner)
            handles: dict[int, Any] = {}
            for fact in graph.nodes:
                handle = cv.node("sourceFact", slots=[source_atom[1]])
                handles[fact.node_id] = handle
                values: dict[str, str | int] = {
                    "fact_kind": fact.kind,
                    "fact_id": fact.node_id,
                    "fact_position": fact.position,
                }
                if fact.key is not None:
                    values["fact_key"] = fact.key
                if fact.kind == "str":
                    if type(fact.value) is not str:
                        raise NativeComposeError("invalid source string scalar")
                    values["fact_text"] = fact.value
                if fact.kind in {"int", "bool"}:
                    if not isinstance(fact.value, (int, bool)):
                        raise NativeComposeError("invalid source numeric scalar")
                    values["fact_int"] = int(fact.value)
                cv.feature(handle, **values)
            for fact in graph.nodes:
                if fact.parent_id is None:
                    cv.edge(owner, handles[fact.node_id], has_fact=None)
                else:
                    cv.edge(
                        handles[fact.parent_id], handles[fact.node_id], has_fact=None,
                    )

    output = Fabric(locations=str(destination), silent="deep")
    otext = {
        "sectionTypes": "passage" if has_text else "",
        "sectionFeatures": "source_record_id" if has_text else "",
        "fmt:text-orig-full": "{form}" if has_text else "{source_record_id}",
    }
    if not CV(output, silent="deep").walk(
        director, slotType="atom",
        generic={"source": "Open Greek pinned mixed typed source records"},
        otext=otext,
        featureMeta={
            name: {"description": f"Typed genuine source fact {name}"}
            for name in sorted(available)
        },
        intFeatures=ints,
        warn=False,
    ):
        raise NativeComposeError("Text-Fabric rejected generic mixed source graph")
    if on_phase is not None:
        on_phase("walk-complete")
    stats = _stats(records, graphs)
    # Release the original source FactGraph objects *before* Fabric.load
    # reconstructs another complete typed graph. The CV.walk director uses
    # a closure over graphs, so replacing the variable clears the captured
    # tuple while keeping the closure analyzable by Python/static checkers.
    graphs = ()
    # The independent loaded source graph is the postwrite validator.
    # Do not preflight a *second* full FactGraph collection while the first
    # is still live; public validate_native_records remains fully independent.
    loaded = read_native_records(destination)
    if loaded != records:
        raise NativeComposeError(
            f"generic composer conservation failure: {len(records)} vs {len(loaded)}"
        )
    if on_phase is not None:
        on_phase("load-validated")
    return stats


def read_native_records(destination: Path) -> tuple[NativeRecord, ...]:
    """Independently load TF and reconstruct source records, including null."""
    fabric = Fabric(locations=str(destination), silent="deep")
    discovered = fabric.explore(silent="deep")
    if not discovered:
        raise NativeComposeError("cannot discover native source features")
    mandatory = {
        "atom_kind", "source_file", "source_ordinal", "source_seq",
        "source_record_id", "record_kind", "fact_count", "fact_digest",
        "fact_kind", "fact_id", "fact_position", "has_fact",
    }
    optional = {"fact_key", "fact_text", "fact_int", "form"}
    declared_nodes = set(discovered["nodes"])
    declared_edges = set(discovered["edges"])
    declared = declared_nodes | declared_edges
    if (
        not (mandatory - {"has_fact"}).issubset(declared_nodes)
        or "has_fact" not in declared_edges
        or "has_fact" in declared_nodes
    ):
        raise NativeComposeError("missing or wrong-kind required native TF feature")
    api = fabric.load(
        " ".join(sorted(mandatory | (optional & declared))), silent="deep",
    )
    if not api:
        raise NativeComposeError("cannot load native typed source graph")
    roots = tuple(api.F.otype.s("passage")) + tuple(api.F.otype.s("metadataRecord"))
    fact_handles = set(api.F.otype.s("sourceFact"))
    atom_handles = set(api.F.otype.s("atom"))
    if not roots:
        raise NativeComposeError("missing source records")
    if api.F.otype.s("word") or (destination / "word.tf").exists():
        raise NativeComposeError("native composer invented word-level content")
    # TF's F.otype.all reports node-type labels (big to small), not node IDs.
    allowed = {"atom", "passage", "metadataRecord", "sourceFact"}
    if set(api.F.otype.all) - allowed:
        raise NativeComposeError("unexpected Text-Fabric node type")
    used_atoms: set[int] = set()
    used_facts: set[int] = set()
    used_ids: set[tuple[str, int]] = set()
    seqs: dict[int, NativeRecord] = {}

    for root in roots:
        is_text = api.F.otype.v(root) == "passage"
        filename = api.F.source_file.v(root)
        ordinal = api.F.source_ordinal.v(root)
        seq = api.F.source_seq.v(root)
        record_id = api.F.source_record_id.v(root)
        record_kind = api.F.record_kind.v(root)
        count = api.F.fact_count.v(root)
        digest = api.F.fact_digest.v(root)
        if (
            type(filename) is not str or not filename
            or type(ordinal) is not int or ordinal < 1
            or type(seq) is not int or seq < 1 or seq in seqs
            or type(record_id) is not str or not record_id
            or type(record_kind) is not str or not record_kind
            or type(count) is not int or count < 1
            or type(digest) is not str
            or (filename, ordinal) in used_ids
        ):
            raise NativeComposeError("invalid or duplicate loaded record identity")
        used_ids.add((filename, ordinal))
        slots = tuple(api.E.oslots.s(root))
        if not slots:
            raise NativeComposeError("missing genuine record source atom")
        anchor = slots[-1]
        if (
            anchor not in atom_handles or anchor in used_atoms
            or api.F.atom_kind.v(anchor) != (
                "source-row" if is_text else "metadata-record"
            )
            or api.F.source_file.v(anchor) != filename
            or api.F.source_record_id.v(anchor) != record_id
        ):
            raise NativeComposeError("missing, shared or wrong source row atom")
        if not is_text and len(slots) != 1:
            raise NativeComposeError("metadata record acquired fake text slots")
        used_atoms.add(anchor)

        # Every fact must be reached from this source owner's single root edge.
        first = tuple(api.E.has_fact.f(root))
        if len(first) != 1 or first[0] not in fact_handles:
            raise NativeComposeError("source record missing unique root fact")
        queue: list[tuple[int, int | None]] = [(first[0], None)]
        observed: dict[int, FactNode] = {}
        while queue:
            handle, parent = queue.pop(0)
            if handle in used_facts or handle not in fact_handles:
                raise NativeComposeError("orphaned, repeated or foreign source fact")
            used_facts.add(handle)
            if tuple(api.E.oslots.s(handle)) != (anchor,):
                raise NativeComposeError("source fact linked to foreign atom")
            local_id = api.F.fact_id.v(handle)
            position = api.F.fact_position.v(handle)
            kind = api.F.fact_kind.v(handle)
            key = api.F.fact_key.v(handle) if "fact_key" in declared else None
            if (
                type(local_id) is not int or local_id in observed
                or type(position) is not int
                or kind not in {"object", "array", "str", "int", "bool", "null"}
            ):
                raise NativeComposeError("invalid local source fact identity/type")
            text = api.F.fact_text.v(handle) if "fact_text" in declared else None
            number = api.F.fact_int.v(handle) if "fact_int" in declared else None
            if kind == "str":
                if type(text) is not str or number is not None:
                    raise NativeComposeError("bad source string scalar")
                value: str | int | bool | None = text
            elif kind in {"int", "bool"}:
                if type(number) is not int or text is not None:
                    raise NativeComposeError("bad source numeric scalar")
                if kind == "bool" and number not in (0, 1):
                    raise NativeComposeError("invalid native boolean value")
                value = bool(number) if kind == "bool" else number
            else:
                if text is not None or number is not None:
                    raise NativeComposeError("container/null acquired scalar payload")
                value = None
            observed[local_id] = FactNode(
                node_id=local_id, parent_id=parent,
                position=position, key=key, kind=kind, value=value,
            )
            for child in api.E.has_fact.f(handle):
                if child not in fact_handles:
                    raise NativeComposeError("non-fact edge target")
                queue.append((child, local_id))
        if set(observed) != set(range(count)):
            raise NativeComposeError("missing, repeated or extra source fact")
        graph = FactGraph(
            (filename, ordinal),
            tuple(observed[i] for i in range(count)),
            count,
            digest,
        )
        try:
            fields = restore_fact_fields(graph)
        except FactGraphError as exc:
            raise NativeComposeError("native TF changed nested typed source facts") from exc

        if is_text:
            source_text = fields.get("text")
            if type(source_text) is not str:
                raise NativeComposeError("passage has no literal source text")
            runs: list[str] = []
            for slot in slots[:-1]:
                if slot not in atom_handles or slot in used_atoms:
                    raise NativeComposeError("duplicate or unknown text atom")
                used_atoms.add(slot)
                if api.F.atom_kind.v(slot) != "text":
                    raise NativeComposeError("text run has wrong atom kind")
                run = api.F.form.v(slot) if "form" in declared else None
                if type(run) is not str or not run:
                    raise NativeComposeError("missing literal text run")
                runs.append(run)
            if "".join(runs) != source_text:
                raise NativeComposeError("native text slots differ from source facts")
            anchor_form = api.F.form.v(anchor) if "form" in declared else None
            if anchor_form not in (None, "") or (source_text and anchor_form is not None):
                raise NativeComposeError("source anchor contains fabricated text")
            if api.T.text(root, fmt="text-orig-full") != source_text:
                raise NativeComposeError("Text-Fabric rendered passage differs")
        else:
            source_text = None
            if "form" in declared and api.F.form.v(anchor) is not None:
                raise NativeComposeError("metadata atom acquired lexical form")
        seqs[seq] = NativeRecord(
            filename, ordinal, record_id, record_kind, fields, source_text,
        )

    if used_atoms != atom_handles or used_facts != fact_handles:
        raise NativeComposeError("unaccounted native TF source or fact nodes")
    if set(seqs) != set(range(1, len(seqs) + 1)):
        raise NativeComposeError("missing or duplicated global source order")
    return tuple(seqs[i] for i in range(1, len(seqs) + 1))


def validate_native_records(
    records: tuple[NativeRecord, ...], destination: Path,
) -> NativeStats:
    """Compare source records with independently reloaded native TF features."""
    graphs = _preflight(records)
    actual = read_native_records(destination)
    if actual != records:
        raise NativeComposeError(
            f"generic composer conservation failure: {len(records)} vs {len(actual)}"
        )
    return _stats(actual, graphs)
