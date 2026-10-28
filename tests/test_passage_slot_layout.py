"""RED-first native TF passage-slot experiment (#78).

The default run-level atom model must remain byte-for-byte untouched. Compact
passage slots are opt-in, not an inferred word-level annotation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.cli import main
from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import (
    NativeComposeError,
    NativeRecord,
    read_native_records,
    write_native_records,
)
from opengreek_tf.record_stream import FieldArray, FieldObject
from opengreek_tf.release import SUPPORTED_RELEASE
from opengreek_tf.source import SourceSnapshot
from opengreek_tf.text_materializer import materialize_texts
from opengreek_tf.text_runs import segment_runs
from opengreek_tf.tf_integrity import native_tf_manifest

GREEK = "λόγος  ἀνήρ\t\nφιλοσοφία\\ καί;  ἄνθρωπος\n"


@pytest.fixture
def records() -> tuple[NativeRecord, ...]:
    return (
        NativeRecord(
            "data/corpus/a.jsonl", 1, "a:1", "primary-passage",
            FieldObject((
                ("text", GREEK),
                ("notes", FieldArray((None, False, 0, "", "λ", "λ"))),
            )),
            text=GREEK,
        ),
        NativeRecord(
            "data/corpus/a.jsonl", 2, "a:2", "primary-passage",
            FieldObject((("text", ""),)), text="",
        ),
        NativeRecord(
            "data/corpus_secondary/b.jsonl", 1, "a:1", "secondary-witness",
            FieldObject((
                ("text", "ἄλλος λόγος"), ("dfhg_flag", False),
                ("page", 0), ("extra", None),
            )),
        ),
        NativeRecord(
            "data/paratext/c.jsonl", 1, "c:1", "paratext-record",
            FieldObject((("text", "σημείωμα"), ("lang", "grc"))),
        ),
    )


def test_passage_slots_preserve_complete_unicode_and_native_facts(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    output = tmp_path / "passages"
    stats = write_native_records(records, output, slot_layout="passage")
    assert stats.records == 4
    assert stats.text_records == 2
    assert stats.metadata_records == 2
    assert read_native_records(output) == records
    fabric = Fabric(locations=str(output), silent="deep")
    api = fabric.load("source_file source_record_id atom_kind form has_fact", silent="deep")
    assert api
    assert fabric.features["otext"].metaData["slotLayout"] == "passage"
    passages = api.F.otype.s("passage")
    assert len(passages) == 2
    assert len(api.F.otype.s("metadataRecord")) == 2
    assert not api.F.otype.s("word")
    assert len(api.F.otype.s("atom")) == 5
    assert api.T.text(passages[0], fmt="text-orig-full") == GREEK
    assert api.T.text(passages[1], fmt="text-orig-full") == ""
    slots = tuple(api.E.oslots.s(passages[0]))
    assert len(slots) == 2
    assert api.F.atom_kind.v(slots[0]) == "text"
    assert api.F.form.v(slots[0]) == GREEK
    assert api.F.atom_kind.v(slots[1]) == "source-row"
    assert tuple(api.E.oslots.s(passages[1]))  # existing empty anchor
    assert all(api.F.otype.v(x) == "sourceFact" for x in api.F.otype.s("sourceFact"))


def test_old_run_layout_remains_identical_under_explicit_default_option(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    original = tmp_path / "original"
    named_default = tmp_path / "named-default"
    compact = tmp_path / "compact"
    write_native_records(records, original)
    write_native_records(records, named_default, slot_layout="runs")
    write_native_records(records, compact, slot_layout="passage")
    assert native_tf_manifest(original).canonical_sha256 == (
        native_tf_manifest(named_default).canonical_sha256
    )
    assert native_tf_manifest(original).canonical_sha256 != (
        native_tf_manifest(compact).canonical_sha256
    )
    fabric = Fabric(locations=str(original), silent="deep")
    api = fabric.load("atom_kind form", silent="deep")
    assert api
    assert "slotLayout" not in fabric.features["otext"].metaData
    assert len(tuple(api.E.oslots.s(api.F.otype.s("passage")[0]))) == (
        1 + len(tuple(segment_runs(GREEK)))
    )
    assert read_native_records(original) == read_native_records(named_default) == records


@pytest.mark.parametrize("forged", ["runs", "unknown", "RunS"])
def test_loaded_compact_layout_rejects_forged_config(
    tmp_path: Path, records: tuple[NativeRecord, ...], forged: str,
) -> None:
    out = tmp_path / "compact"
    write_native_records(records, out, slot_layout="passage")
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.explore(silent="deep")
    meta = dict(fabric.features["otext"].metaData)
    meta["slotLayout"] = forged
    assert fabric.save(metaData={"otext": meta}, silent="deep")
    with pytest.raises(NativeComposeError, match="slot|layout|text"):
        read_native_records(out)


def test_compact_mode_cannot_be_downgraded_to_legacy_runs(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "compact"
    write_native_records(records, out, slot_layout="passage")
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.explore(silent="deep")
    meta = dict(fabric.features["otext"].metaData)
    meta.pop("slotLayout")
    assert fabric.save(metaData={"otext": meta}, silent="deep")
    with pytest.raises(NativeComposeError, match="slot|run|layout|text"):
        read_native_records(out)


def test_old_run_layout_cannot_forge_compact_passage_claim(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "legacy"
    write_native_records(records, out)
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.explore(silent="deep")
    meta = dict(fabric.features["otext"].metaData)
    meta["slotLayout"] = "passage"
    assert fabric.save(metaData={"otext": meta}, silent="deep")
    with pytest.raises(NativeComposeError, match="slot|layout"):
        read_native_records(out)


def test_invalid_layout_rejected_before_writing(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "invalid"
    with pytest.raises(ValueError, match="slot|layout"):
        write_native_records(records, out, slot_layout="words")
    assert not out.exists()


def test_compact_mixed_original_jsonl_independent_native_conservation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "upstream"
    names = (
        "data/corpus/a.jsonl",
        "data/corpus_secondary/b.jsonl",
        "data/paratext/c.jsonl",
    )
    examples = (
        {"urn": "a", "locus": "1", "edition": "edition", "source": "tei",
         "license": "CC0", "text": GREEK, "page": 0, "dfhg_flag": False},
        {"urn": "a", "locus": "1", "edition": "ocr", "source": "ocr",
         "license": "CC0", "text": "λέξις", "rank": "secondary",
         "secondary_reason": "replaced"},
        {"slug": "a", "page": "1", "lang": "grc", "edition": "ed",
         "source": "tei", "license": "CC0", "text": "σημείωμα"},
    )
    for name, obj in zip(names, examples, strict=True):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8",
        )
    out = tmp_path / "native"
    stats = materialize_texts(root, names, out, slot_layout="passage")
    check = validate_native_jsonl_sources(root, names, out)
    assert stats.records == check.records == 3
    assert stats.fact_nodes == check.source_fact_nodes
    assert (check.primary_passages, check.secondary_witnesses,
            check.paratext_records) == (1, 1, 1)
    assert read_native_records(out)[0].text == GREEK


def test_user_cli_opt_in_declares_layout_and_preserves_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "upstream"
    path = root / "data/corpus/a.jsonl"
    path.parent.mkdir(parents=True)
    row = {"urn": "a", "locus": "1", "edition": "ed",
           "source": "tei", "license": "CC0", "text": GREEK}
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    snapshot = SourceSnapshot(root.resolve(), SUPPORTED_RELEASE.commit)
    with patch("opengreek_tf.cli.verify_source", return_value=snapshot):
        assert main(["convert-texts", str(root), "--file", "data/corpus/a.jsonl",
                     "--slot-layout", "passage", "--output", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["slot_layout"] == "passage"
    assert report["records"] == 1
    assert report["primary_passages"] == 1
    assert validate_native_jsonl_sources(
        root, ("data/corpus/a.jsonl",), out,
    ).records == 1


def test_user_cli_rejects_fake_layout_without_output(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["convert-texts", str(tmp_path), "--all", "--slot-layout", "word",
              "--output", str(tmp_path / "generated")])
    assert not (tmp_path / "generated").exists()


def test_bare_compact_layout_declaration_is_not_silent_legacy_fallback(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    """A present-but-empty otext declaration must not mean legacy runs."""
    out = tmp_path / "compact"
    write_native_records(records, out, slot_layout="passage")
    config = out / "otext.tf"
    original = config.read_text(encoding="utf-8")
    assert "@slotLayout=passage\n" in original
    config.write_text(
        original.replace("@slotLayout=passage\n", "@slotLayout\n"),
        encoding="utf-8",
    )
    with pytest.raises(NativeComposeError, match="slot|layout"):
        read_native_records(out)
