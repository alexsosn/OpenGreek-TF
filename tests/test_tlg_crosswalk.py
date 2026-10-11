"""RED-first native TF conservation tests for complete TLG crosswalk (#7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.tlg_crosswalk import (
    CrosswalkError,
    CrosswalkRecord,
    CrosswalkStats,
    parse_tlg_crosswalk,
    read_tlg_crosswalk_tf,
    validate_tlg_crosswalk_tf,
    write_tlg_crosswalk_tf,
)


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "upstream"
    (root / "data").mkdir(parents=True)
    (root / "data/tlg_crosswalk.json").write_text(
        json.dumps({
            "alpha.first": {
                "cts": "urn:cts:greekLit:tlg0001.tlg001",
                "tlg": "tlg0001.tlg001",
                "author_slug": "alpha",
                "title": "",
                "note": "line one\n\tline two",
            },
            "alpha.second": {
                "cts": "urn:cts:greekLit:tlg0001.tlg001",
                "tlg": "tlg0001.tlg001",
                "author_slug": "",
                "title": "Ἀθήνη \\ path",
            },
            "unassigned.third": {
                "pta": "fragmenta",
                "author_slug": "unassigned",
                "title": "",
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return root


def test_parse_conserves_order_empty_missing_and_nonunique_ids(source_root: Path) -> None:
    assert parse_tlg_crosswalk(source_root) == (
        CrosswalkRecord("alpha.first", 1, (
            ("cts", "urn:cts:greekLit:tlg0001.tlg001"),
            ("tlg", "tlg0001.tlg001"),
            ("author_slug", "alpha"),
            ("title", ""),
            ("note", "line one\n\tline two"),
        )),
        CrosswalkRecord("alpha.second", 2, (
            ("cts", "urn:cts:greekLit:tlg0001.tlg001"),
            ("tlg", "tlg0001.tlg001"),
            ("author_slug", ""),
            ("title", "Ἀθήνη \\ path"),
        )),
        CrosswalkRecord("unassigned.third", 3, (
            ("pta", "fragmenta"),
            ("author_slug", "unassigned"),
            ("title", ""),
        )),
    )


def test_native_tf_roundtrip_includes_missing_and_empty_facts(
    source_root: Path, tmp_path: Path,
) -> None:
    dest = tmp_path / "crosswalk"
    report = write_tlg_crosswalk_tf(source_root, dest)
    assert report == CrosswalkStats(records=3, fields=12, empty_values=3, source_atoms=3)
    original = parse_tlg_crosswalk(source_root)
    assert read_tlg_crosswalk_tf(dest) == original
    assert validate_tlg_crosswalk_tf(source_root, dest) == report
    api = Fabric(locations=str(dest), silent="deep").load(
        "atom_kind source_file source_record_id source_ordinal "
        "crosswalk_id crosswalk_key crosswalk_position crosswalk_kind "
        "crosswalk_value has_crosswalk_field",
        silent="deep",
    )
    assert api
    assert len(api.F.otype.s("atom")) == 3
    assert len(api.F.otype.s("crosswalkRecord")) == 3
    assert len(api.F.otype.s("crosswalkField")) == 12
    assert api.F.otype.s("word") == ()
    assert api.F.otype.s("passage") == ()
    assert not (dest / "form.tf").exists()
    assert all(p.suffix == ".tf" for p in dest.iterdir() if p.is_file())


@pytest.mark.parametrize("bad", [
    {"tlg": 100, "title": "x"},
    {"title": ["x"]},
    {"title": None},
    {"title": True},
    {"unexpected": "x"},
])
def test_source_rejects_unknown_and_nonstring_values(
    source_root: Path, bad: dict[str, object],
) -> None:
    path = source_root / "data/tlg_crosswalk.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    source["alpha.first"] = bad
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(CrosswalkError):
        parse_tlg_crosswalk(source_root)


def test_repeated_json_keys_rejected(source_root: Path) -> None:
    (source_root / "data/tlg_crosswalk.json").write_text(
        '{"alpha.first":{"title":"a","title":"b"}}', encoding="utf-8",
    )
    with pytest.raises(CrosswalkError):
        parse_tlg_crosswalk(source_root)


def test_preexisting_destination_refused(source_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "existing"
    dest.mkdir()
    with pytest.raises(CrosswalkError):
        write_tlg_crosswalk_tf(source_root, dest)


@pytest.mark.parametrize("mutation", ["missing", "changed-empty", "reordered"])
def test_reject_source_mutation(
    source_root: Path, tmp_path: Path, mutation: str,
) -> None:
    dest = tmp_path / "native"
    write_tlg_crosswalk_tf(source_root, dest)
    path = source_root / "data/tlg_crosswalk.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "missing":
        del source["unassigned.third"]
    elif mutation == "changed-empty":
        source["alpha.first"]["title"] = "filled"
    else:
        fields = source["alpha.first"]
        source["alpha.first"] = {"title": fields["title"], **fields}
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CrosswalkError):
        validate_tlg_crosswalk_tf(source_root, dest)


def test_native_value_corruption_detected(source_root: Path, tmp_path: Path) -> None:
    dest = tmp_path / "native"
    write_tlg_crosswalk_tf(source_root, dest)
    path = dest / "crosswalk_value.tf"
    original = path.read_text(encoding="utf-8")
    assert "alpha" in original
    path.write_text(original.replace("alpha", "bravo", 1), encoding="utf-8")
    with pytest.raises(CrosswalkError):
        validate_tlg_crosswalk_tf(source_root, dest)
