"""RED-first generic mixed source-record native Text-Fabric composer (#6)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.native_composer import (
    NativeComposeError,
    NativeRecord,
    read_native_records,
    validate_native_records,
    write_native_records,
)
from opengreek_tf.record_stream import FieldArray, FieldObject


@pytest.fixture
def records() -> tuple[NativeRecord, ...]:
    return (
        NativeRecord(
            "data/source_registry.json#authors", 1, "sophocles",
            "registry-author",
            FieldObject((
                ("name", "Σοφοκλῆς"),
                ("aliases", FieldObject((
                    ("wikidata", "Q7235"), ("isni", "00000001"),
                ))),
            )),
        ),
        NativeRecord(
            "data/corpus/antigone.jsonl", 3, "antigone:3",
            "primary-passage",
            FieldObject((
                ("urn", "antigone"), ("locus", "1.1"),
                ("edition", "ed"), ("text", "ἄνδρα \tλόγος\n"),
                ("license", "CC0"), ("source", "tei"),
                ("corrections", FieldArray(("", "ῥ", "ῥ"))),
            )),
            text="ἄνδρα \tλόγος\n",
        ),
        NativeRecord(
            "data/source_registry.json#works", 1, "sophocles.antigone",
            "registry-work",
            FieldObject((
                ("author", "sophocles"),
                ("default_edition", None),
                ("title", "Ἀντιγόνη"),
                ("tags", FieldArray(("genre:tragedy", "genre:tragedy"))),
                ("editions", FieldObject((
                    ("sophocles.antigone.ed", FieldObject((
                        ("year", -441),
                        ("servable", True),
                        ("scheme_inferred", False),
                        ("year_note", ""),
                    ))),
                ))),
            )),
        ),
    )


def test_mixed_native_roundtrip_is_exact_without_phantom_word_or_passage(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "mixed"
    stats = write_native_records(records, out)
    assert stats.records == 3
    assert stats.metadata_records == 2
    assert stats.text_records == 1
    assert stats.source_atoms == 3
    assert stats.fact_nodes > 15
    assert read_native_records(out) == records
    assert validate_native_records(records, out) == stats
    api = Fabric(locations=str(out), silent="deep").load(
        "atom_kind source_file source_record_id record_kind source_seq "
        "source_ordinal fact_count fact_digest fact_kind fact_id "
        "fact_position fact_key fact_text fact_int has_fact form", silent="deep",
    )
    assert api
    assert len(api.F.otype.s("metadataRecord")) == 2
    assert len(api.F.otype.s("passage")) == 1
    assert not api.F.otype.s("word")
    assert not (out / "word.tf").exists()
    assert api.T.text(api.F.otype.s("passage")[0], fmt="text-orig-full") == (
        "ἄνδρα \tλόγος\n"
    )


def test_metadata_only_preserves_null_and_empty_structures(tmp_path: Path) -> None:
    source = (NativeRecord(
        "data/source_registry.json#works", 1, "empty.work", "registry-work",
        FieldObject((
            ("year", None), ("aliases", FieldObject(())),
            ("tags", FieldArray(())), ("boolean", False), ("zero", 0),
            ("empty", ""),
        )),
    ),)
    out = tmp_path / "metadata"
    stats = write_native_records(source, out)
    assert stats.records == stats.source_atoms == stats.metadata_records == 1
    assert stats.text_records == 0
    assert read_native_records(out) == source
    assert not (out / "form.tf").exists()


def test_text_only_roundtrip_and_empty_text(tmp_path: Path) -> None:
    source = (
        NativeRecord(
            "data/corpus/a.jsonl", 1, "a:1", "primary-passage",
            FieldObject((("text", ""), ("locus", "1"), ("page", 0))),
            text="",
        ),
        NativeRecord(
            "data/corpus/a.jsonl", 2, "a:2", "primary-passage",
            FieldObject((("text", "αβ"), ("locus", "2"))),
            text="αβ",
        ),
    )
    out = tmp_path / "text"
    write_native_records(source, out)
    assert read_native_records(out) == source


def test_reject_duplicate_source_identity_or_destination(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    with pytest.raises(NativeComposeError, match="duplicate"):
        write_native_records((records[0], records[0]), tmp_path / "dupe")
    out = tmp_path / "native"
    write_native_records(records, out)
    with pytest.raises(NativeComposeError, match="exist"):
        write_native_records(records, out)


def test_reject_fabrication_and_lossy_carriage_return(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    bad_text = NativeRecord(
        "data/corpus/a.jsonl", 1, "a", "primary-passage",
        FieldObject((("text", "α\rβ"),)), text="α\rβ",
    )
    with pytest.raises(NativeComposeError):
        write_native_records((bad_text,), tmp_path / "cr")
    with pytest.raises(NativeComposeError):
        write_native_records((
            NativeRecord(
                "data/corpus/a.jsonl", 1, "a", "primary-passage",
                FieldObject((("text", "β"),)), text="α",
            ),
        ), tmp_path / "mismatch")
    assert not (tmp_path / "cr").exists()
    assert not (tmp_path / "mismatch").exists()


@pytest.mark.parametrize("feature,old,new", [
    ("source_record_id.tf", "sophocles", "homer"),
    ("fact_kind.tf", "null", "int"),
    ("fact_digest.tf", "a", "f"),
    ("form.tf", "λόγος", "χάος"),
])
def test_corrupt_native_dataset_fails_closed(
    tmp_path: Path, records: tuple[NativeRecord, ...],
    feature: str, old: str, new: str,
) -> None:
    out = tmp_path / "tf"
    write_native_records(records, out)
    path = out / feature
    raw = path.read_text(encoding="utf-8")
    if feature == "fact_digest.tf":
        digest = re.search(r"[0-9a-f]{64}", raw)
        assert digest is not None
        original_hash = digest.group(0)
        changed_hash = ("f" if original_hash[0] != "f" else "a") + original_hash[1:]
        raw = raw.replace(original_hash, changed_hash, 1)
    else:
        assert old in raw
        raw = raw.replace(old, new, 1)
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(NativeComposeError):
        validate_native_records(records, out)


def test_reject_orphan_or_unexpected_metadata_fact(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    out = tmp_path / "native"
    write_native_records(records, out)
    p = out / "has_fact.tf"
    text = p.read_text(encoding="utf-8")
    assert "@" in text
    # Corrupted relationship layer cannot silently pass the independent reader.
    p.write_text(text.replace("@edge", "@node", 1), encoding="utf-8")
    with pytest.raises(NativeComposeError):
        read_native_records(out)


@pytest.mark.parametrize(("genuine", "forged"), [
    ("source_file.tf", "invented_lemma.tf"),
    ("has_fact.tf", "invented_alignment.tf"),
    ("otext.tf", "invented_config.tf"),
])
def test_loaded_generic_source_rejects_unaccounted_real_tf_features(
    tmp_path: Path, records: tuple[NativeRecord, ...],
    genuine: str, forged: str,
) -> None:
    """An authentic F/E/config feature duplicated with a forged semantic name."""
    out = tmp_path / "native"
    write_native_records(records, out)
    assert read_native_records(out) == records
    assert (out / genuine).is_file()
    shutil.copyfile(out / genuine, out / forged)
    with pytest.raises(NativeComposeError, match="unexpected.*feature"):
        read_native_records(out)


def test_generic_source_rejects_extra_native_text_recipe(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    """Known otext config can still introduce an invented researcher-facing format."""
    out = tmp_path / "native"
    write_native_records(records, out)
    assert read_native_records(out) == records
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.save(
        metaData={"otext": {
            "sectionTypes": "passage",
            "sectionFeatures": "source_record_id",
            "fmt:text-orig-full": "{form}",
            "fmt:forged-author": "{source_file}",
        }},
        silent="deep",
    )
    with pytest.raises(NativeComposeError, match="otext|rendering"):
        read_native_records(out)


def test_generic_reader_rejects_known_source_file_on_fact_node(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    """Real native F.source_file gets an extra false claim on a sourceFact."""
    out = tmp_path / "native"
    write_native_records(records, out)
    fabric = Fabric(locations=str(out), silent="deep")
    api = fabric.load("source_file", silent="deep")
    assert api
    extra = api.F.otype.s("sourceFact")[0]
    source_files = dict(api.F.source_file.items())
    source_files[extra] = "forged/witness.jsonl"
    assert fabric.save(
        nodeFeatures={"source_file": source_files},
        metaData={"source_file": {"valueType": "str"}},
        silent="deep",
    )
    with pytest.raises(NativeComposeError, match="unexpected.*placement"):
        read_native_records(out)


def test_generic_reader_rejects_known_relation_from_text_atom(
    tmp_path: Path, records: tuple[NativeRecord, ...],
) -> None:
    """Additional true TF has_fact edge makes an atom appear to own source facts."""
    out = tmp_path / "native"
    write_native_records(records, out)
    fabric = Fabric(locations=str(out), silent="deep")
    api = fabric.load("has_fact atom_kind", silent="deep")
    assert api
    atom = next(n for n in api.F.otype.s("atom")
                if api.F.atom_kind.v(n) == "text")
    fact = api.F.otype.s("sourceFact")[0]
    edges = {n: set(targets) for n, targets in api.E.has_fact.items()}
    edges[atom] = {fact}
    assert fabric.save(
        edgeFeatures={"has_fact": edges},
        metaData={"has_fact": {"edgeValues": False}},
        silent="deep",
    )
    with pytest.raises(NativeComposeError, match="unexpected.*edge"):
        read_native_records(out)
