"""RED-first cross-family writer-independent original JSONL conservation (#9)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opengreek_tf.jsonl_conservation import (
    JsonlConservationError,
    validate_native_jsonl_sources,
)
from opengreek_tf.native_composer import write_native_records
from opengreek_tf.primary_materializer import iter_native_primary
from opengreek_tf.unaligned_materializer import iter_native_unaligned


FILES = (
    "data/corpus/p.jsonl",
    "data/corpus_secondary/s.jsonl",
    "data/paratext/a.jsonl",
)


@pytest.fixture
def corpus(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "original source with spaces"
    primary = [
        {"urn": "p", "edition": "ed", "locus": "1", "source": "tei",
         "license": "PD", "text": "λόγος  ἀνήρ\n", "dfhg_flag": False},
        {"urn": "p", "edition": "ed", "locus": "2", "source": "tei",
         "license": "PD", "text": "", "page": 0},
    ]
    secondary = [
        {"urn": "p", "edition": "alt", "locus": "1", "source": "ocr",
         "license": "CC0", "text": "ἕτερον", "rank": "secondary",
         "secondary_reason": "replaced", "dfhg_flag": True},
    ]
    paratext = [
        {"slug": "p", "page": "1", "lang": "grc", "class": "apparatus",
         "source": "tei", "edition": "ed", "license": "PD",
         "text": "ὑπόμνημα", "greek_remaining_in_this_row": 0},
    ]
    for name, original in zip(FILES, (primary, secondary, paratext), strict=True):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in original),
            encoding="utf-8",
        )
    out = tmp_path / "native"
    records = (
        *iter_native_primary(root, FILES[:1]),
        *iter_native_unaligned(root, FILES[1:]),
    )
    write_native_records(tuple(records), out)
    return root, out


def test_mixed_original_jsonl_and_loaded_native_tf_are_exact(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    report = validate_native_jsonl_sources(root, FILES, out)
    assert report.records == 4
    assert report.primary_passages == 2
    assert report.secondary_witnesses == 1
    assert report.paratext_records == 1
    assert report.source_files == 3
    assert report.source_fact_nodes > 20
    assert report.source_unicode_codepoints == len("λόγος  ἀνήρ\n") + len("ἕτερον") + len("ὑπόμνημα")
    assert len(report.original_source_sha256) == 64


@pytest.mark.parametrize(("file_index", "field", "value"), [
    (0, "dfhg_flag", 0),  # False == 0 under Python equality
    (1, "dfhg_flag", 1),  # True == 1 under Python equality
    (2, "greek_remaining_in_this_row", False),  # 0 == False
    (1, "text", "ἕτερος"),
])
def test_rejects_changed_original_value_or_type(
    corpus: tuple[Path, Path], file_index: int, field: str, value: object,
) -> None:
    root, out = corpus
    path = root / FILES[file_index]
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0][field] = value
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")
    with pytest.raises(JsonlConservationError, match="source"):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_field_order_change_even_when_dictionary_equal(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    path = root / FILES[1]
    value = json.loads(path.read_text(encoding="utf-8"))
    reordered = {key: value[key] for key in reversed(tuple(value))}
    assert reordered == value
    path.write_text(json.dumps(reordered, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(JsonlConservationError, match="source"):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_missing_extra_and_reordered_original_rows(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    p = root / FILES[0]
    rows = p.read_text(encoding="utf-8").splitlines(keepends=True)
    for bad in (rows[:1], rows + rows[:1], rows[::-1]):
        p.write_text("".join(bad), encoding="utf-8")
        with pytest.raises(JsonlConservationError):
            validate_native_jsonl_sources(root, FILES, out)


def test_rejects_changed_file_selection_order(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    with pytest.raises(JsonlConservationError):
        validate_native_jsonl_sources(root, FILES[::-1], out)


@pytest.mark.parametrize("corruption", [
    '{"urn":"p","urn":"forged"}\n',
    '{"text":NaN}\n',
    '{"text":3.14}\n',
    "\n",
])
def test_rejects_nonstandard_or_ambiguous_source_json(
    corpus: tuple[Path, Path], corruption: str,
) -> None:
    root, out = corpus
    (root / FILES[0]).write_text(corruption, encoding="utf-8")
    with pytest.raises(JsonlConservationError):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_invalid_utf8_and_missing_file(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    (root / FILES[0]).write_bytes(b"\xff\n")
    with pytest.raises(JsonlConservationError):
        validate_native_jsonl_sources(root, FILES, out)
    (root / FILES[0]).unlink()
    with pytest.raises(JsonlConservationError):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_duplicate_physical_source_aliases(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    source = root / FILES[0]
    alias = source.with_name("alias.jsonl")
    try:
        os.link(source, alias)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    with pytest.raises(JsonlConservationError, match="duplicate"):
        validate_native_jsonl_sources(
            root, (FILES[0], "data/corpus/alias.jsonl", *FILES[1:]), out,
        )

def test_corrupt_native_edge_feature_is_a_conservation_failure(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    edge_path = out / "has_fact.tf"
    assert edge_path.is_file()
    edge_path.unlink()
    with pytest.raises(JsonlConservationError, match="native TF"):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_missing_or_extra_json_members_even_with_same_top_level_count(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    path = root / FILES[2]
    item = json.loads(path.read_text(encoding="utf-8"))
    item.pop("license")
    item["other"] = "PD"
    path.write_text(json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(JsonlConservationError, match="source"):
        validate_native_jsonl_sources(root, FILES, out)


def test_rejects_selected_empty_jsonl_file_even_when_other_rows_exist(
    corpus: tuple[Path, Path],
) -> None:
    root, out = corpus
    file = "data/corpus/empty.jsonl"
    (root / file).write_bytes(b"")
    with pytest.raises(JsonlConservationError, match="empty"):
        validate_native_jsonl_sources(root, (*FILES, file), out)
