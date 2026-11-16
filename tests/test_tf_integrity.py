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


def test_text_fabric_13_1_utc_aware_written_stamp(tmp_path: Path) -> None:
    # tf.core.helpers.utcnow() is dt.now(timezone.utc), then the writer
    # appends a literal Z to the ISO timestamp containing +00:00.
    _write_tf(tmp_path, "atom_kind.tf", "2026-10-11T10:12:55+00:00Z", "1\\tsource-row\\n")
    assert native_tf_manifest(tmp_path).tf_file_count == 1


def test_manifest_streams_feature_bytes_with_exact_historical_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-MiB original Unicode feature data must not be copied into RAM."""
    import hashlib
    import tracemalloc

    name = "form.tf"
    stamp = b"@dateWritten=2026-10-11T10:00:00Z\n"
    header = b"@node\n@writtenBy=Text-Fabric\n" + stamp + b"\n"
    body = ("λόγος  ἀνήρ\t\n" * 500_000).encode("utf-8")
    raw = header + body
    (tmp_path / name).write_bytes(raw)
    # The expectation is computed independently, from the original byte
    # contract rather than from this module's header parser or streaming code.
    prefix = name.encode("utf-8") + b"\0"
    raw_hash = hashlib.sha256(prefix + hashlib.sha256(raw).digest()).hexdigest()
    canon = raw.replace(stamp, b"", 1)
    canon_hash = hashlib.sha256(prefix + hashlib.sha256(canon).digest()).hexdigest()
    del raw, body, canon

    def forbidden_read_bytes(self: Path) -> bytes:
        raise AssertionError("manifest must stream the TF feature, not read_bytes()")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)
    tracemalloc.start()
    try:
        manifest = native_tf_manifest(tmp_path)
        peak_bytes = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert manifest.tf_file_count == 1
    assert manifest.output_bytes > 5_000_000
    assert manifest.raw_sha256 == raw_hash
    assert manifest.canonical_sha256 == canon_hash
    assert peak_bytes < 3 * 1024 * 1024, peak_bytes


def test_manifest_header_delimiter_across_stream_chunk_boundary(
    tmp_path: Path,
) -> None:
    """The two-LF header/body delimiter may straddle a fixed read boundary."""
    import hashlib

    name = "large_header.tf"
    stamp = b"@dateWritten=2026-10-11T10:00:00Z\n"
    prefix_header = b"@node\n@description="
    before_delimiter = b"\n" + stamp[:-1]
    padding = (64 * 1024 - 1) - len(prefix_header) - len(before_delimiter)
    header = prefix_header + b"x" * padding + before_delimiter + b"\n\n"
    assert header[64 * 1024 - 1 : 64 * 1024 + 1] == b"\n\n"
    body = b"1\talpha\r\nbeta\n" + b"\0" * 200_000
    raw = header + body
    (tmp_path / name).write_bytes(raw)
    prefix = name.encode() + b"\0"
    expected_raw = hashlib.sha256(prefix + hashlib.sha256(raw).digest()).hexdigest()
    expected_canonical = hashlib.sha256(
        prefix + hashlib.sha256(raw.replace(stamp, b"", 1)).digest()
    ).hexdigest()
    result = native_tf_manifest(tmp_path)
    assert result.raw_sha256 == expected_raw
    assert result.canonical_sha256 == expected_canonical
    assert result.output_bytes == len(raw)


def test_manifest_rejects_oversized_unterminated_header(tmp_path: Path) -> None:
    """Malformed headers cannot force unbounded buffering."""
    (tmp_path / "form.tf").write_bytes(
        b"@node\n@description=" + b"x" * (1024 * 1024 + 128)
    )
    with pytest.raises(NativeTfIntegrityError, match="oversized"):
        native_tf_manifest(tmp_path)
