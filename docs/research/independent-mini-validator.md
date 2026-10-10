# #9 increment — independent validator for the bounded native primary TF proof

Status: **one validation increment**, not the whole-corpus conservation validator. The parent #9 remains open; no release claim.

## Research

As of main commit `cd160a694e6d8fefea7bc7fdd2cf511b3d3d244e`, PR #28's bounded `write_primary_probe` uses the already-validated `ParsedRecord` object both for writing and for its test expectations. Consequently parser mistakes, swapped labels or omitted scalar fields might be shared by producer and checker. A conservation test must reread the immutable source JSONL bytes separately and compare them with a genuinely reloaded TF graph.

The pinned three-row Heraclides smoke proves `CV.walk -> Fabric.load -> F/E/T` works, but still creates its expected values through the same `parse_file` that feeds the writer. The full audited corpus contains 1,970,947 primary rows, many alternative / nested semantics, and cannot be marked covered by a 32-row scalar-only proof.

## Contract and plan

- Read source JSONL with **stdlib `json` from raw UTF-8 bytes**, without importing `record_stream`, `text_runs`, or `mini_writer`. Reject duplicate object keys and invalid Unicode/JSON.
- This initial validator accepts a **source prefix of an explicit positive count** and only `str` / `int` scalar fields besides required `text`; unexpected arrays, objects, bools and nulls fail with source context. It does not pretend to validate unsupported corpus families.
- Derive the exact feature inventory from source, then `Fabric.load` the corresponding TF data. Verify work/passage/atom counts; source-file + physical ordinal occurrence identity; work-URN slug; every scalar source field, including absence and numeric types; literal repeated loci; passage text from both `form` atoms and `T.text`; source-row anchor count and placement; and source/passage slot order.
- The validator must reject dropped, duplicated, reordered or relabeled rows, changed text, changed scalar facts, missing/extra text-bearing atoms, or unsupported source facts. It must not call the production parser or reuse the writer's segmentation routine.
- RED-first tests generate a valid native micro-graph with the existing writer, then independently corrupt **the loaded TF files or original source file** to prove detection. Keep separate textual/metadata/order/unsupported-data corruption fixtures.
- A pinned-source smoke should invoke the validator on the first three source rows used in PR #28, proving independent checks against real upstream records.
- Exact-head full CI and pinned job must pass, then a logically independent adversarial review grounded in implementation and real source data must be posted before merge.

## Known limits

This is a narrowly bounded validator for #27's prototype. It is not a replacement for the full pinned-source, all-family ontology-aware validator of #9. CR/CRLF native TF round-trip remains P0 #29; the current writer refuses those source values, and validator must not weaken that gate. A complete validator eventually also needs identity/crosswalk edges, metadata-only nodes, secondary witnesses, paratext, corrections, provenance and whole-corpus reproducibility.
