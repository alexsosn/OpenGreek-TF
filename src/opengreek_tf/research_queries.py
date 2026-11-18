"""Literal Greek and provenance queries against genuine native Text-Fabric F/E.

This intentionally does not infer Greek lexical tokens, work identities or
relations between primary editions and unaligned secondary witnesses.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tf.fabric import Fabric  # type: ignore[import-untyped]


class NativeResearchQueryError(ValueError):
    """Unsupported or unsafe native TF research query."""


@dataclass(frozen=True, slots=True)
class NativeResearchHit:
    kind: str
    source_file: str
    source_ordinal: int
    source_record_id: str
    source_seq: int
    text: str
    urn: str | None = None
    edition: str | None = None
    source: str | None = None
    license: str | None = None
    locus: str | None = None
    slug: str | None = None
    page: str | None = None


_KINDS = {
    "primary-passage": "passage",
    "secondary-witness": "metadataRecord",
    "paratext-record": "metadataRecord",
}
_SOURCE_STRINGS = frozenset({
    "urn", "edition", "source", "license", "locus", "slug", "page", "text",
})


def _exact_CR_source_string(
    api: Any, owner: int, fact: int, *, has_fragment_text: bool,
) -> str:
    """Source-exact original string from genuine ordered integer-13 F/E.

    This is an independent query-time reconstruction. Ordinary source text
    must remain on its existing direct fact_text fast path. No raw CR is
    stored in Text-Fabric string features or inferred by T.text.
    """
    if api.F.otype.v(owner) != "metadataRecord":
        raise NativeResearchQueryError("primary passage acquired CR source fragments")
    owner_slots = tuple(api.E.oslots.s(owner))
    if len(owner_slots) != 1:
        raise NativeResearchQueryError("metadata record has inauthentic text slots")
    fragments = tuple(api.E.has_cr_fragment.f(fact))
    if not fragments:
        raise NativeResearchQueryError("missing original CR fragments")
    seen_nodes: set[int] = set()
    by_position: dict[int, tuple[str, str | int]] = {}
    for fragment in fragments:
        position = api.F.fragment_position.v(fragment)
        kind = api.F.fragment_kind.v(fragment)
        literal = (
            api.F.fragment_text.v(fragment) if has_fragment_text else None
        )
        codepoint = api.F.fragment_codepoint.v(fragment)
        if (
            fragment in seen_nodes
            or api.F.otype.v(fragment) != "crFragment"
            or tuple(api.E.oslots.s(fragment)) != owner_slots
            or type(position) is not int or position < 0
            or position in by_position
        ):
            raise NativeResearchQueryError("forged CR fragment or source provenance")
        seen_nodes.add(fragment)
        if kind == "run":
            if (
                type(literal) is not str or not literal
                or "\r" in literal or codepoint is not None
            ):
                raise NativeResearchQueryError("invalid literal source CR run")
            by_position[position] = ("run", literal)
        elif kind == "cr":
            if type(codepoint) is not int or codepoint != 13 or literal is not None:
                raise NativeResearchQueryError("invalid native integer-13 CR atom")
            by_position[position] = ("cr", 13)
        else:
            raise NativeResearchQueryError("unrecognized native CR source fragment")
    if sorted(by_position) != list(range(len(by_position))):
        raise NativeResearchQueryError("missing or reordered CR source fragment")
    ordered = [by_position[index] for index in range(len(by_position))]
    raw = "".join(value if isinstance(value, str) else "\r" for _, value in ordered)
    expected: list[tuple[str, str | int]] = []
    parts = raw.split("\r")
    for index, part in enumerate(parts):
        if part:
            expected.append(("run", part))
        if index < len(parts) - 1:
            expected.append(("cr", 13))
    if "\r" not in raw or ordered != expected:
        raise NativeResearchQueryError("uncanonical CR source string topology")
    return raw


def _direct_source_strings(
    api: Any, owner: int, *, has_cr_fragments: bool,
    has_fragment_text: bool,
) -> dict[str, str]:
    """Read top-level original JSON string members *through native F/E*.

    One has_fact edge starts at the owner and points to the source object.
    Its direct children are the source member facts. Nested arrays/objects
    remain native facts but cannot masquerade as top-level filter values.
    """
    roots = tuple(api.E.has_fact.f(owner))
    if len(roots) != 1 or api.F.fact_kind.v(roots[0]) != "object":
        raise NativeResearchQueryError("invalid native source fact root")
    members: dict[str, str] = {}
    seen: set[str] = set()
    for fact in api.E.has_fact.f(roots[0]):
        name = api.F.fact_key.v(fact)
        if type(name) is not str or name in seen:
            raise NativeResearchQueryError("invalid or duplicated native source member")
        seen.add(name)
        field_kind = api.F.fact_kind.v(fact)
        if name not in _SOURCE_STRINGS:
            continue
        if field_kind == "str":
            value = api.F.fact_text.v(fact)
            fragment_units = (
                tuple(api.E.has_cr_fragment.f(fact)) if has_cr_fragments else ()
            )
            if fragment_units:
                if value is not None:
                    raise NativeResearchQueryError("CR fact has conflicting native text")
                value = _exact_CR_source_string(
                    api, owner, fact, has_fragment_text=has_fragment_text,
                )
            elif isinstance(value, str) and "\r" in value:
                raise NativeResearchQueryError("raw CR in Text-Fabric string feature")
            if type(value) is not str:
                raise NativeResearchQueryError(f"invalid native source string {name}")
            members[name] = value
        elif name != "page":
            # Original primary page can be a literal integer. The query API
            # exposes only the paratext's original string page identifier.
            raise NativeResearchQueryError(f"nonliteral native source string {name}")
    if "text" not in members:
        raise NativeResearchQueryError("native source record has no literal text")
    return members


def search_native(
    destination: Path,
    *,
    kind: str,
    contains: str = "",
    urn: str | None = None,
    edition: str | None = None,
    source: str | None = None,
    source_file: str | None = None,
    locus: str | None = None,
    max_results: int = 20,
) -> tuple[NativeResearchHit, ...]:
    """Search the verified native TF dataset without reading original JSONL.

    Literal substring, Unicode/case/accent-sensitive, not a lemmatizer or
    aligned witness search. Bounded *results*, but whole-corpus F/E loading
    and passage scans may still consume substantial time and memory.
    """
    if type(kind) is not str or kind not in _KINDS:
        raise NativeResearchQueryError("unsupported native record kind")
    if type(max_results) is not int or not 1 <= max_results <= 10000:
        raise NativeResearchQueryError("invalid max_results")
    if type(contains) is not str:
        raise NativeResearchQueryError("contains must be a literal string")
    for name, value in (
        ("urn", urn), ("edition", edition), ("source", source),
        ("source_file", source_file), ("locus", locus),
    ):
        if value is not None and type(value) is not str:
            raise NativeResearchQueryError(f"{name} must be a literal string")

    fabric = Fabric(locations=str(destination), silent="deep")
    inventory = fabric.explore(silent="deep")
    if not inventory:
        raise NativeResearchQueryError("cannot discover native Text-Fabric features")
    node_features = set(inventory["nodes"])
    edge_features = set(inventory["edges"])
    needed = {
        "source_file", "source_ordinal", "source_record_id", "source_seq",
        "record_kind", "fact_kind", "fact_key", "fact_text",
    }
    if (
        not needed.issubset(node_features)
        or "has_fact" not in edge_features
        or (kind == "primary-passage" and "form" not in node_features)
    ):
        raise NativeResearchQueryError("missing native source F/E features")
    has_cr_fragments = "has_cr_fragment" in edge_features
    fragment_features = {
        "fragment_kind", "fragment_position", "fragment_codepoint",
        "fragment_text",
    }
    if (
        (has_cr_fragments and not {
            "fragment_kind", "fragment_position", "fragment_codepoint",
        }.issubset(node_features))
        or (not has_cr_fragments and bool(fragment_features & node_features))
    ):
        raise NativeResearchQueryError("incomplete or forged native CR feature schema")
    to_load = needed | {"has_fact"}
    if kind == "primary-passage":
        to_load.add("form")
    if has_cr_fragments:
        to_load.update({
            "has_cr_fragment", "fragment_kind", "fragment_position",
            "fragment_codepoint",
        })
        if "fragment_text" in node_features:
            to_load.add("fragment_text")
    api: Any = fabric.load(" ".join(sorted(to_load)), silent="deep")
    if not api:
        raise NativeResearchQueryError("cannot load native source F/E features")

    node_type = _KINDS[kind]
    output: list[NativeResearchHit] = []
    # TF node type ordering is not guaranteed to equal caller's original
    # cross-family record order; source_seq is its explicit global order.
    ordered = sorted(api.F.otype.s(node_type), key=api.F.source_seq.v)
    for owner in ordered:
        if api.F.record_kind.v(owner) != kind:
            continue
        fields = _direct_source_strings(
            api, owner, has_cr_fragments=has_cr_fragments,
            has_fragment_text="fragment_text" in node_features,
        )
        text = fields["text"]
        if kind == "primary-passage":
            rendered = api.T.text(owner, fmt="text-orig-full")
            if rendered != text:
                raise NativeResearchQueryError("native Greek text differs from source facts")
            text = rendered
        if (
            contains not in text
            or (urn is not None and fields.get("urn") != urn)
            or (edition is not None and fields.get("edition") != edition)
            or (source is not None and fields.get("source") != source)
            or (locus is not None and fields.get("locus") != locus)
        ):
            continue
        original_file = api.F.source_file.v(owner)
        original_ordinal = api.F.source_ordinal.v(owner)
        record_id = api.F.source_record_id.v(owner)
        sequence = api.F.source_seq.v(owner)
        if (
            type(original_file) is not str or not original_file
            or type(original_ordinal) is not int or original_ordinal < 1
            or type(record_id) is not str or not record_id
            or type(sequence) is not int or sequence < 1
        ):
            raise NativeResearchQueryError("invalid source occurrence provenance")
        if source_file is not None and original_file != source_file:
            continue
        output.append(NativeResearchHit(
            kind=kind,
            source_file=original_file, source_ordinal=original_ordinal,
            source_record_id=record_id, source_seq=sequence,
            text=text,
            urn=fields.get("urn"), edition=fields.get("edition"),
            source=fields.get("source"), license=fields.get("license"),
            locus=fields.get("locus"), slug=fields.get("slug"),
            page=fields.get("page"),
        ))
        if len(output) == max_results:
            break
    return tuple(output)


def main(argv: list[str] | None = None) -> int:
    """Small standalone command for reproducible native TF research examples."""
    parser = argparse.ArgumentParser(
        description="Search literal original Greek text/source facts in native TF"
    )
    parser.add_argument("tf_directory", type=Path)
    parser.add_argument("--kind", choices=sorted(_KINDS), required=True)
    parser.add_argument("--contains", default="")
    parser.add_argument("--urn")
    parser.add_argument("--edition")
    parser.add_argument("--source")
    parser.add_argument("--source-file", help="Exact original source_file provenance string")
    parser.add_argument("--locus", help="Exact original source-authored locus string")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args(argv)
    for hit in search_native(
        args.tf_directory,
        kind=args.kind,
        contains=args.contains,
        urn=args.urn,
        edition=args.edition,
        source=args.source,
        source_file=args.source_file, locus=args.locus,
        max_results=args.max_results,
    ):
        print(json.dumps(asdict(hit), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
