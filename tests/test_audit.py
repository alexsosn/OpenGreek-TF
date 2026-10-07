from __future__ import annotations

import json
from pathlib import Path

import pytest

from opengreek_tf.audit import AuditError, audit_source


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture(root: Path) -> None:
    _jsonl(
        root / "data/corpus/author.work.jsonl",
        [
            {
                "urn": "author.work",
                "edition": "ed-a",
                "locus": "1.1",
                "source": "first1k",
                "license": "CC-BY-SA-4.0",
                "text": "λόγος τις",
                "corrections": ["manual"],
                "provenance": {"page": 1, "method": "tei"},
            },
            {
                "urn": "author.work",
                "edition": "ed-a",
                "locus": "1.2",
                "source": "first1k",
                "license": "CC-BY-SA-4.0",
                "text": "ἄλλος",
            },
        ],
    )
    _jsonl(
        root / "data/corpus_secondary/author.work.jsonl",
        [
            {
                "urn": "author.work",
                "edition": "ed-b",
                "locus": "PG001_0010.1",
                "source": "cgpg",
                "license": "CC-BY-4.0",
                "text": "λόγος",
                "rank": "secondary",
                "secondary_reason": "superseded by ed-a",
                "witness": "migne",
            }
        ],
    )
    _jsonl(
        root / "data/paratext/latin.jsonl",
        [
            {
                "slug": "author.work",
                "page": 10,
                "lang": "la",
                "license": "PD",
                "source": "ocr",
                "edition": "ed-b",
                "text": "latine",
                "class": "apparatus",
            }
        ],
    )

    _json(
        root / "data/work_index.json",
        {
            "_meta": {"counts": {"works": 1, "redirects": 1}},
            "works": {
                "author.work": {
                    "id": "ogc000001",
                    "slug": "author.work",
                    "former_slugs": ["old.work"],
                    "title": "Work",
                    "author": {
                        "id": "oga000001",
                        "slug": "author",
                        "name": "Author",
                        "authorities": {"wikidata": "Q1"},
                    },
                    "work_anchors": {"cts": "urn:cts:greekLit:tlg1.tlg1"},
                    "manifestation": {
                        "edition": "ed-a",
                        "source": "first1k",
                        "license": "CC-BY-SA-4.0",
                        "n_passages": 2,
                        "n_tokens": 3,
                    },
                }
            },
            "redirects": {"old.work": "author.work"},
        },
    )
    _json(
        root / "data/work_ids.json",
        {
            "_meta": {"counts": {"active": 1, "retired": 1}},
            "works": {
                "ogc000001": {"slug": "author.work", "former_slugs": [], "status": "served"},
                "ogc000002": {"slug": "retired.work", "former_slugs": [], "status": "retired"},
            },
        },
    )
    _json(
        root / "data/author_ids.json",
        {
            "_meta": {"counts": {"active": 1}},
            "authors": {
                "oga000001": {"slug": "author", "former_slugs": [], "status": "served"}
            },
        },
    )
    _json(
        root / "data/source_registry.json",
        {
            "works": {
                "author.work": {
                    "title": "Work",
                    "author": "author",
                    "tags": ["genre:history", "century:2"],
                    "best_source": "open_corpus",
                    "aliases": {"cts": "urn:cts:greekLit:tlg1.tlg1"},
                    "editions": {
                        "ed-a": {
                            "source": "first1k",
                            "provider": "first1k",
                            "scheme": "book.section",
                            "scheme_inferred": False,
                            "servable": True,
                            "license": "CC-BY-SA-4.0",
                            "editor": "Editor",
                        }
                    },
                }
            },
            "authors": {
                "author": {
                    "name": "Author",
                    "aliases": {"wikidata": "Q1"},
                }
            },
        },
    )
    _json(
        root / "data/corpus_editions.json",
        {
            "author.work": {
                "id": "ogc000001",
                "edition": "ed-a",
                "source": "first1k",
                "license": "CC-BY-SA-4.0",
                "n_passages": 2,
                "n_tokens": 3,
            }
        },
    )
    _json(
        root / "data/served_scheme_inference.json",
        {
            "_meta": {"works": 1},
            "works": {
                "author.work": {
                    "class": "logical-numeric",
                    "depth": 2,
                    "scheme": "book.section",
                }
            },
        },
    )
    _json(
        root / "data/tlg_crosswalk.json",
        {
            "author.work": {
                "cts": "urn:cts:greekLit:tlg1.tlg1",
                "tlg": "tlg1.tlg1",
                "author_slug": "author",
                "title": "Work",
            }
        },
    )
    _json(
        root / "data/corpus_loci_disambiguated.json",
        {
            "author.work": {
                "1.1": {
                    "basis": "ordinal",
                    "loci": ["1.1", "1.1~2"],
                }
            }
        },
    )
    _json(
        root / "data/work_metadata_remaps.json",
        {
            "_meta": {"description": "fixture"},
            "works": {"author.work": "canonical.work"},
        },
    )
    _json(
        root / "data/pseudo_author_attributions.json",
        {
            "_meta": {"description": "fixture"},
            "authors": {
                "collective-author": {
                    "name": "Collective Author",
                    "aliases": {"wikidata": "Q2"},
                    "note": "curated collective",
                }
            },
            "works": {
                "author.work": {
                    "author": "collective-author",
                    "title": "Curated Work",
                    "evidence": ["served rows", "bibliography"],
                }
            },
        },
    )
    _json(
        root / "data/coverage.json",
        {
            "author.work": {
                "license": "CC-BY-SA-4.0",
                "passages": 2,
                "source": "first1k",
                "tokens": 3,
            }
        },
    )
    _json(
        root / "data/partial_ceilings.json",
        {
            "title_rule": {
                "pattern": "Fragmenta",
                "reason": "modern locked collection",
            },
            "rule_exceptions": [
                {"tlg_id": "tlg1", "work_id": "001", "note": "exception"}
            ],
            "works": [
                {
                    "tlg_id": "tlg2",
                    "work_id": "002",
                    "reason": "structural ceiling",
                    "evidence": "survey",
                }
            ],
        },
    )
    _json(
        root / "data/ocr_quality_report.json",
        {
            "works": {
                "author.work": {
                    "unattested_rate": 0.01,
                    "witness": {
                        "secondary_edition": "ed-b",
                        "agreement": 0.9,
                    },
                }
            }
        },
    )
    _json(
        root / "data/serving_deficits.json",
        {"_meta": {"description": "fixture"}, "works": {}},
    )
    _json(
        root / "data/work_id_aliases.json",
        {
            "_meta": {"description": "fixture"},
            "renames": [
                {
                    "from": "old.work",
                    "to": "author.work",
                    "source": "fixture",
                    "note": "rename",
                }
            ],
        },
    )
    _json(
        root / "data/oga_dating.json",
        {
            "_meta": {"description": "fixture"},
            "works": {
                "tlg1.tlg1": {
                    "title": "Work",
                    "author": "Author",
                    "estimated_work_date": "150 CE",
                    "formatted_work_date": "+0101-01/+0200-12",
                    "date_label": "p2_1/p2_2",
                    "is_temporary_work_date": False,
                    "date_source": "source",
                    "date_source_link": "https://example.invalid/date",
                    "comment": "",
                    "century": 2,
                    "era": "imperial",
                    "century_from_label": 2,
                    "cog_slug": "author.work",
                    "in_registry": True,
                    "served": True,
                }
            },
        },
    )
    _json(
        root / "data/oga_dating_adjudication.json",
        {
            "_meta": {"description": "fixture"},
            "decisions": {
                "author.work": {
                    "urn": "tlg1.tlg1",
                    "decision": "c",
                    "cog_century": [1],
                    "oga_century": 2,
                    "basis": "disputed",
                }
            },
        },
    )
    _json(
        root / "data/oga_dating_report.json",
        {
            "_meta": {"description": "fixture"},
            "filled": [],
            "adjudicated": [
                {
                    "urn": "tlg1.tlg1",
                    "slug": "author.work",
                    "decision": "c",
                    "readings": [
                        {"century": [1], "source": "cog"},
                        {"century": 2, "source": "oga"},
                    ],
                }
            ],
            "conflicts": [],
            "resolved_no_registry_home": [],
        },
    )
    _json(
        root / "data/oga_duplicates_tlg_pta.json",
        {
            "_meta": {"description": "fixture"},
            "pairs": [
                {
                    "tlg": "tlg1.tlg1",
                    "pta": "pta1.pta1",
                    "tlg_slug": "author.work",
                    "tlg_served": True,
                    "pta_slug": "author.work",
                    "pta_served": True,
                    "same_slug": True,
                    "status": "same-slug",
                }
            ],
        },
    )
    _json(
        root / "data/collection_serving_map.json",
        {
            "comment": "fixture",
            "collections": [
                {
                    "tlg_id": "tlg1",
                    "work_id": "001",
                    "title": "Collection",
                    "served_prefixes": ["author."],
                    "evidence": "fixture",
                    "date": "2026-01-01",
                }
            ],
        },
    )
    _json(
        root / "data/corpus_loci_warnings.json",
        {
            "author.work": {
                "edition": "ed-a",
                "disambiguated_dup_loci": 1,
            }
        },
    )
    _json(
        root / "data/corpus_release.json",
        {
            "release_id": "fixture",
            "corpus": {"works": 1, "passages": 2, "tokens": 3},
            "pin": {"corpus_sha256": "a" * 64, "catalog_sha256": "b" * 64},
        },
    )
    (root / "data/corpus_catalog.tsv").write_text(
        "slug\twork_id\tsource\tedition\tlicense\tcorrection\tscheme_class\tsha256\n"
        "author.work\togc000001\tfirst1k\ted-a\tCC-BY-SA-4.0\tnot-ocr\t"
        "logical-numeric\tdeadbeef\n",
        encoding="utf-8",
    )


def test_audit_censuses_text_families_and_nested_structure(tmp_path: Path) -> None:
    _fixture(tmp_path)

    report = audit_source(tmp_path)

    primary = report["text_families"]["primary"]
    assert primary["files"] == 1
    assert primary["rows"] == 2
    assert primary["paths"]["/corrections"]["types"] == {"array": 1}
    assert primary["paths"]["/corrections"]["missing"] == 1
    assert primary["paths"]["/corrections"]["list_length"] == {"min": 1, "max": 1}
    assert primary["paths"]["/provenance"]["missing"] == 1
    assert primary["paths"]["/provenance"]["object_length"] == {"min": 2, "max": 2}
    assert primary["paths"]["/provenance/page"]["types"] == {"integer": 1}
    assert primary["paths"]["/provenance/page"]["missing"] == 0
    assert primary["vocabularies"]["source"] == ["first1k"]
    assert primary["vocabularies"]["license"] == ["CC-BY-SA-4.0"]
    assert primary["row_slug_mismatches"] == 0
    assert primary["row_slug_mismatches_by_file"] == {}
    assert primary["duplicate_loci"] == 0
    assert primary["duplicate_loci_by_file"] == {}
    assert primary["duplicate_record_keys"] == 0
    assert primary["duplicate_record_keys_by_file"] == {}
    assert len(primary["ordered_sha256"]) == 64

    secondary = report["text_families"]["secondary"]
    assert secondary["vocabularies"]["rank"] == ["secondary"]
    assert secondary["vocabularies"]["witness"] == ["migne"]

    paratext = report["text_families"]["paratext"]
    assert paratext["vocabularies"]["lang"] == ["la"]
    assert paratext["vocabularies"]["class"] == ["apparatus"]
    assert paratext["duplicate_record_keys"] == 0


def test_audit_wildcards_registry_editions_and_counts_identity_ledgers(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)

    report = audit_source(tmp_path)

    registry = report["metadata"]["source_registry_works"]
    assert registry["records"] == 1
    assert registry["paths"]["/editions"]["types"] == {"object": 1}
    assert registry["paths"]["/editions"]["object_length"] == {"min": 1, "max": 1}
    assert registry["paths"]["/editions/*/editor"]["types"] == {"string": 1}
    assert registry["paths"]["/editions/*/editor"]["missing"] == 0
    assert registry["paths"]["/tags/*"]["types"] == {"string": 2}

    assert report["metadata"]["work_ids"]["records"] == 2
    assert report["metadata"]["author_ids"]["records"] == 1
    assert report["metadata"]["work_index"]["records"] == 1
    assert report["metadata"]["work_index_redirects"]["records"] == 1
    disambiguated = report["metadata"]["corpus_loci_disambiguated"]
    assert disambiguated["records"] == 1
    assert disambiguated["paths"]["/*"]["types"] == {"object": 1}
    assert disambiguated["paths"]["/*/basis"]["types"] == {"string": 1}
    assert disambiguated["paths"]["/*/loci"]["list_length"] == {"min": 2, "max": 2}
    assert disambiguated["vocabularies"]["/*/basis"] == ["ordinal"]
    assert report["metadata"]["work_metadata_remaps"]["records"] == 1
    assert report["metadata"]["pseudo_author_attribution_authors"]["records"] == 1
    assert report["metadata"]["pseudo_author_attribution_works"]["records"] == 1
    assert report["metadata"]["partial_ceiling_works"]["records"] == 1
    assert report["metadata"]["partial_ceiling_rule_exceptions"]["records"] == 1
    assert report["metadata"]["partial_ceiling_policy"]["records"] == 1
    assert report["metadata"]["ocr_quality_works"]["records"] == 1
    assert report["metadata"]["serving_deficits"]["records"] == 0
    assert report["metadata"]["work_id_aliases"]["records"] == 1
    assert report["metadata"]["oga_dating_works"]["records"] == 1
    assert report["metadata"]["oga_dating_adjudication"]["records"] == 1
    assert report["metadata"]["oga_dating_report_adjudicated"]["records"] == 1
    assert report["metadata"]["oga_duplicates_tlg_pta"]["records"] == 1
    assert report["metadata"]["collection_serving_map"]["records"] == 1
    assert report["metadata"]["corpus_loci_warnings"]["records"] == 1


def test_audit_records_exact_source_edition_license_vocabularies(tmp_path: Path) -> None:
    _fixture(tmp_path)

    report = audit_source(tmp_path)

    assert report["text_families"]["primary"]["vocabularies"] == {
        "edition": ["ed-a"],
        "license": ["CC-BY-SA-4.0"],
        "source": ["first1k"],
    }
    registry = report["metadata"]["source_registry_works"]
    assert registry["vocabularies"]["/best_source"] == ["open_corpus"]
    assert registry["vocabularies"]["/tags/*"] == ["century:2", "genre:history"]
    assert registry["vocabularies"]["/editions/*/license"] == ["CC-BY-SA-4.0"]
    assert registry["vocabularies"]["/editions/*/provider"] == ["first1k"]
    assert registry["vocabularies"]["/editions/*/scheme"] == ["book.section"]
    assert registry["vocabularies"]["/editions/*/scheme_inferred"] == ["False"]
    assert registry["vocabularies"]["/editions/*/servable"] == ["True"]
    assert registry["vocabularies"]["/editions/*/source"] == ["first1k"]
    assert report["metadata"]["oga_dating_works"]["vocabularies"]["/era"] == [
        "imperial"
    ]
    assert report["metadata"]["oga_dating_adjudication"]["vocabularies"][
        "/decision"
    ] == ["c"]
    assert report["metadata"]["oga_duplicates_tlg_pta"]["vocabularies"][
        "/status"
    ] == ["same-slug"]


def test_audit_detects_duplicate_loci_and_row_slug_mismatch(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "data/corpus/author.work.jsonl"
    rows: list[dict[str, object]] = [
        {
            "urn": "wrong.work",
            "edition": "ed-a",
            "locus": "1",
            "source": "first1k",
            "license": "CC-BY-SA-4.0",
            "text": "α",
        },
        {
            "urn": "wrong.work",
            "edition": "ed-a",
            "locus": "1",
            "source": "first1k",
            "license": "CC-BY-SA-4.0",
            "text": "β",
        },
    ]
    _jsonl(path, rows)

    primary = audit_source(tmp_path)["text_families"]["primary"]

    assert primary["row_slug_mismatches"] == 2
    assert primary["row_slug_mismatches_by_file"] == {"author.work.jsonl": 2}
    assert primary["duplicate_loci"] == 1
    assert primary["duplicate_loci_by_file"] == {"author.work.jsonl": 1}
    assert primary["duplicate_record_keys"] == 1
    assert primary["duplicate_record_keys_by_file"] == {"author.work.jsonl": 1}


def test_audit_is_deterministic(tmp_path: Path) -> None:
    _fixture(tmp_path)

    assert audit_source(tmp_path) == audit_source(tmp_path)


def test_audit_fails_closed_on_malformed_jsonl(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "data/corpus/author.work.jsonl"
    path.write_text('{"urn": "author.work"}\n{broken\n', encoding="utf-8")

    with pytest.raises(AuditError, match=r"author\.work\.jsonl:2"):
        audit_source(tmp_path)


def test_audit_fails_closed_when_required_metadata_is_missing(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "data/work_index.json").unlink()

    with pytest.raises(AuditError, match="work_index.json"):
        audit_source(tmp_path)


def test_paratext_duplicate_key_uses_paratext_identity_fields(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "data/paratext/latin.jsonl"
    _jsonl(
        path,
        [
            {
                "slug": "author.work",
                "page": 10,
                "lang": "la",
                "license": "PD",
                "source": "ocr",
                "edition": "ed-b",
                "text": "one",
                "class": "apparatus",
            },
            {
                "slug": "author.work",
                "page": 11,
                "lang": "la",
                "license": "PD",
                "source": "ocr",
                "edition": "ed-b",
                "text": "two",
                "class": "apparatus",
            },
        ],
    )

    paratext = audit_source(tmp_path)["text_families"]["paratext"]

    assert paratext["duplicate_record_keys"] == 0
    assert paratext["duplicate_record_keys_by_file"] == {}


def test_audit_fails_closed_when_required_semantic_metadata_is_missing(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    (tmp_path / "data/oga_dating.json").unlink()

    with pytest.raises(AuditError, match="oga_dating.json"):
        audit_source(tmp_path)
