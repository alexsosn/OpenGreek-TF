# #20 — full grouped TLG work-authority native TF batch

## Research (pinned upstream SHA 338aa27310b3cfe2588a993b4d113b503597d70f)

Inspected the **actual** 768,669-byte `data/work_authority.json` source. It is an insertion-ordered JSON object of **585** `tlgNNNN` parent keys mapping to lists of **4,062** work-description objects, not a map of 4,062 unique QIDs or OGA/OGC ledger IDs. No empty groups at this release, but source-compatible empty arrays/groups must remain representable. Largest group: `tlg0096` with 566 entries. **58 duplicate QID occurrences** (4062 entries minus distinct QIDs): QID is a declared *field*, not a unique authority identity.

Exact observed source fields: `label` and `qid` each 4,062 strings; `la` 2,114, `el` 736, `grc` 649 strings; `year` 1,057 signed integers; `alts` 2,035 ordered arrays with 5,089 strings; `langs` 3,446 arrays with 3,574 strings; `genres` 1,676 arrays with 1,738 strings. No source carriage returns found in 4,062 entries. Do not infer lexical passages, authorship beyond source group membership, TLG↔OGA/OGC crosswalks, QID uniqueness or bibliographic normalization.

## Research → plan → RED → implement → pinned tests → adversarial review

1. Strict read of the **whole file**; reject duplicate JSON object keys, unrecognized field names/types, malformed TLG group names, bad scalar/array element types including bool-as-int, CR source strings, and absent mandatory `label`/`qid`. Preserve order of parent keys, work index within group, property order, array item order/repetitions, literal Greek strings and signed years. **A group with an empty work list remains a native parent.**
2. Native TF: one authentic **group-record atom** for each parent + one authentic **work-record atom** for each element. `workAuthorityGroup` and `workAuthority` nodes attached only to their own atoms; typed `has_authority_work` group→work edge; `workAuthorityField` and `workAuthorityItem` nodes anchored to that work's genuine source-record atom with typed `has_authority_field`/ `has_authority_item` edges. Numeric `work_index`, field and item indexes; no fake Greek `word`/ `passage`/ `form.tf`, no source JSON serialized as feature text or sidecar.
3. Independent `Fabric.load` validator reconstructs *all* 585 source group IDs and 4,062 ordered work entries with their typed field values. Verify source provenance, ownership, orphan/multilink/gapped indexes, group-level empty lists, repeated QIDs and repeated array items. Compare source vs TF and reject changed source/TF.
4. TDD: stub → failing pytest on actual-like fixtures, malformed input, corruption, repeated QIDs and empty lists; confirm RED CI before implementing. Then exact-head pytest, Ruff, mypy and real full-file pinned workflow verifying counts and measuring time/bytes.
5. Logically independent adversarial review anchored in real source, code/diff and actual CI logs; no merge before green, no duplicate work if PR changes. Keep #20 open for full catalogs, source_registry/crosswalks and mixed Greek text/browser behavior; do not freeze #3. This is **one batch of all work-authority records**, not separate PR per source work.

TF 13.1 CV requires a default text format even for metadata-only native TF. Use the literal source record key for metadata display, explicitly not Greek text.
