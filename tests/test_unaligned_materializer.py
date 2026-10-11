"""RED-first genuinely unaligned witness and paratext TF modeling (#8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import (
    NativeRecord,
    read_native_records,
    validate_native_records,
)
from opengreek_tf.record_stream import FieldObject
from opengreek_tf.tf_integrity import native_tf_manifest
from opengreek_tf.unaligned_materializer import (
    iter_native_unaligned,
    materialize_unaligned,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    base = tmp_path / "pinned source with spaces"
    secondary = base / "data/corpus_secondary"
    apparatus = base / "data/paratext"
    secondary.mkdir(parents=True)
    apparatus.mkdir(parents=True)
    samples = {
        secondary / "w.jsonl": [
            {
                "urn": "work-a", "edition": "alt-ocr", "locus": "1.2",
                "source": "ocr", "license": "PD", "text": "ἀντὶ λόγου",
                "rank": "secondary", "secondary_reason": "superseded",
            },
            {
                "urn": "work-a", "edition": "alt-ocr", "locus": "1.2",
                "source": "ocr", "license": "PD", "text": "ἕτερον",
                "displaced_by": {
                    "date": "2026-01-01", "pass": "merge", "reason": "better OCR",
                },
            },
        ],
        apparatus / "edition_apparatus.jsonl": [
            {
                "slug": "cogPG.PG003", "page": "xii", "lang": "grc",
                "class": "edition_apparatus", "source": "cgpg",
                "license": "CC-BY-4.0", "edition": "cgpg",
                "why_not_served": "quoted secondary author",
                "text": "Ὑποθώμεθα δὲ τὸν θεῖον Διονύσιον.",
            },
        ],
        apparatus / "latin_in_greek_script.jsonl": [
            {
                "slug": "hermas.pastor", "page": "26.30.3",
                "lang": "la", "class": "latin_in_greek_script",
                "script": "grc (Latin transliterated upstream)",
                "source": "first1k", "license": "CC-BY-SA-4.0",
                "edition": "1st1K-grc1",
                "greek_remaining_in_this_row": 18,
                "text": "θυοδσι δε ξετερ μοντιβυς",
            },
        ],
    }
    for path, records in samples.items():
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
            encoding="utf-8",
        )
    return base


FILES = (
    "data/corpus_secondary/w.jsonl",
    "data/paratext/edition_apparatus.jsonl",
    "data/paratext/latin_in_greek_script.jsonl",
)


def test_all_unaligned_rows_are_real_metadata_records(root: Path) -> None:
    records = tuple(iter_native_unaligned(root, FILES))
    assert len(records) == 4
    assert all(isinstance(row, NativeRecord) and row.text is None for row in records)
    assert [
        (row.source_file, row.ordinal, row.source_record_id, row.record_kind)
        for row in records
    ] == [
        (FILES[0], 1, f"{FILES[0]}:1", "secondary-witness"),
        (FILES[0], 2, f"{FILES[0]}:2", "secondary-witness"),
        (FILES[1], 1, f"{FILES[1]}:1", "paratext-record"),
        (FILES[2], 1, f"{FILES[2]}:1", "paratext-record"),
    ]
    assert records[0].fields.require("text") == "ἀντὶ λόγου"
    assert records[1].fields.require("edition") == "alt-ocr"
    displacement = records[1].fields.require("displaced_by")
    assert isinstance(displacement, FieldObject)
    assert displacement.require("reason") == "better OCR"
    assert records[3].fields.require("greek_remaining_in_this_row") == 18


def test_metadata_native_tf_preserves_every_source_without_fake_alignment(
    root: Path, tmp_path: Path,
) -> None:
    records = tuple(iter_native_unaligned(root, FILES))
    dest = tmp_path / "unaligned"
    stats = materialize_unaligned(root, FILES, dest)
    assert stats.records == stats.metadata_records == stats.source_atoms == 4
    assert stats.text_records == 0
    assert stats.fact_nodes > 30
    assert read_native_records(dest) == records
    assert validate_native_records(records, dest) == stats
    api = Fabric(locations=str(dest), silent="deep").load(
        "source_file source_ordinal source_seq record_kind "
        "fact_kind fact_key fact_text fact_int has_fact atom_kind", silent="deep",
    )
    assert api
    assert len(api.F.otype.s("metadataRecord")) == 4
    assert len(api.F.otype.s("atom")) == 4
    assert not api.F.otype.s("passage")
    assert not api.F.otype.s("word")
    assert not (dest / "form.tf").exists()
    assert not (dest / "has_alignment.tf").exists()
    assert [api.F.record_kind.v(n) for n in api.F.otype.s("metadataRecord")] == [
        r.record_kind for r in records
    ]
    texts = {"ἀντὶ λόγου", "ἕτερον", "Ὑποθώμεθα δὲ τὸν θεῖον Διονύσιον.",
             "θυοδσι δε ξετερ μοντιβυς"}
    assert texts.issubset(
        {api.F.fact_text.v(n) for n in api.F.otype.s("sourceFact")}
    )


@pytest.mark.parametrize("files", [
    (),
    (FILES[0], FILES[0]),
    ("data/corpus/primary.jsonl",),
    ("data/corpus_secondary/../corpus_secondary/w.jsonl",),
])
def test_rejects_empty_duplicate_primary_or_escaping_selection(
    root: Path, tmp_path: Path, files: tuple[str, ...],
) -> None:
    output = tmp_path / "broken"
    with pytest.raises(ValueError):
        materialize_unaligned(root, files, output)
    assert not output.exists()


def test_rejects_symlink_alias_of_same_physical_record(
    root: Path, tmp_path: Path,
) -> None:
    original = root / FILES[0]
    alias = root / "data/corpus_secondary/alias.jsonl"
    try:
        alias.symlink_to(original)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(str(exc))
    output = tmp_path / "alias"
    with pytest.raises(ValueError, match="duplicate"):
        materialize_unaligned(root, (FILES[0], "data/corpus_secondary/alias.jsonl"), output)
    assert not output.exists()


def test_invalid_last_family_row_cannot_leave_a_partial_native_output(
    root: Path, tmp_path: Path,
) -> None:
    last = root / FILES[-1]
    raw = json.loads(last.read_text(encoding="utf-8").strip())
    del raw["license"]
    last.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")
    output = tmp_path / "broken-last"
    with pytest.raises(ValueError, match="license"):
        materialize_unaligned(root, FILES, output)
    assert not output.exists()


def test_canonical_feature_graph_independent_of_generated_timestamps(
    root: Path, tmp_path: Path,
) -> None:
    p = tmp_path / "a"
    q = tmp_path / "b"
    materialize_unaligned(root, FILES, p)
    materialize_unaligned(root, FILES, q)
    assert native_tf_manifest(p).canonical_sha256 == (
        native_tf_manifest(q).canonical_sha256
    )


def test_rejects_hardlink_alias_of_same_physical_source_file(
    root: Path, tmp_path: Path,
) -> None:
    original = root / FILES[0]
    alias = root / "data/corpus_secondary/hardlink.jsonl"
    try:
        alias.hardlink_to(original)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"hard links unsupported: {exc}")
    assert alias.resolve() != original.resolve()
    assert alias.stat().st_ino == original.stat().st_ino
    output = tmp_path / "hardlink"
    with pytest.raises(ValueError, match="duplicate"):
        materialize_unaligned(
            root, (FILES[0], "data/corpus_secondary/hardlink.jsonl"), output,
        )
    assert not output.exists()


def test_nonexistent_source_file_fails_before_any_native_output(
    root: Path, tmp_path: Path,
) -> None:
    destination = tmp_path / "missing"
    with pytest.raises(ValueError, match="source"):
        materialize_unaligned(
            root, (FILES[0], "data/paratext/absent.jsonl"), destination,
        )
    assert not destination.exists()
