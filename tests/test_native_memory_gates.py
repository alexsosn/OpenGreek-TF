"""RED-first regression gates for bounded-memory native TF composition (#52)."""

from __future__ import annotations

from pathlib import Path

import pytest

import opengreek_tf.native_composer as composer
from opengreek_tf.native_composer import (
    NativeRecord,
    NativeStats,
    read_native_records,
    validate_native_records,
    write_native_records,
)
from opengreek_tf.record_stream import FieldArray, FieldObject
from opengreek_tf.tf_integrity import native_tf_manifest


@pytest.fixture
def records() -> tuple[NativeRecord, ...]:
    return (
        NativeRecord(
            "data/source_registry.json#works", 1, "a.first", "registry-work",
            FieldObject((
                ("title", "Ἄλφα"), ("default_edition", None),
                ("tags", FieldArray(("A", "", "A"))),
                ("year", -412), ("available", False),
            )),
        ),
        NativeRecord(
            "data/corpus/a.jsonl", 1, "a:1", "primary-passage",
            FieldObject((
                ("text", "Ἀβ γδ\t\n"),
                ("nested", FieldObject((
                    ("names", FieldArray(("ἀβ", "ἀβ"))),
                    ("unknown", None),
                ))),
            )),
            text="Ἀβ γδ\t\n",
        ),
    )


def test_writer_preflights_once_but_retains_full_loaded_validation(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = composer._preflight

    def tracked(value: tuple[NativeRecord, ...]) -> tuple[composer.FactGraph, ...]:
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(composer, "_preflight", tracked)
    dest = tmp_path / "native"
    stats = write_native_records(records, dest)
    assert stats == NativeStats(2, 1, 1, 2, stats.fact_nodes)
    assert calls == 1, "the writer must not allocate a second full graph set"
    assert read_native_records(dest) == records

    # The public external validator still independently preflights its input.
    assert validate_native_records(records, dest) == stats
    assert calls == 2


def test_opt_in_lifecycle_metrics_without_source_fact_mutation(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    stages: list[str] = []
    with_hook = tmp_path / "observed"
    base = tmp_path / "plain"
    expected = write_native_records(records, with_hook, on_phase=stages.append)
    assert stages == ["preflight-complete", "walk-complete", "load-validated"]
    assert read_native_records(with_hook) == records
    assert write_native_records(records, base) == expected
    assert native_tf_manifest(with_hook).canonical_sha256 == (
        native_tf_manifest(base).canonical_sha256
    )


def test_empty_and_invalid_records_do_not_emit_phase_or_partial_output(
    tmp_path: Path,
) -> None:
    observed: list[str] = []
    invalid = (NativeRecord(
        "data/corpus/a.jsonl", 1, "a", "primary-passage",
        FieldObject((("text", "α\rβ"),)), text="α\rβ",
    ),)
    with pytest.raises(ValueError):
        write_native_records(invalid, tmp_path / "broken", on_phase=observed.append)
    assert observed == []
    assert not (tmp_path / "broken").exists()
