"""RED-first source-exact TF feature manifest despite volatile write stamps (#13)."""

from __future__ import annotations

from pathlib import Path

import pytest

from opengreek_tf.tf_integrity import NativeTfIntegrityError, native_tf_manifest


def _write_tf(folder: Path, name: str, date: str, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(
        ("@node\n@writtenBy=Text-Fabric\n@dateWritten=" + date
         + "\n\n" + body).encode("utf-8")
    )


def test_canonical_manifest_ignores_only_volatile_write_stamps(tmp_path: Path) -> None:
    a, b = tmp_path / "first", tmp_path / "second"
    _write_tf(a, "fact_text.tf", "2026-10-11T10:00:00Z", "1\tλόγος\n")
    _write_tf(b, "fact_text.tf", "2026-10-11T10:00:59Z", "1\tλόγος\n")
    _write_tf(a, "otype.tf", "2026-10-11T10:00:00Z", "1\tatom\n")
    _write_tf(b, "otype.tf", "2026-10-11T10:01:00Z", "1\tatom\n")
    # Text-Fabric creates its internal '.tf' cache directory, also matched
    # by Path.glob('*.tf'); it is not a serialized .tf feature file.
    (a / ".tf").mkdir()
    (a / ".tf" / "cache").write_bytes(b"non-semantic cache")
    (b / ".tf").mkdir()
    got_a = native_tf_manifest(a)
    got_b = native_tf_manifest(b)
    assert got_a.tf_file_count == got_b.tf_file_count == 2
    assert got_a.output_bytes == got_b.output_bytes
    assert got_a.raw_sha256 != got_b.raw_sha256
    assert got_a.canonical_sha256 == got_b.canonical_sha256
    assert len(got_a.canonical_sha256) == 64


@pytest.mark.parametrize(("name", "replacement"), [
    ("fact_text.tf", "1\tχάος\n"),
    ("otype.tf", "1\tword\n"),
])
def test_canonical_manifest_detects_actual_feature_change(
    tmp_path: Path, name: str, replacement: str,
) -> None:
    _write_tf(tmp_path, name, "2026-10-11T10:00:00Z", "1\tλόγος\n")
    before = native_tf_manifest(tmp_path)
    _write_tf(tmp_path, name, "2026-10-11T10:01:00Z", replacement)
    after = native_tf_manifest(tmp_path)
    assert before.canonical_sha256 != after.canonical_sha256


def test_canonical_manifest_detects_nonvolatile_header_changes(tmp_path: Path) -> None:
    _write_tf(tmp_path, "form.tf", "2026-10-11T10:00:00Z", "1\tἀνήρ\n")
    before = native_tf_manifest(tmp_path)
    f = tmp_path / "form.tf"
    f.write_bytes(f.read_bytes().replace(b"@writtenBy=Text-Fabric", b"@writtenBy=Unknown"))
    assert before.canonical_sha256 != native_tf_manifest(tmp_path).canonical_sha256


@pytest.mark.parametrize("broken", [
    b"@node\n\n1\ta\n",
    b"@node\n@dateWritten=x\n@dateWritten=y\n\n1\ta\n",
    b"@node\n@dateWritten=\n\n1\ta\n",
])
def test_canonical_manifest_requires_one_real_write_stamp(
    tmp_path: Path, broken: bytes,
) -> None:
    (tmp_path / "form.tf").write_bytes(broken)
    with pytest.raises(NativeTfIntegrityError, match="dateWritten"):
        native_tf_manifest(tmp_path)


def test_canonical_manifest_rejects_empty_payload(tmp_path: Path) -> None:
    (tmp_path / ".tf").mkdir()
    with pytest.raises(NativeTfIntegrityError, match="feature files"):
        native_tf_manifest(tmp_path)
