"""RED-first replayable original-record native TF writer contract (#75)."""

from __future__ import annotations

import gc
import json
import weakref
from collections.abc import Iterator
from pathlib import Path

import pytest

import opengreek_tf.text_materializer as texts
from opengreek_tf.native_composer import (
    NativeComposeError,
    NativeRecord,
    read_native_records,
    write_native_record_factory,
    write_native_records,
)
from opengreek_tf.record_stream import FieldArray, FieldObject
from opengreek_tf.text_materializer import materialize_texts
from opengreek_tf.tf_integrity import native_tf_manifest


def _record(ordinal: int, *, text: str = "λόγος  ἀνήρ\n") -> NativeRecord:
    return NativeRecord(
        "data/corpus/a.jsonl", ordinal, f"work:{ordinal}",
        "primary-passage",
        FieldObject((
            ("text", text),
            ("nested", FieldArray((None, False, 0, "", "ἀνήρ", "ἀνήρ"))),
        )),
        text=text,
    )


def test_factory_replays_three_independent_passes_and_never_retains_all_inputs(
    tmp_path: Path,
) -> None:
    """Each source row can be collected before the next; TF stays real."""
    class Tracked(NativeRecord):
        __slots__ = ("__weakref__",)

    factory_calls = 0
    live: weakref.WeakSet[Tracked] = weakref.WeakSet()
    maximum = 0

    def original_rows() -> Iterator[NativeRecord]:
        nonlocal factory_calls, maximum
        factory_calls += 1
        for i in range(1, 49):
            base = _record(i)
            record = Tracked(
                base.source_file, base.ordinal, base.source_record_id,
                base.record_kind, base.fields, base.text,
            )
            live.add(record)
            maximum = max(maximum, len(live))
            yield record

    dest = tmp_path / "native"
    stats = write_native_record_factory(original_rows, dest)
    assert stats.records == stats.text_records == 48
    assert factory_calls == 3
    assert maximum <= 2, f"retained {maximum} source-record objects"
    gc.collect()
    assert not live
    assert read_native_records(dest) == tuple(_record(i) for i in range(1, 49))


def test_preflight_rejects_invalid_final_stream_record_before_output(
    tmp_path: Path,
) -> None:
    def rows() -> Iterator[NativeRecord]:
        for i in range(1, 17):
            yield _record(i)
        yield _record(17, text="ἄκυρον\rτέλος")

    out = tmp_path / "invalid"
    with pytest.raises(NativeComposeError, match="carriage return"):
        write_native_record_factory(rows, out)
    assert not out.exists()


def test_replayed_input_that_mutates_after_preflight_is_rejected(
    tmp_path: Path,
) -> None:
    calls = 0

    def rows() -> Iterator[NativeRecord]:
        nonlocal calls
        calls += 1
        yield _record(1, text="λόγος" if calls == 1 else "λόγοι")
        yield _record(2)

    with pytest.raises(NativeComposeError, match="changed|preflight|replay"):
        write_native_record_factory(rows, tmp_path / "mutated")
    assert calls >= 2


def test_eager_public_writer_and_replayable_writer_have_identical_native_tf(
    tmp_path: Path,
) -> None:
    records = (_record(1, text=""), _record(2, text="ἀρχή  τέλος\n"))
    eager = tmp_path / "old"
    replay = tmp_path / "new"
    a = write_native_records(records, eager)
    b = write_native_record_factory(lambda: iter(records), replay)
    assert a == b
    assert native_tf_manifest(eager).canonical_sha256 == (
        native_tf_manifest(replay).canonical_sha256
    )
    assert read_native_records(replay) == records


def test_text_materializer_uses_replayable_source_instead_of_eager_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "original"
    primary = "data/corpus/primary.jsonl"
    witness = "data/corpus_secondary/secondary.jsonl"
    for name, row in (
        (primary, {"urn": "u", "locus": "1", "edition": "ed",
                   "source": "s", "license": "CC0", "text": "ἀρχή  τέλος"}),
        (witness, {"urn": "u", "locus": "1", "edition": "ed",
                   "source": "s", "license": "CC0", "text": "αλλο",
                   "rank": "secondary", "secondary_reason": "replaced"}),
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("text-family CLI must not materialize an all-record tuple")

    monkeypatch.setattr(texts, "write_native_records", forbidden, raising=False)
    dest = tmp_path / "mixed"
    actual = materialize_texts(root, (primary, witness), dest)
    assert actual.records == 2
    native = read_native_records(dest)
    assert [row.record_kind for row in native] == [
        "primary-passage", "secondary-witness",
    ]
    assert native[0].text == "ἀρχή  τέλος"
    assert native[1].fields.require("text") == "αλλο"



@pytest.mark.parametrize("changed_text", ["λόγοι", None])
def test_replay_refuses_layout_text_mutation_with_unchanged_typed_source_fact(
    tmp_path: Path, changed_text: str | None,
) -> None:
    """Layout must not drift from its independently preserved source fact."""
    from dataclasses import replace

    calls = 0
    unchanged = _record(1)

    def rows() -> Iterator[NativeRecord]:
        nonlocal calls
        calls += 1
        if calls == 1:
            yield unchanged
        else:
            # All typed source fields, source ids and graph digest are unchanged.
            yield replace(unchanged, text=changed_text)

    with pytest.raises(
        NativeComposeError, match="changed between preflight|source passage text differs",
    ):
        write_native_record_factory(rows, tmp_path / "layout-drift")
    assert calls >= 2



def test_third_source_replay_cannot_change_original_typed_facts_after_writing(
    tmp_path: Path,
) -> None:
    calls = 0

    def rows() -> Iterator[NativeRecord]:
        nonlocal calls
        calls += 1
        yield _record(1, text="ἀρχή" if calls < 3 else "ἄκρη")

    with pytest.raises(NativeComposeError, match="conservation"):
        write_native_record_factory(rows, tmp_path / "modified-third-pass")
    assert calls == 3


def test_single_use_source_iterator_is_rejected_not_mistaken_for_empty_replay(
    tmp_path: Path,
) -> None:
    source = iter((_record(1),))
    with pytest.raises(NativeComposeError, match="changed between preflight"):
        write_native_record_factory(lambda: source, tmp_path / "single-use")
