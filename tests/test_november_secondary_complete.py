"""RED-first November 2026 complete secondary source grammar and native fidelity.

Authentic shapes from the immutable publishing commit 122f2cba907dbac0...
and its complete 338,245-row secondary JSONL source census (#88).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from opengreek_tf.fact_graph import build_fact_graph, restore_fact_fields
from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import read_native_records
from opengreek_tf.record_stream import FieldArray, FieldObject, RecordParseError, parse_file
from opengreek_tf.release import NOVEMBER_RELEASE
from opengreek_tf.text_materializer import materialize_texts
from opengreek_tf.tf_integrity import native_tf_manifest

DUBNER = "data/corpus_secondary/scholia-in-aristophanem.triclinius-meters-dubner-1855.jsonl"
PIN = "data/corpus_secondary/vitae-pindari-et-varia-de-pindaro.vita-metrica.jsonl"
CYRIL = "data/corpus_secondary/cyrillus-theology.commentarii-in-joannem.reviewed-duplicate-witnesses.jsonl"
HESYCHIUS = "data/corpus_secondary/hesychius-lexicography.lexicon-o.missing-columns-witnesses.jsonl"

BASE = {
    "urn": "scholia-in-aristophanem.triclinius-meters-dubner-1855",
    "edition": "dubner-1855-legacy-witnesses",
    "locus": "scholia_aristoph_dubner_0040.2",
    "source": "ocr",
    "license": "PD",
    "text": "τὸ μὲν πρῶτον",
}
TARGET = {
    "slug": "cyrillus-theology.commentarii-in-joannem",
    "path": "data/corpus/cyrillus-theology.commentarii-in-joannem.jsonl",
    "locus": "reviewed-duplicate.PG073.483",
}
DUBNER_ROW = {
    **BASE,
    "original_locus": "scholia_aristoph_dubner_0040.2",
    "original_work": "scholia-in-aristophanem.scholia-in-acharnenses-scholia-vetera-et-recentiora-triclinii",
    "original_edition": "qwen36-scholia_aristoph_dubner-masked",
    "source_char_range": [0, 1338],
    "source_role": "historical-prolegomena",
    "source_role_evidence": "toronto-pdf-0040",
    "witness_group": "dubner-1855-toronto",
    "source_pdf_page": 40,
    "dubner_source_scope": {
        "authority": "data/corpus_changes/dubner-1855-scope/changes.json",
    },
}
CYRIL_ROW = {
    **BASE,
    "cts": "urn:cts:greekLit:tlg4090.tlg002",
    "source_role": "literal-duplicate-reading",
    "source_role_evidence": "Two markers repeat one leaf",
    "evidence": "data/corpus_changes/cyril-john-coverage/changes.json",
    "source_location": {
        "volume": "PG073", "marker_page": "483", "start_line": "1",
    },
    "current_target": TARGET,
    "reviewed_duplicate_witness": {
        "authority": "data/corpus_changes/reviewed-duplicate-blocks/changes.json",
        "key": "cyril:PG073.483",
    },
}
PIN_ROW = {
    **BASE,
    "text_lines": ["Πίνδαρον", "γείνατο"],
    "original_urn": "tlg4170.tlg001c",
    "original_locus": "1",
    "original_edition": "1st1K-grc1",
    "original_row": {
        "urn": "tlg4170.tlg001c",
        "edition": "1st1K-grc1",
        "locus": "1",
        "source": "first1k",
        "license": "CC-BY-SA-4.0",
        "text": "Πίνδαρον γείνατο",
        "text_lines": ["Πίνδαρον", "γείνατο"],
    },
    "source_role": "literal-duplicate-serialization",
    "pindar_duplicate_review": {
        "authority": "data/corpus_changes/pindar-duplicate-primaries/changes.json",
    },
    "canonical_target": {
        "slug": "vitae-pindari-et-varia-de-pindaro.vita-metrica",
        "path": "data/corpus/vitae-pindari-et-varia-de-pindaro.vita-metrica.jsonl",
        "locus": "1",
    },
    "independent_witness": False,
}
HESYCHIUS_ROW = {
    **BASE,
    "source_role": "literal-gap-OCR-witness",
    "source_page": {
        "crop_size": [495, 1149],
        "id": "harvard:259",
        "max_side": 1600,
        "path": "data/corpus_changes/hesychius-missing-columns/source-evidence/harvard-column-259.png",
        "pixel_box": [185, 215, 680, 1364],
        "printed_column": 259,
        "region": [0.14, 0.11, 0.515, 0.698],
        "sha256": "6c9fce9974c7fc073759dd80f44b802b9159ba5291568f721a8094c44ee5565a",
        "source": "harvard",
        "source_page": 151,
    },
    "model": "mlx-community/Qwen3.6-27B-8bit",
    "revision": "c5a593c1475a746e43a543b0a02bd2b357e5745f",
    "vote_group": "qwen36",
    "current_target": {
        "slug": "hesychius-lexicography.lexicon-o",
        "path": "data/corpus/hesychius-lexicography.lexicon-o.jsonl",
        "locus": "schmidt-1867.column-259",
    },
}


def _record(root: Path, rel: str, value: dict[str, object]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


@pytest.mark.parametrize(("name", "source"), [
    (DUBNER, DUBNER_ROW),
    (CYRIL, CYRIL_ROW),
    (PIN, PIN_ROW),
    (HESYCHIUS, HESYCHIUS_ROW),
])
def test_all_november_secondary_editorial_variants_have_source_facts(
    tmp_path: Path, name: str, source: dict[str, object],
) -> None:
    _record(tmp_path, name, source)
    row = next(parse_file(tmp_path, name, identity=NOVEMBER_RELEASE))
    assert row.family == "secondary"
    assert row.occurrence_key == (name, 1)
    assert row.text == source["text"]
    restored = restore_fact_fields(build_fact_graph(row))
    assert restored == row.fields
    with pytest.raises(RecordParseError):
        list(parse_file(tmp_path, name))


def test_float_image_crop_region_keeps_exact_runtime_type(
    tmp_path: Path,
) -> None:
    _record(tmp_path, HESYCHIUS, HESYCHIUS_ROW)
    row = next(parse_file(tmp_path, HESYCHIUS, identity=NOVEMBER_RELEASE))
    source_page = row.fields.require("source_page")
    assert isinstance(source_page, FieldObject)
    region = source_page.require("region")
    assert isinstance(region, FieldArray)
    assert region.items == (0.14, 0.11, 0.515, 0.698)
    assert all(type(value) is float for value in region.items)

    result = tmp_path / "native"
    stats = materialize_texts(
        tmp_path, (HESYCHIUS,), result, identity=NOVEMBER_RELEASE,
    )
    assert stats.records == stats.metadata_records == 1
    loaded = read_native_records(result)
    assert len(loaded) == 1
    loaded_page = loaded[0].fields.require("source_page")
    assert isinstance(loaded_page, FieldObject)
    floats = loaded_page.require("region")
    assert isinstance(floats, FieldArray)
    assert floats.items == region.items
    assert all(type(value) is float for value in floats.items)
    report = validate_native_jsonl_sources(
        tmp_path, (HESYCHIUS,), result, identity=NOVEMBER_RELEASE,
    )
    assert report.records == 1
    assert "fact_float" in set(
        __import__("tf.fabric", fromlist=["Fabric"]).Fabric(
            locations=str(result), silent="deep",
        ).explore(silent="deep")["nodes"]
    )


@pytest.mark.parametrize(("bad_value", "field"), [
    ([0, 0.11, 0.515, 0.698], "region"),
    ([False, 0.11, 0.515, 0.698], "region"),
    (["0.14", 0.11, 0.515, 0.698], "region"),
    ([0.14, 0.11, float("nan"), 0.698], "region"),
    ([0.14, 0.11, float("inf"), 0.698], "region"),
    ([0.14, 0.11, 0.515], "region"),
])
def test_crop_region_never_accepts_forged_or_nonfinite_scalars(
    tmp_path: Path, bad_value: list[object], field: str,
) -> None:
    source = deepcopy(HESYCHIUS_ROW)
    assert isinstance(source["source_page"], dict)
    source["source_page"]["region"] = bad_value
    _record(tmp_path, HESYCHIUS, source)
    with pytest.raises(RecordParseError, match=field):
        list(parse_file(tmp_path, HESYCHIUS, identity=NOVEMBER_RELEASE))


@pytest.mark.parametrize(("field", "changed"), [
    ("source_char_range", [0, "1338"]),
    ("source_char_range", [0]),
    ("dubner_source_scope", {"authority": "ok", "fake": "yes"}),
    ("dubner_source_scope", {"new": "wrong"}),
])
def test_dubner_rejects_forged_boundaries_and_source_authority(
    tmp_path: Path, field: str, changed: object,
) -> None:
    source = deepcopy(DUBNER_ROW)
    source[field] = changed
    _record(tmp_path, DUBNER, source)
    with pytest.raises(RecordParseError, match=field):
        list(parse_file(tmp_path, DUBNER, identity=NOVEMBER_RELEASE))


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda x: x.pop("canonical_target"), "canonical_target"),
    (lambda x: x.pop("original_row"), "original_row"),
    (lambda x: x["original_row"].__setitem__("fabricated", 1), "fabricated"),
    (lambda x: x.__setitem__("independent_witness", 0), "independent_witness"),
])
def test_former_primary_pindar_rejects_incomplete_and_forged_evidence(
    tmp_path: Path, mutate: object, message: str,
) -> None:
    source = deepcopy(PIN_ROW)
    assert callable(mutate)
    mutate(source)
    _record(tmp_path, PIN, source)
    with pytest.raises(RecordParseError, match=message):
        list(parse_file(tmp_path, PIN, identity=NOVEMBER_RELEASE))


def test_version_scoped_four_real_shape_files_become_one_conserved_native_TF(
    tmp_path: Path,
) -> None:
    sources = [(DUBNER, DUBNER_ROW), (PIN, PIN_ROW), (CYRIL, CYRIL_ROW),
               (HESYCHIUS, HESYCHIUS_ROW)]
    for name, source in sources:
        _record(tmp_path, name, source)
    files = tuple(name for name, _ in sources)
    output = tmp_path / "mixed"
    stats = materialize_texts(tmp_path, files, output, identity=NOVEMBER_RELEASE)
    assert stats.records == stats.metadata_records == len(sources)
    assert stats.text_records == 0
    loaded = read_native_records(output)
    assert len(loaded) == 4
    assert [record.source_file for record in loaded] == list(files)
    assert [record.record_kind for record in loaded] == ["secondary-witness"] * 4
    independent = validate_native_jsonl_sources(
        tmp_path, files, output, identity=NOVEMBER_RELEASE,
    )
    assert independent.records == 4
    assert independent.source_fact_nodes == stats.fact_nodes


def test_ordinary_non_float_metadata_keeps_stable_native_semantics(
    tmp_path: Path,
) -> None:
    _record(tmp_path, DUBNER, DUBNER_ROW)
    left, right = tmp_path / "left", tmp_path / "right"
    materialize_texts(tmp_path, (DUBNER,), left, identity=NOVEMBER_RELEASE)
    materialize_texts(tmp_path, (DUBNER,), right, identity=NOVEMBER_RELEASE)
    assert native_tf_manifest(left).canonical_sha256 == (
        native_tf_manifest(right).canonical_sha256
    )
    assert read_native_records(left) == read_native_records(right)
