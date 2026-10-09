# Native Text-Fabric ontology: research and decision gates

Status: **research for #3; schema NOT FROZEN**.  
Upstream: Open Greek `corpus-2026-09-15.2`.  
Evidence: merged audit #2/PR #17, source-identity #4, live studies #18 and #20.

## Constraints from the complete source audit

The source material to preserve is not a flat work/passage table:

- 1,970,947 primary passage records spanning 3,909 works;
- 307,085 secondary-witness records in 533 files, often unaligned to primary;
- 15,958 paratext records in five language/class-aware files;
- 31 audited metadata inventories, including work/author ledgers, registry
  bibliography/tags, WEMI crosswalks, historical renames, source quality,
  textual uncertainty, alternate dating/adjudication, and collection relations;
- primary `locus` repeats 4,222 times, including different text under the same
  literal label; file + 1-based original row ordinal is the conservative
  occurrence identity, whereas `locus` remains source-declared citation data;
- 2,614 logical-numeric, 986 edition-prefixed and 309 mixed citation schemes.
  None licenses universal `book/chapter/verse` semantics.

The release must expose all in-scope semantics through TF node features, edge
features, nodes and text formats—not JSON/XML blobs, packed lists or semantic
sidecars. Provenance-only reports are allowed but cannot supply the only copy of
a research-semantic fact.

## D-01: Slot unit and exact text reconstruction (OPEN)

BHSA uses `word` slots and trailer features. Open Greek's base JSONL instead
holds exact Unicode passage strings, heterogeneous scripts, punctuation, editorial
symbols, whitespace, original/diplomatic layers and sometimes physical line
boundaries. Its word-count regular expressions are *not* an official canonical
token stream.

Candidate A: word-like lexical token slots with prefix/trailer text, plus a
defined lossless fallback for punctuation-only/whitespace-only/empty passages.

Candidate B: a generic `token` or `segment` slot covering every Unicode
run by deterministic segmentation, plus higher-order word objects when
linguistically justified. This may improve text conservatism at the cost of
unfamiliar TF query conventions.

Candidate C: character/grapheme slots. This guarantees exact strings/offset
anchors but would multiply nodes dramatically across ~65M Greek runs and may
make ordinary word queries cumbersome.

**Required RED-first acceptance tests** (must be written before a tokenizer
implementation):
- reconstruct source text byte-for-byte / codepoint-for-codepoint without
  normalization on representative real and generated hard-case records;
- polytonic Greek, decomposed marks, spacing breathings, non-Greek script,
  editorial brackets/symbols, punctuation-only and numeral-only passages;
- multiple/leading/trailing whitespaces, tabs, newlines, whitespace-only and
  empty text; avoid phantom visible words;
- `text_lines` reconstructs its original physical line partition, not only its
  joined form;
- `text_orig` remains a distinct diplomatic text layer when supplied;
- text offset to slot span is verified before attaching the 9,655
  published OCR merge-guesses, rather than inferred by token counts;
- end-to-end Fabric load/text rendering and independent full-snapshot
  conservation, including secondary/paratext layers;
- performance evidence at complete release scale.

A reversible `passage.text` string feature can be a *validation* backstop during
research, but **must not stand in for** actual TF token/structural modeling or
serve as a hidden blob substitute.

## D-02: Textual hierarchy and citation navigation (OPEN)

Do not use raw `locus` as a unique section key. At minimum distinguish:
- intellectual work identity (`ogc` expression and external anchors);
- individual source text occurrence (source family/file + row ordinal);
- original, potentially ambiguous `locus` label;
- source/edition/witness identity and uncertainty;
- optional evidence-backed citation divisions and physical page/line structure.

Text-Fabric supports at most three configured section levels; section display
labels must not pretend the heterogeneous source citation schemes share a
book/chapter/verse hierarchy.

Candidate browser navigation: work / source-text layer / stable passage ordinal,
with original locus displayed as a separate label. Freeze exact
`sectionTypes/sectionFeatures` only after #18's collision classification.

## D-03: Shared entities and metadata-only nodes (OPEN; #20)

Source registry has 11,075 works and 3,315 authors, including many without
served text; the opaque ledgers retain retired IDs. These are scholarly facts
but cannot be assigned made-up word occurrences.

Text-Fabric's data model permits nodes not linked to slots, yet the standard
`tf.convert.walker.CV` documentation explicitly states that unlinked non-slot
nodes are removed during validation. Do not assume `cv.node('author')` with no
slots preserves a metadata-only entity.

#20 must prove, using TF 13.1.x and a loaded dataset, how to represent these
natively without synthetic textual slots. Writer (#6) cannot rely on untested
metadata node survival.

Regardless of writer mechanism, model current identities, former slugs,
status/tombstones, author-to-work, work-to-expression, edition/source authority,
external identifier namespace+value+provenance and source-catalog relations
without delimiter-packed strings.

## D-04: Multi-valued scholarly statements (OPEN)

Nested upstream structures are **not** generic JSON containers to copy into TF.

Examples needing first-class nodes/edges and ordered occurrence indices:

- ordered correction stamps; source method and uncertainty;
- `bekker` arrays and physical source markers;
- edition records, citation scheme sources, default-edition policy;
- century/era/genre/dialect tags, disputed chronological readings with
  source/evidence/adjudication, not a single flattened century;
- rejected OCR-read alternatives at exact text offsets;
- curated collection-to-part relations, renames/redirects and crosswalks;
- `merged_read` and `displaced_by` decisions/relationships;
- paratext class/language/why-excluded semantics and secondary witness reasons.

The schema ADR must specify for every field family: entity or occurrence, value
type, optionality, order, target edge semantics, uncertainty provenance,
round-trip invariant, and whether derived/recomputable.

## D-05: Primary, secondary and paratext graphs (OPEN)

Do not give displaced witnesses primary slots or invent alignments. A shared
TF dataset may place the text from each distinct layer in disjoint, ordered
slot ranges and connect it to work/edition/source nodes. Whether to include
different layers in default section navigation is a separate app choice.

Include a genuine diplomatic text layer for `text_orig` rather than replacing
the regularized reading; model physical `text_lines` at their exact boundaries
where alignment can be established.

A secondary filename may encode an OCR witness container while a row `urn`
still names the primary work. Both identities must be retained.

## D-06: Independent conservation tests (OPEN)

The writer must not validate itself by reading its own IR and comparing only
counts. The independent validator (#9) rereads pinned upstream bytes and the
**loaded TF** to check exact text, order, original labels, identities, missingness,
multiplicity, relation targets, alternative readings, language and correction
metadata. Intentional corruption fixtures must prove failure.

## Decision checklist for the schema-freeze PR

- [ ] #18: repeated-locus source evidence and display policy grounded in data
- [ ] #20: metadata-only entity survival proven through Fabric.load()
- [ ] selected slot unit proven lossless on source and edge-case fixtures
- [ ] all 31 metadata inventories mapped or explicitly classified derived/provenance
- [ ] every in-scope semantic source construct has native graph representation
- [ ] no fabricated linguistic analysis, text, bibliography, or alignment
- [ ] TF app section/text-format contract works under source heterogeneity
- [ ] reproducibility/invariant strategy demonstrated in tests
- [ ] independent adversarial review of the exact final head
