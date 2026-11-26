from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import read_native_records
from opengreek_tf.record_stream import FieldArray, FieldObject, RecordParseError, parse_file
from opengreek_tf.release import NOVEMBER_RELEASE
from opengreek_tf.text_materializer import materialize_texts

FILE = "data/corpus/sample.jsonl"


def record(root: Path, **fields: object) -> None:
    path = root / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {
        "urn": "sample", "edition": "sample", "source": "sample",
        "license": "CC-BY-SA-4.0", "locus": "1", "text": "α β",
    }
    row.update(fields)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def test_editorial_projections_and_original_text(tmp_path: Path) -> None:
    record(
        tmp_path, reading_text="αβ", analysis_text="α", analysis_segments=["α"],
        contextual_eligible=True, critical_markup={"schema": "sample"},
        tokens=[{"analysis": None, "end": 1, "form": "α", "id": "t1",
                 "lemma": None, "lexical_eligible": True, "span_ids": ["s1"],
                 "start": 0, "status": ["visible"]}],
    )
    row = next(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))
    assert row.text == "α β"
    assert row.fields.require("reading_text") == "αβ"
    assert row.fields.require("analysis_text") == "α"
    tokens = row.fields.require("tokens")
    assert isinstance(tokens, FieldArray)
    token = tokens.items[0]
    assert isinstance(token, FieldObject)
    assert token.require("lemma") is None
    with pytest.raises(RecordParseError):
        list(parse_file(tmp_path, FILE))
    output = tmp_path / "native"
    materialize_texts(tmp_path, (FILE,), output, identity=NOVEMBER_RELEASE)
    loaded = read_native_records(output)
    assert loaded[0].fields == row.fields
    assert validate_native_jsonl_sources(
        tmp_path, (FILE,), output, identity=NOVEMBER_RELEASE,
    ).records == 1


def test_scan_numeric_types_and_null(tmp_path: Path) -> None:
    record(
        tmp_path, source_printed_page=None,
        source_scan={"region": [0, 0.125, 1, 0.75], "scan_page": 2,
                     "sha256": "abc", "url": "https://example.org"},
    )
    row = next(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))
    scan = row.fields.require("source_scan")
    assert isinstance(scan, FieldObject)
    region = scan.require("region")
    assert isinstance(region, FieldArray)
    assert tuple(type(x) for x in region.items) == (int, float, int, float)
    assert row.fields.require("source_printed_page") is None
    output = tmp_path / "native"
    materialize_texts(tmp_path, (FILE,), output, identity=NOVEMBER_RELEASE)
    assert validate_native_jsonl_sources(
        tmp_path, (FILE,), output, identity=NOVEMBER_RELEASE,
    ).records == 1


@pytest.mark.parametrize("bad", [True, "0.5", float("nan"), float("inf")])
def test_scan_rejects_non_numeric_or_nonfinite(tmp_path: Path, bad: object) -> None:
    record(tmp_path, source_scan={"region": [bad], "scan_page": 2,
                                  "sha256": "abc", "url": "url"})
    with pytest.raises(RecordParseError, match="region"):
        list(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))


def test_null_only_and_unknown_nested_fields(tmp_path: Path) -> None:
    token: dict[str, object] = {
        "analysis": None, "end": 1, "form": "α", "id": "t1", "lemma": "invented",
        "lexical_eligible": True, "span_ids": ["s1"], "start": 0, "status": [],
    }
    record(tmp_path, tokens=[token])
    with pytest.raises(RecordParseError, match="lemma"):
        list(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))
    token["lemma"] = None
    token["invented"] = True
    record(tmp_path, tokens=[token])
    with pytest.raises(RecordParseError, match="invented"):
        list(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))


def test_source_location_and_critical_markup_reject_unknown_keysets(tmp_path: Path) -> None:
    record(tmp_path, source_location={"volume": "I", "marker_page": "1"})
    with pytest.raises(RecordParseError, match="source_location"):
        list(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))
    record(tmp_path, critical_markup={"schema": "sample", "invented": 1})
    with pytest.raises(RecordParseError, match="critical_markup"):
        list(parse_file(tmp_path, FILE, identity=NOVEMBER_RELEASE))
