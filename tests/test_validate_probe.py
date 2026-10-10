"""RED-first adversarial tests for independent raw-JSONL to loaded-TF checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.mini_writer import write_primary_probe
from opengreek_tf.record_stream import parse_file
from opengreek_tf.validate_probe import ProbeValidationError, validate_primary_probe


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "upstream"
    rel = "data/corpus/test-work.jsonl"
    source = root / rel
    source.parent.mkdir(parents=True)
    rows = [
        {
            "urn": "test-work",
            "edition": "grc",
            "source": "tei",
            "license": "CC-BY-SA-4.0",
            "locus": "1",
            "page": 7,
            "text": "  λόγος\tκόσμος\n",
        },
        {
            "urn": "test-work",
            "edition": "grc",
            "source": "tei",
            "license": "CC-BY-SA-4.0",
            "locus": "1",
            "text": "",
        },
        {
            "urn": "test-work",
            "edition": "grc",
            "source": "tei",
            "license": "CC-BY-SA-4.0",
            "locus": "2",
            "text": "α\u0301  ἕτερον",
        },
    ]
    source.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    dest = tmp_path / "tf"
    write_primary_probe(list(parse_file(root, rel)), dest)
    return root, dest, rel


def _corrupt_feature(dest: Path, name: str, old: str, new: str) -> None:
    path = dest / f"{name}.tf"
    content = path.read_text(encoding="utf-8")
    assert old in content, f"test corruption target missing in {name}"
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def test_independent_validator_accepts_exact_loaded_graph(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    report = validate_primary_probe(root, rel, dest, record_count=3)
    assert report.passage_count == 3
    assert report.text_codepoints == len("  λόγος\tκόσμος\n") + len("α\u0301  ἕτερον")


def test_validator_detects_corrupt_native_text(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    _corrupt_feature(dest, "form", "λόγος", "βῆτα")
    with pytest.raises(ProbeValidationError, match="text"):
        validate_primary_probe(root, rel, dest, record_count=3)


def test_validator_detects_corrupt_scalar_metadata(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    _corrupt_feature(dest, "src_license", "CC-BY-SA-4.0", "CC-BY-4.0")
    with pytest.raises(ProbeValidationError, match="src_license"):
        validate_primary_probe(root, rel, dest, record_count=3)


def test_validator_detects_dropped_or_reordered_source_rows(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    source = root / rel
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    source.write_text("".join([lines[2], lines[1], lines[0]]), encoding="utf-8")
    with pytest.raises(ProbeValidationError):
        validate_primary_probe(root, rel, dest, record_count=3)


def test_validator_rejects_unrepresented_nested_source_facts(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    source = root / rel
    lines = source.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["provenance"] = {"method": "manual"}
    lines[0] = json.dumps(first, ensure_ascii=False)
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ProbeValidationError, match="unsupported"):
        validate_primary_probe(root, rel, dest, record_count=3)


def test_validator_rejects_extra_or_missing_passages(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    with pytest.raises(ProbeValidationError, match="passage count"):
        validate_primary_probe(root, rel, dest, record_count=2)


def test_validator_rejects_duplicate_source_json_keys(tmp_path: Path) -> None:
    root, dest, rel = _fixture(tmp_path)
    source = root / rel
    data = source.read_text(encoding="utf-8")
    source.write_text(
        data.replace('"locus": "1"', '"locus": "1", "locus": "2"', 1),
        encoding="utf-8",
    )
    with pytest.raises(ProbeValidationError, match="duplicate"):
        validate_primary_probe(root, rel, dest, record_count=3)
