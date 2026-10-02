# Design

Status: **working architecture; TF schema intentionally not frozen**.

Issue #3 freezes the graph model only after issue #2 establishes the complete supported upstream semantic contract.

## Goal

Produce a complete, queryable Text-Fabric adaptation of the supported Open Greek Corpus release without requiring the original JSONL/JSON/TSV files after materialization.

Research semantics must survive in native TF nodes, node features, edge features, and text formats.

## Non-goals

- storing upstream bulk corpus files in this repository;
- storing generated TF data in this repository;
- embedding arbitrary raw JSON/XML in TF features;
- delimiter-packed pseudo-lists;
- semantic sidecars;
- silently correcting or "improving" Open Greek text or metadata;
- inventing linguistic annotation absent from the supported release;
- treating every locus syntax as one universal citation hierarchy;
- replacing the Open Greek editorial pipeline.

## Source/build boundary

```text
Agora/manual acquisition
  -> immutable local Open Greek release checkout
  -> source audit / typed parser
  -> canonical IR
  -> OpenGreek-specific TF director
  -> native TF graph
  -> independent source->graph conservation
  -> standard Text-Fabric advanced app/browser
  -> external materialized artifact
```

Conversion is network-free.

Provenance/validation sidecars may contain build identities, hashes, counts and diagnostics. They may never be the sole storage location for a research-semantic fact.

## Working graph hypotheses

These are hypotheses pending #2/#3:

- a word-like slot type is preferred if exact text reconstruction can be achieved with BHSA-style trailer/text-format features;
- `passage` and `work` are expected structural/occurrence nodes;
- `author` may be a shared entity node if the opaque author ledger establishes stable identity;
- edition/source/license identity may be features or entity relations depending on audit cardinality and reuse;
- citation loci may require source-specific node/features rather than a single parsed three-level hierarchy;
- alternate witnesses should not share primary slots unless exact alignment is evidenced;
- paratext may require its own textual occurrences rather than fabricated attachment to primary passages;
- crosswalks with multiplicity are likely edge relations or mapping nodes, not joined strings;
- correction/quality statements must retain method/status/provenance and their epistemic limits.

## Slot and text reconstruction

The slot contract is a release-critical decision.

BHSA suggests `word` slots with word-form features and `trailer` preserving inter-word material. Open Greek, however, stores passage text strings rather than an upstream canonical token stream in the base corpus.

Issue #3 must prove a tokenizer/reconstruction scheme over real corpus-wide evidence. It must define handling of:

- punctuation;
- exact whitespace;
- combining marks and Unicode normalization;
- Greek numerals;
- Latin or other-script spans;
- editorial symbols;
- empty/degenerate passages;
- source-specific anomalies.

No writer implementation may freeze a regex by convenience before this decision.

## Identity

Keep identity namespaces separate:

- Open Greek opaque work IDs;
- Open Greek opaque author IDs;
- current/historical slugs;
- CTS identifiers;
- TLG identifiers;
- Wikidata/VIAF/GND/ISNI/etc identifiers;
- source-specific edition/witness identifiers.

Synthetic converter IDs, if unavoidable, must be deterministic and namespaced.

The upstream row key called `urn` is not automatically a CTS URN.

## Primary, secondary, and paratext

The served primary reading is one layer of upstream scholarship. Secondary witnesses and paratext are not allowed to disappear merely because the primary TF slot stream is convenient.

The frozen ontology must state how each supported textual family is represented, how it relates to work/edition/source identity, and whether alignment to primary passages is source-declared, derived, or absent.

No inferred alignment may masquerade as source fact.

## BHSA reference rule

BHSA is the preferred fallback precedent when multiple TF representations are semantically valid.

Reuse requires semantic equivalence. Examples:

- word slots/trailers are a plausible text representation if reconstruction is proven;
- three section levels can be configured only if Open Greek has defensible section semantics;
- lexical/entity nodes are appropriate only when upstream supplies stable identity;
- Hebrew-specific morphology and feature naming are irrelevant without equivalent Greek source semantics.

Every deliberate divergence from an applicable BHSA convention belongs in the schema ADR.

## Writer

After #3 freezes the ontology, implementation should use supported Text-Fabric conversion APIs (normally `tf.convert.walker.CV`) rather than hand-writing opaque `.tf` files.

The emitted graph must be load-validated independently through Text-Fabric before project-specific semantic validation.

## Advanced app / web browser

The standard Text-Fabric advanced app under `app/` is a release deliverable.

It should provide:

- honest section navigation;
- useful Greek text formats;
- work/author/source/edition labels;
- citation/source links where evidence supports them;
- feature documentation and provenance;
- sensible type display for entities/witnesses/paratext.

A separate custom web stack is not the default plan. The standard TF browser is the web application unless a concrete limitation is demonstrated.

## Agora materializer

Direct conversion is authoritative. The eventual Agora contract should conceptually execute:

```text
opengreek-tf convert SOURCE_DIR --output OUTPUT_DIR --upstream-commit REVISION
```

Agora acquires/pins the source and invokes conversion with network denied. OpenGreek-TF owns all source interpretation.

## Validation

Two independent layers are required:

1. unit/integration/schema tests for converter behavior;
2. an independent source->loaded-TF conservation validator.

Release validation must detect silent drops, duplicates, reorderings, normalization, flattened multiplicity, broken identities, fabricated relations, and missing supported textual layers.
