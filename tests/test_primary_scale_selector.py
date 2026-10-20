"""RED-first whole-source-file scale-rung selection contract (#13)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from opengreek_tf.text_materializer import select_whole_primary_rung


@pytest.fixture
def originals(tmp_path: Path) -> Path:
    root = tmp_path / "originals"
    corpus = root / "data" / "corpus"
    corpus.mkdir(parents=True)
    for label, rows in (("b", 3), ("a", 2), ("c", 4)):
        (corpus / f"{label}.jsonl").write_text(
            "".join(json.dumps({
                "urn": label, "locus": str(i), "edition": "e",
                "source": "tei", "license": "CC0", "text": "λ",
            }) + "\n" for i in range(rows)),
            encoding="utf-8",
        )
    return root


def test_rung_uses_complete_sorted_source_files_with_measured_row_count(
    originals: Path,
) -> None:
    selection = select_whole_primary_rung(
        originals, minimum_rows=4, maximum_rows=6,
    )
    assert selection.files == (
        "data/corpus/a.jsonl", "data/corpus/b.jsonl",
    )
    assert selection.primary_rows == 5
    assert selection.file_count == 2


def test_rung_rejects_overshoot_instead_of_truncating_original_text(
    originals: Path,
) -> None:
    with pytest.raises(ValueError, match="maximum|bound"):
        select_whole_primary_rung(originals, minimum_rows=4, maximum_rows=4)


def test_rung_rejects_insufficient_original_rows(
    originals: Path,
) -> None:
    with pytest.raises(ValueError, match="minimum|insufficient"):
        select_whole_primary_rung(originals, minimum_rows=10, maximum_rows=15)


@pytest.mark.parametrize("minimum,maximum", [
    (0, 10), (-1, 4), (6, 5), (True, 10), (1.2, 10),
])
def test_rung_rejects_invalid_size_limits(
    originals: Path, minimum: object, maximum: object,
) -> None:
    with pytest.raises(ValueError):
        select_whole_primary_rung(
            originals, minimum_rows=minimum, maximum_rows=maximum,  # type: ignore[arg-type]
        )


def test_rung_fails_closed_on_zero_row_original_before_reaching_target(
    originals: Path,
) -> None:
    (originals / "data/corpus/a.jsonl").write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        select_whole_primary_rung(originals, minimum_rows=3, maximum_rows=9)


def test_rung_rejects_duplicate_physical_source_alias(
    originals: Path,
) -> None:
    original = originals / "data/corpus/a.jsonl"
    alias = originals / "data/corpus/aa.jsonl"
    try:
        os.link(original, alias)
    except OSError as exc:
        pytest.skip(f"filesystem has no hardlinks: {exc}")
    with pytest.raises(ValueError, match="duplicate"):
        select_whole_primary_rung(originals, minimum_rows=4, maximum_rows=12)


def test_rung_refuses_symlinked_source_and_missing_source_dir(
    originals: Path, tmp_path: Path,
) -> None:
    original = originals / "data/corpus/a.jsonl"
    alias = originals / "data/corpus/aa.jsonl"
    try:
        alias.symlink_to(original)
    except OSError as exc:
        pytest.skip(f"filesystem has no symlinks: {exc}")
    with pytest.raises(ValueError, match="symlink"):
        select_whole_primary_rung(originals, minimum_rows=4, maximum_rows=12)
    with pytest.raises(ValueError, match="directory"):
        select_whole_primary_rung(tmp_path / "missing", minimum_rows=1, maximum_rows=2)
