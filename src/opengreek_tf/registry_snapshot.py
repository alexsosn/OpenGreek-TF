"""Batch all immutable author/work ID-ledger entries into native TF (#20).

This covers the 5,460 ID-ledger entries, NOT the broader Open Greek catalogs.
The validator independently reads source JSON and *loaded* TF features.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .registry_probe import (
    LedgerRecord,
    RegistryKind,
    RegistryProbeError,
    parse_ledger,
    read_registry_probe,
    write_registry_probe,
)


@dataclass(frozen=True, slots=True)
class LedgerSnapshotStats:
    authors: int
    works: int
    retired_authors: int
    retired_works: int
    former_slug_facts: int
    source_atoms: int


def _reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Independent JSON key-conservation check rather than last-wins parsing."""
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise RegistryProbeError(f"repeated source JSON key: {key}")
        out[key] = value
    return out


def _independent_raw_records(source_root: Path) -> tuple[LedgerRecord, ...]:
    """Walk every source entry without using the registry-probe source parser."""
    records: list[LedgerRecord] = []
    sources: tuple[tuple[RegistryKind, str, str, str], ...] = (
        ("author", "data/author_ids.json", "authors", "oga"),
        ("work", "data/work_ids.json", "works", "ogc"),
    )
    for kind, filename, collection, namespace in sources:
        try:
            payload = json.loads(
                (source_root / filename).read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RegistryProbeError(f"cannot read source {filename}") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"_meta", collection}
            or not isinstance(payload["_meta"], dict)
            or payload["_meta"].get("scheme") != namespace
            or not isinstance(payload[collection], dict)
        ):
            raise RegistryProbeError(f"invalid source ledger root: {filename}")
        ledger = payload[collection]
        for ordinal, (identifier, entry) in enumerate(ledger.items(), 1):
            if (
                not isinstance(identifier, str)
                or re.fullmatch(namespace + r"[0-9]{6}", identifier) is None
                or not isinstance(entry, dict)
                or set(entry) != {"slug", "status", "former_slugs"}
                or not isinstance(entry["slug"], str)
                or not entry["slug"]
                or entry["status"] not in ("served", "retired")
                or not isinstance(entry["former_slugs"], list)
                or any(
                    not isinstance(alias, str) or not alias
                    for alias in entry["former_slugs"]
                )
            ):
                raise RegistryProbeError(f"invalid source ledger entry: {identifier}")
            records.append(
                LedgerRecord(
                    kind, identifier, filename, ordinal, entry["slug"],
                    entry["status"], tuple(entry["former_slugs"]),
                )
            )
        counts = payload["_meta"].get("counts")
        if not isinstance(counts, dict):
            raise RegistryProbeError(f"missing ledger counts: {filename}")
        observed_active = sum(entry["status"] == "served" for entry in ledger.values())
        observed_retired = sum(entry["status"] == "retired" for entry in ledger.values())
        if (
            type(counts.get("active")) is not int
            or type(counts.get("retired")) is not int
            or counts["active"] != observed_active
            or counts["retired"] != observed_retired
        ):
            raise RegistryProbeError(f"source ledger counts changed: {filename}")
    return tuple(records)


def _stats(records: tuple[LedgerRecord, ...]) -> LedgerSnapshotStats:
    count_authors = sum(row.kind == "author" for row in records)
    count_works = sum(row.kind == "work" for row in records)
    return LedgerSnapshotStats(
        authors=count_authors,
        works=count_works,
        retired_authors=sum(
            row.kind == "author" and row.status == "retired" for row in records
        ),
        retired_works=sum(
            row.kind == "work" and row.status == "retired" for row in records
        ),
        former_slug_facts=sum(len(row.former_slugs) for row in records),
        source_atoms=len(records),
    )


def validate_full_registry_snapshot(
    source_root: Path, destination: Path,
) -> LedgerSnapshotStats:
    """Independently compare *all* source IDs, status, order and aliases to TF."""
    expected = _independent_raw_records(source_root)
    observed = read_registry_probe(destination)
    if observed != expected:
        wrong = next(
            (
                index
                for index, (left, right) in enumerate(zip(expected, observed, strict=False))
                if left != right
            ),
            min(len(expected), len(observed)),
        )
        raise RegistryProbeError(
            f"full ledger conservation failed at index {wrong}: "
            f"source={len(expected)} TF={len(observed)}"
        )
    return _stats(observed)


def write_full_registry_snapshot(
    source_root: Path, destination: Path,
) -> LedgerSnapshotStats:
    """Emit every author/work ID-ledger row via the tested native-TF writer."""
    author_rows = parse_ledger(source_root, "author")
    work_rows = parse_ledger(source_root, "work")
    if not author_rows or not work_rows:
        raise RegistryProbeError("both source identity ledgers must contain records")
    write_registry_probe(
        source_root, destination,
        authors=tuple(row.identifier for row in author_rows),
        works=tuple(row.identifier for row in work_rows),
    )
    return validate_full_registry_snapshot(source_root, destination)
