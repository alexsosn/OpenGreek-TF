"""RED-first native Fabric source-row streaming and end-of-input validation (#71)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

import opengreek_tf.native_composer as composer
from opengreek_tf.native_composer import (
    NativeComposeError,
    NativeRecord,
    iter_native_records,
    read_native_records,
    validate_native_records,
    write_native_records,
)
from opengreek_tf.fact_graph import restore_fact_fields
from opengreek_tf.record_stream import FieldArray, FieldObject


@pytest.fixture
def ordered_records() -> tuple[NativeRecord, ...]:
    return (
        NativeRecord(
            "data/source_registry.json#authors", 1, "ancient.author",
            "registry-author",
            FieldObject((("name", "Σωκράτης"), ("links", FieldArray((None, 0, False))))),
        ),
        NativeRecord(
            "data/corpus/p.jsonl", 1, "data/corpus/p.jsonl:1",
            "primary-passage",
            FieldObject((("text", "λόγος  ἀνήρ\n"), ("flag", False))),
            text="λόγος  ἀνήρ\n",
        ),
        NativeRecord(
            "data/source_registry.json#works", 1, "ancient.work",
            "registry-work",
            FieldObject((("edition", None), ("nested", FieldObject((("a", 0),))))),
        ),
        NativeRecord(
            "data/corpus_secondary/s.jsonl", 1, "data/corpus_secondary/s.jsonl:1",
            "secondary-witness",
            FieldObject((("text", "ἄλλος"), ("multiplicity", FieldArray(("x", "x"))))),
        ),
    )


def test_native_stream_preserves_mixed_original_sequence(
    tmp_path: Path, ordered_records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "tf"
    write_native_records(ordered_records, out)
    assert tuple(iter_native_records(out)) == ordered_records
    assert read_native_records(out) == ordered_records


def test_native_reader_restores_one_record_at_a_time(
    tmp_path: Path, ordered_records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "tf"
    write_native_records(ordered_records, out)
    calls = 0
    original_restore = restore_fact_fields

    def measured(*args: object, **kwargs: object) -> FieldObject:
        nonlocal calls
        calls += 1
        return original_restore(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(composer, "restore_fact_fields", measured)
    iterator = iter_native_records(out)
    assert calls == 0
    assert next(iterator) == ordered_records[0]
    assert calls == 1, "native iterator must not reconstruct all source records upfront"
    assert tuple(iterator) == ordered_records[1:]
    assert calls == len(ordered_records)


def test_writer_and_public_validator_do_not_allocate_full_loaded_tuple(
    tmp_path: Path, ordered_records: tuple[NativeRecord, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("writer must compare the independent native stream, not a full loaded tuple")

    monkeypatch.setattr(composer, "read_native_records", forbidden)
    out = tmp_path / "tf"
    stats = write_native_records(ordered_records, out)
    assert validate_native_records(ordered_records, out) == stats


def test_stream_fails_at_exhaustion_on_forged_known_feature(
    tmp_path: Path, ordered_records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "tf"
    write_native_records(ordered_records, out)
    fabric = Fabric(locations=str(out), silent="deep")
    api = fabric.load("source_file", silent="deep")
    assert api
    fact = api.F.otype.s("sourceFact")[0]
    values = dict(api.F.source_file.items())
    values[fact] = "forged/not-an-original-source.jsonl"
    assert fabric.save(
        nodeFeatures={"source_file": values},
        metaData={"source_file": {"valueType": "str"}},
        silent="deep",
    )
    iterator = iter_native_records(out)
    assert next(iterator) == ordered_records[0]
    with pytest.raises(NativeComposeError, match="placement"):
        tuple(iterator)
    with pytest.raises(NativeComposeError, match="placement"):
        read_native_records(out)
