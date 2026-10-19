"""RED-first installed CLI → pinned-source-style native TF conversion (#6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.cli import main
from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.release import SUPPORTED_RELEASE
from opengreek_tf.source import SourceAcquisitionError, SourceSnapshot


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "verified source"
    corpus = root / "data" / "corpus"
    corpus.mkdir(parents=True)
    examples = (
        ("a.jsonl", [
            {"urn": "alpha", "edition": "first", "locus": "I.1",
             "source": "tei", "license": "CC BY-SA", "text": "λόγος  ἀνήρ\n",
             "corrections": ["", "ῥ", "ῥ"], "dfhg_flag": False, "page": 0},
            {"urn": "alpha", "edition": "first", "locus": "I.2",
             "source": "tei", "license": "CC BY-SA", "text": ""},
        ]),
        ("b.jsonl", [
            {"urn": "beta", "edition": "other", "locus": "2",
             "source": "ocr", "license": "PD", "text": "βῆτα\tἄλφα"},
        ]),
    )
    for filename, rows in examples:
        (corpus / filename).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    return root


def _snapshot(source: Path) -> SourceSnapshot:
    return SourceSnapshot(path=source.resolve(), revision=SUPPORTED_RELEASE.commit)


def _args(source: Path, destination: Path) -> list[str]:
    return [
        "convert-primary", str(source),
        "--file", "data/corpus/b.jsonl",
        "--file", "data/corpus/a.jsonl",
        "--output", str(destination),
    ]


def test_public_primary_cli_reloads_all_original_greek_and_typed_facts(
    source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "generated"
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)) as verify:
        assert main(_args(source, output)) == 0
    verify.assert_called_once_with(str(source), identity=SUPPORTED_RELEASE)
    result = json.loads(capsys.readouterr().out)
    assert result["revision"] == SUPPORTED_RELEASE.commit
    assert result["source_files"] == [
        "data/corpus/b.jsonl", "data/corpus/a.jsonl",
    ]
    assert result["records"] == result["primary_passages"] == 3
    assert result["canonical_sha256"] and len(result["canonical_sha256"]) == 64
    assert len(result["original_source_sha256"]) == 64
    assert result["status"] == "validated-selected-primary"
    assert result["destination"] == str(output.resolve())

    api = Fabric(locations=str(output), silent="deep").load(
        "source_file source_ordinal source_record_id record_kind form has_fact",
        silent="deep",
    )
    assert api
    passages = api.F.otype.s("passage")
    assert len(passages) == 3
    assert not api.F.otype.s("word")
    assert not api.F.otype.s("metadataRecord")
    assert [api.T.text(p, fmt="text-orig-full") for p in passages] == [
        "βῆτα\tἄλφα", "λόγος  ἀνήρ\n", "",
    ]
    assert [api.F.source_record_id.v(p) for p in passages] == [
        "data/corpus/b.jsonl:1", "data/corpus/a.jsonl:1",
        "data/corpus/a.jsonl:2",
    ]
    checked = validate_native_jsonl_sources(
        source, ("data/corpus/b.jsonl", "data/corpus/a.jsonl"), output,
    )
    assert checked.records == 3 and checked.source_fact_nodes > 20


@pytest.mark.parametrize("selection", [
    ["--file", "data/corpus/a.jsonl", "--file", "data/corpus/a.jsonl"],
    ["--file", "data/corpus_secondary/a.jsonl"],
    ["--file", "data/corpus/../corpus/a.jsonl"],
])
def test_public_primary_cli_rejects_invalid_selection_without_output(
    source: Path, tmp_path: Path, selection: list[str],
) -> None:
    output = tmp_path / "invalid"
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)):
        with pytest.raises(ValueError):
            main(["convert-primary", str(source), *selection, "--output", str(output)])
    assert not output.exists()


def test_public_primary_cli_rejects_checkout_output_and_existing_target(
    source: Path, tmp_path: Path,
) -> None:
    inside = source / "generated"
    existing = tmp_path / "already"
    existing.mkdir()
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)):
        with pytest.raises(ValueError, match="outside"):
            main(_args(source, inside))
        with pytest.raises(ValueError, match="exist"):
            main(_args(source, existing))
    assert not inside.exists()
    assert list(existing.iterdir()) == []


def test_public_primary_cli_fails_closed_before_writing_when_source_unverified(
    source: Path, tmp_path: Path,
) -> None:
    output = tmp_path / "unauthorized"
    with patch(
        "opengreek_tf.cli.verify_source",
        side_effect=SourceAcquisitionError("dirty source checkout"),
    ):
        with pytest.raises(SourceAcquisitionError, match="dirty"):
            main(_args(source, output))
    assert not output.exists()


def test_public_primary_cli_requires_explicit_file_selection_and_output(
    source: Path,
) -> None:
    with pytest.raises(SystemExit) as missing_files:
        main(["convert-primary", str(source), "--output", "somewhere"])
    assert missing_files.value.code == 2
    with pytest.raises(SystemExit) as missing_output:
        main(["convert-primary", str(source), "--file", "data/corpus/a.jsonl"])
    assert missing_output.value.code == 2


def test_public_primary_cli_rechecks_pinned_checkout_before_reporting_success(
    source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Independent TF equality must not certify a checkout dirtied during conversion."""
    output = tmp_path / "converted-before-mutation-is-detected"
    with patch(
        "opengreek_tf.cli.verify_source",
        side_effect=[_snapshot(source), SourceAcquisitionError("checkout became dirty")],
    ) as verify:
        with pytest.raises(SourceAcquisitionError, match="dirty"):
            main(_args(source, output))
    assert verify.call_count == 2
    assert capsys.readouterr().out == ""
