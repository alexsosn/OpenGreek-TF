"""RED-first adversarial surface verification for loaded CR native TF (#29).

The integrity reader must not silently accept injected F/E semantic features
outside the documented Text-Fabric CR-codepoint graph.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from opengreek_tf.cr_codepoint_probe import (
    CRCodepointError,
    read_cr_codepoint_probe,
    write_cr_codepoint_probe,
)


@pytest.mark.parametrize("source_feature", ["locus.tf", "source_file.tf"])
def test_reader_rejects_injected_undeclared_node_feature(
    tmp_path: Path, source_feature: str,
) -> None:
    output = tmp_path / "cr-tf"
    text = "α\r\nβ\x7f\x81"
    write_cr_codepoint_probe(
        text, output, source_file="data/corpus/greek.jsonl", source_ordinal=17,
    )
    assert read_cr_codepoint_probe(output).text == text
    # Duplicate a *valid* native TF feature with a new semantic name:
    # previously the reader loaded a whitelist and silently ignored it.
    shutil.copyfile(output / source_feature, output / "undocumented_truth.tf")
    with pytest.raises(CRCodepointError, match="unexpected.*feature"):
        read_cr_codepoint_probe(output)


def test_reader_rejects_injected_undeclared_edge_feature(tmp_path: Path) -> None:
    output = tmp_path / "cr-tf"
    write_cr_codepoint_probe(
        "\rἄνθρωπος", output, source_file="data/corpus/greek.jsonl",
        source_ordinal=1,
    )
    assert read_cr_codepoint_probe(output).text == "\rἄνθρωπος"
    # oslots.tf is a real valid TF *edge* feature. A cloned edge under an
    # invented name must not become an unaccounted semantic relation.
    assert (output / "oslots.tf").is_file()
    shutil.copyfile(output / "oslots.tf", output / "invented_alignment.tf")
    with pytest.raises(CRCodepointError, match="unexpected.*feature"):
        read_cr_codepoint_probe(output)


def test_reader_accepts_genuine_native_control_graph_without_extra_features(
    tmp_path: Path,
) -> None:
    output = tmp_path / "cr-tf"
    original = "\rλόγος\r\n\r\x7f\x81"
    write_cr_codepoint_probe(
        original, output, source_file="data/corpus/greek.jsonl",
        source_ordinal=1043,
    )
    restored = read_cr_codepoint_probe(output)
    assert restored.text == original
    assert restored.cr_count == 3
    assert restored.source_file == "data/corpus/greek.jsonl"
    assert restored.source_ordinal == 1043


def test_reader_rejects_provenance_for_ordinary_text_atom(tmp_path: Path) -> None:
    from tf.fabric import Fabric  # type: ignore[import-untyped]

    out = tmp_path / "native"
    write_cr_codepoint_probe(
        "ἀνήρ\rλόγος", out,
        source_file="data/corpus/greek.jsonl", source_ordinal=2,
    )
    fabric = Fabric(locations=str(out), silent="deep")
    api = fabric.load("source_file atom_kind", silent="deep")
    assert api
    text_slot = next(
        node for node in api.F.otype.s("atom")
        if api.F.atom_kind.v(node) == "text-run"
    )
    source_file_values = dict(api.F.source_file.items())
    source_file_values[text_slot] = "fake/witness.jsonl"
    # Write a syntactically valid native node feature under the *allowed*
    # name. Checking feature names alone cannot detect forged per-node data.
    assert fabric.save(
        nodeFeatures={"source_file": source_file_values},
        metaData={"source_file": {"valueType": "str"}},
        silent="deep",
    )
    with pytest.raises(CRCodepointError, match="provenance"):
        read_cr_codepoint_probe(out)


def test_reader_rejects_forged_config_feature(tmp_path: Path) -> None:
    out = tmp_path / "native"
    write_cr_codepoint_probe(
        "ἀνήρ\rλόγος", out,
        source_file="data/corpus/greek.jsonl", source_ordinal=2,
    )
    assert (out / "otext.tf").is_file()
    shutil.copyfile(out / "otext.tf", out / "untrusted_format.tf")
    with pytest.raises(CRCodepointError, match="unexpected.*feature"):
        read_cr_codepoint_probe(out)


def test_reader_rejects_forged_native_text_rendering_config(tmp_path: Path) -> None:
    from tf.fabric import Fabric

    out = tmp_path / "native"
    original = "ἀνήρ\rλόγος"
    write_cr_codepoint_probe(
        original, out,
        source_file="data/corpus/greek.jsonl", source_ordinal=7,
    )
    assert original.count("\r") == 1
    assert read_cr_codepoint_probe(out).text == original
    # This is an *allowed* config feature name but rewrites the native
    # researcher-facing text recipe to render the file name as Greek text.
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.save(
        metaData={"otext": {
            "sectionTypes": "passage",
            "sectionFeatures": "locus",
            "fmt:text-orig-full": "{source_file}",
        }},
        silent="deep",
    )
    with pytest.raises(CRCodepointError, match="rendering|otext"):
        read_cr_codepoint_probe(out)


def test_reader_rejects_additional_forged_text_format(tmp_path: Path) -> None:
    from tf.fabric import Fabric

    out = tmp_path / "native"
    original = "λόγος\rἄλλος"
    assert original.count("\r") == 1
    write_cr_codepoint_probe(
        original, out,
        source_file="data/corpus/greek.jsonl", source_ordinal=7,
    )
    assert read_cr_codepoint_probe(out).text == original
    # Preserve the genuine required format unchanged, but add an extra TF
    # research-facing text recipe that displays the source filename.
    fabric = Fabric(locations=str(out), silent="deep")
    assert fabric.save(
        metaData={"otext": {
            "sectionTypes": "passage",
            "sectionFeatures": "locus",
            "fmt:text-orig-full": "{form}",
            "fmt:forged-text": "{source_file}",
        }},
        silent="deep",
    )
    with pytest.raises(CRCodepointError, match="rendering|otext"):
        read_cr_codepoint_probe(out)
