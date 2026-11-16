"""Regression tests for full-source fire/tongue candidate enumeration."""
import json
from pathlib import Path

import pytest

from opengreek_tf import fire_tongues_scan as scanner
from opengreek_tf.fire_tongues_scan import fold, matches, nearest_distant, scan
from opengreek_tf.source import SourceAcquisitionError


def test_greek_normalization_and_core_collocations() -> None:
    assert fold("ΓΛῶΣΣΑΙ ΠΥΡΌΣ") == "γλωσσαι πυροσ"
    assert any(x["tier"] == "core" for x in matches("καὶ γλῶσσαι πυρὸς"))
    assert any(x["tier"] == "core" for x in matches("ἐν γλώσσαις πυρὸς"))
    assert any(x["tier"] == "core" for x in matches("γλῶττα καὶ φλόγα"))
    assert matches("γλῶσσαι " + ("ἀ" * 200) + " πυρός") == []


def test_expanded_fire_and_non_fire_words() -> None:
    got = matches("γλῶσσα καιομένη")
    assert got and all(x["tier"] == "expanded" for x in got)
    assert matches("γλῶσσα καὶ ἐξ αὐτῆς λόγοι") == []


def test_distant_same_passage_is_reportable() -> None:
    text = "γλῶσσαι " + ("ἀ" * 240) + " πυρός"
    assert matches(text) == []
    distant = nearest_distant(fold(text))
    assert distant is not None and distant["distance"] > 160


def test_every_pair_not_just_nearest() -> None:
    pairs = matches("πῦρ γλῶσσα φλόξ")
    assert len(pairs) == 2
    assert {p["fire_root"] for p in pairs} == {"πυρ", "φλοξ"}


def test_scans_each_family_and_detects_cross_record(tmp_path: Path) -> None:
    root = tmp_path / "source"
    rows = {
        "corpus": [
            {"text": "ἐν γλώσσαις πυρὸς", "locus": "14.15", "urn": "enoch"},
            {"text": "γλῶσσαι", "locus": "15.1"},
            {"text": "πυρός", "locus": "15.2"},
        ],
        "corpus_secondary": [
            {"text": "γλῶττα καὶ φλόγα", "locus": "1"},
        ],
        "paratext": [
            {"text": "non-Greek paratext", "slug": "x", "page": "1"},
        ],
    }
    for folder, family_rows in rows.items():
        path = root / "data" / folder / "a.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in family_rows),
            encoding="utf-8",
        )
    result = scan(root, tmp_path / "results", expected=False)
    assert result["families"]["primary"]["rows"] == 3
    assert result["families"]["secondary"]["rows"] == 1
    assert result["families"]["paratext"]["rows"] == 1
    events = [
        json.loads(line) for line in
        (tmp_path / "results" / "candidates.jsonl").read_text().splitlines()
    ]
    assert any(e["scope"] == "adjacent-passages" and e["previous_locus"] == "15.1"
               and e["locus"] == "15.2" for e in events)
    assert any(e["locus"] == "14.15" for e in events)
    assert any(e["family"] == "secondary" for e in events)


def test_scanner_keeps_later_distant_tongue_after_early_close_pair(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    path = root / "data" / "corpus" / "example.jsonl"
    path.parent.mkdir(parents=True)
    original = "γλῶσσα πυρός " + "α" * 300 + " γλῶσσα " + "β" * 240 + " πῦρ"
    path.write_text(json.dumps({"text": original}, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    scan(root, tmp_path / "results", expected=False)
    entries = [
        json.loads(line)
        for line in (tmp_path / "results" / "candidates.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert any(row["scope"] == "intra-passage" for row in entries)
    assert any(
        row["scope"] == "intra-passage-distant"
        and row["tongue_offset"] > 300
        and row["distance"] > 160
        for row in entries
    )


def test_source_context_is_positioned_with_decomposed_greek(tmp_path: Path) -> None:
    root = tmp_path / "source"
    path = root / "data" / "corpus" / "example.jsonl"
    path.parent.mkdir(parents=True)
    original = ("α\u0301" * 800) + " γλῶσσα πυρός"
    path.write_text(json.dumps({"text": original}, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    scan(root, tmp_path / "results", expected=False)
    entries = [
        json.loads(line)
        for line in (tmp_path / "results" / "candidates.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert any(
        row["scope"] == "intra-passage" and "γλῶσσα πυρός" in row["context"]
        for row in entries
    )


def test_default_scanner_rejects_unverified_source_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    target = tmp_path / "not-written"

    def reject(_root: Path) -> None:
        raise SourceAcquisitionError("tampered source checkout")

    monkeypatch.setattr(scanner, "verify_source", reject, raising=False)
    with pytest.raises(SourceAcquisitionError, match="tampered"):
        scan(root, target)
    assert not target.exists()


def test_fixture_scan_does_not_claim_pinned_identity(tmp_path: Path) -> None:
    root = tmp_path / "source"
    path = root / "data" / "corpus" / "example.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"text":"γλῶσσα πυρός"}\n', encoding="utf-8")
    report = scan(root, tmp_path / "results", expected=False)
    assert report["pinned_commit"] is None
    assert report["source_verified"] is False


def test_cross_record_match_survives_decomposed_unicode_window(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    path = root / "data" / "corpus" / "example.jsonl"
    path.parent.mkdir(parents=True)
    records = [
        {"text": "γλῶσσα " + ("α\u0301" * 130), "locus": "1"},
        {"text": "πυρός", "locus": "2"},
    ]
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )
    scan(root, tmp_path / "results", expected=False)
    entries = [
        json.loads(line)
        for line in (tmp_path / "results" / "candidates.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert any(
        row["scope"] == "adjacent-passages"
        and row["previous_locus"] == "1" and row["locus"] == "2"
        for row in entries
    )
