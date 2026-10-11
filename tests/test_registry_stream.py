"""RED-first complete source-registry typed IR and null-fact conservation (#5)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from opengreek_tf.fact_graph import FactGraphError, build_fact_graph, restore_fact_fields
from opengreek_tf.record_stream import FieldArray, FieldObject
from opengreek_tf.registry_stream import RegistryError, RegistryRecord, iter_registry


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    path = tmp_path / "data/source_registry.json"
    path.parent.mkdir(parents=True)
    source = {
        "authors": {
            "a": {"name": "Ἀ", "aliases": {"wikidata": "Q1", "isni": "00001"}},
            "b": {"name": "", "aliases": {}},
        },
        "works": {
            "a.first": {
                "author": "a", "title": "ἄλφα  \n", "aliases": {
                    "cts": "urn:cts:greekLit:tlg0001.tlg001"
                },
                "default_edition": None, "best_source": "locked",
                "tags": ["genre:poetry", "genre:poetry", ""],
                "editions": {
                    "a.first.1": {
                        "name": "Edition", "provider": "test", "scheme": "",
                        "editor": "", "year": None, "source": "",
                        "servable": False, "license": "", "scheme_inferred": False,
                        "aliases": {"cts": "urn:cts:greekLit:tlg0001.tlg001.ed1"},
                    },
                    "a.first.2": {
                        "name": "", "provider": "test", "scheme": "page.line",
                        "editor": "", "year": -301, "source": "test",
                        "servable": True, "license": "PD", "scheme_inferred": True,
                        "aliases": {},
                    },
                },
            },
            "b.second": {
                "author": "b", "title": "β", "aliases": {"cts": ""},
                "default_edition": "b.second.ed", "best_source": "open_corpus",
                "tags": [], "editions": {
                    "b.second.ed": {
                        "name": "X", "provider": "test", "scheme": "", "editor": "",
                        "year": 0, "source": "", "servable": True, "license": "",
                        "scheme_inferred": False, "aliases": {},
                    }
                },
            },
        },
    }
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_registry_types_order_and_true_null_round_trip(registry: Path) -> None:
    records = tuple(iter_registry(registry))
    assert [(r.kind, r.slug, r.ordinal) for r in records] == [
        ("author", "a", 1), ("author", "b", 2),
        ("work", "a.first", 1), ("work", "b.second", 2),
    ]
    assert records[0].occurrence_key == ("data/source_registry.json#authors", 1)
    assert records[2].occurrence_key == ("data/source_registry.json#works", 1)
    assert records[0].occurrence_key != records[2].occurrence_key
    assert records[0].fields.get("name") == "Ἀ"
    work = records[2].fields
    assert work.get("default_edition") is None
    assert "default_edition" in dict(work.items)
    assert work.get("tags") == FieldArray(("genre:poetry", "genre:poetry", ""))
    editions = work.get("editions")
    assert isinstance(editions, FieldObject)
    first = editions.items[0][1]
    assert isinstance(first, FieldObject)
    assert "year" in dict(first.items) and first.get("year") is None
    for record in records:
        graph = build_fact_graph(record)
        assert restore_fact_fields(graph) == record.fields
    assert any(
        node.kind == "null" and node.value is None
        for node in build_fact_graph(records[2]).nodes
    )


def test_graph_rejects_wrong_null_kind_and_keeps_absent_distinct(registry: Path) -> None:
    record = tuple(iter_registry(registry))[2]
    graph = build_fact_graph(record)
    index = next(n.node_id for n in graph.nodes if n.kind == "null")
    changed = list(graph.nodes)
    changed[index] = replace(changed[index], value=0)
    with pytest.raises(FactGraphError):
        restore_fact_fields(replace(graph, nodes=tuple(changed)))
    assert dict(record.fields.items)["default_edition"] is None
    assert "default_edition" not in dict(tuple(iter_registry(registry))[0].fields.items)


@pytest.mark.parametrize(("path_parts", "bad_value"), [
    (("authors", "a", "aliases", "unknown"), "Q42"),
    (("authors", "a", "name"), 9),
    (("works", "a.first", "default_edition"), False),
    (("works", "a.first", "tags"), ["x", 1]),
    (("works", "a.first", "editions", "a.first.1", "year"), True),
    (("works", "a.first", "editions", "a.first.1", "servable"), 1),
    (("works", "a.first", "editions", "a.first.1", "aliases", "unexpected"), "urn:x"),
    (("works", "a.first", "editions", "a.first.1", "unknown"), "x"),
    (("works", "a.first", "author"), "missing-author"),
    (("works", "a.first", "default_edition"), "unknown-edition"),
])
def test_invalid_nested_registry_fails_closed(
    registry: Path, path_parts: tuple[str, ...], bad_value: object,
) -> None:
    path = registry / "data/source_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cursor = payload
    for key in path_parts[:-1]:
        cursor = cursor[key]
    cursor[path_parts[-1]] = bad_value
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RegistryError):
        tuple(iter_registry(registry))


def test_reject_duplicate_nested_key(registry: Path) -> None:
    path = registry / "data/source_registry.json"
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"name": "Ἀ"', '"name": "Ἀ", "name": "Β"', 1), encoding="utf-8")
    with pytest.raises(RegistryError, match="duplicate"):
        tuple(iter_registry(registry))


def test_reject_absent_null_and_empty_collection(registry: Path) -> None:
    path = registry / "data/source_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["works"]["a.first"]["default_edition"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RegistryError):
        tuple(iter_registry(registry))
    payload["works"] = {}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RegistryError):
        tuple(iter_registry(registry))


def test_reject_invalid_utf8_and_carriage_return(registry: Path) -> None:
    path = registry / "data/source_registry.json"
    path.write_bytes(b'{"authors": "\xff"}')
    with pytest.raises(RegistryError):
        tuple(iter_registry(registry))
    path.write_text('{"authors": {}, "works": {"w": {"title": "a\\rb"}}}', encoding="utf-8")
    with pytest.raises(RegistryError):
        tuple(iter_registry(registry))


def test_registry_emits_conservative_metadata_without_text_nodes(registry: Path) -> None:
    records = tuple(iter_registry(registry))
    assert all(isinstance(r, RegistryRecord) for r in records)
    assert all(r.kind in {"author", "work"} for r in records)
    assert all(r.relative_file == "data/source_registry.json" for r in records)
    assert not any("word" in dict(r.fields.items) for r in records)
