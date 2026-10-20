"""RED-first end-user all-text-family native TF conversion contract (#8)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.cli import main
from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import read_native_records
from opengreek_tf.release import SUPPORTED_RELEASE
from opengreek_tf.source import SourceSnapshot
from opengreek_tf.text_materializer import select_all_text_files

FILES = (
    "data/corpus/p.jsonl",
    "data/corpus_secondary/s.jsonl",
    "data/paratext/a.jsonl",
)
EMPTY = "data/corpus_secondary/democritus.fragmenta.jsonl"


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "verified"
    data: tuple[list[dict[str, object]], ...] = (
        [
            {"urn": "p", "locus": "1", "edition": "e", "source": "tei",
             "license": "CC0", "text": "λόγος  ἀνήρ\n", "page": 0, "dfhg_flag": False},
            {"urn": "p", "locus": "2", "edition": "e", "source": "tei",
             "license": "CC0", "text": ""},
        ],
        [
            {"urn": "p", "locus": "1", "edition": "ocr", "source": "ocr",
             "license": "CC0", "text": "ἄλλος", "rank": "secondary",
             "secondary_reason": "replaced", "dfhg_flag": True},
        ],
        [
            {"slug": "p", "page": "2", "lang": "grc", "class": "apparatus",
             "edition": "e", "source": "tei", "license": "CC0",
             "text": "ὑπόμνημα", "greek_remaining_in_this_row": 0},
        ],
    )
    for name, rows in zip(FILES, data, strict=True):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows),
            encoding="utf-8",
        )
    (root / EMPTY).write_bytes(b"")
    return root


def _snapshot(root: Path) -> SourceSnapshot:
    return SourceSnapshot(root.resolve(), SUPPORTED_RELEASE.commit)


def test_selected_all_text_families_share_one_native_tf_graph(
    source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "native"
    argv = ["convert-texts", str(source)]
    for name in FILES:
        argv += ["--file", name]
    argv += ["--output", str(destination)]
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)) as verify:
        assert main(argv) == 0
    assert verify.call_count == 2
    report = json.loads(capsys.readouterr().out)
    assert report["revision"] == SUPPORTED_RELEASE.commit
    assert report["status"] == "validated-selected-texts"
    assert report["records"] == 4
    assert report["primary_passages"] == 2
    assert report["secondary_witnesses"] == 1
    assert report["paratext_records"] == 1
    assert report["source_files"] == list(FILES)
    assert report["empty_source_files"] == 0
    assert len(report["canonical_sha256"]) == 64
    assert len(report["original_source_sha256"]) == 64

    restored = read_native_records(destination)
    assert [x.source_file for x in restored] == [
        FILES[0], FILES[0], FILES[1], FILES[2],
    ]
    assert [x.record_kind for x in restored] == [
        "primary-passage", "primary-passage", "secondary-witness", "paratext-record",
    ]
    assert [x.fields.require("text") for x in restored] == [
        "λόγος  ἀνήρ\n", "", "ἄλλος", "ὑπόμνημα",
    ]
    assert restored[0].fields.require("dfhg_flag") is False
    assert restored[0].fields.require("page") == 0
    assert type(restored[0].fields.require("page")) is int
    assert type(restored[0].fields.require("dfhg_flag")) is bool
    api = Fabric(locations=str(destination), silent="deep").load(
        "source_record_id record_kind has_fact form", silent="deep",
    )
    assert api
    assert len(api.F.otype.s("passage")) == 2
    assert len(api.F.otype.s("metadataRecord")) == 2
    assert not api.F.otype.s("word")
    assert [api.T.text(p, fmt="text-orig-full") for p in
            api.F.otype.s("passage")] == ["λόγος  ἀνήρ\n", ""]
    assert validate_native_jsonl_sources(source, FILES, destination).records == 4


def test_all_original_source_inventory_accounts_for_empty_tracked_file(
    source: Path,
) -> None:
    with pytest.raises(ValueError, match="incomplete|expected"):
        select_all_text_files(source)
    inventory = select_all_text_files(source, expected_file_counts=(1, 2, 1))
    assert inventory.files == (
        FILES[0], EMPTY, FILES[1], FILES[2],
    )
    assert inventory.empty_files == frozenset({EMPTY})
    assert inventory.file_counts == (1, 2, 1)


def test_complete_mode_includes_empty_file_in_original_source_digest(
    source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from opengreek_tf.text_materializer import select_all_text_files as inventory

    out = tmp_path / "all"
    with (
        patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)),
        patch("opengreek_tf.cli.select_all_text_files",
              side_effect=lambda root: inventory(
                  root, expected_file_counts=(1, 2, 1))),
        patch("opengreek_tf.cli._PINNED_ALL_TEXT_ROWS", (2, 1, 1)),
    ):
        assert main(["convert-texts", str(source), "--all", "--output", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "validated-all-texts"
    assert report["source_file_count"] == 4
    assert report["empty_source_files"] == 1
    assert report["records"] == 4
    assert report["primary_passages"] == 2
    assert report["secondary_witnesses"] == 1
    assert report["paratext_records"] == 1
    selected = (FILES[0], EMPTY, FILES[1], FILES[2])
    checked = validate_native_jsonl_sources(
        source, selected, out, allow_empty_files=frozenset({EMPTY}),
    )
    assert checked.original_source_sha256 == report["original_source_sha256"]
    with pytest.raises(ValueError, match="empty"):
        validate_native_jsonl_sources(source, selected, out)


@pytest.mark.parametrize("bad", [
    ("data/corpus/p.jsonl", "data/corpus/p.jsonl"),
    ("data/corpus/../corpus/p.jsonl",),
    ("data/corpus_secondary/missing.jsonl",),
    ("data/unknown/x.jsonl",),
    (EMPTY,),
])
def test_selected_invalid_or_empty_source_rejects_before_output(
    source: Path, tmp_path: Path, bad: tuple[str, ...],
) -> None:
    out = tmp_path / "invalid"
    argv = ["convert-texts", str(source)]
    for name in bad:
        argv.extend(["--file", name])
    argv.extend(["--output", str(out)])
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)):
        with pytest.raises(ValueError):
            main(argv)
    assert not out.exists()


def test_all_source_inventory_detects_hardlink_duplicate_and_escapes(
    source: Path,
) -> None:
    alias = source / "data/corpus_secondary/alias.jsonl"
    try:
        os.link(source / FILES[1], alias)
    except OSError as exc:
        pytest.skip(f"hardlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="duplicate"):
        select_all_text_files(source, expected_file_counts=(1, 3, 1))


def test_all_mode_fails_closed_on_incomplete_source_and_existing_output(
    source: Path, tmp_path: Path,
) -> None:
    with patch("opengreek_tf.cli.verify_source", return_value=_snapshot(source)):
        out = tmp_path / "incomplete"
        with pytest.raises(ValueError, match="incomplete|expected"):
            main(["convert-texts", str(source), "--all", "--output", str(out)])
        assert not out.exists()
        with pytest.raises(ValueError, match="outside"):
            main(["convert-texts", str(source), "--file", FILES[0],
                  "--output", str(source / "native")])
        out.mkdir()
        with pytest.raises(ValueError, match="exist"):
            main(["convert-texts", str(source), "--file", FILES[0],
                  "--output", str(out)])


def test_all_texts_must_not_succeed_if_checkout_changes_after_conversion(
    source: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from opengreek_tf.source import SourceAcquisitionError

    with patch("opengreek_tf.cli.verify_source", side_effect=[
        _snapshot(source), SourceAcquisitionError("source dirty after conversion"),
    ]) as verify:
        argv = ["convert-texts", str(source), "--file", FILES[0],
                "--file", FILES[1], "--output", str(tmp_path / "generated")]
        with pytest.raises(SourceAcquisitionError, match="dirty"):
            main(argv)
    assert verify.call_count == 2
    assert capsys.readouterr().out == ""
