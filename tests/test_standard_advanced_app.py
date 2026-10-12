"""RED-first standard TF advanced-app proof on real generated native F/E (#10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tf.app import use  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import NativeRecord, write_native_records
from opengreek_tf.record_stream import FieldObject


@pytest.fixture
def mixed_native(tmp_path: Path) -> tuple[Path, str, str]:
    record_id = "data/corpus/p.jsonl:1"
    greek = "λόγος  ἀνήρ\n"
    records = (
        NativeRecord(
            "data/corpus/p.jsonl", 1, record_id, "primary-passage",
            FieldObject((
                ("urn", "work-a"), ("locus", "1.1"),
                ("edition", "first"), ("source", "tei"),
                ("license", "PD"), ("text", greek),
            )),
            text=greek,
        ),
        NativeRecord(
            "data/corpus_secondary/p.jsonl", 1,
            "data/corpus_secondary/p.jsonl:1",
            "secondary-witness",
            FieldObject((
                ("urn", "work-a"), ("locus", "1.1"),
                ("edition", "alternate"), ("source", "ocr"),
                ("license", "PD"), ("text", "ἕτερος λόγος"),
            )),
        ),
    )
    out = tmp_path / "native"
    write_native_records(records, out)
    return out, record_id, greek


def test_standard_local_tf_app_navigates_actual_native_source_record(
    mixed_native: tuple[Path, str, str],
) -> None:
    native_dir, record_id, original = mixed_native
    api = Fabric(locations=str(native_dir), silent="deep").load(
        "source_file source_record_id source_seq form fact_key "
        "fact_kind fact_text has_fact record_kind", silent="deep",
    )
    assert api
    app_dir = Path(__file__).resolve().parents[1] / "app"
    app = use(f"app:{app_dir}", api=api, silent="deep")
    assert app is not None and app.api is not None
    passages = app.api.F.otype.s("passage")
    assert len(passages) == 1
    passage = passages[0]
    assert app.api.T.text(passage, fmt="text-orig-full") == original
    assert app.sectionStrFromNode(passage) == record_id
    assert app.nodeFromSectionStr(record_id) == passage
    assert not app.api.F.otype.s("word")
    assert len(app.api.F.otype.s("metadataRecord")) == 1


def test_standard_app_exposes_honest_single_passage_section_and_docs(
    mixed_native: tuple[Path, str, str],
) -> None:
    native_dir, source_record_id, _ = mixed_native
    api = Fabric(locations=str(native_dir), silent="deep").load(
        "source_record_id form record_kind", silent="deep",
    )
    assert api
    app_dir = Path(__file__).resolve().parents[1] / "app"
    app = use(f"app:{app_dir}", api=api, silent="deep")
    assert app is not None and app.api is not None
    assert tuple(app.api.T.sectionTypes) == ("passage",)
    assert app.context.exampleSection == source_record_id
    assert app.context.docPage == "research/native-query-examples"
    assert app.context.textFormat == "text-orig-full"
