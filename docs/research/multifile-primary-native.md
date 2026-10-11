# Native primary multi-file composition — bounded source-authentic gate (#6)

## Research: source and unmet contract

The pinned upstream release `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` stores 1,970,947 served primary passages across many files. The merged generic native Text-Fabric composer (#50), complete scholarly registry proof (#51), retention guard (#53), and isolated registry profiling (#54) preserve typed facts in native `F/E`. Prior CI had only a **two-passage** mixed authentic text sample, not a proven multi-file primary text adapter or extensive passage-text fidelity gate.

Direct inspection of four **real** pinned Greek primary JSONL files:

| Source JSONL in `data/corpus/` | Physical passages |
| --- | ---: |
| `abydenus.fragmenta.jsonl` | 6 |
| `achaeus.fragmenta.jsonl` | 52 |
| `acta-barnabae.acta-barnabae.jsonl` | 26 |
| `acta-philippi.acta-philippi.jsonl` | 148 |
| **Total** | **232** |

All selected source text values contain **no CR**; the existing Text-Fabric 13.1 default renderer limitation for CR-containing text (issue #29) remains unresolved. The files contain variable source features and diverse texts; they are not invented Greek sentences or generic fixture data.

## Research-plan-TDD-test gates

1. **RED-first** tests for ordered multi-file `ParsedRecord`→`NativeRecord` mapping, strict canonical source path, duplicate source file rejection, empty selection, field type conservation (`False` distinct from `0`), source original Greek `text` and empty text, invalid *later* file fail-before-output, determinism after removing volatile TF `@dateWritten`. Pin these tests before any adapter implementation.
2. Implement thin `iter_native_primary` / `materialize_primary`: accept explicit ordered tuple of source paths; reject duplicates/path traversal/secondary selection; use existing `parse_file` strict schema and generic `write_native_records`. Technical source occurrence identity is literally `{relative_file}:{physical_ordinal}`. **Not a new CTS identity** and does not imply Greek manuscript equivalence. No JSON/string serialized semantic blobs or new source-family-specific TF feature schema.
3. New pinned sparse-source CI: independently `json.loads` every real source row; type-sensitive/order-sensitive comparison with independent native `Fabric.load` source fact reconstruction for **all 232**; compare `T.text` of **every** passage with original source Unicode (including spaces/newlines, not just hashes); check exact original source file/ordinal, nested fields, F/E fact/edge census, no fake `word` nodes; record actual output bytes, nodes, slots, whole-process RSS/timing, normalized content digest.
4. Independent adversarial review of source parsing, duplicate/escape guards, TF source-order, metadata-only invariants and loaded-text roundtrip; correct any defects and rerun exact-head standard CI/Ruff/mypy plus pinned upstream 232-passages workflow. Merge only with passing review and checks.

## Explicit non-goals

This provides **multi-file, all-at-once selected-source composition** as a verified architectural increment. It does **not** prove source-complete native TF for 1,970,947 passages/65M tokens, a user-facing `word` ontology, corpus-scale memory bounds, full paragraph/work section modeling, secondary witnesses, passage-to-registry canonical IDs, licensing equivalence or 0.1.0 release. #3/#6/#9/#13/#29/#52 remain open. Incremental input parsing and output TF compilation are distinct; this adapter does not claim streaming or low-memory `CV.walk`.
