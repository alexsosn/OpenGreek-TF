"""RED-first tests for the exact audited Open Greek JSONL source stream."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.record_stream import (
    FieldArray,
    FieldObject,
    RecordParseError,
    iter_family,
    parse_file,
)


def _source(tmp_path: Path, family: str, name: str, lines: list[str]) -> str:
    parent = {
        "primary": "data/corpus",
        "secondary": "data/corpus_secondary",
        "paratext": "data/paratext",
    }[family]
    relative = f"{parent}/{name}.jsonl"
    full = tmp_path / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return relative


def test_primary_source_order_exact_text_and_nested_types(tmp_path: Path) -> None:
    rel = _source(
        tmp_path,
        "primary",
        "test-work",
        [
            json.dumps(
                {
                    "urn": "test-work",
                    "edition": "grc",
                    "locus": "1.1",
                    "source": "tei",
                    "license": "PD",
                    "text": "  λόγος  \t\n",
                    "corrections": ["manual:alpha", "manual:beta"],
                    "page": 12,
                    "dfhg_flag": False,
                    "text_lines": ["  λόγος  ", "\t"],
                    "bekker": ["1a", "1b"],
                    "provenance": {
                        "method": "direct",
                        "consolidated_from": ["x", "y"],
                        "dropped_gap": 0,
                    },
                    "merged_read": {
                        "guessed": 2,
                        "substituted": 1,
                        "with": ["reading-a"],
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "urn": "test-work",
                    "edition": "grc",
                    "locus": "1.1",
                    "source": "tei",
                    "license": "PD",
                    "text": "ἕτερον",
                },
                ensure_ascii=False,
            ),
        ],
    )
    rows = list(parse_file(tmp_path, rel))
    assert len(rows) == 2
    assert (rows[0].family, rows[0].relative_file, rows[0].ordinal) == (
        "primary",
        rel,
        1,
    )
    assert rows[1].ordinal == 2
    assert rows[0].occurrence_key != rows[1].occurrence_key
    assert rows[0].text == "  λόγος  \t\n"
    assert rows[0].fields.get("locus") == rows[1].fields.get("locus") == "1.1"
    assert rows[0].fields.get("page") == 12
    assert rows[0].fields.get("dfhg_flag") is False
    assert rows[0].fields.get("corrections") == FieldArray(
        ("manual:alpha", "manual:beta")
    )
    assert rows[0].fields.get("text_lines") == FieldArray(("  λόγος  ", "\t"))
    assert rows[0].fields.get("bekker") == FieldArray(("1a", "1b"))
    provenance = rows[0].fields.get("provenance")
    assert isinstance(provenance, FieldObject)
    assert provenance.get("dropped_gap") == 0
    assert provenance.get("consolidated_from") == FieldArray(("x", "y"))
    merged = rows[0].fields.get("merged_read")
    assert isinstance(merged, FieldObject)
    assert merged.get("guessed") == 2
    assert merged.get("with") == FieldArray(("reading-a",))
    assert rows[1].fields.get("page") is None
    assert rows[0].fields.items[0] == ("urn", "test-work")


def test_secondary_keeps_container_and_work_identity_distinct(tmp_path: Path) -> None:
    rel = _source(
        tmp_path,
        "secondary",
        "original.duplicate-read",
        [
            '{"urn":"original","edition":"alt","locus":"1","source":"ocr",'
            '"license":"PD","text":"ἀήρ",'
            '"rank":"secondary","secondary_reason":"duplicate OCR"}',
            '{"urn":"original","edition":"alt","locus":"1","source":"ocr",'
            '"license":"PD","text":"ἀήρ","displaced_by":'
            '{"date":"2026-01-01","pass":"merge","reason":"better scan"}}',
        ],
    )
    rows = list(parse_file(tmp_path, rel))
    assert rows[0].relative_file == rel
    assert rows[0].fields.get("urn") == "original"
    assert rows[0].fields.get("rank") == "secondary"
    assert rows[1].fields.get("secondary_reason") is None
    displacement = rows[1].fields.get("displaced_by")
    assert isinstance(displacement, FieldObject)
    assert displacement.get("reason") == "better scan"


def test_paratext_string_page_and_language(tmp_path: Path) -> None:
    rel = _source(
        tmp_path,
        "paratext",
        "apparatus",
        [
            '{"slug":"work","edition":"printed","page":"xii",'
            '"source":"ocr","license":"PD","lang":"la","text":"quod",'
            '"class":"edition_apparatus",'
            '"script":"latin","greek_remaining_in_this_row":0,'
            '"why_not_served":"not Greek"}',
        ],
    )
    row = next(parse_file(tmp_path, rel))
    assert row.family == "paratext"
    assert row.text == "quod"
    assert row.fields.get("page") == "xii"
    assert row.fields.get("class") == "edition_apparatus"
    assert row.fields.get("greek_remaining_in_this_row") == 0


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":"a","page":true}', "page"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":"a","extra":"surprise"}', "extra"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":"a","corrections":[1]}', "corrections"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":"a","provenance":{"unknown":5}}', "unknown"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":"a","merged_read":{"guessed":"three"}}', "guessed"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
         '"text":null}', "text"),
        ('{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD"}',
         "text"),
        ('{"urn":"w","urn":"w","edition":"e","locus":"1","source":"s",'
         '"license":"PD","text":"a"}', "duplicate"),
    ],
)
def test_invalid_primary_rows_fail_with_file_line_and_field(
    tmp_path: Path, body: str, field: str
) -> None:
    rel = _source(tmp_path, "primary", "w", [body])
    with pytest.raises(RecordParseError) as exc:
        list(parse_file(tmp_path, rel))
    message = str(exc.value)
    assert f"{rel}:1" in message
    assert field in message


def test_lazy_row_iteration_and_blank_rows_fail_closed(tmp_path: Path) -> None:
    rel = _source(
        tmp_path, "primary", "w",
        [
            '{"urn":"w","edition":"e","locus":"1","source":"s",'
            '"license":"PD","text":"ok"}',
            "",
        ],
    )
    stream = parse_file(tmp_path, rel)
    assert next(stream).text == "ok"
    with pytest.raises(RecordParseError, match=r":2.*blank"):
        next(stream)


def test_family_reader_streams_files_in_lexical_order(tmp_path: Path) -> None:
    def row(urn: str) -> str:
        return ('{"urn":"' + urn + '","edition":"e","locus":"1",'
                '"source":"s","license":"PD","text":"x"}')

    _source(tmp_path, "primary", "z", [row("z")])
    _source(tmp_path, "primary", "a", [row("a")])
    assert [r.relative_file for r in iter_family(tmp_path, "primary")] == [
        "data/corpus/a.jsonl", "data/corpus/z.jsonl"
    ]


def test_unexpected_family_and_incompatible_page_type(tmp_path: Path) -> None:
    rel = _source(
        tmp_path, "paratext", "notes",
        ['{"slug":"s","edition":"e","page":1,"source":"s",'
         '"license":"PD","lang":"la","text":"nota"}'],
    )
    with pytest.raises(RecordParseError, match="page"):
        list(parse_file(tmp_path, rel))
    with pytest.raises(RecordParseError, match="unsupported"):
        list(parse_file(tmp_path, "data/unknown/notes.jsonl"))


def test_invalid_utf8_fails_with_physical_source_row(tmp_path: Path) -> None:
    rel = "data/corpus/w.jsonl"
    file = tmp_path / rel
    file.parent.mkdir(parents=True)
    file.write_bytes(b'{"urn":"w","text":"\xff"}\n')
    with pytest.raises(RecordParseError) as exc:
        list(parse_file(tmp_path, rel))
    assert f"{rel}:1" in str(exc.value)
    assert "UTF-8" in str(exc.value)


def test_noncanonical_file_identity_and_invalid_family_fail_closed(
    tmp_path: Path,
) -> None:
    rel = _source(
        tmp_path,
        "primary",
        "w",
        ['{"urn":"w","edition":"e","locus":"1","source":"s",'
         '"license":"PD","text":"x"}'],
    )
    with pytest.raises(RecordParseError, match="noncanonical"):
        list(parse_file(tmp_path, rel.replace("corpus/", "corpus/./")))
    with pytest.raises(RecordParseError, match="unsupported"):
        list(iter_family(tmp_path, "nonexistent"))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("extra_fields", "failure"),
    [
        ('"rank":"secondary"', "secondary_reason"),
        ('"secondary_reason":"stale"', "rank"),
        ('"displaced_by":{}', "displaced_by"),
        ('"displaced_by":{"date":"2026","pass":"replace","reason":"x"},'
         '"rank":"secondary","secondary_reason":"other"', "displaced_by"),
    ],
)
def test_secondary_witness_variant_must_be_complete(
    tmp_path: Path, extra_fields: str, failure: str
) -> None:
    body = (
        '{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
        '"text":"x",' + extra_fields + "}"
    )
    rel = _source(tmp_path, "secondary", "w", [body])
    with pytest.raises(RecordParseError, match=failure):
        list(parse_file(tmp_path, rel))


@pytest.mark.parametrize(
    "merged",
    [
        '{"guessed":1}',
        '{"guesses":1,"note":"x"}',
        '{"guessed":1,"substituted":2,"with":["x"],"guesses":0}',
    ],
)
def test_partial_or_mixed_merged_read_variants_rejected(
    tmp_path: Path, merged: str
) -> None:
    body = (
        '{"urn":"w","edition":"e","locus":"1","source":"s","license":"PD",'
        '"text":"x","merged_read":' + merged + "}"
    )
    rel = _source(tmp_path, "primary", "w", [body])
    with pytest.raises(RecordParseError, match="merged_read"):
        list(parse_file(tmp_path, rel))


def test_empty_source_file_is_not_silently_skipped(tmp_path: Path) -> None:
    rel = "data/corpus/empty.jsonl"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    with pytest.raises(RecordParseError) as exc:
        list(parse_file(tmp_path, rel))
    assert rel in str(exc.value)
    assert "empty source file" in str(exc.value)
