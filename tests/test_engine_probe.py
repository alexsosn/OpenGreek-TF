"""RED-first real-native TF engine-equivalence probe (#13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.engine_probe import main, probe_native
from opengreek_tf.primary_materializer import materialize_primary


@pytest.fixture
def native(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    corpus = source / "data" / "corpus"
    corpus.mkdir(parents=True)
    records = [
        {"urn": "not-cts:one", "edition": "α", "locus": "I",
         "source": "tei", "license": "CC0", "text": "λόγος  ἀνήρ\n",
         "corrections": ["α", "α"], "dfhg_flag": False},
        {"urn": "not-cts:two", "edition": "β", "locus": "2",
         "source": "ocr", "license": "CC0", "text": ""},
    ]
    (corpus / "sample.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    out = tmp_path / "generated native"
    stats = materialize_primary(source, ("data/corpus/sample.jsonl",), out)
    assert stats.text_records == 2
    return out


def test_reference_probe_conserves_native_features_relations_and_greek_text(
    native: Path,
) -> None:
    result = probe_native(native, engine="tf")
    assert result.engine == "tf"
    assert result.passages == 2
    assert result.metadata_records == 0
    assert result.fact_nodes > 10
    assert result.atoms >= 3
    assert result.nodes == result.passages + result.fact_nodes + result.atoms
    assert len(result.canonical_sha256) == 64
    assert result.load_seconds >= 0
    assert result.peak_rss_mib > 0
    assert result.cache_bytes >= 0
    assert result.canonical_sha256 == probe_native(native, engine="tf").canonical_sha256


def test_probe_digest_changes_when_original_greek_changes(tmp_path: Path) -> None:
    def build(text: str, destination: str) -> Path:
        source = tmp_path / ("source" + destination)
        corpus = source / "data" / "corpus"
        corpus.mkdir(parents=True)
        (corpus / "sample.jsonl").write_text(
            json.dumps({
                "urn": "u", "edition": "e", "locus": "1",
                "source": "tei", "license": "CC0", "text": text,
            }, ensure_ascii=False) + "\n", encoding="utf-8",
        )
        out = tmp_path / destination
        materialize_primary(source, ("data/corpus/sample.jsonl",), out)
        return out
    assert probe_native(build("λόγος", "a"), engine="tf").canonical_sha256 != (
        probe_native(build("λογος", "b"), engine="tf").canonical_sha256
    )


def test_probe_command_outputs_parseable_report(
    native: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--engine", "tf", "--corpus", str(native)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["engine"] == "tf"
    assert report["passages"] == 2
    assert report["canonical_sha256"] == probe_native(
        native, engine="tf",
    ).canonical_sha256


def test_probe_rejects_missing_corpus_or_bad_engine(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        probe_native(tmp_path / "missing", engine="tf")
    with pytest.raises(ValueError):
        probe_native(tmp_path, engine="invisible")
