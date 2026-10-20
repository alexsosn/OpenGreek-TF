"""RED-first regression gates for bounded-memory native TF composition (#52)."""

from __future__ import annotations

import gc
import weakref
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tf.convert.walker import CV  # type: ignore[import-untyped]

import opengreek_tf.native_composer as composer
from opengreek_tf.fact_graph import FactGraph, build_fact_graph
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

    def tracked(value: tuple[NativeRecord, ...]) -> tuple[NativeStats, set[str]]:
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
    # Track actual FactGraphs at their construction site; there is no longer
    # a retained _preflight graph tuple to wrap or extend.
    class TrackedGraph(FactGraph):
        __slots__ = ("__weakref__",)

    tracked: list[weakref.ReferenceType[TrackedGraph]] = []
    original_build = build_fact_graph
    original_reader = composer.read_native_records

    def track_build(record: NativeRecord) -> FactGraph:
        g = original_build(record)
        tracked_graph = TrackedGraph(
            g.occurrence_key, g.nodes, g.declared_size, g.digest,
        )
        tracked.append(weakref.ref(tracked_graph))
        return tracked_graph

    def independent_reader(destination: Path) -> tuple[NativeRecord, ...]:
        gc.collect()
        assert len(tracked) >= len(records)
        assert all(ref() is None for ref in tracked), (
            "source fact graphs should not coexist with heavy independent Fabric reload"
        )
        return original_reader(destination)

    monkeypatch.setattr(composer, "build_fact_graph", track_build)
    monkeypatch.setattr(composer, "read_native_records", independent_reader)
    out = tmp_path / "native"
    assert write_native_records(records, out).records == 2
    assert original_reader(out) == records


def test_postwrite_conservation_rejects_bool_int_equal_values(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_iterator = composer.iter_native_records
    original_fields = records[0].fields
    forged_fields = FieldObject(tuple(
        (key, 0 if key == "available" else value)
        for key, value in original_fields.items
    ))
    # This exposes the exact typed-integrity bug in native dataclass equality.
    assert forged_fields == original_fields
    assert type(forged_fields.require("available")) is int
    assert type(original_fields.require("available")) is bool

    def forged_loader(path: Path) -> Iterator[NativeRecord]:
        for index, record in enumerate(original_iterator(path)):
            yield replace(record, fields=forged_fields) if index == 0 else record

    # The writer must detect a forged type even when source records are
    # independently yielded one at a time rather than materialized in a tuple.
    monkeypatch.setattr(composer, "iter_native_records", forged_loader)
    out = tmp_path / "forged"
    with pytest.raises(NativeComposeError, match="conservation"):
        write_native_records(records, out)
    assert out.exists()
    # The public independent validator must also reject the same forged data.
    with pytest.raises(NativeComposeError, match="conservation"):
        validate_native_records(records, out)


def test_writer_releases_each_preflight_graph_before_cv_walk(
    tmp_path: Path,
    records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every preflight FactGraph must be dead at native CV entry.

    The real CV.walk executes, and the test instruments graph construction
    directly instead of assuming preflight returns a full graph collection.
    """
    class TrackedGraph(FactGraph):
        __slots__ = ("__weakref__",)

    refs: list[weakref.ReferenceType[TrackedGraph]] = []
    original_build = build_fact_graph
    original_walk = CV.walk

    def tracked_build(record: NativeRecord) -> FactGraph:
        graph = original_build(record)
        tracked = TrackedGraph(
            graph.occurrence_key, graph.nodes, graph.declared_size, graph.digest,
        )
        refs.append(weakref.ref(tracked))
        return tracked

    def inspected_walk(self: Any, *args: Any, **kwargs: Any) -> Any:
        gc.collect()
        assert len(refs) == len(records)
        assert all(ref() is None for ref in refs), (
            "a preflight FactGraph is retained during native TF conversion"
        )
        return original_walk(self, *args, **kwargs)

    monkeypatch.setattr(composer, "build_fact_graph", tracked_build)
    monkeypatch.setattr(CV, "walk", inspected_walk)
    out = tmp_path / "native"
    assert write_native_records(records, out).records == len(records)
    assert read_native_records(out) == records
