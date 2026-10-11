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
