"""RED-first all-author-authority native TF coverage (issue #20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.author_authority import (
    AuthorityError,
    AuthorityRecord,
    AuthorityStats,
    parse_author_authority,
    read_author_authority_tf,
    validate_author_authority_tf,
    write_author_authority_tf,
)


@pytest.fixture
def authority_root(tmp_path: Path) -> Path:
    root = tmp_path / "upstream"
    data = root / "data"
    data.mkdir(parents=True)
    (data / "author_authority.json").write_text(
        json.dumps(
            {
                "tlg0001": {
                    "birth": -294, "death": -214, "gnd": "00001234X",
                    "wikidata": "Q192638", "_multi": ["Q1", "Q1"],
                },
                "tlg0002": {
                    "floruit": 0, "isni": "0000000408078793",
                    "wikidata": "Q336115", "_multi": [],
                },
                "tlg0003": {"wikidata": "Q41683"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def test_strict_authority_source_preserves_every_scalar_array_and_field_order(
    authority_root: Path,
) -> None:
    rows = parse_author_authority(authority_root)
    assert rows == (
        AuthorityRecord(
            "tlg0001", 1,
            (
                ("birth", -294), ("death", -214), ("gnd", "00001234X"),
                ("wikidata", "Q192638"), ("_multi", ("Q1", "Q1")),
            ),
        ),
        AuthorityRecord(
            "tlg0002", 2,
            (("floruit", 0), ("isni", "0000000408078793"),
             ("wikidata", "Q336115"), ("_multi", ())),
        ),
        AuthorityRecord("tlg0003", 3, (("wikidata", "Q41683"),)),
    )


def test_native_tf_roundtrip_preserves_all_tlg_authority_and_nested_fields(
    authority_root: Path, tmp_path: Path,
) -> None:
    dest = tmp_path / "authority-tf"
    report = write_author_authority_tf(authority_root, dest)
    assert report == AuthorityStats(
        records=3, fields=10, array_items=2, source_atoms=3,
    )
    assert read_author_authority_tf(dest) == parse_author_authority(authority_root)
    assert validate_author_authority_tf(authority_root, dest) == report
    loaded = Fabric(locations=str(dest), silent="deep").load(
        "atom_kind source_file source_record_id source_ordinal "
        "authority_key authority_position authority_kind authority_text "
        "authority_int authority_item_position has_authority_field "
        "has_authority_item",
        silent="deep",
    )
    assert loaded
    assert len(loaded.F.otype.s("atom")) == 3
    assert len(loaded.F.otype.s("authorAuthority")) == 3
    assert len(loaded.F.otype.s("authorityField")) == 10
    assert len(loaded.F.otype.s("authorityArrayItem")) == 2
    assert loaded.F.otype.s("word") == ()
    assert loaded.F.otype.s("passage") == ()
    assert not (dest / "form.tf").exists()
    assert all(p.suffix == ".tf" for p in dest.iterdir() if p.is_file())


def test_no_array_values_do_not_invent_optional_features(
    authority_root: Path, tmp_path: Path,
) -> None:
    path = authority_root / "data" / "author_authority.json"
    payload = json.loads(path.read_text())
    payload["tlg0001"].pop("_multi")
    payload["tlg0002"].pop("_multi")
    path.write_text(json.dumps(payload), encoding="utf-8")
    dest = tmp_path / "no-array"
    report = write_author_authority_tf(authority_root, dest)
    assert report.array_items == 0
    assert read_author_authority_tf(dest) == parse_author_authority(authority_root)


@pytest.mark.parametrize("bad_entry", [
    {"birth": 1.5, "wikidata": "Q1"},
    {"birth": False, "wikidata": "Q1"},
    {"birth": None, "wikidata": "Q1"},
    {"wiki_title": {"lang": "grc"}, "wikidata": "Q1"},
    {"wikidata": "Q1", "_multi": ["Q2", 9]},
])
def test_unrepresentable_or_unknown_source_field_fails_closed(
    authority_root: Path, bad_entry: dict[str, object],
) -> None:
    path = authority_root / "data" / "author_authority.json"
    payload = json.loads(path.read_text())
    payload["tlg0001"] = bad_entry
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AuthorityError):
        parse_author_authority(authority_root)


def test_duplicate_raw_json_key_fails_closed(authority_root: Path) -> None:
    path = authority_root / "data" / "author_authority.json"
    path.write_text(
        '{"tlg0001":{"gnd":"0123","gnd":"0456","wikidata":"Q1"}}',
        encoding="utf-8",
    )
    with pytest.raises(AuthorityError):
        parse_author_authority(authority_root)


def test_metadata_authority_rejects_preexisting_destination(
    authority_root: Path, tmp_path: Path,
) -> None:
    dest = tmp_path / "existing"
    dest.mkdir()
    with pytest.raises(AuthorityError):
        write_author_authority_tf(authority_root, dest)


@pytest.mark.parametrize("mutation", ("lost-author", "changed-year", "reordered-multi"))
def test_independent_native_validator_rejects_changed_raw_authority(
    authority_root: Path, tmp_path: Path, mutation: str,
) -> None:
    dest = tmp_path / "native"
    write_author_authority_tf(authority_root, dest)
    path = authority_root / "data" / "author_authority.json"
    data = json.loads(path.read_text())
    if mutation == "lost-author":
        del data["tlg0003"]
    elif mutation == "changed-year":
        data["tlg0001"]["birth"] = -293
    else:
        data["tlg0001"]["_multi"] = ["Q1", "Q2"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AuthorityError):
        validate_author_authority_tf(authority_root, dest)


def test_validator_rejects_mutated_native_integer_feature(
    authority_root: Path, tmp_path: Path,
) -> None:
    dest = tmp_path / "native"
    write_author_authority_tf(authority_root, dest)
    path = dest / "authority_int.tf"
    raw = path.read_text(encoding="utf-8")
    assert "-294" in raw
    path.write_text(raw.replace("-294", "-293", 1), encoding="utf-8")
    with pytest.raises(AuthorityError):
        validate_author_authority_tf(authority_root, dest)
