"""RED-first CR diagnostic tests for source field paths and native TF 13.1."""

from __future__ import annotations

from pathlib import Path

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.record_stream import FieldArray, FieldObject, ParsedRecord
from opengreek_tf.source_controls import iter_carriage_returns


def test_cr_census_walks_nested_typed_source_values_without_false_positives() -> None:
    row = ParsedRecord(
        family="primary",
        relative_file="data/corpus/example.jsonl",
        ordinal=37,
        fields=FieldObject(
            (
                ("text", "λόγος\r\nἕτερος"),
                ("provenance", FieldObject((("note", "a\rb\rc"),))),
                ("corrections", FieldArray(("literal\\r", "a\r"))),
                ("locus", "1"),
                ("page", 1),
                ("dfhg_flag", False),
            )
        ),
    )
    hits = tuple(iter_carriage_returns(row))
    assert [(hit.field_path, hit.count) for hit in hits] == [
        ("text", 1),
        ("provenance.note", 2),
        ("corrections[1]", 1),
    ]
    assert all(hit.family == "primary" for hit in hits)
    assert all(hit.relative_file == row.relative_file for hit in hits)
    assert all(hit.ordinal == 37 for hit in hits)


def test_cr_census_retains_actual_zero_and_literal_backslash_r() -> None:
    row = ParsedRecord(
        family="paratext",
        relative_file="data/paratext/notes.jsonl",
        ordinal=1,
        fields=FieldObject((("text", "α\\rβ"), ("page", "2"), ("lang", "la"))),
    )
    assert tuple(iter_carriage_returns(row)) == ()


def _tf_roundtrip(tmp_path: Path, text: str) -> str | None:
    output = tmp_path / "native"
    fabric = Fabric(locations=str(output), silent="deep")

    def director(cv: CV) -> None:
        passage = cv.node("passage")
        slot = cv.slot()
        cv.feature(slot, form=text)
        cv.feature(passage, locus="1")
        cv.terminate(passage)

    assert CV(fabric, silent="deep").walk(
        director,
        slotType="word",
        generic={"source": "Synthetic native TF CR serialization probe"},
        otext={
            "sectionTypes": "passage",
            "sectionFeatures": "locus",
            "fmt:text-orig-full": "{form}",
        },
        featureMeta={
            "locus": {"description": "Real section label"},
            "form": {"description": "Actual source text"},
        },
        warn=False,
    )
    loaded = Fabric(locations=str(output), silent="deep").load(
        "form locus", silent="deep"
    )
    return loaded.F.form.v(1) if loaded else None


def test_native_tf_baseline_lf_tab_and_backslash_roundtrip(tmp_path: Path) -> None:
    raw = "λόγος\n\t\\ἕτερος"
    assert _tf_roundtrip(tmp_path, raw) == raw


def test_native_tf_13_1_does_not_roundtrip_unescaped_cr(tmp_path: Path) -> None:
    for index, raw in enumerate(("λόγος\rἕτερος", "λόγος\r\nἕτερος")):
        returned = _tf_roundtrip(tmp_path / str(index), raw)
        assert returned != raw, (
            "Text-Fabric behavior changed; revisit #29 before claiming CR loss"
        )
