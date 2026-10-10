"""RED-first fact graph proof: all native source facts stay typed and ordered."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.fact_graph import (
    FactGraphError,
    build_fact_graph,
    restore_fact_fields,
)
from opengreek_tf.fact_probe import read_fact_probe, write_fact_probe
from opengreek_tf.record_stream import FieldArray, FieldObject, ParsedRecord


def _row(fields: FieldObject, family: str = "primary") -> ParsedRecord:
    return ParsedRecord(
        family=family,  # type: ignore[arg-type]
        relative_file=f"data/{'paratext' if family == 'paratext' else 'corpus'}/a.jsonl",
        ordinal=1043,
        fields=fields,
    )


@pytest.fixture
def representative() -> FieldObject:
    return FieldObject(
        (
            ("urn", "test-work"),
            ("locus", "2.1"),
            ("text", "α\u0301  λόγος\n"),
            ("page", 0),
            ("dfhg_flag", False),
            ("provenance", FieldObject(
                (("method", "OCR"), ("note", ""), ("dropped_gap", 0),
                 ("consolidated_from", FieldArray(("w1", "w1", "w2"))))
            )),
            ("corrections", FieldArray(("", "λόγος", "λόγος"))),
            ("text_lines", FieldArray(("α", "", "λόγος"))),
            ("bekker", FieldArray(())),
            ("merged_read", FieldObject(
                (("guessed", 0), ("substituted", 0), ("with", FieldArray(())))
            )),
        )
    )


def test_canonical_fact_graph_is_source_exact_deterministic(
    representative: FieldObject,
) -> None:
    record = _row(representative)
    graph = build_fact_graph(record)
    assert graph == build_fact_graph(record)
    assert graph.occurrence_key == (record.relative_file, 1043)
    assert graph.nodes[0].kind == "object"
    assert graph.nodes[0].parent_id is None
    assert tuple(node.node_id for node in graph.nodes) == tuple(range(len(graph.nodes)))
    assert restore_fact_fields(graph) == representative
    assert any(node.kind == "bool" and node.value is False for node in graph.nodes)
    assert any(node.kind == "int" and node.value == 0 for node in graph.nodes)
    assert any(node.kind == "array" for node in graph.nodes)


@pytest.mark.parametrize("family", ["primary", "secondary", "paratext"])
def test_field_graph_supports_every_text_family_without_locus_assumptions(
    family: str, representative: FieldObject
) -> None:
    record = _row(representative, family=family)
    assert restore_fact_fields(build_fact_graph(record)) == representative


@pytest.mark.parametrize(
    "value",
    [
        FieldObject(()), FieldArray(()),
        FieldArray((FieldObject(()), FieldArray(()))),
        FieldObject((("nested", FieldArray((False, 0, "0", True))),)),
    ],
)
def test_graph_retains_empty_containers_and_scalar_type_and_order(
    value: FieldObject | FieldArray,
) -> None:
    fields = FieldObject((("container", value), ("empty", "")))
    assert restore_fact_fields(build_fact_graph(_row(fields))) == fields


def test_corrupted_missing_node_is_detected(representative: FieldObject) -> None:
    graph = build_fact_graph(_row(representative))
    with pytest.raises(FactGraphError):
        restore_fact_fields(replace(graph, nodes=graph.nodes[:-1]))


def test_corrupted_duplicate_child_order_is_detected(
    representative: FieldObject,
) -> None:
    graph = build_fact_graph(_row(representative))
    a = graph.nodes[1]
    b = graph.nodes[2]
    assert a.parent_id == b.parent_id
    corrupted = list(graph.nodes)
    corrupted[2] = replace(b, position=a.position)
    with pytest.raises(FactGraphError):
        restore_fact_fields(replace(graph, nodes=tuple(corrupted)))


def test_corrupted_value_type_is_detected(representative: FieldObject) -> None:
    graph = build_fact_graph(_row(representative))
    idx = next(n.node_id for n in graph.nodes if n.kind == "bool")
    corrupted = list(graph.nodes)
    corrupted[idx] = replace(corrupted[idx], value=0)
    with pytest.raises(FactGraphError):
        restore_fact_fields(replace(graph, nodes=tuple(corrupted)))


def test_real_native_tf_graph_restores_every_nested_fact(
    tmp_path: Path, representative: FieldObject
) -> None:
    record = _row(representative)
    dest = tmp_path / "native"
    write_fact_probe(record, dest)
    api = Fabric(locations=str(dest), silent="deep").load(
        "fact_kind fact_key fact_position fact_id fact_text fact_int "
        "source_file source_ordinal has_fact", silent="deep"
    )
    assert api
    assert len(api.F.otype.s("passage")) == 1
    assert len(api.F.otype.s("sourceFact")) == len(build_fact_graph(record).nodes)
    graph = read_fact_probe(dest)
    assert graph.occurrence_key == record.occurrence_key
    assert restore_fact_fields(graph) == record.fields


def test_native_probe_rejects_unroundtrippable_cr_without_output(tmp_path: Path) -> None:
    record = _row(FieldObject((("text", "α\rβ"), ("urn", "test-work"))))
    dest = tmp_path / "native"
    with pytest.raises(FactGraphError, match="carriage return"):
        write_fact_probe(record, dest)
    assert not dest.exists()


def test_native_probe_rejects_existing_destination_before_output(
    tmp_path: Path, representative: FieldObject
) -> None:
    record = _row(representative)
    dest = tmp_path / "native"
    dest.mkdir()
    with pytest.raises(FactGraphError, match="exists"):
        write_fact_probe(record, dest)


def test_graph_declares_count_and_source_value_digest(
    representative: FieldObject,
) -> None:
    graph = build_fact_graph(_row(representative))
    assert graph.declared_size == len(graph.nodes)
    assert len(graph.digest) == 64
    changed = list(graph.nodes)
    index = next(n.node_id for n in changed if n.kind == "str" and n.value == "2.1")
    changed[index] = replace(changed[index], value="2.2")
    with pytest.raises(FactGraphError, match="digest"):
        restore_fact_fields(replace(graph, nodes=tuple(changed)))


def test_graph_detects_valid_permutation_of_original_object_order(
    representative: FieldObject,
) -> None:
    graph = build_fact_graph(_row(representative))
    changed = list(graph.nodes)
    first, second = changed[1], changed[2]
    assert first.parent_id == second.parent_id
    changed[1] = replace(first, position=second.position)
    changed[2] = replace(second, position=first.position)
    with pytest.raises(FactGraphError, match="digest"):
        restore_fact_fields(replace(graph, nodes=tuple(changed)))
