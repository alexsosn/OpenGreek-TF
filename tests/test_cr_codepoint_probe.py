"""RED-first native TF 13.1 integer CR-codepoint roundtrip proof (#29)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.cr_codepoint_probe import (
    CRCodepointError,
    CRProbeResult,
    read_cr_codepoint_probe,
    write_cr_codepoint_probe,
)


@pytest.mark.parametrize(
    "raw",
    [
        "λόγος\rἕτερος",
        "λόγος\r\nἕτερος",
        "\r\r",
        "\rabc\r",
        "α\r\rβ",
        "",
        "α\\rβ",
        "α\u0301  ἄλλος\n\t",
        "α\x7f\x81β",
    ],
)
def test_native_integer_cr_atom_roundtrips_exact_unicode_without_fake_words(
    tmp_path: Path, raw: str,
) -> None:
    out = tmp_path / "tf"
    write_cr_codepoint_probe(
        raw, out, source_file="data/corpus/probe.jsonl", source_ordinal=1043,
    )
    recovered = read_cr_codepoint_probe(out)
    assert recovered == CRProbeResult(
        "data/corpus/probe.jsonl", 1043, raw, raw.count("\r"),
        len([s for s in raw.split("\r") if s]),
    )
    api = Fabric(locations=str(out), silent="deep").load(
        "form atom_kind codepoint source_file source_ordinal "
        "text_digest text_length cr_count locus", silent="deep",
    )
    assert api
    assert api.F.otype.s("word") == ()
    assert len(api.F.otype.s("passage")) == 1
    assert len(api.F.otype.s("atom")) == recovered.text_slot_count + raw.count("\r") + 1
    assert sum(api.F.codepoint.v(s) == 13 for s in api.F.otype.s("atom")) == raw.count("\r")
    assert all(p.suffix == ".tf" for p in out.iterdir() if p.is_file())


def test_native_tf_default_text_view_is_not_misrepresented_as_cr_safe(
    tmp_path: Path,
) -> None:
    raw = "α\r\nβ"
    out = tmp_path / "native"
    write_cr_codepoint_probe(raw, out, source_file="data/corpus/a.jsonl", source_ordinal=1)
    api = Fabric(locations=str(out), silent="deep").load(
        "form atom_kind codepoint source_file source_ordinal "
        "text_digest text_length cr_count locus", silent="deep",
    )
    assert api
    passage = api.F.otype.s("passage")[0]
    assert api.T.text(passage, fmt="text-orig-full") != raw
    assert read_cr_codepoint_probe(out).text == raw


def test_native_tf_without_cr_preserves_normal_original_text_view(tmp_path: Path) -> None:
    raw = "λόγος\n  ἄλλος"
    out = tmp_path / "plain"
    write_cr_codepoint_probe(raw, out, source_file="data/corpus/a.jsonl", source_ordinal=1)
    api = Fabric(locations=str(out), silent="deep").load(
        "form atom_kind codepoint source_file source_ordinal "
        "text_digest text_length cr_count locus", silent="deep",
    )
    assert api
    assert api.T.text(api.F.otype.s("passage")[0], fmt="text-orig-full") == raw


@pytest.mark.parametrize("replacement", ["12", "14", "0"])
def test_independent_reader_rejects_tampered_integer_codepoint(
    tmp_path: Path, replacement: str,
) -> None:
    out = tmp_path / "native"
    write_cr_codepoint_probe("α\rβ", out, source_file="data/corpus/a.jsonl", source_ordinal=1)
    path = out / "codepoint.tf"
    content = path.read_text(encoding="utf-8")
    assert "13" in content
    path.write_text(content.replace("13", replacement, 1), encoding="utf-8")
    with pytest.raises(CRCodepointError):
        read_cr_codepoint_probe(out)


def test_independent_reader_rejects_lost_native_text_unit(tmp_path: Path) -> None:
    out = tmp_path / "native"
    write_cr_codepoint_probe("α\r\rβ", out, source_file="data/corpus/a.jsonl", source_ordinal=1)
    # Deleting one CR atom must trip native count/digest invariants rather
    # than silently normalizing or producing plausible-but-wrong text.
    path = out / "codepoint.tf"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    rows = [i for i, line in enumerate(lines) if line.strip().endswith("\t13")]
    assert len(rows) == 2
    lines.pop(rows[-1])
    path.write_text("".join(lines), encoding="utf-8")
    with pytest.raises(CRCodepointError):
        read_cr_codepoint_probe(out)


def test_probe_rejects_source_provenance_cr_and_preexisting_destination(
    tmp_path: Path,
) -> None:
    out = tmp_path / "native"
    with pytest.raises(CRCodepointError):
        write_cr_codepoint_probe("x", out, source_file="file\rname", source_ordinal=1)
    assert not out.exists()
    with pytest.raises(CRCodepointError):
        write_cr_codepoint_probe("x", out, source_file="f", source_ordinal=0)
    assert not out.exists()
    out.mkdir()
    with pytest.raises(CRCodepointError):
        write_cr_codepoint_probe("x", out, source_file="f", source_ordinal=1)
