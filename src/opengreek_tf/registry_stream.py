"""Strict complete source-registry typed IR, shared with the source fact graph.

Preserves physical JSON member order, nested ordered facts and explicit JSON null;
does not invent OGA/OGC IDs, Greek word slots or one-to-one authority links.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .record_stream import FieldArray, FieldObject

Kind = Literal["author", "work"]
_SOURCE = "data/source_registry.json"
_AUTHOR_FIELDS = {"name", "aliases"}
_WORK_FIELDS = {
    "author", "title", "aliases", "default_edition",
    "best_source", "tags", "editions",
}
_EDITION_FIELDS = {
    "name", "provider", "scheme", "editor", "year",
    "source", "servable", "license", "scheme_inferred", "aliases",
}
_AUTHOR_ALIASES = {"wikidata", "viaf", "gnd", "isni"}
_WORK_ALIASES = {"cts", "wikidata"}
_EDITION_ALIASES = {"cts"}
_BEST_SOURCES = {
    "pd_edition", "locked", "open_corpus", "duplicate",
    "migne_pd", "migne_cgpg", "byzantium_gr",
}


class RegistryError(ValueError):
    """Pinned source registry violates its audited semantic schema."""


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    kind: Kind
    slug: str
    ordinal: int
    fields: FieldObject
    relative_file: str = _SOURCE

    @property
    def occurrence_key(self) -> tuple[str, int]:
        """The source section and physical JSON member ordinal identify a row."""
        return (f"{self.relative_file}#{self.kind}s", self.ordinal)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def _object(value: Any, expected: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise RegistryError(f"{where}: expected exactly {sorted(expected)!r}")
    return value


def _text(value: Any, where: str) -> str:
    if type(value) is not str or "\r" in value:
        raise RegistryError(f"{where}: expected exact string without CR")
    return value


def _key(value: Any, where: str) -> str:
    text = _text(value, where)
    if not text:
        raise RegistryError(f"{where}: empty physical source member ID")
    return text


def _aliases(value: Any, allowed: set[str], where: str) -> FieldObject:
    if not isinstance(value, dict):
        raise RegistryError(f"{where}: expected alias object")
    entries: list[tuple[str, str]] = []
    for name, alias in value.items():
        if name not in allowed:
            raise RegistryError(f"{where}: unknown alias namespace {name!r}")
        entries.append((name, _text(alias, f"{where}.{name}")))
    return FieldObject(tuple(entries))


def _author(raw: Any, where: str) -> FieldObject:
    obj = _object(raw, _AUTHOR_FIELDS, where)
    result: list[tuple[str, str | FieldObject]] = []
    for name, value in obj.items():
        if name == "name":
            result.append((name, _text(value, f"{where}.name")))
        else:
            result.append((name, _aliases(value, _AUTHOR_ALIASES, f"{where}.aliases")))
    return FieldObject(tuple(result))


def _edition(raw: Any, where: str) -> FieldObject:
    obj = _object(raw, _EDITION_FIELDS, where)
    entries: list[tuple[str, str | int | bool | None | FieldObject]] = []
    for name, value in obj.items():
        if name == "year":
            if value is not None and type(value) is not int:
                raise RegistryError(f"{where}.year: expected int or explicit null")
            entries.append((name, value))
        elif name in {"servable", "scheme_inferred"}:
            if type(value) is not bool:
                raise RegistryError(f"{where}.{name}: expected bool")
            entries.append((name, value))
        elif name == "aliases":
            entries.append((name, _aliases(value, _EDITION_ALIASES, f"{where}.aliases")))
        else:
            entries.append((name, _text(value, f"{where}.{name}")))
    return FieldObject(tuple(entries))


def _work(
    raw: Any, where: str, authors: set[str],
) -> FieldObject:
    obj = _object(raw, _WORK_FIELDS, where)
    if type(obj["author"]) is not str or obj["author"] not in authors:
        raise RegistryError(f"{where}.author: unknown source author")
    default = obj["default_edition"]
    if default is not None and type(default) is not str:
        raise RegistryError(f"{where}.default_edition: expected str or null")
    if type(obj["best_source"]) is not str or obj["best_source"] not in _BEST_SOURCES:
        raise RegistryError(f"{where}.best_source: unknown source class")
    if not isinstance(obj["tags"], list):
        raise RegistryError(f"{where}.tags: expected array")
    if not isinstance(obj["editions"], dict):
        raise RegistryError(f"{where}.editions: expected object")
    if default is not None and default not in obj["editions"]:
        raise RegistryError(f"{where}.default_edition: missing edition key")
    fields: list[tuple[str, Any]] = []
    for name, value in obj.items():
        if name in {"author", "title", "best_source"}:
            fields.append((name, _text(value, f"{where}.{name}")))
        elif name == "aliases":
            fields.append((name, _aliases(value, _WORK_ALIASES, f"{where}.aliases")))
        elif name == "default_edition":
            fields.append((
                name,
                None if value is None else _text(value, f"{where}.default_edition"),
            ))
        elif name == "tags":
            fields.append((
                name,
                FieldArray(tuple(
                    _text(item, f"{where}.tags[{i}]")
                    for i, item in enumerate(value)
                )),
            ))
        elif name == "editions":
            entries: list[tuple[str, FieldObject]] = []
            for edition_slug, edition in value.items():
                _key(edition_slug, f"{where}.editions")
                entries.append((
                    edition_slug,
                    _edition(edition, f"{where}.editions.{edition_slug}"),
                ))
            fields.append((name, FieldObject(tuple(entries))))
    return FieldObject(tuple(fields))


def iter_registry(source_root: Path) -> Iterator[RegistryRecord]:
    """Validate and yield all author/work source members, preserving physical order.

    The upstream mapping is a single 8.2 MB JSON object, not a JSONL stream.
    This function decodes it once; records are converted and emitted lazily.
    """
    try:
        payload = json.loads(
            (source_root / _SOURCE).read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot decode strict UTF-8 {_SOURCE}") from exc
    root = _object(payload, {"authors", "works"}, _SOURCE)
    authors = root["authors"]
    works = root["works"]
    if (
        not isinstance(authors, dict) or not authors
        or not isinstance(works, dict) or not works
    ):
        raise RegistryError("registry requires nonempty author and work objects")
    author_slugs = {_key(k, "authors") for k in authors}
    for ordinal, (slug, raw) in enumerate(authors.items(), 1):
        yield RegistryRecord("author", slug, ordinal, _author(raw, f"authors.{slug}"))
    for ordinal, (slug, raw) in enumerate(works.items(), 1):
        _key(slug, "works")
        yield RegistryRecord(
            "work", slug, ordinal, _work(raw, f"works.{slug}", author_slugs),
        )
