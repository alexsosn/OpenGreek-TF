"""RED-first proof: actual typed records -> loadable, text-exact native TF."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.mini_writer import (
    UnsupportedSourceStructure,
    write_primary_probe,
)
from opengreek_tf.record_stream import ParsedRecord, parse_file
from opengreek_tf.text_runs import segment_runs


def _source(tmp_path: Path, rows: list[dict[str, object]]) -> list[ParsedRecord]:
    root = tmp_path / "upstream"
    path = root / "data" / "corpus" / "test-work.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return list(parse_file(root, "data/corpus/test-work.jsonl"))


def _row(text: str, locus: str = "1", **extra: object) -> dict[str, object]:
    return {
        "urn": "test-work", "edition": "grc", "source": "tei",
        "license": "CC-BY-SA-4.0", "locus": locus, "text": text, **extra,
    }


def test_native_tf_preserves_repeated_loci_empty_text_and_exact_slots(
    tmp_path: Path,
) -> None:
    texts = ["  λόγος· \tκόσμος\n", "", "α\u0301  ἕτερον"]
    rows = _source(
        tmp_path,
        [
            _row(texts[0], locus="1.1", page=8, work="ΣΧΟΛΙΑ"),
            _row(texts[1], locus="1.1"),
            _row(texts[2], locus="1.2"),
        ],
    )
    assert len(rows) == 3
    destination = tmp_path / "tf"
    write_primary_probe(rows, destination)
    api = Fabric(locations=str(destination), silent="deep").load(
        "form atom_kind work_slug passage_key source_file source_ordinal "
        "src_urn src_locus src_edition src_source src_license src_page src_work",
        silent="deep",
    )
    assert api
    assert len(api.F.otype.s("work")) == 1
    passages = api.F.otype.s("passage")
    assert len(passages) == 3
    assert len(api.F.otype.s("word")) == 0
    assert api.F.work_slug.v(api.F.otype.s("work")[0]) == "test-work"
    assert [api.F.src_locus.v(p) for p in passages] == ["1.1", "1.1", "1.2"]
    assert [api.F.source_ordinal.v(p) for p in passages] == [1, 2, 3]
    assert len({api.F.passage_key.v(p) for p in passages}) == 3
    assert api.F.src_page.v(passages[0]) == 8
    assert api.F.src_work.v(passages[0]) == "ΣΧΟΛΙΑ"
    assert api.F.src_license.v(passages[0]) == "CC-BY-SA-4.0"

    for passage, original in zip(passages, texts, strict=True):
        atoms = tuple(api.E.oslots.s(passage))
        text_atoms = [s for s in atoms if api.F.atom_kind.v(s) == "text"]
        row_atoms = [s for s in atoms if api.F.atom_kind.v(s) == "source-row"]
        assert len(row_atoms) == 1
        assert api.F.form.v(row_atoms[0]) is None
        assert "".join(api.F.form.v(s) for s in text_atoms) == original
        assert len(text_atoms) == len(list(segment_runs(original)))
        assert api.T.text(passage, fmt="text-orig-full") == original
    assert [api.F.src_urn.v(p) for p in passages] == ["test-work"] * 3
    assert len(api.F.otype.s("atom")) == sum(
        len(tuple(segment_runs(text))) + 1 for text in texts
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"corrections": ["manual"]},
        {"text_lines": ["λόγος"]},
        {"text_orig": "λογος"},
        {"provenance": {"method": "direct"}},
        {"merged_read": {"guessed": 1, "substituted": 0, "with": ["other"]}},
        {"bekker": ["12a"]},
        {"dfhg_flag": True},
    ],
)
def test_writer_rejects_unimplemented_semantics_before_output(
    tmp_path: Path, extra: dict[str, object]
) -> None:
    row = _row("λόγος")
    row.update(extra)
    source_rows = _source(tmp_path, [row])
    dest = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure):
        write_primary_probe(source_rows, dest)
    assert not dest.exists()


def test_writer_rejects_mixed_work_ids_before_any_tf_output(tmp_path: Path) -> None:
    records = _source(
        tmp_path,
        [_row("λόγος"), {**_row("ἕτερον"), "urn": "different-work"}],
    )
    dest = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure, match="URN"):
        write_primary_probe(records, dest)
    assert not dest.exists()


def test_writer_rejects_incomplete_and_unbounded_input(tmp_path: Path) -> None:
    records = _source(tmp_path, [_row("α"), _row("β"), _row("γ")])
    dest = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure, match="maximum"):
        write_primary_probe(records, dest, max_records=2)
    assert not dest.exists()


def test_writer_rejects_secondary_layer_without_inventing_alignment(
    tmp_path: Path,
) -> None:
    records = _source(tmp_path, [_row("λόγος")])
    only = records[0]
    secondary = ParsedRecord(
        family="secondary",
        relative_file=only.relative_file.replace("/corpus/", "/corpus_secondary/"),
        ordinal=only.ordinal,
        fields=only.fields,
    )
    destination = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure, match="primary"):
        write_primary_probe([secondary], destination)
    assert not destination.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"text": "λόγος\r\nἄλλος"},
        {"text": "λόγος\rἄλλος"},
        {"work": "ΕΡΓΟΝ\rΔΕΥΤΕΡΟΝ"},
    ],
)
def test_writer_rejects_unroundtrippable_carriage_return(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    # TF 13.1 text-feature encoding escapes LF and TAB but not CR, while its
    # default text reader has universal newline semantics.
    row = _row("λόγος")
    row.update(changes)
    records = _source(tmp_path, [row])
    dest = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure, match="carriage return"):
        write_primary_probe(records, dest)
    assert not dest.exists()


@pytest.mark.parametrize("order", [(0, 0), (1, 0)])
def test_writer_rejects_duplicate_or_reordered_physical_source_rows(
    tmp_path: Path, order: tuple[int, int]
) -> None:
    source_rows = _source(tmp_path, [_row("πρῶτον"), _row("δεύτερον")])
    destination = tmp_path / "tf"
    with pytest.raises(UnsupportedSourceStructure, match="physical source order"):
        write_primary_probe([source_rows[i] for i in order], destination)
    assert not destination.exists()
