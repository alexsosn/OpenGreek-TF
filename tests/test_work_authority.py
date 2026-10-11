"""RED-first real-shaped grouped work-authority native TF proof (#20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.work_authority import (
    WorkAuthorityError,
    WorkAuthorityStats,
    WorkEntry,
    WorkGroup,
    parse_work_authority,
    read_work_authority_tf,
    validate_work_authority_tf,
    write_work_authority_tf,
)


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "upstream"
    data = root / "data"
    data.mkdir()
    (data / "work_authority.json").write_text(
        json.dumps(
            {
                "tlg0001": [
                    {"label": "Ἀργοναυτικά", "qid": "Q123",
                     "alts": ["Argonautica", "Argonautica"],
                     "langs": ["Ancient Greek"], "year": -200},
                    {"label": "Book II", "qid": "Q123"},
                ],
                "tlg0002": [],
                "tlg0003": [
                    {"label": "Third", "qid": "Q123", "genres": ["epic", "epic"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def test_strict_source_parser_preserves_groups_records_fields_and_duplicate_qids(
    source_root: Path,
) -> None:
    rows = parse_work_authority(source_root)
    assert rows == (
        WorkGroup(
            "tlg0001", 1,
            (
                WorkEntry(
                    0, (("label", "Ἀργοναυτικά"), ("qid", "Q123"),
                        ("alts", ("Argonautica", "Argonautica")),
                        ("langs", ("Ancient Greek",)), ("year", -200)),
                ),
                WorkEntry(1, (("label", "Book II"), ("qid", "Q123"))),
            ),
        ),
        WorkGroup("tlg0002", 2, ()),
        WorkGroup(
            "tlg0003", 3,
            (WorkEntry(0, (("label", "Third"), ("qid", "Q123"),
                           ("genres", ("epic", "epic")))),),
        ),
    )


def test_real_native_tf_round_trip_preserves_group_and_work_atoms(
    source_root: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "work-native"
    report = write_work_authority_tf(source_root, out)
    assert report == WorkAuthorityStats(
        groups=3, works=3, fields=10, array_items=5, source_atoms=6,
    )
    assert read_work_authority_tf(out) == parse_work_authority(source_root)
    assert validate_work_authority_tf(source_root, out) == report
    api = Fabric(locations=str(out), silent="deep").load(
        "atom_kind source_file source_record_id source_ordinal "
        "authority_group_id authority_work_index authority_key authority_position "
        "authority_kind authority_text authority_int authority_item_position "
        "has_authority_work has_authority_field has_authority_item",
        silent="deep",
    )
    assert api
    assert len(api.F.otype.s("atom")) == 6
    assert len(api.F.otype.s("workAuthorityGroup")) == 3
    assert len(api.F.otype.s("workAuthority")) == 3
    assert len(api.F.otype.s("workAuthorityField")) == 10
    assert len(api.F.otype.s("workAuthorityItem")) == 5
    assert api.F.otype.s("word") == api.F.otype.s("passage") == ()
    assert not (out / "form.tf").exists()
    assert all(p.suffix == ".tf" for p in out.iterdir() if p.is_file())


@pytest.mark.parametrize(
    "bad",
    [
        {"label": "x", "qid": "Q1", "year": False},
        {"label": "x", "qid": "Q1", "year": 1.5},
        {"label": "x", "qid": "Q1", "genres": ["epic", 0]},
        {"label": "x", "qid": "Q1", "genres": "epic"},
        {"label": "x", "qid": "Q1", "new-key": True},
        {"qid": "Q1"},
        {"label": "x", "qid": "Q1", "grc": "a\rb"},
    ],
)
def test_strict_source_rejects_unknown_or_bad_fields(
    source_root: Path, bad: dict[str, object],
) -> None:
    path = source_root / "data" / "work_authority.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tlg0001"][0] = bad
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(WorkAuthorityError):
        parse_work_authority(source_root)


def test_reject_duplicate_json_keys(source_root: Path) -> None:
    path = source_root / "data" / "work_authority.json"
    path.write_text(
        '{"tlg0001":[{"label":"A","qid":"Q1","qid":"Q2"}]}',
        encoding="utf-8",
    )
    with pytest.raises(WorkAuthorityError):
        parse_work_authority(source_root)


@pytest.mark.parametrize("mutation", ("remove-group", "reorder-items", "change-qid"))
def test_validator_rejects_changed_source_after_native_tf_was_written(
    source_root: Path, tmp_path: Path, mutation: str,
) -> None:
    out = tmp_path / "native"
    write_work_authority_tf(source_root, out)
    path = source_root / "data" / "work_authority.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "remove-group":
        del data["tlg0002"]
    elif mutation == "reorder-items":
        data["tlg0001"][0]["alts"] = ["Argonautica", "NEW"]
    else:
        data["tlg0003"][0]["qid"] = "Q999"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(WorkAuthorityError):
        validate_work_authority_tf(source_root, out)


def test_validator_rejects_modified_native_text_feature(
    source_root: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "native"
    write_work_authority_tf(source_root, out)
    feature = out / "authority_text.tf"
    raw = feature.read_text(encoding="utf-8")
    assert "Book II" in raw
    feature.write_text(raw.replace("Book II", "FAKE", 1), encoding="utf-8")
    with pytest.raises(WorkAuthorityError):
        validate_work_authority_tf(source_root, out)


def test_rejects_existing_destination(source_root: Path, tmp_path: Path) -> None:
    occupied = tmp_path / "already"
    occupied.mkdir()
    with pytest.raises(WorkAuthorityError):
        write_work_authority_tf(source_root, occupied)
