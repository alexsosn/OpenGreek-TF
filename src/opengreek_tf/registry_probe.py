"""Bounded native TF proof for real source-ledger identity records (issue #20).

Every `atom` represents a real author/work ID ledger entry, never a Greek
word or a fabricated passage. This deliberately does NOT freeze issue #3.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

RegistryKind = Literal["author", "work"]

_FILES: dict[RegistryKind, tuple[str, str, str]] = {
    "author": ("data/author_ids.json", "authors", "oga"),
    "work": ("data/work_ids.json", "works", "ogc"),
}
_NODE_TYPE: dict[RegistryKind, str] = {
    "author": "registryAuthor",
    "work": "registryWork",
}


class RegistryProbeError(ValueError):
    """A ledger or its native TF representation violates source semantics."""


@dataclass(frozen=True, slots=True)
class LedgerRecord:
    kind: RegistryKind
    identifier: str
    source_file: str
    ordinal: int
    slug: str
    status: str
    former_slugs: tuple[str, ...]


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in pairs:
        if key in values:
            raise RegistryProbeError(f"duplicate source JSON key: {key!r}")
        values[key] = value
    return values


def parse_ledger(root: Path, kind: RegistryKind) -> tuple[LedgerRecord, ...]:
    """Parse one complete ID ledger in source order, rejecting malformed entries."""
    if kind not in _FILES:
        raise RegistryProbeError(f"unsupported ledger kind: {kind}")
    relative, root_key, prefix = _FILES[kind]
    try:
        payload = json.loads(
            (root / relative).read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_json_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryProbeError(f"cannot read valid source ledger {relative}") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"_meta", root_key}
        or not isinstance(payload["_meta"], dict)
        or payload["_meta"].get("scheme") != prefix
        or not isinstance(payload[root_key], dict)
    ):
        raise RegistryProbeError(f"invalid {kind} ledger root / namespace")
    rows: list[LedgerRecord] = []
    for ordinal, (identifier, raw) in enumerate(payload[root_key].items(), 1):
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(prefix + r"[0-9]{6}", identifier)
            or not isinstance(raw, dict)
            or set(raw) != {"slug", "former_slugs", "status"}
        ):
            raise RegistryProbeError(f"invalid {kind} ID or record: {identifier!r}")
        slug, aliases, status = raw["slug"], raw["former_slugs"], raw["status"]
        if (
            not isinstance(slug, str)
            or not slug
            or not isinstance(status, str)
            or status not in {"served", "retired"}
            or not isinstance(aliases, list)
            or any(not isinstance(alias, str) or not alias for alias in aliases)
        ):
            raise RegistryProbeError(f"invalid source fields for {identifier!r}")
        rows.append(
            LedgerRecord(
                kind, identifier, relative, ordinal, slug, status, tuple(aliases)
            )
        )
    counts = payload["_meta"].get("counts")
    if counts is not None:
        if not isinstance(counts, dict):
            raise RegistryProbeError(f"invalid {kind} counts")
        observed = {
            "active": sum(entry.status == "served" for entry in rows),
            "retired": sum(entry.status == "retired" for entry in rows),
        }
        for key, value in observed.items():
            if type(counts.get(key)) is not int or counts[key] != value:
                raise RegistryProbeError(f"{kind} ledger {key} count mismatch")
    return tuple(rows)


def _selected_records(
    source_root: Path, authors: tuple[str, ...], works: tuple[str, ...]
) -> tuple[LedgerRecord, ...]:
    selected: list[LedgerRecord] = []
    selections: tuple[tuple[RegistryKind, tuple[str, ...]], ...] = (
        ("author", authors), ("work", works),
    )
    for kind, ids in selections:
        if len(ids) != len(set(ids)):
            raise RegistryProbeError(f"duplicate selection for {kind} ledger")
        all_rows = parse_ledger(source_root, kind)
        requested = set(ids)
        actual = {row.identifier for row in all_rows if row.identifier in requested}
        if actual != requested:
            raise RegistryProbeError(f"{kind} identity not in pinned ledger: {requested-actual}")
        selected.extend(row for row in all_rows if row.identifier in requested)
    if not selected:
        raise RegistryProbeError("cannot emit an empty source-record TF proof")
    return tuple(selected)


def write_registry_probe(
    source_root: Path,
    destination: Path,
    *,
    authors: tuple[str, ...],
    works: tuple[str, ...],
) -> None:
    """Emit a native TF graph of actual ID-ledger source-record atoms only."""
    if destination.exists() or destination.is_symlink():
        raise RegistryProbeError("destination already exists")
    records = _selected_records(source_root, authors, works)
    features: dict[str, dict[str, str]] = {
        "atom_kind": {"description": "Declared genuine source-atom class"},
        "source_file": {"description": "Exact source ledger path"},
        "source_record_id": {"description": "Exact opaque source record key"},
        "source_ordinal": {"description": "One-based entry order in source ledger"},
        "opaque_id": {"description": "Immutable Open Greek ID"},
        "registry_slug": {"description": "Current declared source slug"},
        "registry_status": {"description": "Declared served or retired state"},
    }
    aliases_present = any(record.former_slugs for record in records)
    if aliases_present:
        features.update({
            "alias_value": {"description": "One source-declared former slug"},
            "alias_position": {"description": "Zero-based index in former_slugs"},
            "has_former_slug": {"description": "Source-declared former-slug relation"},
        })

    def director(cv: CV) -> None:
        for record in records:
            identity = cv.node(_NODE_TYPE[record.kind])
            atom = cv.slot()
            cv.feature(
                atom,
                atom_kind="registry-record",
                source_file=record.source_file,
                source_record_id=record.identifier,
                source_ordinal=record.ordinal,
            )
            cv.feature(
                identity,
                opaque_id=record.identifier,
                registry_slug=record.slug,
                registry_status=record.status,
            )
            cv.terminate(identity)
            for position, former in enumerate(record.former_slugs):
                # The alias is a fact *about this exact real source entry*;
                # it does not occupy a word or create an extra source atom.
                alias = cv.node("formerSlug", slots=[atom[1]])
                cv.feature(alias, alias_value=former, alias_position=position)
                cv.edge(identity, alias, has_former_slug=None)
                cv.terminate(alias)

    output = Fabric(locations=str(destination), silent="deep")
    converter = CV(output, silent="auto")
    integer_features = {"source_ordinal"}
    if aliases_present:
        integer_features.add("alias_position")
    ok = converter.walk(
        director,
        slotType="atom",
        generic={"source": "Pinned Open Greek identity-ledger research probe"},
        # CV 13.1 insists on explicit (possibly empty) section definitions
        # and the conventional default format. Both formats display *actual
        # opaque registry IDs* only; no Greek word or passage is invented.
        otext={
            "sectionTypes": "",
            "sectionFeatures": "",
            "fmt:text-orig-full": "{source_record_id}",
            "fmt:metadata-id": "{source_record_id}",
        },
        intFeatures=integer_features,
        featureMeta=features,
        warn=False,
    )
    if not ok:
        raise RegistryProbeError("native TF ledger atom graph rejected by CV")


def read_registry_probe(destination: Path) -> tuple[LedgerRecord, ...]:
    """Independently load TF node/edge semantics without any source JSON."""
    aliases_present = (destination / "alias_value.tf").is_file()
    required = (
        "atom_kind source_file source_record_id source_ordinal "
        "opaque_id registry_slug registry_status"
    )
    if aliases_present:
        required += " alias_value alias_position has_former_slug"
    loaded = Fabric(locations=str(destination), silent="deep").load(
        required, silent="deep"
    )
    if not loaded:
        raise RegistryProbeError("native TF features cannot be loaded")
    if (destination / "form.tf").exists():
        raise RegistryProbeError("metadata records must not invent source text")
    identities: list[LedgerRecord] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_slots: set[int] = set()
    seen_alias_nodes: set[int] = set()
    source_atoms = set(loaded.F.otype.s("atom"))
    if loaded.F.otype.s("word") or loaded.F.otype.s("passage"):
        raise RegistryProbeError("metadata proof must not introduce phantom text")
    for kind in ("author", "work"):
        source_file, _root_key, prefix = _FILES[kind]
        for node in loaded.F.otype.s(_NODE_TYPE[kind]):
            identifier = loaded.F.opaque_id.v(node)
            slug = loaded.F.registry_slug.v(node)
            status = loaded.F.registry_status.v(node)
            key = (kind, identifier)
            if (
                not isinstance(identifier, str)
                or re.fullmatch(prefix + r"[0-9]{6}", identifier) is None
                or not isinstance(slug, str)
                or not slug
                or status not in {"served", "retired"}
                or key in seen_keys
            ):
                raise RegistryProbeError("missing/duplicate/malformed registry identity")
            seen_keys.add(key)
            slots = tuple(loaded.E.oslots.s(node))
            if len(slots) != 1 or slots[0] not in source_atoms or slots[0] in seen_slots:
                raise RegistryProbeError("missing or shared real registry-record atom")
            slot = slots[0]
            seen_slots.add(slot)
            if (
                loaded.F.atom_kind.v(slot) != "registry-record"
                or loaded.F.source_file.v(slot) != source_file
                or loaded.F.source_record_id.v(slot) != identifier
            ):
                raise RegistryProbeError("registry atom source provenance mismatch")
            ordinal = loaded.F.source_ordinal.v(slot)
            if type(ordinal) is not int or ordinal < 1:
                raise RegistryProbeError("invalid source-ledger ordinal")
            aliases: dict[int, str] = {}
            linked = loaded.E.has_former_slug.f(node) if aliases_present else set()
            for alias in linked:
                if (
                    alias not in loaded.F.otype.s("formerSlug")
                    or alias in seen_alias_nodes
                    or tuple(loaded.E.oslots.s(alias)) != slots
                ):
                    raise RegistryProbeError("alias not anchored to its source record")
                seen_alias_nodes.add(alias)
                index = loaded.F.alias_position.v(alias)
                value = loaded.F.alias_value.v(alias)
                if (
                    type(index) is not int
                    or index < 0
                    or index in aliases
                    or not isinstance(value, str)
                    or not value
                ):
                    raise RegistryProbeError("invalid alias ordinal/value")
                aliases[index] = value
            if set(aliases) != set(range(len(aliases))):
                raise RegistryProbeError("missing/reordered former-slug entry")
            identities.append(
                LedgerRecord(
                    kind, identifier, source_file, ordinal,
                    slug, status, tuple(aliases[i] for i in sorted(aliases)),
                )
            )
    if seen_slots != source_atoms:
        raise RegistryProbeError("unaccounted metadata source-record atoms")
    if seen_alias_nodes != set(loaded.F.otype.s("formerSlug")):
        raise RegistryProbeError("orphan former-slug fact")
    for kind in ("author", "work"):
        ordinals = [r.ordinal for r in identities if r.kind == kind]
        if len(set(ordinals)) != len(ordinals):
            raise RegistryProbeError("duplicate physical source-ledger ordinal")
    return tuple(sorted(
        identities, key=lambda r: (0 if r.kind == "author" else 1, r.ordinal)
    ))
