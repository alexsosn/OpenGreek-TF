"""RED-first native-TF tests for actual-shape registry identity atoms (#20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tf.fabric import Fabric  # type: ignore[import-untyped]

from opengreek_tf.registry_probe import (
    LedgerRecord,
    RegistryProbeError,
    parse_ledger,
    read_registry_probe,
    write_registry_probe,
)


@pytest.fixture
def ledger_root(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    data = root / "data"
    data.mkdir(parents=True)
    (data / "author_ids.json").write_text(
        json.dumps(
            {
                "_meta": {"scheme": "oga", "counts": {"active": 1, "retired": 1}},
                "authors": {
                    "oga000001": {
                        "slug": "abas", "former_slugs": [], "status": "served"
                    },
                    "oga000330": {
                        "slug": "cedrenus-et-psellus-pg122",
                        "former_slugs": [],
                        "status": "retired",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (data / "work_ids.json").write_text(
        json.dumps(
            {
                "_meta": {"scheme": "ogc", "counts": {"active": 1, "retired": 1}},
                "works": {
                    "ogc000772": {
                        "slug": "choerilus.fragmenta-epica",
                        "former_slugs": ["choerilus.tituli-p-oxy-11-1399", "other-old-slug"],
                        "status": "served",
                    },
                    "ogc000839": {
                        "slug": "cogPG.PG003", "former_slugs": [], "status": "retired"
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return root


def test_parse_real_ledger_shape_preserves_identity_order_status_and_aliases(
    ledger_root: Path,
) -> None:
    authors = parse_ledger(ledger_root, "author")
    works = parse_ledger(ledger_root, "work")
    assert authors == (
        LedgerRecord("author", "oga000001", "data/author_ids.json", 1,
                     "abas", "served", ()),
        LedgerRecord("author", "oga000330", "data/author_ids.json", 2,
                     "cedrenus-et-psellus-pg122", "retired", ()),
    )
    assert works[0] == LedgerRecord(
        "work", "ogc000772", "data/work_ids.json", 1,
        "choerilus.fragmenta-epica", "served",
        ("choerilus.tituli-p-oxy-11-1399", "other-old-slug"),
    )


def test_native_tf_roundtrip_uses_one_genuine_nonlexical_atom_per_record(
    ledger_root: Path, tmp_path: Path,
) -> None:
    out = tmp_path / "tf"
    write_registry_probe(
        ledger_root, out,
        authors=("oga000330", "oga000001"),
        works=("ogc000839", "ogc000772"),
    )
    expected = (
        *parse_ledger(ledger_root, "author"),
        *parse_ledger(ledger_root, "work"),
    )
    assert read_registry_probe(out) == expected
    api = Fabric(locations=str(out), silent="deep").load(
        "atom_kind source_file source_record_id opaque_id registry_slug "
        "registry_status alias_value alias_position has_former_slug",
        silent="deep",
    )
    assert api
    assert len(api.F.otype.s("atom")) == 4
    assert len(api.F.otype.s("registryAuthor")) == 2
    assert len(api.F.otype.s("registryWork")) == 2
    assert len(api.F.otype.s("formerSlug")) == 2
    assert api.F.otype.s("word") == ()
    assert api.F.otype.s("passage") == ()
    assert not (out / "form.tf").exists()
    assert all(api.F.atom_kind.v(s) == "registry-record"
               for s in api.F.otype.s("atom"))
    for node in (*api.F.otype.s("registryAuthor"), *api.F.otype.s("registryWork")):
        (source_slot,) = api.E.oslots.s(node)
        assert api.F.source_record_id.v(source_slot) == api.F.opaque_id.v(node)
    work = next(n for n in api.F.otype.s("registryWork")
                if api.F.opaque_id.v(n) == "ogc000772")
    aliases = api.E.has_former_slug.f(work)
    assert len(aliases) == 2
    assert sorted(api.F.alias_position.v(n) for n in aliases) == [0, 1]
    for alias in aliases:
        assert api.E.oslots.s(alias) == api.E.oslots.s(work)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("author", {"slug": "a", "former_slugs": [], "status": "unknown"}),
        ("author", {"slug": "a", "former_slugs": "not-a-list", "status": "served"}),
        ("author", {"slug": "a", "former_slugs": [], "status": "served", "lost": 3}),
        ("author", {"slug": "", "former_slugs": [], "status": "served"}),
    ],
)
def test_rejects_invalid_registry_record_instead_of_silent_loss(
    ledger_root: Path, kind: str, payload: dict[str, object],
) -> None:
    path = ledger_root / "data" / "author_ids.json"
    data = json.loads(path.read_text())
    data["authors"]["oga000001"] = payload
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegistryProbeError):
        parse_ledger(ledger_root, "author")


def test_rejects_duplicate_json_keys_even_if_default_parser_would_overwrite(
    ledger_root: Path,
) -> None:
    path = ledger_root / "data" / "author_ids.json"
    path.write_text(
        '{"_meta":{"scheme":"oga"}, "authors":{'
        '"oga000001":{"slug":"first","slug":"second","former_slugs":[],'
        '"status":"served"}}}',
        encoding="utf-8",
    )
    with pytest.raises(RegistryProbeError):
        parse_ledger(ledger_root, "author")


def test_missing_selection_fails_closed(ledger_root: Path, tmp_path: Path) -> None:
    with pytest.raises(RegistryProbeError):
        write_registry_probe(
            ledger_root, tmp_path / "tf",
            authors=("oga999999",),
            works=("ogc000772",),
        )


def test_duplicate_selection_fails_closed(ledger_root: Path, tmp_path: Path) -> None:
    with pytest.raises(RegistryProbeError):
        write_registry_probe(
            ledger_root, tmp_path / "tf",
            authors=("oga000001", "oga000001"),
            works=("ogc000772",),
        )
