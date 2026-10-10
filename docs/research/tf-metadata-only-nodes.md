# Issue #20 — preserving metadata-only nodes in native Text-Fabric

Status: research and test plan, **not a frozen corpus ontology**.

## Source constraints

The pinned Open Greek corpus has 11,075 registry works, 3,315 registry authors,
35 retired work IDs, and 16 retired author IDs. Many have no corresponding
primary text slots. The converter cannot invent textual spans for them, discard
their scholarly identity, or outsource their semantics to a JSON sidecar.

## Text-Fabric 13.1 evidence

The upstream `tf.convert.walker.CV.walk` implementation executes
`_removeUnlinked()` after the director: this removes non-slot nodes that have
no `oslots` entry, also removing their feature values and edge endpoints.

The upstream `tf.dataset.modify.modify` accepts `addTypes` with explicit
`nodeSlots`. Its implementation writes these slot mappings as sets into
`oslots` without demanding positive cardinality in the `addT` step.
But this is *not proof* that the resulting dataset loads and is queryable.

The generic low-level `Fabric.save` can serialize user-supplied `otype`
and `oslots`, bypassing CV. That too requires a real load/query test before
adoption.

## Experiment gate — native nodes without invented slots

Build a tiny word-slot TF dataset with CV. Demonstrate that CV removes a
metadata-only author. Then use the supported `tf.dataset.modify` interface
to add two metadata-only `author` nodes (served identity and retired identity)
with `nodeSlots={id: set()}` and ordinary typed node features.

Load the resulting dataset through `Fabric.load` and assert:

1. both author nodes exist in `F.otype.s("author")`;
2. their exact `oga` IDs and `status` values survive and are distinguishable;
3. `E.oslots.s(author)` returns an empty set for both;
4. the real passage/word slot is not changed, and `F.otype` remains valid;
5. a separate edge feature can link an entity to a textual work/occurrence if
   such a relation is source-declared;
6. an author without linked passages survives regardless;
7. no phantom word slots, fake authorship, empty-content passage, semantic
   JSON sidecar or serialized pseudo-list is created.

If `modify` or TF precomputation fails, test direct native serialization
through `Fabric.save` as a fallback and assess its loading/query semantics.
Do **not** hide the failure by assigning metadata-only entities to arbitrary
existing words.

## Follow-up decisions

A positive test demonstrates native TF representability, not automatically
complete Text-Fabric browser behavior or a scalable whole-corpus writer.
Issue #3 must choose a stable final node layout and writer, and #10 must verify
how advanced app/browser features expose metadata-only nodes.

The resulting method will be integrated only when schema requirements and
full-corpus conservation gates are ready.
