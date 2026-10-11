# #8 — Unaligned secondary witnesses and paratext in native TF

## Source audit

Pinned upstream: `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`.

Examined genuine source families, **not** back-projected alignments:

| Source JSONL | Physical rows | Observed class |
| --- | ---: | --- |
| `data/corpus_secondary/abydenus.fragmenta.jsonl` | 47 | ranked secondary OCR witness |
| `data/paratext/edition_apparatus.jsonl` | 56 | editorial apparatus, often quotations |
| `data/paratext/latin_in_greek_script.jsonl` | 57 | Latin transliterated into Greek script |
| **Total** | **160** | separate from served primary text |

Secondary rows expose **source `urn`, `edition`, `locus`, `source`, `license`, `text`, and either `rank` + `secondary_reason` or structured `displaced_by`**. Paratext exposes **`slug`, `page` (string), `lang`, `class`, `license`, `source`, `edition`, and original `text`**, with family-specific `script`, `why_not_served`, or an original integer Greek-remnant count. None of these establishes a mechanically verifiable passage-to-passage correspondence with the primary served Greek text. Same-looking `urn`, `locus` or `slug` is **not** sufficient evidence of an actual alignment or identity relation.

## Bounded design

Build on strict, already audited `record_stream.parse_file` and the *same* generic `native_composer.write_native_records`. A `secondary` row is **`record_kind=secondary-witness`**, a `paratext` row **`record_kind=paratext-record`**. Each is a **`metadataRecord` with one nonlexical genuine source atom and a complete nested typed `sourceFact` F/E graph**. Every original text is retained as a *queryable native scalar string fact* (not a compressed opaque JSON field); no synthetic `word`, `passage`, `form`, or `has_alignment` is created. `source_file` + positive physical row is the exact source identity; `source_record_id` is literal `{relative_file}:{ordinal}`, **not** an authoritative CTS ID.

That means **Text-Fabric `T.text` cannot render these metadata-only rows as primary passages**. The correct discovery surface is `metadataRecord` + `record_kind` and native `fact_text` / `has_fact` structure. A future reviewed, evidence-backed cross-corpus alignment may create explicit separate relations; this batch must not.

## Research → plan → TDD → independent review gates

1. Commit RED-first fixture covering ranked and displaced secondary variants, non-Greek paratext, Greek apparatus, ordered nested fields, exact scalar types, source path/physical ordinal, Unicode text, empty/duplicate/escaping source selections, alias symlinks and *invalid last-file fail-before-output*.
2. Add only a thin adapter; do **not** modify the generic writer or introduce a second TF serializer. Use explicit ordered input file selection, guard against a source path escaping the supplied root and against distinct lexical names resolving to one physical file.
3. Pin exact immutable Git source with sparse checkout, run a **160-row** native Text-Fabric output, independently reconstruct *all* original data using loaded TF `F/E`, compare source value/order/type against **separately decoded stock JSON**; check all physical occurrences, full fact/edge census, no `passage`/ `word` / `form`, normalized feature-content digest and output size/RSS/timings.
4. Require exact-head Ruff/mypy/unit tests and pinned full-source CI. Perform a **logically independent adversarial review** against actual upstream rows, then fix and re-review before merging.

## Boundaries

This is an **unaligned, metadata-only native source preservation proof**, **not** proof that secondary writings are lexically tokenized, aligned with primary passages, or fully modeled as independent witness corpora. Complete secondary family (>500 source files), larger Latin paratext family, annotated apparatus, source-level text-format rules and a consolidated one-graph primary+secondary+paratext ontology are still future tickets. Issue #8 stays OPEN until full family coverage and evidence-backed relation policy; #3/#6/#9/#29/#13 remain open. Source licensing remains per-record original fact rather than a newly asserted distribution permission.
