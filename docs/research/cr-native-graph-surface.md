# #29 — CR-codepoint native TF loaded-graph feature-surface integrity

## Source-backed research

Open Greek pinned corpus at `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` was independently scanned in earlier batches: 2,293,990 source records, **zero real U+000D CR**, but 52 physical rows contain 93 DEL/C1 occurrences. Native Text-Fabric 13.1's plain F.form serialization does not faithfully reconstruct synthetic CR; the current `cr_codepoint_probe` conserves U+000D by writing integer `codepoint=13` slots and independently loading the source graph, while `T.text` still **does not** support CR. No real corpus data or Unicode is modified in this change.

A skeptical audit of `read_cr_codepoint_probe` found that it directly calls `Fabric.load(`only known features`)` and then checks the loaded atoms and digest. It never checks `Fabric.explore` against the **entire** serialized F/E feature inventory, potentially letting an otherwise source-exact graph carry an unreported, invented native semantic feature (e.g. fabricated alignment edge) or unrelated feature data. Such a graph should fail the exact native-surface conservation contract, not be mistaken for a clean immutable source representation.

## Research → plan → TDD → tests

1. RED-first tests produce a genuine TF CR graph through the actual writer and then copy valid native features under *new* node and edge feature names (real `locus.tf` / `source_file.tf` and TF's `oslots.tf`), proving that an unknown native feature is currently ignored by the reader. The unchanged genuine CR/CRLF, DEL and C1 graph must still be accepted.
2. Add a strict `Fabric.explore` feature-surface check to the **independent** native loader, verifying mandatory node features, exact optional `form` and `codepoint` types where emitted, allowed TF system edge features, and no unexplained F/E features or unexpected node-type labels. Keep TF-owned `otype`/`oslots` inside the supported graph.
3. Prove standard exact-head Ruff/mypy/pytest, pinned true Herodian DEL row and synthetic CR-codepoint real-TF verification. Post a logically independent adversarial review and fix any findings before merging.
4. Keep issue #29 open: this hardening **does not fix default TF T.text rendering of CR**, provide a custom TF advanced browser format or implement CR-safe primary full corpus materialization. Full source has zero CR at this pinned revision, not a future universal guarantee. This work is independent of PR #60 (claims) and #61 (stratified primary scale).
