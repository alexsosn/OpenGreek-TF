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
`nodeSlots`. However its **input validation explicitly rejects** every
added node with an empty slot set (reporting `nodes not linked to slots`).
Therefore `modify(addTypes=...)` cannot be used for genuine metadata-only
entities even though its later `addT` loop could serialize empty sets.
Do not bypass or monkeypatch that validation.

The generic low-level `Fabric.save` can serialize user-supplied `otype`
and `oslots`, bypassing CV. That too requires a real load/query test before
adoption.

## Experiment gate — native nodes without invented slots

Build a tiny word-slot TF dataset with CV and demonstrate that CV removes a
metadata-only author. Since `modify` also rejects unlinked nodes, test a
**direct `Fabric.save` native graph** with two metadata-only `author`
nodes (served identity and retired identity), explicit `oslots` mappings
to empty sets, and ordinary typed node features.

`Fabric.save` checks every non-slot node has an `oslots` **mapping**, but
does not explicitly require that the mapping's set be nonempty. This candidate
still requires an actual save/load/query proof, not just source inspection.

This candidate was **rejected by direct TF 13.1 source inspection**:
the plain-text edge parser reports `emptyNode2Spec` for empty `oslots`
rows, and loading the dataset fails. The executable regression test must
assert this failure rather than claiming that `Fabric.save=True` establishes
a round-trippable dataset.

For the **alternative source-atom-slot proof**, `Fabric.load` must show:

1. served and retired registry author nodes survive as `F.otype.s("author")`;
2. exact `oga` identities and statuses stay distinguishable;
3. each metadata author spans only its own genuine registry-record atom,
   not a word or passage of Greek text;
4. actual passage and word nodes map only to real textual atoms;
5. typed `has_author` edges can refer from a real passage to a real author
   without changing either node's text extent;
6. an unserved or retired author with no passage links is still queryable;
7. no phantom word, empty-content passage, invented authorship,
   semantic JSON/XML feature blob, or semantic sidecar is created.

If direct `Fabric.save` or TF precomputation fails, record the precise
failure and investigate Text-Fabric's low-level format/graph limitations.
Do not invent slot attachments as a fallback.
Do **not** hide the failure by assigning metadata-only entities to arbitrary
existing words.

## Follow-up decisions

A positive test demonstrates native TF representability, not automatically
complete Text-Fabric browser behavior or a scalable whole-corpus writer.
Issue #3 must choose a stable final node layout and writer, and #10 must verify
how advanced app/browser features expose metadata-only nodes.

The resulting method will be integrated only when schema requirements and
full-corpus conservation gates are ready.


## Research candidate: real source-atom slots

Since an unlinked native node is rejected by all three paths, the test branch
also probes a *different slot ontology*. With `slotType=atom`, some slots
represent genuine text atoms, while other slots represent genuine metadata
records from the Open Greek identity/registry ledgers. A non-slot `author`
node can legitimately contain its own metadata-record slot; no word token,
text extent or authorship of an unrelated work is fabricated.

The test asserts that `F.otype.s("word")` still enumerates only the
real text-bearing word object, and that metadata atoms have no `form`.
It separately checks exact source IDs and retired/served status, slot
disjointness, loaded query features and passage membership.

This is **not yet the selected design**:

- It departs from BHSA's `word` slot type for a concrete source-data reason.
- Representing every text word both as an `atom` slot and a separate
  `word` object may almost double node count at full-corpus scale.
- An optimized alternative would query text atoms directly by a
  `slotKind=text` feature, avoiding all individual wrapper `word`
  nodes but changing familiar Text-Fabric word-query ergonomics.
- Section navigation, cross-type edges, Text-Fabric query performance, and
  the advanced app still require proof against the real corpus.
- Any adoption requires a recorded #3 ontology ADR and #13 benchmark; this
  research probe must not silently set the production slot model.

## Source-level negative finding

Text-Fabric 13.1's `Fabric.save` checks that every non-slot node has an
`oslots` **key**, and can serialize an empty Python set, but its plain-text
edge reader rejects an empty target specification (`emptyNode2Spec`) and
reconstructs `oslots` using only successfully parsed edge rows.
Consequently the separately tested empty-slot native graph is not a
round-trippable, loaded TF corpus. A `.tf` file existing on disk is not
sufficient evidence of successful modeling.
