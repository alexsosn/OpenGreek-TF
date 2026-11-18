"""RED-first native CR-codepoint fact fragments in the normal composer (#29).

The genuine November Gutenberg paratext contains 73 U+000D in source text
fields. These are metadata facts, not ordinary Greek passage slots.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.jsonl_conservation import validate_native_jsonl_sources
from opengreek_tf.native_composer import (
    NativeComposeError,
    NativeRecord,
    read_native_records,
    write_native_records,
)
from opengreek_tf.record_stream import FieldObject
from opengreek_tf.release import NOVEMBER_RELEASE
from opengreek_tf.text_materializer import materialize_texts
from opengreek_tf.tf_integrity import native_tf_manifest

FILE = "data/paratext/gutenberg/32549.jsonl"


def _record(raw: str) -> NativeRecord:
    return NativeRecord(
        source_file=FILE,
        ordinal=1,
        source_record_id=f"{FILE}:1",
        record_kind="paratext-record",
        fields=FieldObject((
            ("locus", "apparatus.1"),
            ("text", raw),
            ("source", "gutenberg"),
            ("source_sha256", "a" * 64),
        )),
        text=None,
    )


@pytest.mark.parametrize("raw", [
    "α\\rβ",     # Literal backslash followed by r; no carriage return.
    "α\rβ",
    "α\r\nβ",
    "\r\r",
    "\rἀνήρ\r",
    "α\r\rβ",
    "α\\r\rβ",
    "κόσμος\r\n  λόγος\n\t",
])
def test_original_source_fact_exact_through_native_F_E(
    tmp_path: Path, raw: str,
) -> None:
    output = tmp_path / "native"
    original = _record(raw)
    stats = write_native_records((original,), output)
    assert stats.records == stats.metadata_records == 1
    assert stats.text_records == 0
    assert read_native_records(output) == (original,)

    fabric = Fabric(locations=str(output), silent="deep")
    found = fabric.explore(silent="deep")
    assert found
    nodes = set(found["nodes"])
    edges = set(found["edges"])
    assert ("has_cr_fragment" in edges) == ("\r" in raw)
    if "\r" in raw:
        assert {"fragment_codepoint", "fragment_position", "fragment_kind"}.issubset(nodes)
        features = "fragment_kind fragment_position fragment_codepoint"
        if "fragment_text" in nodes:
            features += " fragment_text"
        api = fabric.load(features, silent="deep")
        assert api
        assert len(api.F.otype.s("crFragment")) == (
            len([part for part in raw.split("\r") if part]) + raw.count("\r")
        )
        assert sum(
            api.F.fragment_codepoint.v(n) == 13
            for n in api.F.otype.s("crFragment")
        ) == raw.count("\r")
        if "fragment_text" in nodes:
            assert all("\r" not in value for _, value in api.F.fragment_text.items())
    else:
        assert not any(name.startswith("fragment_") for name in nodes)


def test_ordinary_native_source_preserves_historical_feature_surface(
    tmp_path: Path,
) -> None:
    original = _record("α\\rβ\nλόγος")
    left, right = tmp_path / "one", tmp_path / "two"
    write_native_records((original,), left)
    write_native_records((original,), right)
    assert native_tf_manifest(left).canonical_sha256 == (
        native_tf_manifest(right).canonical_sha256
    )
    surface = Fabric(locations=str(left), silent="deep").explore(silent="deep")
    assert surface
    assert "has_cr_fragment" not in surface["edges"]
    assert not any(name.startswith("fragment_") for name in surface["nodes"])
    assert read_native_records(left) == (original,)


def test_mixed_native_CRs_conserved_against_independent_original_JSONL(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    path = root / FILE
    path.parent.mkdir(parents=True)
    originals = ["Α\r\nΒ", "\r\r", "γ\\r\rδ"]
    path.write_text(
        "".join(json.dumps({
            "locus": f"apparatus.{i}", "text": value,
            "source": "gutenberg", "source_sha256": "a" * 64,
        }, ensure_ascii=False) + "\n" for i, value in enumerate(originals, 1)),
        encoding="utf-8",
    )
    output = tmp_path / "mixed"
    stats = materialize_texts(root, (FILE,), output, identity=NOVEMBER_RELEASE)
    independent = validate_native_jsonl_sources(
        root, (FILE,), output, identity=NOVEMBER_RELEASE,
    )
    assert (stats.records, stats.fact_nodes) == (
        independent.records, independent.source_fact_nodes,
    )
    assert stats.records == 3
    assert [row.fields.require("text") for row in read_native_records(output)] == originals


@pytest.mark.parametrize("replacement", ["12", "0", "14"])
def test_integer_CR_fragment_tampering_is_rejected(
    tmp_path: Path, replacement: str,
) -> None:
    output = tmp_path / "graph"
    write_native_records((_record("α\rβ"),), output)
    path = output / "fragment_codepoint.tf"
    original = path.read_text(encoding="utf-8")
    header, separator, payload = original.partition("\n\n")
    assert separator and "\t13" in payload
    changed = payload.replace("\t13", f"\t{replacement}", 1)
    assert changed != payload
    path.write_text(header + separator + changed, encoding="utf-8")
    with pytest.raises(NativeComposeError):
        read_native_records(output)


@pytest.mark.parametrize("source", ["has_cr_fragment.tf", "fragment_codepoint.tf"])
def test_native_CR_rejects_forged_F_E(tmp_path: Path, source: str) -> None:
    output = tmp_path / "graph"
    write_native_records((_record("α\rβ"),), output)
    shutil.copyfile(output / source, output / "invented_semantics.tf")
    with pytest.raises(NativeComposeError, match="unexpected|missing"):
        read_native_records(output)


def test_primary_CR_still_rejected_before_writing(tmp_path: Path) -> None:
    original = _record("α\rβ")
    primary = NativeRecord(
        original.source_file, original.ordinal, original.source_record_id,
        "primary-passage", original.fields, text="α\rβ",
    )
    output = tmp_path / "wrong"
    with pytest.raises(NativeComposeError, match="carriage return"):
        write_native_records((primary,), output)
    assert not output.exists()
