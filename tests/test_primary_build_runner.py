"""RED-first isolated original Greek primary writer gates (#56)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opengreek_tf.native_composer import read_native_records
from opengreek_tf.primary_build_runner import PrimaryBuildError, run_isolated_primary_build
from opengreek_tf.primary_materializer import iter_native_primary, materialize_primary
from opengreek_tf.tf_integrity import native_tf_manifest


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "root with spaces"
    path = root / "data" / "corpus"
    path.mkdir(parents=True)
    first = [
        {"urn": "t.a", "edition": "e.a", "locus": "1", "source": "tei",
         "license": "CC0", "text": "ἄλφα\n  βῆτα"},
        {"urn": "t.a", "edition": "e.a", "locus": "2", "source": "tei",
         "license": "CC0", "text": "", "text_lines": ["", "a"]},
    ]
    second = [
        {"urn": "t.b", "edition": "e.b", "locus": "1", "source": "glaux",
         "license": "CC-BY", "text": "λόγος\tλόγος", "dfhg_flag": False},
    ]
    for name, data in (("a.jsonl", first), ("b.jsonl", second)):
        (path / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in data),
            encoding="utf-8",
        )
    return root


FILES = ("data/corpus/a.jsonl", "data/corpus/b.jsonl")


def test_isolated_primary_build_uses_different_pid_and_native_source_equality(
    source: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "native with spaces"
    expected = tuple(iter_native_primary(source, FILES))
    report = run_isolated_primary_build(source, FILES, out)
    assert report["pid"] != os.getpid()
    assert report["stats"]["records"] == 3
    assert report["stats"]["text_records"] == 3
    assert report["stats"]["source_atoms"] == 3
    assert report["stats"]["metadata_records"] == 0
    assert report["stats"]["fact_nodes"] >= 20
    assert report["peak_rss_mib"] > 0
    assert report["build_seconds"] >= 0
    assert [entry["phase"] for entry in report["phases"]] == [
        "source-input-loaded", "preflight-complete",
        "walk-complete", "load-validated",
    ]
    assert read_native_records(out) == expected
    assert native_tf_manifest(out).canonical_sha256 == report["canonical_sha256"]


def test_opt_in_primary_phase_hook_does_not_mutate_output(
    source: Path, tmp_path: Path,
) -> None:
    phases: list[str] = []
    materialize_primary(source, FILES, tmp_path / "instrumented", on_phase=phases.append)
    materialize_primary(source, FILES, tmp_path / "plain")
    assert phases == [
        "source-input-loaded", "preflight-complete",
        "walk-complete", "load-validated",
    ]
    assert native_tf_manifest(tmp_path / "instrumented").canonical_sha256 == (
        native_tf_manifest(tmp_path / "plain").canonical_sha256
    )


def test_isolated_primary_is_reproducible_across_separate_child_processes(
    source: Path, tmp_path: Path,
) -> None:
    a = run_isolated_primary_build(source, FILES, tmp_path / "first")
    b = run_isolated_primary_build(source, FILES, tmp_path / "second")
    assert a["canonical_sha256"] == b["canonical_sha256"]


def test_invalid_late_primary_row_fails_before_partial_output(
    source: Path, tmp_path: Path,
) -> None:
    target = source / FILES[-1]
    record = json.loads(target.read_text(encoding="utf-8"))
    record.pop("license")
    target.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    destination = tmp_path / "failed"
    with pytest.raises(PrimaryBuildError, match="failed"):
        run_isolated_primary_build(source, FILES, destination)
    assert not destination.exists()


def test_isolated_primary_does_not_overwrite_existing_output(
    source: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "preexisting"
    out.mkdir()
    (out / "sentinel.txt").write_text("untouched", encoding="utf-8")
    with pytest.raises(PrimaryBuildError, match="failed"):
        run_isolated_primary_build(source, FILES, out)
    assert (out / "sentinel.txt").read_text(encoding="utf-8") == "untouched"


def test_invalid_duplicate_file_selection_cannot_produce_output(
    source: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "duplicate"
    with pytest.raises(PrimaryBuildError, match="failed"):
        run_isolated_primary_build(source, (FILES[0], FILES[0]), out)
    assert not out.exists()
