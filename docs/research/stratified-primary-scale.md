# #13 — Original-source-stratified primary Text-Fabric scale gate

## Research and immovable constraints

The current complete pinned source contains 3,909 primary JSONL files and approximately **1,970,947 primary passages**, but none of our full primary materializations has validated that source-complete load. The largest source-authentic native Text-Fabric CI batch [PR #57](https://github.com/alexsosn/OpenGreek-TF/pull/57) reached **1,267 primary passages / 387,406 Unicode codepoints / 125,049 native layout slots**, with isolated child/parent resident peaks **125.34/132.49 MiB**. It was one small subset; the full corpus remains unproven.

The immutable Git tree `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` independently establishes these **three different original textual shapes**, not synthetic stress records:

| Domain | Original source | Git-blob bytes |
| --- | --- | ---: |
| Epic | `data/corpus/homerus-epic.ilias.jsonl` | 3,451,795 |
| Continuous historical prose | `data/corpus/herodotus.historiae.jsonl` | 2,901,140 |
| Lexicography | `data/corpus/moeris.lexicon-atticum.jsonl` | 3,274,855 |

Total original pinned JSONL **9,627,790 bytes**, compared to the ~1 MB previous textual sample. Source row counts, Unicode codepoints, layout slots and CR exposure must be **measured from the actual immutable files**, not invented based on name or Git blob size.

## Research → RED-first TDD → implementation → verification

1. RED-first independent **stock JSON** source profiler, *without importing* the typed source parser, native Text-Fabric writer or source-FactGraph implementation. It validates canonical paths and distinct physical files, physical 1-based row stream, original UTF-8, duplicate keys, text field type, non-standard JSON, blank/empty input, source CR characters, and counts exact Unicode codepoints and maximal whitespace/non-whitespace runs. It hashes the original physical bytes, retains per-file row counts, and accounts for precisely one non-lexical source anchor atom per row. No normalization, tokenization, inferred CTS or write-side semantic sidecar.
2. Production profiler uses constant additional space **per row**, apart from a small path identity set and output counters. A source row containing CR **must fail closed** rather than falsely claiming Text-Fabric default `T.text` fidelity; issue #29 remains open. Include empty text, non-BMP codepoints, repeated spaces and newline/tab, type errors and file aliases in unit tests.
3. Run a fresh pinned Git sparse checkout of the *three* original sources plus release manifest in GitHub Actions. `verify_source` on exact revision; independent profile **before** using `run_isolated_primary_build`. Verify all row counts, source facts, original physical row order and nested types with `validate_native_jsonl_sources`, which invokes actual independent loaded `Fabric` and never invokes a write-side parser. Require `source_fact_nodes == writer.stats.fact_nodes`, `codepoints == original profile`, and loaded `otype.atom` count == profiler's independently counted exact layout+source anchors; compare canonical TF digest against child output and all `T.text` passage values through the validator's loaded-graph conservation. Record child/parent RSS, build/load time, output bytes and reproducibility digest.
4. If upstream text contains CR, keep the failed preflight as a **real source blocker** and either choose a different pinned real stratum or create a focused issue #29. No silently dropping or stripping CR or original rows.
5. Exact-head Ruff/mypy/pytest and pinned source CI, then a logically separate skeptical adversarial review examining actual source and native F/E. Correct blocking findings and re-run final head before squash merge.

## Scope

This batch **does not** claim a production release, full 65-million-token build, bounded native Text-Fabric writer memory, lexical token ontology, or cross-family source alignment. The source profiler's constant per-row extra memory is distinct from the all-at-once writer and loaded TF memory. Leave #13/#6/#9/#3/#29 open until their actual gates pass.
