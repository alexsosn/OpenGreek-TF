"""RED-first regression gates for bounded-memory native TF composition (#52)."""

from __future__ import annotations

import gc
import weakref
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tf.convert.walker import CV  # type: ignore[import-untyped]

import opengreek_tf.native_composer as composer
from opengreek_tf.fact_graph import FactGraph
from opengreek_tf.native_composer import (
    NativeComposeError,
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

    def tracked(value: tuple[NativeRecord, ...]) -> tuple[FactGraph, ...]:
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


def test_writer_releases_preflight_graphs_before_independent_fabric_load(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Emulate weakref-capable immutable graphs to establish object lifetime.
    # This tests retained references rather than assuming peak RSS decreases.
    class TrackedGraph(FactGraph):
        __slots__ = ("__weakref__",)

    tracked: list[weakref.ReferenceType[TrackedGraph]] = []
    original_preflight = composer._preflight
    original_reader = composer.read_native_records

    def preflight(value: tuple[NativeRecord, ...]) -> tuple[FactGraph, ...]:
        graphs = original_preflight(value)
        converted = tuple(
            TrackedGraph(g.occurrence_key, g.nodes, g.declared_size, g.digest)
            for g in graphs
        )
        tracked.extend(weakref.ref(g) for g in converted)
        return converted

    def independent_reader(destination: Path) -> tuple[NativeRecord, ...]:
        gc.collect()
        assert tracked and all(ref() is None for ref in tracked), (
            "preflight graph objects should not coexist with the heavy "
            "independent Text-Fabric reload"
        )
        return original_reader(destination)

    monkeypatch.setattr(composer, "_preflight", preflight)
    monkeypatch.setattr(composer, "read_native_records", independent_reader)
    out = tmp_path / "native"
    assert write_native_records(records, out).records == 2
    assert original_reader(out) == records


def test_postwrite_conservation_rejects_bool_int_equal_values(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_reader = composer.read_native_records
    original_fields = records[0].fields
    forged_fields = FieldObject(tuple(
        (key, 0 if key == "available" else value)
        for key, value in original_fields.items
    ))
    # This exposes the exact typed-integrity bug in native dataclass equality.
    assert forged_fields == original_fields
    assert type(forged_fields.require("available")) is int
    assert type(original_fields.require("available")) is bool

    def forged_loader(path: Path) -> tuple[NativeRecord, ...]:
        loaded = original_reader(path)
        return (replace(loaded[0], fields=forged_fields), *loaded[1:])

    monkeypatch.setattr(composer, "read_native_records", forged_loader)
    out = tmp_path / "forged"
    with pytest.raises(NativeComposeError, match="conservation"):
        write_native_records(records, out)
    assert out.exists()
    # The public independent validator must also reject the same forged data.
    with pytest.raises(NativeComposeError, match="conservation"):
        validate_native_records(records, out)


def test_writer_releases_complete_preflight_graph_set_before_cv_walk(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED: source-checked FactGraphs must not remain held during heavy CV walk.

    Actual TF conversion is still exercised; check object liveness at its
    entry point, independently of allocator/RSS noise and phase callbacks.
    """
    class TrackedGraph(FactGraph):
        __slots__ = ("__weakref__",)

    refs: list[weakref.ReferenceType[TrackedGraph]] = []
    original_preflight = composer._preflight
    original_walk = CV.walk

    def tracked_preflight(value: tuple[NativeRecord, ...]) -> tuple[FactGraph, ...]:
        graphs = original_preflight(value)
        wrapped = tuple(
            TrackedGraph(g.occurrence_key, g.nodes, g.declared_size, g.digest)
            for g in graphs
        )
        refs.extend(weakref.ref(g) for g in wrapped)
        return wrapped

    def inspected_walk(self: Any, *args: Any, **kwargs: Any) -> Any:
        gc.collect()
        assert len(refs) == len(records)
        assert all(ref() is None for ref in refs), (
            "the entire preflight FactGraph set is retained during TF conversion"
        )
        return original_walk(self, *args, **kwargs)

    monkeypatch.setattr(composer, "_preflight", tracked_preflight)
    monkeypatch.setattr(CV, "walk", inspected_walk)
    out = tmp_path / "native"
    assert write_native_records(records, out).records == len(records)
    assert read_native_records(out) == records
