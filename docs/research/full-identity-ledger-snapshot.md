# #20 — full pinned author/work *ID ledger* native-TF coverage

Research, 2026-10-11. This expands the verified four-entry PR #41 **in one batch**; it does not claim to convert the larger author/work catalogs or settle the production text-slot ontology.

## Real source and prior behavior

Pinned `open-greek/open-greek-corpus` commit `338aa27310b3cfe2588a993b4d113b503597d70f` has two full identity ledgers:
`data/author_ids.json`: **1,516** IDs, **16 retired**, no former slug arrays with contents; `data/work_ids.json`: **3,944** IDs, **35 retired**, six entries with former slug arrays. The broader registry's **3,315 authors / 11,075 works** are different inventories and remain unresolved. The preceding native-TF real-source proof [PR #41](https://github.com/alexsosn/OpenGreek-TF/pull/41) validated **four** chosen source records and native `atom`, `registryAuthor`, `registryWork`, `formerSlug` nodes with ordered typed aliases and zero Greek word/passages.

A full ledger source row represents a genuine *registry* record, not an ancient text occurrence. Each entry must receive exactly one genuine nontext `atom` slot and a registry identity node. Its source-declared former slugs use anchored relation nodes (no alias text slots). Formatting the actual opaque source key is metadata display, **not** Greek source text; no generic `form` feature, phantom passage or semantic sidecar.

## Plan and falsifiable acceptance

1. **RED first**: tests demand an API that converts the entire author/work ID ledgers and independently checks full native TF output, rather than relying on selected IDs. Source order, all ID/status/slug tuples, alias order and repeated aliases must round-trip without omissions or extras; the result reports exact counts and no lexical nodes.
2. **Adversarial corruption**: validation must fail on a TF output with a dropped ledger identity, a modified slug/alias, changed source files after conversion, duplicate/altered source ID or changed selected subset. It must read the *output* through `Fabric.load` and independently construct expectations from the actual source JSON, not merely compare two in-memory writer objects.
3. **Implementation**: reuse tested `registry_probe.write_registry_probe` and `read_registry_probe` to avoid another per-entity converter/ontology. Add a **batch** `write_full_registry_snapshot` and separate `validate_full_registry_snapshot` returning counts of both kinds, both retired statuses, source aliases and source-atom slots. The validator reconstructs all records, not a sample, and compares them to the raw ledgers as an independent walk. No unreviewed file persistence beyond native TF output; canonical provenance feature for each record is required.
4. **Real pinned CI**: modify the existing `registry-identity-pinned.yml` (same exact source commit and checksum-checked manifest) to load/build/validate **all 5,460** ledger entries. Assert 1,516 + 3,944 author/work nodes, 5,460 distinct nontext atoms, 16 + 35 retired states, all ordered former slug facts (source-derived count), **zero** `word`, `passage`, or `form.tf`. Benchmark build+load elapsed wall time and TF file size; avoid checking 5,460 entries into Git.
5. **Review**: exact-head Ruff, mypy, pytest, pinned real-5,460 corpus verification, logically independent skeptical review of algorithmic complexity, byte-level metadata conservation, TF slot count and actual upstream statuses. Merge only after gates; keep issue #20 open pending 3,315/11,075 broader catalog, crosswalks, mixed text+metadata browser semantics and #13 performance.

## Explicit risk and non-goals

Do **not** imply 5,460 ledger identities equals full Open Greek catalog. Do not silently freeze #3's slot scheme or claim a production full-corpus writer. The existing `CV` metadata-only format outputs opaque IDs in `fmt:text-orig-full` because Text-Fabric 13.1 insists on a default format; that is not Greek text. Every new assertion must be test-backed, fail-closed, and validate source vs loaded TF independent of internal writer selection. Memory/time estimates are hypotheses until pinned build logs establish actual numbers.
