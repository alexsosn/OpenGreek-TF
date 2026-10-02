"""Deterministic semantic-surface audit for a pinned Open Greek source tree."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TEXT_FAMILIES = {
    "primary": ("data/corpus", True),
    "secondary": ("data/corpus_secondary", True),
    "paratext": ("data/paratext", False),
}

JSONL_VOCAB_FIELDS = frozenset(
    {"source", "edition", "license", "rank", "witness", "lang", "class"}
)

# name -> (path, collection key, wildcard object paths, exact vocabulary paths)
MAPPING_ARTIFACTS: dict[
    str, tuple[str, str | None, frozenset[str], frozenset[str]]
] = {
    "work_index": (
        "data/work_index.json",
        "works",
        frozenset(),
        frozenset(
            {
                "/manifestation/source",
                "/manifestation/edition",
                "/manifestation/license",
            }
        ),
    ),
    "work_index_redirects": (
        "data/work_index.json",
        "redirects",
        frozenset(),
        frozenset(),
    ),
    "work_ids": ("data/work_ids.json", "works", frozenset(), frozenset({"/status"})),
    "author_ids": (
        "data/author_ids.json",
        "authors",
        frozenset(),
        frozenset({"/status"}),
    ),
    "source_registry_works": (
        "data/source_registry.json",
        "works",
        frozenset({"/editions"}),
        frozenset(
            {
                "/editions/*/source",
                "/editions/*/license",
            }
        ),
    ),
    "source_registry_authors": (
        "data/source_registry.json",
        "authors",
        frozenset(),
        frozenset(),
    ),
    "corpus_editions": (
        "data/corpus_editions.json",
        None,
        frozenset(),
        frozenset({"/source", "/edition", "/license"}),
    ),
    "served_scheme_inference": (
        "data/served_scheme_inference.json",
        "works",
        frozenset(),
        frozenset({"/class", "/scheme"}),
    ),
    "tlg_crosswalk": (
        "data/tlg_crosswalk.json",
        None,
        frozenset(),
        frozenset(),
    ),
    "coverage": (
        "data/coverage.json",
        None,
        frozenset(),
        frozenset({"/source", "/license"}),
    ),
}

# Curated or measured metadata that may affect research interpretation. These are
# audited separately from the reader-facing WEMI index so #3 can decide whether
# each fact belongs in TF semantics or provenance.
OPTIONAL_MAPPING_ARTIFACTS: dict[
    str, tuple[str, str | None, frozenset[str], frozenset[str]]
] = {
    "ocr_quality_works": (
        "data/ocr_quality_report.json",
        "works",
        frozenset(),
        frozenset(),
    ),
    "serving_deficits": (
        "data/serving_deficits.json",
        "works",
        frozenset(),
        frozenset(),
    ),
    "work_metadata_remaps": (
        "data/work_metadata_remaps.json",
        "works",
        frozenset(),
        frozenset(),
    ),
    "pseudo_author_attribution_works": (
        "data/pseudo_author_attributions.json",
        "works",
        frozenset(),
        frozenset(),
    ),
    "pseudo_author_attribution_authors": (
        "data/pseudo_author_attributions.json",
        "authors",
        frozenset(),
        frozenset(),
    ),
}

OPTIONAL_LIST_ARTIFACTS: dict[str, tuple[str, str]] = {
    "partial_ceiling_works": ("data/partial_ceilings.json", "works"),
    "partial_ceiling_rule_exceptions": (
        "data/partial_ceilings.json",
        "rule_exceptions",
    ),
    "work_id_aliases": ("data/work_id_aliases.json", "renames"),
}

OPTIONAL_OBJECT_ARTIFACTS: dict[str, tuple[str, str]] = {
    "partial_ceiling_policy": ("data/partial_ceilings.json", "title_rule"),
}


class AuditError(RuntimeError):
    """Raised when the pinned source cannot be audited losslessly."""


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


@dataclass
class _PathStat:
    present: int = 0
    types: Counter[str] = field(default_factory=Counter)
    list_min: int | None = None
    list_max: int | None = None
    object_min: int | None = None
    object_max: int | None = None

    def observe(self, value: Any) -> None:
        self.present += 1
        self.types[_json_type(value)] += 1
        if isinstance(value, list):
            length = len(value)
            self.list_min = length if self.list_min is None else min(self.list_min, length)
            self.list_max = length if self.list_max is None else max(self.list_max, length)
        if isinstance(value, dict):
            length = len(value)
            self.object_min = (
                length if self.object_min is None else min(self.object_min, length)
            )
            self.object_max = (
                length if self.object_max is None else max(self.object_max, length)
            )

    def render(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "present": self.present,
            "types": dict(sorted(self.types.items())),
        }
        if self.list_min is not None:
            result["list_length"] = {"min": self.list_min, "max": self.list_max}
        if self.object_min is not None:
            result["object_length"] = {
                "min": self.object_min,
                "max": self.object_max,
            }
        return result


@dataclass
class _Census:
    wildcard_object_paths: frozenset[str] = frozenset()
    vocabulary_paths: frozenset[str] = frozenset()
    paths: dict[str, _PathStat] = field(default_factory=dict)
    vocabularies: dict[str, set[str]] = field(default_factory=dict)

    def _path_stat(self, path: str) -> _PathStat:
        return self.paths.setdefault(path, _PathStat())

    def observe(self, value: Any, path: str) -> None:
        self._path_stat(path).observe(value)

        if path in self.vocabulary_paths and value is not None:
            if isinstance(value, (str, int, float, bool)):
                self.vocabularies.setdefault(path, set()).add(str(value))

        if isinstance(value, list):
            child_path = f"{path}/*"
            for item in value:
                self.observe(item, child_path)
            return

        if isinstance(value, dict):
            wildcard = path in self.wildcard_object_paths
            for key in sorted(value):
                child_path = f"{path}/*" if wildcard else f"{path}/{key}"
                self.observe(value[key], child_path)

    def observe_record(self, record: Any) -> None:
        if isinstance(record, dict):
            for key in sorted(record):
                self.observe(record[key], f"/{key}")
        else:
            self.observe(record, "/value")

    def render(
        self, record_count: int
    ) -> tuple[dict[str, Any], dict[str, list[str]]]:
        paths: dict[str, Any] = {}
        for key in sorted(self.paths):
            rendered = self.paths[key].render()
            if not key.endswith("/*"):
                parent = key.rsplit("/", 1)[0]
                if parent == "":
                    contexts = record_count
                else:
                    parent_stat = self.paths.get(parent)
                    contexts = (
                        parent_stat.types.get("object", 0)
                        if parent_stat is not None
                        else 0
                    )
                if contexts >= self.paths[key].present:
                    rendered["missing"] = contexts - self.paths[key].present
            paths[key] = rendered
        vocabs = {
            key: sorted(values)
            for key, values in sorted(self.vocabularies.items())
        }
        return paths, vocabs


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise AuditError(f"required metadata is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"invalid JSON metadata: {path}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _audit_jsonl_family(
    source: Path,
    relative_dir: str,
    *,
    compare_row_slug_to_filename: bool,
) -> dict[str, Any]:
    directory = source / relative_dir
    if not directory.is_dir():
        raise AuditError(f"required text family is missing: {directory}")

    files = sorted(directory.glob("*.jsonl"), key=lambda p: p.name)
    if not files:
        raise AuditError(f"required text family contains no JSONL files: {directory}")

    census = _Census(
        vocabulary_paths=frozenset(f"/{name}" for name in JSONL_VOCAB_FIELDS)
    )
    aggregate = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    rows = 0
    blank_lines = 0
    row_slug_mismatches = 0
    duplicate_loci = 0
    duplicate_record_keys = 0

    for path in files:
        file_hash = _sha256_file(path)
        file_hashes[path.name] = file_hash
        aggregate.update(f"{path.name}\t{file_hash}\n".encode())

        seen_loci: set[str] = set()
        seen_keys: set[tuple[str, ...]] = set()
        expected_slug = path.stem

        try:
            handle = path.open(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise AuditError(f"cannot read JSONL source: {path}") from exc

        with handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    blank_lines += 1
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuditError(f"invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(row, dict):
                    raise AuditError(
                        f"JSONL row is not an object at {path}:{line_number}"
                    )

                rows += 1
                census.observe_record(row)

                if compare_row_slug_to_filename:
                    urn = row.get("urn")
                    if not isinstance(urn, str) or urn != expected_slug:
                        row_slug_mismatches += 1

                locus = row.get("locus")
                if isinstance(locus, str) and locus:
                    if locus in seen_loci:
                        duplicate_loci += 1
                    else:
                        seen_loci.add(locus)

                record_key = tuple(
                    str(row.get(field, ""))
                    for field in ("urn", "locus", "edition", "source", "rank", "witness")
                )
                if record_key in seen_keys:
                    duplicate_record_keys += 1
                else:
                    seen_keys.add(record_key)

    paths, raw_vocabs = census.render(rows)
    vocabularies = {
        path.removeprefix("/"): values
        for path, values in raw_vocabs.items()
        if values
    }
    return {
        "directory": relative_dir,
        "files": len(files),
        "rows": rows,
        "blank_lines": blank_lines,
        "ordered_sha256": aggregate.hexdigest(),
        "file_sha256": file_hashes,
        "paths": paths,
        "vocabularies": dict(sorted(vocabularies.items())),
        "row_slug_mismatches": row_slug_mismatches,
        "duplicate_loci": duplicate_loci,
        "duplicate_record_keys": duplicate_record_keys,
    }


def _collection_from_payload(
    payload: Any,
    *,
    path: Path,
    collection_key: str | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AuditError(f"metadata root is not an object: {path}")
    collection = payload if collection_key is None else payload.get(collection_key)
    if not isinstance(collection, dict):
        raise AuditError(
            f"metadata collection {collection_key!r} is not an object: {path}"
        )
    if collection_key is None and "_meta" in collection:
        collection = {key: value for key, value in collection.items() if key != "_meta"}
    return collection


def _audit_mapping(
    source: Path,
    relative_path: str,
    collection_key: str | None,
    wildcard_paths: frozenset[str],
    vocabulary_paths: frozenset[str],
) -> dict[str, Any]:
    path = source / relative_path
    payload = _load_json(path)
    collection = _collection_from_payload(
        payload,
        path=path,
        collection_key=collection_key,
    )
    census = _Census(
        wildcard_object_paths=wildcard_paths,
        vocabulary_paths=vocabulary_paths,
    )
    for key in sorted(collection):
        census.observe_record(collection[key])

    paths, vocabularies = census.render(len(collection))
    key_digest = hashlib.sha256()
    for key in sorted(collection):
        key_digest.update(f"{key}\n".encode())

    return {
        "path": relative_path,
        "collection": collection_key,
        "records": len(collection),
        "file_sha256": _sha256_file(path),
        "keys_sha256": key_digest.hexdigest(),
        "paths": paths,
        "vocabularies": vocabularies,
    }


def _audit_list(
    source: Path,
    relative_path: str,
    collection_key: str,
) -> dict[str, Any]:
    path = source / relative_path
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise AuditError(f"metadata root is not an object: {path}")
    values = payload.get(collection_key)
    if not isinstance(values, list):
        raise AuditError(
            f"metadata collection {collection_key!r} is not an array: {path}"
        )
    census = _Census()
    for value in values:
        census.observe_record(value)
    paths, vocabularies = census.render(len(values))
    return {
        "path": relative_path,
        "collection": collection_key,
        "records": len(values),
        "file_sha256": _sha256_file(path),
        "paths": paths,
        "vocabularies": vocabularies,
    }


def _audit_named_object(
    source: Path,
    relative_path: str,
    object_key: str,
) -> dict[str, Any]:
    path = source / relative_path
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise AuditError(f"metadata root is not an object: {path}")
    value = payload.get(object_key)
    if not isinstance(value, dict):
        raise AuditError(
            f"metadata object {object_key!r} is not an object: {path}"
        )
    census = _Census()
    census.observe_record(value)
    paths, vocabularies = census.render(1)
    return {
        "path": relative_path,
        "collection": object_key,
        "records": 1,
        "file_sha256": _sha256_file(path),
        "paths": paths,
        "vocabularies": vocabularies,
    }


def _audit_release_manifest(source: Path) -> dict[str, Any]:
    relative_path = "data/corpus_release.json"
    path = source / relative_path
    payload = _load_json(path)
    census = _Census()
    census.observe_record(payload)
    paths, vocabularies = census.render(1)
    release_id = payload.get("release_id") if isinstance(payload, dict) else None
    return {
        "path": relative_path,
        "records": 1,
        "release_id": release_id,
        "file_sha256": _sha256_file(path),
        "paths": paths,
        "vocabularies": vocabularies,
    }


def _audit_catalog(source: Path) -> dict[str, Any]:
    relative_path = "data/corpus_catalog.tsv"
    path = source / relative_path
    if not path.is_file():
        raise AuditError(f"required catalog is missing: {path}")

    vocab_fields = {"source", "edition", "license", "correction", "scheme_class"}
    vocabularies: dict[str, set[str]] = {field: set() for field in vocab_fields}
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames is None:
                raise AuditError(f"catalog has no header: {path}")
            header = list(reader.fieldnames)
            rows = 0
            for row in reader:
                rows += 1
                for field in vocab_fields:
                    value = row.get(field)
                    if value:
                        vocabularies[field].add(value)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise AuditError(f"invalid catalog TSV: {path}") from exc

    return {
        "path": relative_path,
        "rows": rows,
        "columns": header,
        "file_sha256": _sha256_file(path),
        "vocabularies": {
            key: sorted(values)
            for key, values in sorted(vocabularies.items())
        },
    }


def _existing_optional_mapping_reports(source: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    for name, spec in OPTIONAL_MAPPING_ARTIFACTS.items():
        relative_path, collection_key, wildcard_paths, vocabulary_paths = spec
        if (source / relative_path).is_file():
            yield (
                name,
                _audit_mapping(
                    source,
                    relative_path,
                    collection_key,
                    wildcard_paths,
                    vocabulary_paths,
                ),
            )


def _existing_optional_list_reports(source: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    for name, (relative_path, collection_key) in OPTIONAL_LIST_ARTIFACTS.items():
        if (source / relative_path).is_file():
            yield name, _audit_list(source, relative_path, collection_key)


def _existing_optional_object_reports(
    source: Path,
) -> Iterable[tuple[str, dict[str, Any]]]:
    for name, (relative_path, object_key) in OPTIONAL_OBJECT_ARTIFACTS.items():
        if (source / relative_path).is_file():
            yield name, _audit_named_object(source, relative_path, object_key)


def audit_source(source: str | Path) -> dict[str, Any]:
    """Audit the complete currently recognized semantic surface deterministically."""
    root = Path(source).resolve()
    if not root.is_dir():
        raise AuditError(f"source directory does not exist: {root}")

    text_families: dict[str, Any] = {}
    for name, (relative_dir, compare_slug) in TEXT_FAMILIES.items():
        text_families[name] = _audit_jsonl_family(
            root,
            relative_dir,
            compare_row_slug_to_filename=compare_slug,
        )

    metadata: dict[str, Any] = {}
    for name, spec in MAPPING_ARTIFACTS.items():
        relative_path, collection_key, wildcard_paths, vocabulary_paths = spec
        metadata[name] = _audit_mapping(
            root,
            relative_path,
            collection_key,
            wildcard_paths,
            vocabulary_paths,
        )
    metadata.update(_existing_optional_mapping_reports(root))
    metadata.update(_existing_optional_list_reports(root))
    metadata.update(_existing_optional_object_reports(root))
    metadata["corpus_release"] = _audit_release_manifest(root)

    return {
        "schema_version": 1,
        "text_families": text_families,
        "metadata": dict(sorted(metadata.items())),
        "catalog": _audit_catalog(root),
    }
