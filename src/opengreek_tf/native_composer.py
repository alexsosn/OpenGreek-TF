"""Generic mixed native Text-Fabric composer for ordered typed source facts.

Creates one authentic source-row atom per metadata or text record. Passage
text runs occupy separate atoms, and metadata records never become words.
The loader independently reconstructs every source graph from F/E.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator
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
from .record_stream import FieldArray, FieldObject, FieldValue
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


def _update_source_signature(
    digest: Any, record: NativeRecord, graph: FactGraph,
) -> None:
    """Bind original physical order, all typed facts and root kind to a replay.

    The graph digest alone intentionally excludes record_kind and source ID.
    Source text itself is already an exactly typed field in graph.digest,
    and preflight requires equality with the passage layout text.
    """
    digest.update(json.dumps(
        [record.source_file, record.ordinal, record.source_record_id,
         record.record_kind, graph.digest, record.text is not None],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8"))
    digest.update(b"\n")


def _preflight(
    records: Iterable[NativeRecord],
) -> tuple[NativeStats, set[str], str]:
    """Validate each source graph before writing, without retaining all graphs.

    Aggregate only the complete native feature surface and exact fact counts.
    This preflight rejects invalid final rows before output and retains only
    a small feature/count/replay digest, not a full source-record tuple.
    CV.walk remains internally in-memory for all native F/E.
    """
    identities: set[tuple[str, int]] = set()
    available = {
        "atom_kind", "source_file", "source_ordinal", "source_seq",
        "source_record_id", "record_kind", "fact_count", "fact_digest",
        "fact_kind", "fact_id", "fact_position", "has_fact",
    }
    fact_nodes = 0
    text_count = 0
    seen = 0
    signature = hashlib.sha256()
    for record in records:
        seen += 1
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
            text_count += 1
        try:
            graph = build_fact_graph(record)
            if restore_fact_fields(graph) != record.fields:
                raise NativeComposeError("typed fact graph failed source conservation")
        except (FactGraphError, KeyError) as exc:
            raise NativeComposeError("invalid native source fact graph") from exc
        fact_nodes += graph.declared_size
        _update_source_signature(signature, record, graph)
        for node in graph.nodes:
            if (
                (node.key is not None and "\r" in node.key)
                or (isinstance(node.value, str) and "\r" in node.value)
            ):
                raise NativeComposeError("carriage return in native fact")
            if node.key is not None:
                available.add("fact_key")
            if node.kind == "str":
                available.add("fact_text")
            if node.kind in {"int", "bool"}:
                available.add("fact_int")
        # A full FactGraph no longer remains reachable across the entire
        # preflight. The CV director rebuilds at most one validated graph.
        del graph
    if not seen:
        raise NativeComposeError("cannot compose empty source graph")
    if text_count:
        available.add("form")
    return (
        NativeStats(
            records=seen,
            metadata_records=seen - text_count,
            text_records=text_count,
            source_atoms=seen,
            fact_nodes=fact_nodes,
        ),
        available,
        signature.hexdigest(),
    )


def _exact_field_values(a: FieldValue, b: FieldValue) -> bool:
    """Compare ordered nested source data, preserving exact scalar *types*.

    Ordinary Python/dataclass equality equates boolean False to integer 0,
    which is unacceptable for a typed source graph conservation proof.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, FieldObject):
        if not isinstance(b, FieldObject) or len(a.items) != len(b.items):
            return False
        return all(
            key_a == key_b and _exact_field_values(value_a, value_b)
            for (key_a, value_a), (key_b, value_b) in zip(a.items, b.items, strict=True)
        )
    if isinstance(a, FieldArray):
        if not isinstance(b, FieldArray) or len(a.items) != len(b.items):
            return False
        return all(
            _exact_field_values(value_a, value_b)
            for value_a, value_b in zip(a.items, b.items, strict=True)
        )
    return a == b


def _exact_native_records(
    expected: Iterable[NativeRecord], loaded: Iterable[NativeRecord],
) -> bool:
    """Strict source equality without making a second full FactGraph set."""
    actual = iter(loaded)
    for a in expected:
        try:
            b = next(actual)
        except StopIteration:
            return False
        if (
            a.source_file != b.source_file
            or type(a.ordinal) is not type(b.ordinal)
            or a.ordinal != b.ordinal
            or a.source_record_id != b.source_record_id
            or a.record_kind != b.record_kind
            or type(a.text) is not type(b.text)
            or a.text != b.text
            or not _exact_field_values(a.fields, b.fields)
        ):
            return False
    # Explicit extra next() forces final global Fabric integrity checks on
    # validating generators, rather than falsely returning success early.
    return next(actual, None) is None


def write_native_records(
    records: tuple[NativeRecord, ...],
    destination: Path,
    *,
    on_phase: Callable[[str], None] | None = None,
) -> NativeStats:
    """Preserve the public complete-record writer and its exact native F/E."""
    return write_native_record_factory(
        lambda: iter(records), destination, on_phase=on_phase,
    )


def write_native_record_factory(
    source_rows: Callable[[], Iterable[NativeRecord]],
    destination: Path,
    *,
    on_phase: Callable[[str], None] | None = None,
) -> NativeStats:
    """Build native TF from reproducibly replayable strictly typed source rows.

    Preflight consumes the first entire source pass *before* creating output.
    CV walks a second pass, and a third compares to the independently loaded
    native F/E. Does not stream Text-Fabric's own feature and edge maps.
    """
    if destination.exists() or destination.is_symlink():
        raise NativeComposeError("native TF destination already exists")
    stats, available, preflight_signature = _preflight(source_rows())
    if on_phase is not None:
        on_phase("preflight-complete")
    has_text = stats.text_records > 0
    ints = {"source_ordinal", "source_seq", "fact_count", "fact_id", "fact_position"}
    if "fact_int" in available:
        ints.add("fact_int")

    def director(cv: CV) -> None:
        replay_signature = hashlib.sha256()
        replay_rows = 0
        for seq, record in enumerate(source_rows(), 1):
            replay_rows = seq
            # Build only this source occurrence during CV.walk.
            graph = build_fact_graph(record)
            textual = record.text is not None
            if textual and (
                type(record.text) is not str
                or record.fields.require("text") != record.text
            ):
                raise NativeComposeError(
                    "source passage text differs from typed fact during TF replay"
                )
            if textual and "\r" in record.text:
                raise NativeComposeError("carriage return in replayed source passage text")
            _update_source_signature(replay_signature, record, graph)
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
        if replay_rows != stats.records or replay_signature.hexdigest() != preflight_signature:
            raise NativeComposeError("original source changed between preflight and TF replay")

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
    # The independent loaded source graph remains the postwrite validator;
    # public validate_native_records also retains its independent preflight.
    if not _exact_native_records(source_rows(), iter_native_records(destination)):
        raise NativeComposeError(
            f"generic composer conservation failure for {stats.records} source rows"
        )
    if on_phase is not None:
        on_phase("load-validated")
    return stats


def read_native_records(destination: Path) -> tuple[NativeRecord, ...]:
    """Return complete independently loaded native source records."""
    return tuple(iter_native_records(destination))


def iter_native_records(destination: Path) -> Iterator[NativeRecord]:
    """Validate actual native F/E and yield original typed source rows in order.

    Full proof requires EXHAUSTING the iterator: final global feature/edge
    placement, orphan and fabricated node checks run after its last yield.
    The writer and source verifier always exhaust it before reporting success.
    Native TF Fabric features remain loaded, not streamed from disk.
    """
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
    required_nodes = (mandatory - {"has_fact"}) | {"otype"}
    declared_nodes = set(discovered["nodes"])
    declared_edges = set(discovered["edges"])
    declared_configs = set(discovered["configs"])
    declared = declared_nodes | declared_edges
    # A selective Fabric.load cannot reveal fabricated features elsewhere on
    # disk: reject even valid native F/E/config files beyond the writer's
    # exact published surface, before reconstructing the source facts.
    if (
        not required_nodes.issubset(declared_nodes)
        or declared_nodes - required_nodes - optional
        or declared_edges != {"oslots", "has_fact"}
        or declared_configs != {"otext"}
    ):
        raise NativeComposeError("unexpected or missing native TF feature")
    api = fabric.load(
        " ".join(sorted(mandatory | (optional & declared))), silent="deep",
    )
    if not api:
        raise NativeComposeError("cannot load native typed source graph")
    # Native otype groups nodes by kind, not physical source order. Sorting
    # genuine root IDs by explicit source_seq preserves interleaved metadata,
    # primary and witness occurrences without accumulating all restored rows.
    roots = tuple(sorted(
        (*api.F.otype.s("passage"), *api.F.otype.s("metadataRecord")),
        key=lambda n: (
            api.F.source_seq.v(n)
            if type(api.F.source_seq.v(n)) is int else -1
        ),
    ))
    # The known otext file can carry an extra forged research-facing format
    # or unsupported section/structure declarations without changing any
    # source fact. Check those declarations independently of T.text equality.
    has_passages = bool(api.F.otype.s("passage"))
    otext = fabric.features["otext"].metaData
    expected_format = "{form}" if has_passages else "{source_record_id}"
    expected_sections = "passage" if has_passages else ""
    expected_section_features = "source_record_id" if has_passages else ""
    if (
        (has_passages and "form" not in declared_nodes)
        or (not has_passages and "form" in declared_nodes)
        or otext.get("fmt:text-orig-full") != expected_format
        or {key for key in otext if key.startswith("fmt:")} != {"fmt:text-orig-full"}
        or otext.get("sectionTypes", "") != expected_sections
        or otext.get("sectionFeatures", "") != expected_section_features
        or otext.get("structureTypes") not in (None, "")
        or otext.get("structureFeatures") not in (None, "")
    ):
        raise NativeComposeError("unexpected native otext rendering configuration")
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
    for expected_seq, root in enumerate(roots, 1):
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
            or type(seq) is not int or seq != expected_seq
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
        yield NativeRecord(
            filename, ordinal, record_id, record_kind, fields, source_text,
        )

    if used_atoms != atom_handles or used_facts != fact_handles:
        raise NativeComposeError("unaccounted native TF source or fact nodes")

    # A graph may preserve every authentic fact while attaching fabricated
    # values under ALREADY KNOWN feature names. Check the complete loaded F/E
    # surface, not only nodes reached through expected source reconstruction.
    root_handles = set(roots)
    source_anchors = {
        node for node in atom_handles
        if api.F.atom_kind.v(node) in {"source-row", "metadata-record"}
    }
    source_owners = root_handles | source_anchors
    permitted_placements = {
        "source_file": source_owners,
        "source_record_id": source_owners,
        "source_ordinal": root_handles,
        "source_seq": root_handles,
        "record_kind": root_handles,
        "fact_count": root_handles,
        "fact_digest": root_handles,
        "atom_kind": atom_handles,
        "form": atom_handles,
        "fact_kind": fact_handles,
        "fact_id": fact_handles,
        "fact_position": fact_handles,
        "fact_key": fact_handles,
        "fact_text": fact_handles,
        "fact_int": fact_handles,
    }
    for name, allowed_nodes in permitted_placements.items():
        if name in declared_nodes:
            for node, _ in getattr(api.F, name).items():
                if node not in allowed_nodes:
                    raise NativeComposeError(
                        f"unexpected native feature placement: {name} on {node}"
                    )
    for origin, targets in api.E.has_fact.items():
        if origin not in root_handles and origin not in fact_handles:
            raise NativeComposeError("unexpected native source-fact edge origin")
        if any(target not in fact_handles for target in targets):
            raise NativeComposeError("unexpected native source-fact edge target")

    # Contiguous global order is established while yielding, including
    # duplicate/missing/noninteger source_seq. All global checks ran above.


def validate_native_records(
    records: tuple[NativeRecord, ...], destination: Path,
) -> NativeStats:
    """Compare source records with independently reloaded native TF features."""
    stats, _, _ = _preflight(records)
    if not _exact_native_records(records, iter_native_records(destination)):
        raise NativeComposeError(
            f"generic composer conservation failure for {len(records)} source rows"
        )
    return stats
