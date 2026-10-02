# OpenGreek-TF agent instructions

OpenGreek-TF is designed for autonomous, issue-driven development. Coding agents must treat this file as the mandatory entry point.

## Read first

Before changing code or corpus semantics, read in order:

1. `README.md`
2. `research.md`
3. `design.md`
4. `plan.md`
5. `LICENSE_SCOPE.md`
6. `docs/agentic-dev-loop.md`
7. the active GitHub issue and all linked PR/review discussion

When work depends on Open Greek Corpus, Text-Fabric, ETCBC/BHSA, or Agora behavior, verify the current upstream contract against real data/code/documentation rather than memory.

## Development gates

Every behavior or semantic change follows:

**research -> plan/design -> RED-first TDD -> implementation -> exact-head tests -> logically independent adversarial review**

- Work from a GitHub issue with explicit acceptance criteria.
- Check overlapping issues and PRs before starting.
- Ground research in actual upstream records and current code/docs.
- Semantic mapping changes require written evidence before production code.
- Preserve a deterministic failing test before implementing behavior.
- Run the complete relevant test suite against the exact final head.
- A review is valid only for the exact final head; production changes invalidate earlier approval.
- Behavior-changing review fixes repeat RED -> fix -> GREEN -> re-review.
- Reviews must be skeptical and evidence-driven, using real source data and generated TF where applicable.
- Never merge release-critical work with unexplained corpus failures, silent partial success, or unreviewed approximations.

Research may create focused issues when evidence exposes missing work. Do not invent speculative scope.

## Repository and data boundary

This repository stores software, tests, documentation, Text-Fabric app configuration, and acquisition helpers only.

Do not commit an Open Greek source checkout, generated TF corpus, bulk copied upstream JSONL/JSON/XML/TSV, caches, or materialized release artifacts. Small synthetic fixtures and minimal attributed real excerpts for tests are allowed when necessary.

## Corpus semantics

The supported pinned Open Greek release is the source of truth.

Non-negotiable rules:

- Model research semantics in native TF nodes, node features, edge features, and text formats.
- Do not store raw JSON/XML blobs merely to avoid graph modelling.
- Do not serialize arrays/objects into delimiter-packed pseudo-lists.
- Do not require semantic sidecars when TF can represent the information.
- Sidecars/reports are allowed only for provenance, build identity, hashes, validation evidence, and diagnostics.
- Preserve source wording, IDs, ordering, multiplicity, licences, citation labels, edition/source identity, quality/correction status, uncertainty, and witness status.
- Do not invent lemmas, morphology, syntax, authorship, citation hierarchy, alignment, or textual equivalence.
- Distinguish source-declared data from converter-derived structure.
- Unknown in-scope constructs must be measured and fail closed unless the frozen schema explicitly classifies them as ignorable or derived.
- One-to-many mappings must remain one-to-many.
- The upstream `urn` row field is historically a slug, not automatically a CTS URN.

## Text-Fabric design

The initial working hypothesis is a word-like slot model, because Open Greek is a Greek text corpus and BHSA provides a mature word-slot + trailer/text-format precedent. This is **not frozen**: issue #2 audits the full source and issue #3 decides the slot/tokenization contract.

When uncertain:

1. inspect Open Greek evidence;
2. inspect BHSA/ETCBC for a semantically equivalent pattern;
3. reuse the BHSA pattern only when semantics match;
4. document deliberate differences.

Do not create BHSA-style linguistic features unless Open Greek supplies equivalent analyses.

Generated output must load with the supported Text-Fabric version and work through the standard advanced app/browser under `app/`.

## Acquisition and Agora boundary

Acquisition may access the network. Conversion receives a verified local source checkout and must not access the network.

OpenGreek-TF owns source parsing, schema semantics, TF graph construction, validation, advanced-app configuration, and source-specific documentation.

Agora owns marketplace registration/discovery, acquisition/execution integration, sandbox/trust UX, artifact publication/provenance, and consumer composition.

If a semantic bug occurs in direct OpenGreek-TF conversion, fix it here rather than in Agora.

Do not publish `agora.materializer.json` as a working contract until the direct converter CLI exists and passes end-to-end tests.

## Release mode

Issue #14 is the 0.1.0 release gate. A sample converter is not a release. The release must materialize and independently validate the complete supported corpus, load through Text-Fabric, work through the advanced app/browser, and pass the Agora path.
