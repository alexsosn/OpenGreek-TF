# #23: typed source-record stream (slice of #5)

## Research

The successful complete immutable-source audit from PR #17 identifies the
exact observed JSONL field set for each family:

- primary: 1,970,947 rows, 3,909 files, **23 top-level field names**;
- secondary: 307,085 rows, 533 files, **17 names**;
- paratext: 15,958 rows, five files, **11 names**;
- **zero blank lines** across these families.

The source file and *physical* 1-based row ordinal, not an inferred citation,
are the minimal deterministic identity. In a secondary file the filename may
be a displaced witness container while `urn` denotes the original work.
Paratext `page` is a **string**; primary and secondary `page` are **integers**.

Nested source structure observed: arrays of strings `corrections`,
`text_lines`, `bekker`, `merged_read.with`,
`provenance.consolidated_from`; and objects
`merged_read`, `provenance`, `displaced_by` with their audit-defined
typed members. This parser can validate these *source types* without
deciding how they become TF nodes/edges.

## Plan and constraints

1. RED: write source-family fixtures and pathology tests **before** parser
   implementation. The negative tests cover unknown and duplicate keys,
   missing mandatory fields, wrong nested type, `bool` versus `int`,
   malformed/blank lines, and physical-row identity.
2. Implement an immutable, recursive typed source-tree value model
   (`FieldObject` / `FieldArray` / `str` / `int` / `bool`) plus a streaming
   strict validator for every audited field. Nested containers remain typed
   objects and arrays; they are **never serialized into TF value blobs**.
3. Keep the iteration lazy and bounded by the size of the current record
   (no materialization of 65 million tokens); preserve exact strings,
   original field ordering, and missing/empty distinction.
4. CI: strict mypy, Ruff and tests; full pinned snapshot scan checked
   against the PR #17 audit counts in a separate source verification job.
5. Independent adversarial review before merge.

## Boundary

This is the first data-acquisition part of #5, not a claim that the complete
graph-oriented canonical IR is finished. Converting `corrections`,
`provenance`, `merged_read`, identities and metadata catalog structures
into native TF node/edge topology follows #3 and separate #5 increments.

No semantic sidecars and no normalized/replaced source text; source lineage
is an ordinary first-class immutable record attribute for later graph output.

## Adversarial schema refinement from the full census

The nested type census also supports **tagged source variants**, not just
independently optional keys:

- Among 307,085 secondary rows, 306,674 have both `rank` and
  `secondary_reason`, whereas 411 have the three-field `displaced_by`
  record (`date`, `pass`, `reason`). No other displacement representation
  is accepted by the parser.
- Of 1,757 primary `merged_read` objects, 1,745 have the complete
  `guessed` / `substituted` / `with` record, while 12 use the distinct
  `guesses` / `note` / `of` record. The parser must not accept hybrid or
  partially specified objects as valid published source facts.

These rules are direct observations of the verified release and the audit's
field-presence counts, not assumptions about arbitrary future versions.
Unknown additional fields or newly published variants require a deliberate
schema update and a new source pin, rather than permissive copying.
