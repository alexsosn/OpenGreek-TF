"""RED-first tests for issue #29: codepoint controls in every source family."""

from __future__ import annotations

import json
from collections.abc import Iterator
from itertools import chain
from pathlib import Path

import pytest

from opengreek_tf.control_census import ControlLocation, count_controls, main
from opengreek_tf.record_stream import ParsedRecord, iter_family


def _source(root: Path, family: str, name: str, records: list[dict[str, object]]) -> None:
    directory = {
        "primary": "corpus",
        "secondary": "corpus_secondary",
        "paratext": "paratext",
    }[family]
    destination = root / "data" / directory / f"{name}.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )


def _fixture(root: Path) -> None:
    _source(root, "primary", "work", [
        {
            "urn": "work", "edition": "grc", "locus": "1", "source": "tei",
            "license": "CC-BY", "text": "α\r\nβ",
            "text_lines": ["α", "β\r"],
            "provenance": {"note": "x\x00y"},
        },
        {
            "urn": "work", "edition": "grc", "locus": "2", "source": "tei",
            "license": "CC-BY", "text": "γ\n\tδ",
        },
    ])
    _source(root, "secondary", "witness", [{
        "urn": "work", "edition": "other", "locus": "1", "source": "ocr",
        "license": "CC-BY", "text": "α", "rank": "secondary",
        "secondary_reason": "duplicate\x7f",
    }])
    _source(root, "paratext", "excluded", [{
        "slug": "work", "edition": "other", "page": "xi", "source": "ocr",
        "license": "CC-BY", "lang": "la", "text": "alpha\x1b",
    }])


def _rows(root: Path) -> Iterator[ParsedRecord]:
    return chain.from_iterable(
        iter_family(root, family)
        for family in ("primary", "secondary", "paratext")
    )


def test_census_recurses_into_arrays_and_objects_and_counts_every_source_row(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    result = count_controls(_rows(tmp_path))
    assert result.records_by_family == {
        "primary": 2, "secondary": 1, "paratext": 1,
    }
    assert result.occurrences_by_codepoint == {
        "U+0000": 1, "U+000D": 2, "U+001B": 1, "U+007F": 1,
    }
    assert result.crlf_pairs == 1
    assert result.affected_rows == 3
    assert {
        (s.relative_file, s.ordinal, s.field_path, s.offset, s.codepoint)
        for s in result.samples
    } == {
        ("data/corpus/work.jsonl", 1, "text", 1, "U+000D"),
        ("data/corpus/work.jsonl", 1, "text_lines[1]", 1, "U+000D"),
        ("data/corpus/work.jsonl", 1, "provenance.note", 1, "U+0000"),
        ("data/corpus_secondary/witness.jsonl", 1, "secondary_reason", 9, "U+007F"),
        ("data/paratext/excluded.jsonl", 1, "text", 5, "U+001B"),
    }


def test_sample_cap_does_not_cap_census_or_drop_field_paths(tmp_path: Path) -> None:
    _fixture(tmp_path)
    result = count_controls(_rows(tmp_path), sample_limit=1)
    assert len(result.samples) == 1
    assert sum(result.occurrences_by_codepoint.values()) == 5
    assert result.affected_rows == 3
    assert result.crlf_pairs == 1


def test_empty_census_and_invalid_sample_limit(tmp_path: Path) -> None:
    _fixture(tmp_path)
    clean = count_controls(
        row for row in iter_family(tmp_path, "primary") if row.ordinal == 2
    )
    assert clean.records_by_family == {"primary": 1}
    assert clean.occurrences_by_codepoint == {}
    assert clean.affected_rows == 0
    with pytest.raises(ValueError, match="sample_limit"):
        count_controls([], sample_limit=-1)


def test_cli_emits_machine_readable_bounded_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _fixture(tmp_path)
    assert main([str(tmp_path), "--sample-limit", "2"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["records_by_family"] == {
        "primary": 2, "secondary": 1, "paratext": 1,
    }
    assert report["occurrences_by_codepoint"]["U+000D"] == 2
    assert report["crlf_pairs"] == 1
    assert len(report["samples"]) == 2


def test_text_fabric_13_1_cannot_preserve_raw_cr_in_form(
    tmp_path: Path,
) -> None:
    from tf.convert.walker import CV
    from tf.fabric import Fabric

    original = "α\rβ"

    def director(cv: CV) -> None:
        node = cv.slot()
        cv.feature(node, form=original)

    target = tmp_path / "tf"
    assert CV(Fabric(locations=str(target), silent="deep"), silent="deep").walk(
        director,
        slotType="atom",
        generic={"source": "control characterization"},
        otext={"fmt:text-orig-full": "{form}"},
        featureMeta={"form": {"description": "raw codepoints"}},
        warn=False,
    )
    api = Fabric(locations=str(target), silent="deep").load("form", silent="deep")
    assert api
    slot = api.F.otype.s("atom")[0]
    assert api.F.form.v(slot) != original
    assert api.T.text(slot, fmt="text-orig-full") != original


def test_streaming_sink_receives_every_location_despite_sample_cap(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    received: list[ControlLocation] = []
    result = count_controls(_rows(tmp_path), sample_limit=0, on_occurrence=received.append)
    assert result.samples == ()
    assert len(received) == 5
    assert sum(result.occurrences_by_codepoint.values()) == 5
    assert {(location.field_path, location.offset) for location in received} >= {
        ("text_lines[1]", 1), ("provenance.note", 1),
    }


def test_c1_range_including_next_line_is_not_silently_ignored(tmp_path: Path) -> None:
    _fixture(tmp_path)
    _source(tmp_path, "paratext", "c1", [{
        "slug": "work", "edition": "other", "page": "xii", "source": "ocr",
        "license": "CC-BY", "lang": "la", "text": "α\u0085\u009fβ",
    }])
    result = count_controls(iter_family(tmp_path, "paratext"))
    assert result.occurrences_by_codepoint == {
        "U+001B": 1, "U+0085": 1, "U+009F": 1,
    }
    assert result.affected_rows == 2
    assert {
        (s.relative_file, s.offset, s.codepoint) for s in result.samples
    } >= {
        ("data/paratext/c1.jsonl", 1, "U+0085"),
        ("data/paratext/c1.jsonl", 2, "U+009F"),
    }
