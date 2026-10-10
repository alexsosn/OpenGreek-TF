from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.locus_probe import LocusProbeError, analyze_loci


def _rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def test_collision_probe_distinguishes_text_and_preserves_source_ordinals(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fragments.jsonl"
    _rows(
        path,
        [
            {"locus": "2.1", "text": "α", "page": 208, "edition": "dfhg"},
            {"locus": "2.2", "text": "β", "page": 208, "edition": "dfhg"},
            {"locus": "2.1", "text": "γ", "page": 210, "edition": "dfhg"},
            {"locus": "3.1", "text": "δ", "page": 211, "edition": "dfhg"},
            {"locus": "3.1", "text": "δ", "page": 212, "edition": "other"},
        ],
    )

    result = analyze_loci(path)

    assert result["rows"] == 5
    assert result["distinct_loci"] == 3
    assert result["collision_groups"] == 2
    assert result["repeated_occurrences"] == 2
    assert result["colliding_rows"] == 4
    assert result["same_text_groups"] == 1
    assert result["different_text_groups"] == 1
    assert result["different_page_groups"] == 2
    assert result["different_edition_groups"] == 1
    assert [g["locus"] for g in result["top_groups"]] == ["2.1", "3.1"]
    first = result["top_groups"][0]
    assert first["positions"] == [1, 3]
    assert first["distinct_text_hashes"] == 2
    assert first["pages"] == ["208", "210"]
    assert first["same_text"] is False
    assert result["top_groups"][1]["same_text"] is True
    assert result["top_groups"][1]["positions"] == [4, 5]
    assert "α" not in json.dumps(result, ensure_ascii=False)


def test_probe_is_deterministic_and_group_output_capped(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    _rows(
        path,
        [
            {"locus": "z", "text": "A"},
            {"locus": "a", "text": "B"},
            {"locus": "z", "text": "C"},
            {"locus": "a", "text": "D"},
        ],
    )

    expected = analyze_loci(path, max_groups=1)
    assert expected == analyze_loci(path, max_groups=1)
    assert expected["collision_groups"] == 2
    assert len(expected["top_groups"]) == 1
    assert expected["top_groups"][0]["locus"] == "a"


@pytest.mark.parametrize(
    "body, error",
    [
        ('{broken\n', "invalid JSON"),
        ('{"locus":"1"}\n', "text"),
        ('{"text":"abc"}\n', "locus"),
        ('{"locus":1,"text":"abc"}\n', "locus"),
        ('["1","abc"]\n', "object"),
    ],
)
def test_probe_fails_closed_on_invalid_rows(
    tmp_path: Path, body: str, error: str
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(LocusProbeError, match=error):
        analyze_loci(path)


def test_probe_rejects_invalid_group_limit(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    _rows(path, [{"locus": "a", "text": "word"}])
    with pytest.raises(ValueError, match="max_groups"):
        analyze_loci(path, max_groups=-1)
