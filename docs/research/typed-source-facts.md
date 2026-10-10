# #33 — Typed native source-fact graph (research prototype)

## Research and source constraints

The immutable Open Greek release contains 2,293,990 text-family records,
including heterogeneous nested `provenance`, `merged_read`, `displaced_by`,
`corrections`, `text_lines` and `bekker` values. Each is already validated by
the strict #23 parser as recursively typed `FieldObject`, `FieldArray`,
`str`, `int` or `bool`. Ordinary `locus` labels are not source identities;
the physical `relative_file:1-based-ordinal` key is.

The major missing layer is an **explicit, lossless ordered graph IR** that
can eventually become native TF features/edges. Packing arrays as joined
strings or objects as JSON features is prohibited. A source field in a
record is a legitimate source fact, not a manufactured lexical word.

## Plan, explicit gates

1. RED-first tests for exact round-trip of every recursive scalar/array/
   object type, repeated equal values, original key order, empty containers,
   `False` versus integer zero, NFD Greek, multi-family physical identity,
   and intentional node deletion/order corruption.
2. Implement an immutable source-local `FactGraph`: stable preorder IDs,
   explicit parent ID and child ordinal, type tag, object key or array
   position, scalar value and physical source occurrence key. Root is an
   object; types are literal Python union values, no JSON blobs.
3. Independent restorer validates graph well-formedness and reconstructs
   original typed `FieldObject` without reading the original source row.
4. Prove TF 13.1 loaded representation: one authentic source-row `atom`
   anchors a `passage` and its native `sourceFact` nodes, with typed
   `has_fact` edges and `fact_*` features. Read the graph **back** from
   `Fabric.load` and independently reconstruct ordered nested facts.
5. CI exact-head Ruff/mypy/pytest, real pinned source row with nested
   `text_lines`, then logically independent adversarial review.

## Safety and limits

- This is an **ontology candidate**, not a frozen #3 decision. It is not
  the full 65M-token writer or the advanced browser.
- A single source-row atom may anchor all facts of that source row, but may
  never masquerade as a Greek text slot. Fact nodes represent real source
  fields and use native TF node/edge topology, not sidecars or stringified
  JSON. A full-scale implementation must measure fact-node amplification
  and avoid redundant full `text` strings where text atoms already suffice.
- The full published source has **zero carriage returns** in audited string
  values (complete #30 census); the TF fact writer must still fail closed if
  future source revisions introduce unsupported TF string controls.
- The root/source occurrence identity must be recorded separately, not
  assumed recoverable from a possibly duplicated `locus` label.
