"""RED-first original JSONL source profile for native Greek scale gates (#13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.primary_source_profile import (
    PrimarySourceProfileError,
    profile_primary_sources,
)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "verified Greek source with spaces"
    corpus = root / "data" / "corpus"
    corpus.mkdir(parents=True)
    a = [
        {"urn": "alpha", "text": "ἄλφα  βῆτα\n"},
        {"urn": "alpha", "text": ""},
    ]
    b = [{"urn": "beta", "text": "😀\tλ", "dfhg_flag": False}]
    for name, records in (("alpha.jsonl", a), ("beta.jsonl", b)):
        (corpus / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
            encoding="utf-8",
        )
    return root


def test_original_source_profile_counts_codepoints_layout_anchors_and_order(
    source: Path,
) -> None:
    files = ("data/corpus/beta.jsonl", "data/corpus/alpha.jsonl")
    profile = profile_primary_sources(source, files)
    assert profile.source_files == 2
    assert profile.records == 3
    assert profile.file_records == (1, 2)
    assert profile.original_codepoints == len("😀\tλἄλφα  βῆτα\n")
    assert profile.text_layout_atoms == 3 + 4
    assert profile.source_anchor_atoms == 3
    assert profile.total_atoms == 10
    assert profile.max_passage_codepoints == len("ἄλφα  βῆτα\n")
    assert profile.max_layout_atoms == 4
    assert profile.source_bytes == sum((source / f).stat().st_size for f in files)
    assert len(profile.source_sha256) == 64


def test_source_profile_digest_changes_on_lossless_json_member_reorder(
    source: Path,
) -> None:
    files = ("data/corpus/alpha.jsonl",)
    before = profile_primary_sources(source, files)
    path = source / files[0]
    first, second = path.read_text(encoding="utf-8").splitlines()
    reordered = json.dumps(
        {"text": "ἄλφα  βῆτα\n", "urn": "alpha"}, ensure_ascii=False,
    )
    path.write_text(reordered + "\n" + second + "\n", encoding="utf-8")
    after = profile_primary_sources(source, files)
    assert before.records == after.records
    assert before.original_codepoints == after.original_codepoints
    assert before.source_sha256 != after.source_sha256


@pytest.mark.parametrize("problem", [
    "duplicate-file", "other-family", "traversal", "empty", "alias",
])
def test_original_source_preflight_rejects_invalid_selection(
    source: Path, problem: str,
) -> None:
    a = "data/corpus/alpha.jsonl"
    files: tuple[str, ...]
    if problem == "duplicate-file":
        files = (a, a)
    elif problem == "other-family":
        files = ("data/corpus_secondary/alpha.jsonl",)
    elif problem == "traversal":
        files = ("data/corpus/../corpus/alpha.jsonl",)
    elif problem == "empty":
        files = ()
    else:
        alias = source / "data/corpus/alias.jsonl"
        try:
            alias.symlink_to(source / a)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"symlink unavailable: {exc}")
        files = (a, "data/corpus/alias.jsonl")
    with pytest.raises(PrimarySourceProfileError):
        profile_primary_sources(source, files)


@pytest.mark.parametrize(("raw", "expected"), [
    (b'{"text":"x", "text":"y"}\n', "duplicate"),
    (b'{"text":NaN}\n', "nonstandard"),
    (b'{"text":42}\n', "text"),
    (b'{"text":"\\u000d"}\n', "carriage"),
    (b'{"text":"\\ud800"}\n', "invalid Unicode"),
    (b'{"text":"', "invalid"),
    (b'{"text":"\xff"}\n', "UTF-8"),
    (b'\n', "blank"),
])
def test_original_source_profile_rejects_corruption(
    source: Path, raw: bytes, expected: str,
) -> None:
    path = source / "data/corpus/alpha.jsonl"
    path.write_bytes(raw)
    with pytest.raises(PrimarySourceProfileError, match=expected):
        profile_primary_sources(source, ("data/corpus/alpha.jsonl",))


def test_original_source_profile_rejects_empty_file(source: Path) -> None:
    (source / "data/corpus/alpha.jsonl").write_bytes(b"")
    with pytest.raises(PrimarySourceProfileError, match="empty"):
        profile_primary_sources(source, ("data/corpus/alpha.jsonl",))
