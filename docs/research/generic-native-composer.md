# Generic mixed source-record native Text-Fabric composer (#6 / #3 / #7)

## Research and prior evidence

The merged strict source-stream parser (#23) retains physical JSONL rows and exact Greek text. The shared typed fact graph (#33/#35) carries ordered nested source facts. The full source registry parser (#49) handles `null`, nested edition records, author aliases and preserved tag arrays. Earlier TF probes prove that Text-Fabric 13.1 removes genuinely unlinked nodes, but real source-row `atom` slots survive without inventing a lexical `word`. The source `locus` is not globally unique and a metadata source atom is not textual evidence.

Pinned upstream `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` supplies authentic `data/source_registry.json` with 3,315 authors, 11,075 works, 10,202 editions, and source `data/corpus/abydenus.fragmenta.jsonl` (6 primary passage rows, raw Greek text). Source material is acquired at CI time and not redistributed.

## Bounded design

1. Reuse the same `NativeRecord(source_file, ordinal, source_record_id, record_kind, fields, text?)` API for both source registry and JSONL text. Do not assume `source_record_id` is a canonical OGA or OGC identifier.
2. An **authentic source-record atom** is emitted for each source entry; metadata-only roots have type `metadataRecord` and exactly one nonlexical `atom` carrying source provenance. Textual `passage` roots have exact Unicode text-layout `form` atoms and one trailing real `source-row` atom, whose form is absent except for the empty-text case. No fabricated `word` nodes or implicit book/chapter segmentation.
3. One `sourceFact` node per typed graph node, anchored to its authentic record atom, connected by typed `has_fact` edges. `fact_kind` differentiates `object`, `array`, `str`, `int`, `bool`, and `null`, with field order, array order and source-local preorder IDs. Retain empty arrays, empty strings, signed numbers, repeated values, boolean zero vs numeric zero, and explicit null vs missing facts. Semantic records are never stuffed into JSON/string sidecars.
4. Deterministic global `source_seq` allows reassembly across textual and metadata roots, while physical `source_file`, `source_ordinal`, and `source_record_id` remain distinct. Duplicate source occurrences are rejected before writing.
5. Independent `Fabric.load` reconstructs all typed facts, checks source-atom ownership, graph topology/orphans/duplicates, physical provenance, per-record fact count/digest and text-layout fidelity. Compare reconstructed records against independent source records. Reject CR-bearing inputs before creating TF because TF 13.1 plain-string serialization is lossy for CR (issue #29). Verify TF rendering of each text passage.
6. RED-first synthetic mixed regression tests, absent features, empty text, metadata-only, text-only and mutation failures; pinned real Greek-text + author/work-registry workflow; standard exact-head unit tests/Ruff/mypy; **separate logically independent adversarial review** before merge.

## Explicit exclusions and follow-ups

This bounded composer **does not claim a production 65M-token full-corpus build**: memory-bounded streaming, compilation of a complete graph, source registry full materialization, full source text conservation, TF advanced app/browser, section ontology, query ergonomics, ontology freeze and release gate remain open. A per-record source atom increases slot count and must be benchmarked (#13). It is safe to compose mixed records into a common TF dataset, but provenance alone does not imply source mappings are equivalent or that metadata records are passage spans.
