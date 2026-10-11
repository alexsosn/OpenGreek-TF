# #13 — Native Text-Fabric full-registry scale gate

**Upstream immutable source:** `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`, `data/source_registry.json` (8,233,353 bytes on disk). No source payload is bundled with this repository.

## Research

The first generic native TF composer, merged as #50, passed a four-record mixed Greek/metadata proof; #49's typed registry parser separately reconstructed the *complete* 3,315 author and 11,075 work entries with 10,202 nested editions, 23,254 ordered genre/era/time tags, **252,276 typed facts** and **12,735 explicit JSON nulls**. This is the first full-scale native TF benchmark, not the first source parser validation.

The current implementation preflights all records into `FactGraph` objects, precomputes emitted feature vocab, builds native Text-Fabric in one `CV.walk`, then calls a separate `Fabric.load`-based graph reader. This consumes proportional memory, so peak RSS needs explicit measurement before claiming suitability for 65M Greek tokens. Never extrapolate a four-record microbenchmark to the full corpus. The graph's special `atom` slots are genuine nonlexical source anchors; metadata records must not acquire passage/word types.

## Plan

1. **RED-first:** unit tests for complete adapter source family ordering, author/work physical ordinals, null preservation, full nested source facts, deterministic registry output, metadata-only sections, and invalid later work fail-before-output.
2. Add a *thin adapter* `registry_materializer` that maps strict, typed `RegistryRecord` values into `NativeRecord` tuples and reuses **the generic #50 writer unchanged**. No second schema or separate per-entity converter, no assumption of canonical OGC IDs from registry slugs.
3. CI sparse-fetches only immutable `data/source_registry.json` and `data/corpus_release.json`, verifies pinned SHA. Materialize **all 14,390** records in one native TF output, independently reload all source records from F/E, compare every nested field/value/order/scalar type against a separate standard JSON decode, validate exact source order and physical identity, ensure zero textual passages or fabricated words.
4. Measure wall time for materialization (including the writer's own validation), independently loaded reader, file sizes, node/edge/slot counts, peak process RSS, and metadata-only `T.text` behavior. Record measured results (and any limits) in GitHub issue #13 and this document rather than invent numbers.
5. Rerun exact-head Ruff, mypy, unit tests and full pinned real-data GitHub Actions. Perform **logically independent adversarial review**, correct any blocker and repeat the review on the final head before merge. Keep #13 and complete-source issues open.

## Boundaries

This is a **single-source-family, metadata-only** scale gate, not the 1,970,947-row primary Greek corpus build. TF slots are non-lexical record anchors. Whole-corpus streaming, production memory bounds, Greek tokenization/word features, primary/secondary/paratext integration and release remain separate unpassed gates.
