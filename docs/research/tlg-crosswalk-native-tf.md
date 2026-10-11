# #7 — pinned complete TLG crosswalk as native TF (bounded batch)

## Research evidence (immutable Open Greek `338aa27310b3cfe2588a993b4d113b503597d70f`)

Actual `data/tlg_crosswalk.json`: **3,454** ordered source-key entries, **13,848** declared fields. The field census is: `cts` 3,385, `tlg` 3,385, `author_slug` 3,454, `title` 3,454, `pta` 123, `note` 47. All observed values are strings, but not all are present or nonempty. Explicit empty values: `title` 799, `author_slug` 17, `tlg` 57 (**873 total**). Another 69 records lack CTS/TLG altogether. Four titles contain literal LF and in one case TAB characters; they must survive unchanged. TLG and CTS are **non-unique** across source keys: do not use them as primary keys or assume bijections. Field order is significant for a strict source reconstruction; preserve optional `pta` and `note`. A source key is an actual mapping-record slug, not automatically a canonical `ogc*` ID.

Previous #20/native TF proofs establish that the standard TF 13.1 converter removes unattached metadata nodes and that a *genuine source-record* metadata `atom` can anchor source facts without making Greek word/passage claims. Reuse this bounded model; #3 remains unfrozen. Open Greek source data are not redistributed in this repository.

## Plan, RED gate, and acceptance

1. First commit **failing tests** with a minimal API scaffold. Require strict JSON object parsing, duplicate-member rejection, unknown-value rejection, exact entry/field order, optional/missing vs explicit empty strings, repeated CTS/TLG, Greek Unicode, TAB/LF and backslashes.
2. Add exactly one authentic nonlexical `atom` for every crosswalk JSON member and a `crosswalkRecord` node anchored to it. Model each present source field as a separate `crosswalkField` node (typed `empty` vs `str`), retaining key and source position. Add `has_crosswalk_field` edges. Represent a missing field with **no** node, not an empty string. Never create fictitious Greek `word`/`passage` nodes, normalized titles, OGA/OGC links, or out-of-repo semantic sidecars.
3. Independently reload native `F`/`E` via `Fabric.load`, reject orphan/shared nodes, wrong atom, missing/reordered/duplicate field positions, changed kinds and missing provenance; compare the entire reconstructed TF sequence against the original JSON source. Regression cases deliberately corrupt input/TF.
4. Exact pinned-source CI fetches only `data/tlg_crosswalk.json` and `data/corpus_release.json`, verifies the immutable upstream revision, checks the census and full native TF round trip, and records actual runtime and output size. Standard pytest/Ruff/mypy checks on the same PR head.
5. Perform **logically independent adversarial review** against source dataset and diff. Merge only after exact-head checks, code review and any requested fixes. Keep #7 open until all identity, provenance, catalog, CTS and source-registry families have a consistent integrated ontology.

## Exclusions

The mapping record itself does not prove a one-to-one canonical work equivalence. Metadata source atoms are not text tokens or passages. This isolated batch neither delivers whole-corpus writing, researcher browser integration nor the final `0.1.0` release gate.
