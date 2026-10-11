# #5 — Strict, typed complete source-registry IR and shared null fact semantics

Pinned upstream: `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`, file `data/source_registry.json` (8.2 MB).

## Real pinned source audit

- **3,315 authors**, each with exact ordered `name` and `aliases` members. Author alias families: Wikidata 1,401, VIAF 1,355, GND 1,332, ISNI 757.
- **11,075 works**, each with exactly seven fields: `author`, `title`, `aliases`, `default_edition`, `best_source`, `tags`, `editions`. All work aliases have CTS; 579 additionally have Wikidata.
- **10,202 edition descriptions** with `name`, `provider`, `scheme`, `editor`, `year`, `source`, `servable`, `license`, `scheme_inferred`, `aliases`. Edition alias CTS: 1,756.
- **23,254 tag array items** (ordered; do not promote to unique sets); `default_edition` is **explicit JSON null** in **8,158** works, a string in 2,917. Edition `year` is **explicit JSON null** 4,577 times and an integer 5,625 times. Boolean edition `servable`/`scheme_inferred` are distinct from numeric 0/1. 
- All **11,075 author references resolve** within the 3,315-author registry; all nonnull defaults are present edition keys. Work edition cardinality up to seven; some works have no editions. Seven observed `best_source` labels: `pd_edition`, `locked`, `open_corpus`, `duplicate`, `migne_pd`, `migne_cgpg`, `byzantium_gr`.
- This source is *not* `work_index.json`, which drops scholarly tags and nonserved catalog entries. It must be modeled without silent omissions.
- The current Text-Fabric-independent `FieldValue` and `FactGraph` omit JSON null; `FieldObject.get` returns None to mean absent only in audited JSONL families. We must ensure explicit null remains distinguishable from an omitted member through `FieldObject.items` and `FactKind="null"`.

## Plan (bounded, no file-specific TF writer)

1. **RED-first fixture tests:** strict nested schema rejection, exact source order and names, duplicate JSON keys, numeric/boolean/null type separation, empty arrays/strings, Greek Unicode, repeated ordered tags, absent vs explicit null, and author/default edition reference validation.
2. Introduce `registry_stream.iter_registry`, yielding typed `RegistryRecord` with physical source-kind/ordinal key and `FieldObject` fields. JSON of 8.2 MB is manageable in-memory; do not build full source-level `FactGraph` unless consumers request it. Validate source shape and cross-references without inventing equivalences or identifier joins.
3. Extend **shared** `FieldValue`/`FactGraph` with first-class `null` facts; `restore_fact_fields` must preserve typed nullable values and reject forged scalar kinds. Keep text JSONL schema strict (still disallows null).
4. Real pinned job sparse-checkouts only `data/source_registry.json` and `data/corpus_release.json`; confirms immutable SHA and counts, **all** exact source fields/nested types/relationships, and verifies round trip through shared source-fact graph on a deterministic, representative cross-section of authors and works. No semantic sidecars or fake lexical nodes.
5. RED observation -> implement -> pytest/Ruff/mypy and pinned CI on exact PR head -> logically independent adversarial review -> merge only after correction/retest.

This is a *parser and canonical IR batch* for #5 and #7, not completed native TF materialization or full schema freeze. Compose this into a reusable writer as a separate tested follow-up instead of inventing another file-specific writer. Source schema remains restricted to real pinned values; future source revision changes should fail closed.
