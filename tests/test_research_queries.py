"""RED-first researcher-facing native Text-Fabric query cases (#11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import NativeRecord, write_native_records
from opengreek_tf.record_stream import FieldObject
from opengreek_tf.research_queries import NativeResearchQueryError, search_native


@pytest.fixture
def native(tmp_path: Path) -> Path:
    source = (
        NativeRecord(
            "data/corpus/p.jsonl", 1, "data/corpus/p.jsonl:1",
            "primary-passage",
            FieldObject((
                ("urn", "real-work-a"), ("edition", "first"),
                ("source", "tei"), ("license", "CC-BY"), ("locus", "1.1"),
                ("text", "λόγος  ἀνήρ\n"),
            )),
            text="λόγος  ἀνήρ\n",
        ),
        NativeRecord(
            "data/corpus/p.jsonl", 2, "data/corpus/p.jsonl:2",
            "primary-passage",
            FieldObject((
                ("urn", "real-work-a"), ("edition", "revised"),
                ("source", "ocr"), ("license", "PD"), ("locus", "1.2"),
                ("text", "ἄνθρωπος λόγοι"),
            )),
            text="ἄνθρωπος λόγοι",
        ),
        NativeRecord(
            "data/corpus_secondary/p.jsonl", 1,
            "data/corpus_secondary/p.jsonl:1", "secondary-witness",
            FieldObject((
                ("urn", "real-work-a"), ("edition", "alternate"),
                ("source", "ocr"), ("license", "PD"), ("locus", "1.1"),
                ("text", "λόγος ἕτερος"),
                ("secondary_reason", "displaced"),
            )),
        ),
        NativeRecord(
            "data/paratext/p.jsonl", 1, "data/paratext/p.jsonl:1",
            "paratext-record",
            FieldObject((
                ("slug", "real-work-a"), ("page", "folio-4"),
                ("lang", "grc"), ("source", "tei"),
                ("license", "CC-BY"), ("edition", "first"),
                ("text", "ὑπόμνημα λόγου"),
            )),
        ),
    )
    out = tmp_path / "mixed-native"
    write_native_records(source, out)
    return out


def test_primary_search_uses_genuine_native_text_and_source_fact_filters(
    native: Path,
) -> None:
    hits = search_native(
        native, kind="primary-passage", contains="λόγος",
        edition="first", source="tei", urn="real-work-a",
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit.kind == "primary-passage"
    assert hit.text == "λόγος  ἀνήρ\n"
    assert (hit.urn, hit.locus, hit.edition, hit.source, hit.license) == (
        "real-work-a", "1.1", "first", "tei", "CC-BY",
    )
    assert (hit.source_file, hit.source_ordinal, hit.source_record_id) == (
        "data/corpus/p.jsonl", 1, "data/corpus/p.jsonl:1",
    )
    assert hit.source_seq == 1
    assert search_native(native, kind="primary-passage", contains="λόγος", source="ocr") == ()
    assert [h.source_seq for h in search_native(
        native, kind="primary-passage", contains="λόγ",
    )] == [1, 2]


def test_unaligned_source_facts_are_not_lexical_passages_or_inferred_links(
    native: Path,
) -> None:
    secondary = search_native(
        native, kind="secondary-witness", contains="λόγος", edition="alternate",
    )
    assert len(secondary) == 1
    assert secondary[0].text == "λόγος ἕτερος"
    assert secondary[0].source_seq == 3
    assert secondary[0].source_file == "data/corpus_secondary/p.jsonl"

    paratext = search_native(
        native, kind="paratext-record", contains="ὑπόμνημα",
    )
    assert len(paratext) == 1
    assert (paratext[0].slug, paratext[0].page, paratext[0].text) == (
        "real-work-a", "folio-4", "ὑπόμνημα λόγου",
    )
    assert paratext[0].urn is None
    api = Fabric(locations=str(native), silent="deep").load("record_kind", silent="deep")
    assert api
    assert len(api.F.otype.s("passage")) == 2
    assert len(api.F.otype.s("metadataRecord")) == 2
    assert not api.F.otype.s("word")


def test_search_is_bounded_and_ordered_by_original_global_source_sequence(
    native: Path,
) -> None:
    rows = search_native(native, kind="primary-passage", contains="", max_results=1)
    assert len(rows) == 1
    assert rows[0].source_seq == 1
    assert search_native(native, kind="primary-passage", contains="ΛΟΓΟΣ") == ()


@pytest.mark.parametrize(("kwargs", "part"), [
    ({"kind": "word", "contains": "λόγ"}, "kind"),
    ({"kind": "primary-passage", "contains": "", "max_results": 0}, "max_results"),
    ({"kind": "primary-passage", "contains": "", "max_results": True}, "max_results"),
    ({"kind": "primary-passage", "contains": "", "source": 9}, "source"),
])
def test_rejects_unsupported_or_ambiguous_research_query(
    native: Path, kwargs: dict[str, Any], part: str,
) -> None:
    with pytest.raises((ValueError, NativeResearchQueryError), match=part):
        search_native(native, **kwargs)


def test_command_line_emits_machine_readable_genuine_source_provenance(
    native: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from opengreek_tf.research_queries import main

    assert main([
        str(native), "--kind", "primary-passage",
        "--contains", "λόγος", "--edition", "first",
    ]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(rows) == 1
    assert rows[0]["text"] == "λόγος  ἀνήρ\n"
    assert rows[0]["source_file"] == "data/corpus/p.jsonl"
    assert rows[0]["source_ordinal"] == 1
