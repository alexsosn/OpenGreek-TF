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

## Measured pinned full-registry gate (GitHub Actions)

Real immutable registry run: [Actions #38130733743](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38130733743), on implementation head `eb1bd3cfc37dc9ea3ed6e30598cd359e9befd46b`.

| Observation | Real measured value |
| --- | ---: |
| Complete author + work records | 14,390 |
| Nonlexical authentic source atoms | 14,390 |
| Native `sourceFact` nodes | 252,276 |
| Native `has_fact` edges | 252,276 |
| Explicit JSON nulls conserved | 12,735 |
| UTF-8 upstream registry bytes | 8,233,353 |
| Serialized native TF bytes | 14,454,531 |
| Number of native TF feature files | 18 |
| Materialization **including writer-side Fabric validation** | 21.578 seconds |
| Independent second `Fabric.load` reconstruction | 4.101 seconds |
| Peak process RSS **across all phases** | 1,241.7 MiB |
| TF feature-manifest SHA-256 | `e857cfcd5fc93f46cc8cab282d9e048acc380e54732aa4193286c01cbd7bfbe0` |

Every nested field value, field and array order, and exact scalar type was matched against an independently decoded stock JSON source. Every record/edge/atom is accounted for; TF contained zero Greek passage or `word` nodes. The measured wall times are single shared GitHub Actions runner observations, **not performance guarantees**. Peak RSS includes Python source duplication, writer graph and loaded Text-Fabric validation, so it is not evidence of a memory-bounded streaming architecture.

**Scalability blocker:** ~1.24 GiB RSS for an 8.23 MB JSON file is a warning against extrapolation to the 65M-token primary corpus. Open [#52](https://github.com/alexsosn/OpenGreek-TF/issues/52) isolates empirical phase profiling and streaming/memory reductions; #13 remains open until full primary text performance is demonstrated.

The first CI stress run reached every source and native graph conservation assertion but failed *afterwards* in test-only output hashing because Text-Fabric creates a directory `.tf/`, which matches `glob("*.tf")`. We corrected the manifest selector to hash **regular serialized feature files only**, then reran the full gate to green without weakening source correctness checks.
