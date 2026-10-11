"""RED-first complete-registry adapter to reusable native TF composition (#13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import (
    NativeRecord,
    NativeStats,
    read_native_records,
    validate_native_records,
)
from opengreek_tf.registry_materializer import (
    iter_native_registry,
    materialize_registry,
)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    dest = tmp_path / "data" / "source_registry.json"
    dest.parent.mkdir(parents=True)
    body = {
        "authors": {
            "a": {"name": "Ἀ", "aliases": {"wikidata": "Q123"}},
            "b": {"name": "Β", "aliases": {}},
        },
        "works": {
            "a.first": {
                "author": "a",
                "title": "Περὶ Ἀ",
                "aliases": {"cts": "urn:cts:greekLit:tlg001.tlg001"},
                "default_edition": None,
                "best_source": "locked",
                "tags": ["genre:history", "genre:history"],
                "editions": {
                    "a.first.ed": {
                        "name": "", "provider": "test", "scheme": "", "editor": "",
                        "year": None, "source": "", "servable": False,
                        "license": "", "scheme_inferred": False, "aliases": {},
                    },
                },
            },
        },
    }
    dest.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_registry_adapter_keeps_complete_source_identity_and_order(
    source: Path,
) -> None:
    records = tuple(iter_native_registry(source))
    assert len(records) == 3
    assert all(isinstance(row, NativeRecord) for row in records)
    assert [(row.source_file, row.ordinal, row.source_record_id, row.record_kind)
            for row in records] == [
        ("data/source_registry.json#authors", 1, "a", "registry-author"),
        ("data/source_registry.json#authors", 2, "b", "registry-author"),
        ("data/source_registry.json#works", 1, "a.first", "registry-work"),
    ]
    assert all(record.text is None for record in records)
    assert records[2].fields.require("default_edition") is None


def test_complete_registry_writer_is_one_shared_native_tf_graph(
    source: Path,
) -> None:
    out = source / "native-registry"
    expected = tuple(iter_native_registry(source))
    stats = materialize_registry(source, out)
    assert stats == NativeStats(
        records=3, metadata_records=3, text_records=0,
        source_atoms=3, fact_nodes=36,
    )
    assert read_native_records(out) == expected
    assert validate_native_records(expected, out) == stats
    api = Fabric(locations=str(out), silent="deep").load(
        "source_file source_ordinal source_seq source_record_id record_kind "
        "fact_kind fact_key fact_id fact_position has_fact", silent="deep",
    )
    assert api
    assert len(api.F.otype.s("metadataRecord")) == 3
    assert not api.F.otype.s("passage")
    assert not api.F.otype.s("word")
    assert tuple(api.F.source_seq.v(n) for n in api.F.otype.s("metadataRecord")) == (
        1, 2, 3,
    )


def test_bad_late_registry_entry_never_leaves_partial_output(source: Path) -> None:
    path = source / "data/source_registry.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["works"]["a.first"]["author"] = "missing"
    path.write_text(json.dumps(raw), encoding="utf-8")
    out = source / "native-registry"
    with pytest.raises(ValueError, match="author"):
        materialize_registry(source, out)
    assert not out.exists()


def test_no_output_if_destination_preexists(source: Path) -> None:
    out = source / "native-registry"
    out.mkdir()
    with pytest.raises(ValueError, match="exist"):
        materialize_registry(source, out)
