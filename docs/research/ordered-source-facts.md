# Issue #33: ordered source fact graph — research and decision gates

Status: **bounded candidate, not the frozen production TF ontology**.
Input is the immutable strict `ParsedRecord`/`FieldObject`/`FieldArray` parser
(#23/#24). It enforces 23 primary, 17 secondary, 11 paratext top-level
source field names with nested `provenance`, `merged_read`, `displaced_by`,
`corrections`, `bekker`, and `text_lines` under exact audited variants.

## Threat model

- Empty objects/arrays and absent fields differ; `False`, zero and strings
  are different scalar types, and NFD codepoints must not normalize.
- Ordered JSON fields and array elements must remain ordered. Original
  source key = (family, relative file, 1-based physical row) and never a
  potentially duplicated `locus`.
- No arrays packed into delimiter strings or nested JSON string TF features.
- TF non-slot nodes with zero oslots are discarded by standard CV;
  **all fact nodes require a genuine source-row atom as an anchor**.
- Native TF string features silently fail to round-trip CR under tested
  TF 13.1. Fail closed before making output if *any* nested string has CR.
- Source text and source facts are distinct; no invented OCR alignment,
  morphological words or implicit correspondence between witnesses.
- A graph for one bounded source record is not a scalable full converter.

## Plan and RED-first tests

1. RED test a pure immutable flat `FactGraph`: one object/array/scalar
   sourceFact node per source value, a stable unique id, parent id, distinct
   string key or integer index, local sibling position, explicit `kind`,
   and exactly one typed scalar value. Empty containers must be nodes.
2. Build it iteratively or with bounded depth; reject unreasonable nesting
   and graph size, never silently drop unsupported data.
3. Independently decode the graph from its edges/order to exact original
   `FieldObject`; reject duplicate/reordered/missing/orphan/cyclic nodes,
   untyped or type-shifted values and ambiguous object keys/array positions.
4. Native TF 13.1 single-record probe: `sourceFact` nodes/typed features
   and `has_fact` edges on real source-row anchor atom; independent
   `Fabric.load` reconstruction validates graph without sidecars.
5. Fixture matrices across all three text families, optional/empty nested
   structures, physical source row 1043 with `text_lines`, and adversarial
   graph corruption; exact-head CI and pinned data smoke.
6. Independent adversarial review of code, not the same tests/writer logic.

## Deferred

Full corpus writer/multi-file graph, cross-record metadata registry joins,
correction/guess offset interpretation, external crosswalks, deterministic
streaming TF binary/text performance, and advanced browser visualization.
Even a successful prototype does **not** close #3, #5, #6 or #33 without
acceptance evidence for all specified gates.
