"""RED-first public November source conversion / typed reader tests (#88).

The layouts are small authentic-source-shape excerpts from the immutable
corpus-2026-11-17 release. Preserve all original JSON types and physical IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from opengreek_tf.cli import main
from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import NativeComposeError, read_native_records
from opengreek_tf.record_stream import FieldArray, FieldObject, RecordParseError, iter_family, parse_file
from opengreek_tf.release import NOVEMBER_RELEASE
from opengreek_tf.source import SourceSnapshot

PRIMARY = "data/corpus/abas.fragmenta.jsonl"
SECONDARY = "data/corpus_secondary/nicomachus-mathematics.excerpta.jsonl"
PARATEXT = "data/paratext/gutenberg/66595.jsonl"


def _file(root: Path, name: str, *rows: dict[str, object]) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source(root: Path) -> None:
    _file(root, PRIMARY, {
        "urn": "abas.fragmenta", "edition": "dfhg", "locus": "4.1",
        "source": "dfhg", "license": "CC-BY-SA-4.0",
        "text": "Ἡ γυνὴ τὸ ὄνομα", "page": 278,
        "work": "ΙΣΤΟΡΙΚΑ ΥΠΟΜΝΗΜΑΤΑ", "witness": "Photios",
    })
    _file(root, SECONDARY, {
        "urn": "nicomachus-mathematics.excerpta",
        "edition": "qwen36-meibom-1652-legacy",
        "locus": "aristides_quintilianus_meibom_0307.1",
        "source": "ocr", "license": "PD", "text": "ΝΙΚΟΜΑΧΟΥ ΓΕΡΑΣΣΗΝΟΥ,",
        "source_page": {
            "work": "nicomachus-mathematics.excerpta",
            "scan_page": 307, "printed_page": 29, "book": None,
            "greek_column": "left", "duplicate_scan": False,
        },
        "evidence": "data/source_layouts/meibom-1652.json",
        "cts": "urn:cts:greekLit:tlg0358.tlg004",
    })
    _file(root, PARATEXT, {
        "locus": "apparatus.1", "text": "l, 7. ἅμα B. μοι or ἐμοὶ.",
        "source": "gutenberg",
        "source_sha256": "33762f8e07002c8f734e592a62100be482c805b14a40df0ba125c490d2fb069",
    })


def test_november_reader_keeps_new_meibom_secondary_semantics(
    tmp_path: Path,
) -> None:
    _source(tmp_path)
    row = next(parse_file(tmp_path, SECONDARY, identity=NOVEMBER_RELEASE))
    assert row.family == "secondary"
    assert row.occurrence_key == (SECONDARY, 1)
    assert row.text == "ΝΙΚΟΜΑΧΟΥ ΓΕΡΑΣΣΗΝΟΥ,"
    page = row.fields.require("source_page")
    assert isinstance(page, FieldObject)
    assert page.items == (
        ("work", "nicomachus-mathematics.excerpta"),
        ("scan_page", 307),
        ("printed_page", 29),
        ("book", None),
        ("greek_column", "left"),
        ("duplicate_scan", False),
    )
    assert row.fields.require("evidence") == "data/source_layouts/meibom-1652.json"
    with pytest.raises(RecordParseError):
        list(parse_file(tmp_path, SECONDARY))


def test_november_nested_gutenberg_source_exact_text_and_physical_path(
    tmp_path: Path,
) -> None:
    _source(tmp_path)
    rows = list(parse_file(tmp_path, PARATEXT, identity=NOVEMBER_RELEASE))
    assert len(rows) == 1
    assert rows[0].occurrence_key == (PARATEXT, 1)
    assert rows[0].fields.require("source_sha256").startswith("33762")
    assert rows[0].text == "l, 7. ἅμα B. μοι or ἐμοὶ."
    assert [r.relative_file for r in iter_family(
        tmp_path, "paratext", identity=NOVEMBER_RELEASE,
    )] == [PARATEXT]
    with pytest.raises(RecordParseError):
        list(parse_file(tmp_path, PARATEXT))


def test_november_gutenberg_parses_raw_cr_without_normalizing_it(
    tmp_path: Path,
) -> None:
    row = {"locus": "note.1", "source": "gutenberg",
           "source_sha256": "a" * 64, "text": "τοῦ\r\nἄλλου"}
    _file(tmp_path, "data/paratext/gutenberg/32549.jsonl", row)
    parsed = next(parse_file(
        tmp_path, "data/paratext/gutenberg/32549.jsonl", identity=NOVEMBER_RELEASE,
    ))
    assert parsed.fields.require("text") == "τοῦ\r\nἄλλου"


@pytest.mark.parametrize("bad_path", [
    "data/paratext/../corpus/abas.fragmenta.jsonl",
    "data/paratext/gutenberg/../gutenberg/66595.jsonl",
    "data/paratext/gutenberg/extra/note.jsonl",
    "data/corpus/extra/work.jsonl",
])
def test_november_nested_path_never_allows_escapes_or_arbitrary_depth(
    tmp_path: Path, bad_path: str,
) -> None:
    _source(tmp_path)
    with pytest.raises(RecordParseError):
        list(parse_file(tmp_path, bad_path, identity=NOVEMBER_RELEASE))


@pytest.mark.parametrize(("change", "message"), [
    (lambda obj: obj["source_page"].__setitem__("scan_page", True), "scan_page"),
    (lambda obj: obj["source_page"].__setitem__("duplicate_scan", 0), "duplicate_scan"),
    (lambda obj: obj["source_page"].__setitem__("new_key", "fake"), "new_key"),
    (lambda obj: obj.pop("source_page"), "source_page"),
    (lambda obj: obj.pop("evidence"), "evidence"),
])
def test_november_source_page_variant_rejects_forged_or_incomplete_facts(
    tmp_path: Path, change: object, message: str,
) -> None:
    _source(tmp_path)
    path = tmp_path / SECONDARY
    row = json.loads(path.read_text(encoding="utf-8"))
    assert callable(change)
    change(row)
    _file(tmp_path, SECONDARY, row)
    with pytest.raises(RecordParseError, match=message):
        list(parse_file(tmp_path, SECONDARY, identity=NOVEMBER_RELEASE))


def test_november_selected_originals_become_one_conserved_native_tf_graph(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "source"
    _source(root)
    output = tmp_path / "native"
    argv = ["convert-texts", str(root), "--release", NOVEMBER_RELEASE.tag]
    for file in (PRIMARY, SECONDARY, PARATEXT):
        argv += ["--file", file]
    argv += ["--output", str(output)]
    snapshot = SourceSnapshot(root.resolve(), NOVEMBER_RELEASE.commit)
    with patch("opengreek_tf.cli.verify_source", return_value=snapshot) as verify:
        assert main(argv) == 0
    assert verify.call_count == 2
    result = json.loads(capsys.readouterr().out)
    assert result["revision"] == NOVEMBER_RELEASE.commit
    assert result["records"] == 3
    assert (result["primary_passages"], result["secondary_witnesses"],
            result["paratext_records"]) == (1, 1, 1)
    rows = read_native_records(output)
    assert [row.source_file for row in rows] == [PRIMARY, SECONDARY, PARATEXT]
    assert [row.record_kind for row in rows] == [
        "primary-passage", "secondary-witness", "paratext-record",
    ]
    assert rows[1].fields.require("source_page") == FieldObject((
        ("work", "nicomachus-mathematics.excerpta"),
        ("scan_page", 307),
        ("printed_page", 29),
        ("book", None),
        ("greek_column", "left"),
        ("duplicate_scan", False),
    ))
    assert rows[2].fields.require("source_sha256").startswith("33762")
    report = validate_native_jsonl_sources(
        root, (PRIMARY, SECONDARY, PARATEXT), output,
        identity=NOVEMBER_RELEASE,
    )
    assert report.records == 3
    assert report.original_source_sha256 == result["original_source_sha256"]


def test_november_all_mode_remains_blocked_before_writing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    _source(root)
    output = tmp_path / "unreleased"
    snapshot = SourceSnapshot(root.resolve(), NOVEMBER_RELEASE.commit)
    with patch("opengreek_tf.cli.verify_source", return_value=snapshot):
        with pytest.raises(ValueError, match="November|not yet|unsupported"):
            main(["convert-texts", str(root), "--release", NOVEMBER_RELEASE.tag,
                  "--all", "--output", str(output)])
    assert not output.exists()


def test_november_native_writer_rejects_actual_cr_instead_of_losing_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    _file(root, "data/paratext/gutenberg/32549.jsonl", {
        "locus": "note.1", "text": "τοῦ\r\nἄλλου",
        "source": "gutenberg", "source_sha256": "a" * 64,
    })
    output = tmp_path / "unsafe"
    snapshot = SourceSnapshot(root.resolve(), NOVEMBER_RELEASE.commit)
    with patch("opengreek_tf.cli.verify_source", return_value=snapshot):
        with pytest.raises(NativeComposeError, match="carriage return"):
            main(["convert-texts", str(root), "--release", NOVEMBER_RELEASE.tag,
                  "--file", "data/paratext/gutenberg/32549.jsonl",
                  "--output", str(output)])
    assert not output.exists()
