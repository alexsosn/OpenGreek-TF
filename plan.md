# Plan

The 0.1.0 path is issue-driven. Semantic writer work is blocked until the source audit and graph ontology are frozen.

## Bootstrap

- #1 — repository contract, research/design/plan, package/CI scaffold, first pinned acquisition slice.

## Research and schema

- #2 — complete Open Greek semantic/licence audit.
- #3 — freeze native TF ontology and serialization contract.

#3 is blocked by #2.

## Source pipeline

- #4 — pinned acquisition and source identity verification.
- #5 — strict parser and typed canonical IR.
- #6 — native TF writer for primary served corpus.
- #7 — native identity/metadata/citation/crosswalk model.
- #8 — native secondary-witness and paratext model.

#4 can proceed immediately because it changes no corpus semantics.
#5 requires the audit and any relevant ontology decisions.
#6–#8 require #3 and the corresponding parser interfaces.

## Corpus correctness

- #9 — independent whole-corpus conservation/reproducibility validator.
- #13 — complete-corpus performance/load benchmark and semantics-preserving optimization.

## Researcher interface

- #10 — standard Text-Fabric advanced app/browser.
- #11 — feature documentation and reproducible query examples.

The app placeholder may exist from bootstrap, but its section/text-format contract is finalized only after #3.

## Distribution

- #12 — Agora-compatible materializer contract and downstream registration.

Agora integration must consume the public direct converter; it may not become a second parser.

## Release

- #14 — 0.1.0 complete-corpus release gate.

A release requires full supported-snapshot materialization, independent conservation, TF load, advanced-app/browser operation, licensing/attribution correctness, Agora end-to-end materialization, performance evidence, green CI, and logically independent adversarial review of the exact release head.

## Autonomous continuation

If the selected issue is blocked, choose another unblocked dependency. If the explicit backlog is exhausted, continue with evidence-driven performance, stability, ergonomics, documentation, reproducibility, and edge cases. Research may create new issues when actual evidence justifies them.
