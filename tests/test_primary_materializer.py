"""RED-first primary Greek JSONL to generic native TF adapter (#6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import (
    NativeRecord,
    read_native_records,
    validate_native_records,
)
from opengreek_tf.primary_materializer import (
    iter_native_primary,
    materialize_primary,
)
from opengreek_tf.record_stream import FieldArray


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source with spaces"
    directory = root / "data" / "corpus"
    directory.mkdir(parents=True)
    a = [
        {"urn": "work.a", "edition": "ed-a", "locus": "1",
         "source": "tei", "license": "CC0", "text": "ἄλφα  βῆτα\n"},
        {"urn": "work.a", "edition": "ed-a", "locus": "2",
         "source": "tei", "license": "CC0", "text": "",
         "text_lines": ["", "ἄλφα"], "dfhg_flag": False},
    ]
    b = [
        {"urn": "work.b", "edition": "ed-b", "locus": "1",
         "source": "glaux", "license": "CC-BY", "text": "λόγος\tἀνήρ",
         "corrections": ["", "ῥ", "ῥ"], "page": 0},
    ]
    for filename, data in (("a.jsonl", a), ("b.jsonl", b)):
        (directory / filename).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in data),
            encoding="utf-8",
        )
    return root


def test_primary_adapter_preserves_user_file_order_and_physical_identity(
    source: Path,
) -> None:
    rows = tuple(iter_native_primary(
        source, ("data/corpus/b.jsonl", "data/corpus/a.jsonl"),
    ))
    assert len(rows) == 3
    assert all(isinstance(row, NativeRecord) for row in rows)
    assert [
        (row.source_file, row.ordinal, row.source_record_id, row.record_kind)
        for row in rows
    ] == [
        ("data/corpus/b.jsonl", 1, "data/corpus/b.jsonl:1", "primary-passage"),
        ("data/corpus/a.jsonl", 1, "data/corpus/a.jsonl:1", "primary-passage"),
        ("data/corpus/a.jsonl", 2, "data/corpus/a.jsonl:2", "primary-passage"),
    ]
    assert rows[0].text == "λόγος\tἀνήρ"
    assert rows[2].text == ""
    assert isinstance(rows[0].fields.require("corrections"), FieldArray)
    assert rows[2].fields.require("dfhg_flag") is False


def test_primary_writer_and_independent_fabric_preserve_original_text(
    source: Path, tmp_path: Path,
) -> None:
    paths = ("data/corpus/a.jsonl", "data/corpus/b.jsonl")
    expected = tuple(iter_native_primary(source, paths))
    out = tmp_path / "primary"
    stats = materialize_primary(source, paths, out)
    assert stats.records == stats.text_records == stats.source_atoms == 3
    assert stats.metadata_records == 0
    assert stats.fact_nodes > 20
    assert read_native_records(out) == expected
    assert validate_native_records(expected, out) == stats
    api = Fabric(locations=str(out), silent="deep").load(
        "source_file source_seq source_record_id source_ordinal atom_kind "
        "form fact_kind fact_int has_fact", silent="deep",
    )
    assert api
    assert not api.F.otype.s("word")
    assert not api.F.otype.s("metadataRecord")
    passages = api.F.otype.s("passage")
    assert len(passages) == 3
    # Count genuine layout run slots + exactly one source anchor per record.
    assert len(api.F.otype.s("atom")) == 10
    assert [api.F.source_record_id.v(n) for n in passages] == [
        row.source_record_id for row in expected
    ]
    assert [
        api.T.text(n, fmt="text-orig-full") for n in passages
    ] == [row.text for row in expected]


@pytest.mark.parametrize("paths", [
    (),
    ("data/corpus/a.jsonl", "data/corpus/a.jsonl"),
    ("data/corpus_secondary/a.jsonl",),
    ("data/corpus/../corpus/a.jsonl",),
])
def test_invalid_file_selection_fails_before_output(
    source: Path, tmp_path: Path,
    paths: tuple[str, ...],
) -> None:
    out = tmp_path / "bad"
    with pytest.raises(ValueError):
        materialize_primary(source, paths, out)
    assert not out.exists()


def test_malformed_late_source_row_fails_without_partial_tf(
    source: Path, tmp_path: Path,
) -> None:
    path = source / "data/corpus/b.jsonl"
    data = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    data.pop("license")
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "bad-late"
    with pytest.raises(ValueError, match="license"):
        materialize_primary(
            source, ("data/corpus/a.jsonl", "data/corpus/b.jsonl"), out,
        )
    assert not out.exists()


def test_identical_input_has_deterministic_native_feature_contents(
    source: Path, tmp_path: Path,
) -> None:
    from opengreek_tf.tf_integrity import native_tf_manifest

    files = ("data/corpus/b.jsonl", "data/corpus/a.jsonl")
    p = tmp_path / "first"
    q = tmp_path / "second"
    materialize_primary(source, files, p)
    materialize_primary(source, files, q)
    assert native_tf_manifest(p).canonical_sha256 == (
        native_tf_manifest(q).canonical_sha256
    )


def test_reject_resolved_duplicate_primary_files_through_symlink_alias(
    source: Path, tmp_path: Path,
) -> None:
    original = source / "data/corpus/a.jsonl"
    alias = source / "data/corpus/alias.jsonl"
    try:
        alias.symlink_to(original)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink setup unavailable on this platform: {exc}")
    out = tmp_path / "duplicate-alias"
    with pytest.raises(ValueError, match="duplicate"):
        materialize_primary(
            source, ("data/corpus/a.jsonl", "data/corpus/alias.jsonl"), out,
        )
    assert not out.exists()
