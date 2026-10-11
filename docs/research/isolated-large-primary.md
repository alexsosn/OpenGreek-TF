# #56 — Isolated native TF primary text scaling pilot

## Research

Current #55 pinned four-source proof: **232 passages, 131,738 Unicode codepoints, 1,642 nested source facts, 43,242 atoms** (232 source anchors, 43,010 maximal alternating whitespace/non-whitespace text runs), **892,517 .tf bytes, ~127.4 MiB single-process high-water**. Every source row, original Greek Unicode and `T.text` was reconstructed from native Text-Fabric and independently compared to stock JSON. A complete ~65-million-Greek-token source build is *not* demonstrated.

Pinned original `data/corpus/achilles-tatius-scr-erot.leucippe-et-clitophon.jsonl` contains **1,035 passages, 255,668 codepoints and 82,039 independent text runs**, no CR. The exact five-source combination therefore has **1,267 passages, 387,406 codepoints and 125,049 text runs** plus 1,267 true source anchors. The fifth source has variable `text_lines` and ordinary `urn`/edition/locus/source/license keys. This dataset is larger than existing text tests and exercises full `CV.walk` and independent loaded `Fabric` across many text slots.

The source writer and independent verifier should not retain duplicate full representations in the same Python process. #54 already proved the metadata registry benefits from child-process build isolation but its CLI was explicitly registry-specific.

## TDD gates

1. **RED-first:** child-process tests for distinct PID, exact original Greek text/typed nested facts across two files, source paths with spaces, native manifest invariance across independent child runs, phase instrumentation that cannot alter serialized content, fail-closed malformed late row, existing output and duplicate source selections.
2. Implement a **small independent subprocess primary adapter** that calls existing `materialize_primary` / generic `write_native_records`; reuse #54's `_memory_mib` helper to avoid a second memory estimator. Add optional callback support to `materialize_primary` while retaining exactly the same default output. No invented word nodes, CTS equivalence, custom TF writer or JSON source sidecars.
3. Pin a new whole-file five-primary-source GitHub Actions workflow to immutable upstream `338aa27310b3cfe2588a993b4d113b503597d70f`, construct native Text-Fabric in an isolated child, then independently decode all original 1,267 source JSONL rows and load all native F/E, verify exact source record/field/scalar types/order, exact original `T.text` for every original passage, original 125,049 layout text slots plus 1,267 nonlexical anchors, no fabricated word nodes; report child and verifier RSS/time separately and output checksum/size.
4. Require full Ruff, mypy, existing unit tests, #55 source-backed 232-row proof, and independent skeptical adversarial code/data review. Correct blockers and repeat exact-head gates before merge.

## Boundary

A 1,267-row text benchmark cannot establish practical full-corpus streaming, end-to-end deterministic release, final Greek tokenization or 65-million-token memory bounds. Carriage-return compatibility remains unresolved (#29). Keep #13/#6 open and treat measured high-water RSS as distinct values for separate builder/verifier processes.
