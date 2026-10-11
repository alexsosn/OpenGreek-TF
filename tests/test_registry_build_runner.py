"""RED-first subprocess isolation of native TF writer from source verifier (#52)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opengreek_tf.native_composer import read_native_records, validate_native_records
from opengreek_tf.registry_build_runner import (
    RegistryBuildError,
    run_isolated_registry_build,
)
from opengreek_tf.registry_materializer import iter_native_registry
from opengreek_tf.tf_integrity import native_tf_manifest


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "upstream source with spaces"
    path = root / "data" / "source_registry.json"
    path.parent.mkdir(parents=True)
    record = {
        "authors": {
            "a": {"name": "Ἀ", "aliases": {"wikidata": "Q123"}},
            "b": {"name": "Β", "aliases": {}},
        },
        "works": {
            "a.first": {
                "author": "a",
                "title": "Ἄλφα",
                "aliases": {},
                "default_edition": None,
                "best_source": "locked",
                "tags": ["genre:history", "genre:history"],
                "editions": {
                    "a.first.ed": {
                        "name": "", "provider": "test", "scheme": "",
                        "editor": "", "year": None, "source": "",
                        "servable": False, "license": "",
                        "scheme_inferred": False, "aliases": {},
                    },
                },
            },
        },
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return root


def test_native_registry_child_isolation_preserves_all_source_facts(
    source: Path, tmp_path: Path,
) -> None:
    expected = tuple(iter_native_registry(source))
    destination = tmp_path / "native TF with spaces"
    report = run_isolated_registry_build(source, destination)
    assert report["pid"] != os.getpid()
    assert report["stats"] == {
        "records": 3, "metadata_records": 3, "text_records": 0,
        "source_atoms": 3, "fact_nodes": 26,
    }
    assert report["peak_rss_mib"] > 0
    assert report["build_seconds"] >= 0
    assert [step["phase"] for step in report["phases"]] == [
        "registry-input-loaded", "preflight-complete",
        "walk-complete", "load-validated",
    ]
    assert all(step["live_rss_mib"] > 0 for step in report["phases"])
    restored = read_native_records(destination)
    assert restored == expected
    assert report["canonical_sha256"] == (
        native_tf_manifest(destination).canonical_sha256
    )
    assert validate_native_records(expected, destination).records == 3


def test_separate_native_builds_are_canonical_source_identical(
    source: Path, tmp_path: Path,
) -> None:
    first = run_isolated_registry_build(source, tmp_path / "one")
    second = run_isolated_registry_build(source, tmp_path / "two")
    assert first["canonical_sha256"] == second["canonical_sha256"]
    assert first["stats"] == second["stats"]
    assert first["pid"] != os.getpid()
    assert second["pid"] != os.getpid()


def test_invalid_late_source_fails_before_output_and_bubbles_child_error(
    source: Path, tmp_path: Path,
) -> None:
    path = source / "data" / "source_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["works"]["a.first"]["author"] = "unknown"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "native"
    with pytest.raises(RegistryBuildError, match="failed"):
        run_isolated_registry_build(source, out)
    assert not out.exists()


def test_existing_output_is_not_overwritten_by_subprocess(
    source: Path, tmp_path: Path,
) -> None:
    dest = tmp_path / "native"
    dest.mkdir()
    (dest / "sentinel.txt").write_text("untouched", encoding="utf-8")
    with pytest.raises(RegistryBuildError, match="failed"):
        run_isolated_registry_build(source, dest)
    assert (dest / "sentinel.txt").read_text(encoding="utf-8") == "untouched"
