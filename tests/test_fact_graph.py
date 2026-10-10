"""RED-first contracts for reversible source facts (#33)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.fact_graph import (
    FactGraphError,
    build_fact_graph,
    decode_fact_graph,
    read_native_fact_graph,
    write_native_fact_probe,
)
from opengreek_tf.record_stream import FieldArray, FieldObject, ParsedRecord, parse_file


def _record(tmp_path: Path, family: str, values: dict[str, object]) -> ParsedRecord:
    part = {"primary": "corpus", "secondary": "corpus_secondary",
            "paratext": "paratext"}[family]
    path = tmp_path / "data" / part / "test.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False) + "\n", encoding="utf-8")
    return next(parse_file(tmp_path, f"data/{part}/test.jsonl"))


def _base(text: str = " α\tλόγος\n") -> dict[str, object]:
    return {"urn": "w", "edition": "e", "locus": "1", "source": "s",
            "license": "PD", "text": text}


def _complex(tmp_path: Path) -> ParsedRecord:
    return _record(tmp_path, "primary", {
        **_base("α\u0301 β\n"), "page": 0, "dfhg_flag": False,
        "corrections": ["first", "second"], "bekker": [],
        "text_lines": ["α\u0301 β", ""], "provenance": {
            "method": "ocr", "note": "", "consolidated_from": [],
            "dropped_gap": 0,
        }, "merged_read": {"guessed": 0, "substituted": 2, "with": ["x", "y"]},
    })


def test_exact_reconstruction_with_empty_containers_order_false_zero_and_nfd(
    tmp_path: Path,
) -> None:
    original = _complex(tmp_path)
    graph = build_fact_graph(original)
    assert graph.occurrence_key == original.occurrence_key
    assert graph.family == original.family
    assert decode_fact_graph(graph) == original.fields
    assert any(n.kind == "array" and n.value is None for n in graph.nodes)
    assert any(n.kind == "bool" and n.value is False for n in graph.nodes)
    assert any(n.kind == "int" and n.value == 0 for n in graph.nodes)
    assert any(n.kind == "str" and n.value == "α\u0301 β\n" for n in graph.nodes)


def test_empty_object_is_real_fact_not_missing_field(tmp_path: Path) -> None:
    row = _record(tmp_path, "primary", {**_base(), "provenance": {}})
    graph = build_fact_graph(row)
    assert decode_fact_graph(graph) == row.fields
    assert any(n.kind == "object" and n.parent_id is not None for n in graph.nodes)


@pytest.mark.parametrize("family,additional", [
    ("secondary", {"rank": "secondary", "secondary_reason": "alt",
                   "text_lines": ["α", "β"], "corrections": []}),
    ("secondary", {"displaced_by": {"date": "2026", "pass": "replace",
                                   "reason": "curated"}}),
    ("paratext", {"slug": "w", "page": "x", "lang": "la", "class": "apparatus",
                  "greek_remaining_in_this_row": 0}),
])
def test_all_source_families_roundtrip_exactly(
    tmp_path: Path, family: str, additional: dict[str, object],
) -> None:
    payload = _base()
    if family == "paratext":
        payload = {k: v for k, v in payload.items() if k not in {"urn", "locus"}}
    payload.update(additional)
    row = _record(tmp_path, family, payload)
    assert decode_fact_graph(build_fact_graph(row)) == row.fields


@pytest.mark.parametrize("damage", ["missing", "orphan", "duplicate", "reordered",
                                     "type-shift", "wrong-parent", "wrong-index"])
def test_independent_decoder_rejects_corrupt_structure(
    tmp_path: Path, damage: str,
) -> None:
    graph = build_fact_graph(_complex(tmp_path))
    nodes = list(graph.nodes)
    leaf_pos = next(i for i, n in enumerate(nodes) if n.kind == "str" and n.key == "urn")
    leaf = nodes[leaf_pos]
    if damage == "missing":
        nodes.pop(leaf_pos)
    elif damage == "orphan":
        nodes[leaf_pos] = replace(leaf, parent_id=999999)
    elif damage == "duplicate":
        nodes.append(leaf)
    elif damage == "reordered":
        nodes[leaf_pos] = replace(leaf, position=1000)
    elif damage == "type-shift":
        nodes[leaf_pos] = replace(leaf, kind="int")
    elif damage == "wrong-parent":
        nodes[leaf_pos] = replace(leaf, parent_id=leaf.id)
    else:
        element = next(i for i, n in enumerate(nodes) if n.index is not None)
        nodes[element] = replace(nodes[element], index=7)
    with pytest.raises(FactGraphError):
        decode_fact_graph(replace(graph, nodes=tuple(nodes)))


def test_native_tf_graph_retains_source_facts_and_diplomatic_order(
    tmp_path: Path,
) -> None:
    row = _complex(tmp_path)
    output = tmp_path / "native-tf"
    write_native_fact_probe(row, output)
    loaded = read_native_fact_graph(output)
    assert loaded.family == row.family
    assert loaded.occurrence_key == row.occurrence_key
    assert decode_fact_graph(loaded) == row.fields

    api = Fabric(locations=str(output), silent="deep").load(
        "atom_kind form fact_id fact_kind has_fact", silent="deep"
    )
    assert api
    assert len(api.F.otype.s("passage")) == 1
    assert len(api.F.otype.s("sourceFact")) == len(loaded.nodes)
    assert len([s for s in api.F.otype.s("atom")
                if api.F.atom_kind.v(s) == "source-row"]) == 1
    passage = api.F.otype.s("passage")[0]
    assert api.T.text(passage, fmt="text-orig-full") == row.text


def test_native_tf_refuses_cr_in_nested_string_before_output(
    tmp_path: Path,
) -> None:
    row = _record(tmp_path, "primary", {
        **_base(), "provenance": {"note": "alpha\rbeta"},
    })
    path = tmp_path / "forbidden"
    with pytest.raises(FactGraphError, match="CR|carriage return"):
        write_native_fact_probe(row, path)
    assert not path.exists()


def test_native_tf_never_overwrites_existing_source_material(
    tmp_path: Path,
) -> None:
    row = _complex(tmp_path)
    path = tmp_path / "existing"
    path.mkdir()
    with pytest.raises(FactGraphError, match="exist"):
        write_native_fact_probe(row, path)
