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


def test_public_cli_search_native_preserves_greek_and_source_provenance(
    native: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The installed project's CLI must expose the existing native F/E search."""
    from opengreek_tf.cli import main as public_main

    assert public_main([
        "search-native", str(native), "--kind", "primary-passage",
        "--contains", "λόγος", "--urn", "real-work-a",
        "--edition", "first", "--source", "tei", "--max-results", "1",
    ]) == 0
    primary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(primary) == 1
    assert primary[0]["text"] == "λόγος  ἀνήρ\n"
    assert primary[0]["source_record_id"] == "data/corpus/p.jsonl:1"
    assert primary[0]["edition"] == "first"

    assert public_main([
        "search-native", str(native), "--kind", "secondary-witness",
        "--contains", "λόγος",
    ]) == 0
    secondary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(secondary) == 1
    assert secondary[0]["text"] == "λόγος ἕτερος"
    assert secondary[0]["kind"] == "secondary-witness"
    assert secondary[0]["source_file"] == "data/corpus_secondary/p.jsonl"

    with pytest.raises(SystemExit) as invalid:
        public_main(["search-native", str(native), "--kind", "word"])
    assert invalid.value.code == 2


# RED-only dynamic API call lets pytest exercise the absent keywords before
# implementation; replace with the typed entrypoint after observing RED.
raw_search_native: Any = search_native

def test_exact_source_file_and_source_locus_filters_on_loaded_native_facts(
    native: Path,
) -> None:
    """Locus is the exact source string, not an inferred CTS hierarchy."""
    first = raw_search_native(
        native, kind="primary-passage",
        source_file="data/corpus/p.jsonl", locus="1.1",
    )
    assert [(hit.source_seq, hit.locus, hit.text) for hit in first] == [
        (1, "1.1", "λόγος  ἀνήρ\n"),
    ]
    second = raw_search_native(
        native, kind="primary-passage",
        source_file="data/corpus/p.jsonl", locus="1.2",
        edition="revised", contains="ἄνθρωπος",
    )
    assert [(hit.source_seq, hit.locus) for hit in second] == [(2, "1.2")]
    assert raw_search_native(
        native, kind="primary-passage", source_file="data/corpus_secondary/p.jsonl",
    ) == ()
    secondary = raw_search_native(
        native, kind="secondary-witness",
        source_file="data/corpus_secondary/p.jsonl", locus="1.1",
    )
    assert len(secondary) == 1 and secondary[0].source_seq == 3
    # Editorial paratext has a page, not a fabricated source locus.
    assert raw_search_native(native, kind="paratext-record", locus="1.1") == ()
    assert raw_search_native(native, kind="primary-passage", locus="1") == ()


def test_source_file_filter_does_not_conflate_different_primary_files(
    tmp_path: Path,
) -> None:
    """Same source-authored locus may occur in separate original JSONL files."""
    rows = (
        NativeRecord(
            "data/corpus/abydenus.fragmenta.jsonl", 1, "abydenus:1",
            "primary-passage",
            FieldObject((("urn", "abydenus.fragmenta"), ("locus", "4.1"),
                         ("text", "λόγος"))), text="λόγος",
        ),
        NativeRecord(
            "data/corpus/abydenus.fragmenta.jsonl", 2, "abydenus:2",
            "primary-passage",
            FieldObject((("urn", "abydenus.fragmenta"), ("locus", "4.5"),
                         ("text", "λόγος"))), text="λόγος",
        ),
        NativeRecord(
            "data/corpus/other.fragmenta.jsonl", 1, "other:1",
            "primary-passage",
            FieldObject((("urn", "other.fragmenta"), ("locus", "4.1"),
                         ("text", "λόγος"))), text="λόγος",
        ),
    )
    destination = tmp_path / "native-multifile"
    write_native_records(rows, destination)
    assert [hit.source_seq for hit in raw_search_native(
        destination, kind="primary-passage", contains="λόγος", locus="4.1",
    )] == [1, 3]
    assert [(hit.source_seq, hit.source_file) for hit in raw_search_native(
        destination, kind="primary-passage", contains="λόγος",
        source_file="data/corpus/abydenus.fragmenta.jsonl", locus="4.1",
    )] == [(1, "data/corpus/abydenus.fragmenta.jsonl")]
    assert [hit.source_seq for hit in raw_search_native(
        destination, kind="primary-passage",
        source_file="data/corpus/abydenus.fragmenta.jsonl",
    )] == [1, 2]


@pytest.mark.parametrize(("filter_key", "invalid"), [
    ("source_file", 3),
    ("source_file", False),
    ("locus", 4),
    ("locus", True),
])
def test_research_query_new_filters_reject_non_strings_before_fabric_loading(
    tmp_path: Path, filter_key: str, invalid: object,
) -> None:
    with pytest.raises(NativeResearchQueryError, match=filter_key):
        raw_search_native(tmp_path / "not-a-fabric", kind="primary-passage",
                      **{filter_key: invalid})


def test_public_and_module_search_cli_accept_original_source_and_locus(
    native: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from opengreek_tf.cli import main as public_main
    from opengreek_tf.research_queries import main as module_main

    arguments = [
        str(native), "--kind", "primary-passage",
        "--source-file", "data/corpus/p.jsonl", "--locus", "1.2",
        "--contains", "ἄνθρωπος",
    ]
    assert public_main(["search-native", *arguments]) == 0
    public_hits = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert len(public_hits) == 1
    assert public_hits[0]["source_seq"] == 2
    assert public_hits[0]["locus"] == "1.2"
    assert module_main(arguments) == 0
    module_hits = [
        json.loads(line) for line in capsys.readouterr().out.splitlines()
    ]
    assert module_hits == public_hits
