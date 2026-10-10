# Research plan: duplicate citation labels in pinned Open Greek

Issue: #18  
Pinned source: `corpus-2026-09-15.2` at publishing commit `338aa27310b3cfe2588a993b4d113b503597d70f`.

## Evidence before implementation

The complete source audit (#2, PR #17) identified 4,222 primary repeat occurrences of
`locus` labels, mainly Proclus In Timaeum (2,415) and DFHG fragment collections.
Upstream row inspection already proves that the same `locus` may carry different text
and distinct printed pages. The upstream open-TEI converter, by contrast, has
dedicated collision-disambiguation machinery.

This ticket does not infer that a repeated label identifies the same passage or
textual witness; it measures and classifies the evidence.

## Plan

Implement a bounded, deterministic, source-read-only diagnostic. For selected
JSONL works it will:

1. stream records in physical file order;
2. retain a compact descriptor per row (1-based ordinal, exact `locus`,
   `edition`, `source`, optional `witness`, optional `page`, and
   SHA-256 of original `text`), not the full passage text;
3. group by literal `locus` (not normalized/parsed citation components);
4. report total rows, distinct labels, repeated-label counts and grouping,
   identical-vs-different text hashes within groups, and evidence for page/
   witness/edition changes;
5. provide a stable capped set of worst groups and a list of affected loci
   without copying bulk copyrighted text;
6. fail closed on malformed rows or absent/non-string `locus`/`text`.

Tests come first (RED), using small synthetic records to demonstrate both
identical and different text under the same label. The executable study runs
against pinned upstream files through a GitHub Actions sparse checkout.

## Non-goals

No corpus repair, deduplication, invented identity, inferred alignment,
replacement of original `locus` values, or TF schema changes in this ticket.

The ontology must preserve every row occurrence as an independent node;
`locus` is a non-unique scholarly label and cannot serve as an occurrence key.


## Pinned-source measured results

Evidence: GitHub Actions `Pinned locus collision probe`, successful run
[38003155026](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38003155026),
artifact `locus-collisions` (SHA-256
`686f96eaef6630d08b5ac0ffea39210ce07dec80708e7bed1d553e6c1a27cf8a`).
All files are from the exact pinned publishing commit.

| Source file | Rows | Collision groups | Extra occurrences | Same-text groups | Different-text groups |
| --- | ---: | ---: | ---: | ---: | ---: |
| `proclus.in-platonis-timaeum-commentaria` (primary) | 16,373 | 2,415 | 2,415 | 71 | 2,344 |
| `apollodorus-atheniensis.fragmenta` (primary) | 1,031 | 114 | 794 | 0 | 114 |
| `heraclides-ponticus.fragmenta` (primary) | 101 | 8 | 90 | 0 | 8 |
| `heraclides-ponticus.fragmenta-fhg2` (secondary) | 56 | 3 | 53 | 0 | 3 |

These counts measure repeated **literal** source labels within each physical
JSONL file; no citation parsing, Unicode normalization, source text rewriting,
or inferred alignment is involved.

### Proclus: two OCR editions share a label namespace

Each of the 2,415 repeated `locus` labels occurs **exactly twice**, with
two different `edition` values:
`qwen36-proclus_timaeus_v1` and
`qwen36-proclus_timaeus_v2-singlecol`.
Exactly 2,344 pairs have different SHA-256s of the served text; 71 pairs have
identical text. No group varies by `page` because page is absent from these rows.

For example, `proclus_timaeus_v2_0007.1` occurs at source row ordinals
5511 and 12538 with identical text; `proclus_timaeus_v2_0007.3`
at ordinals 5513 and 12540 has different text. Such a pair **must not** be
collapsed even if its text happens to be identical.

This interpretation is backed by upstream
`scripts/ingest_held_reocr_batch2.py` and
`data/corpus_changes/proclus.in-platonis-timaeum-commentaria.reocr-coverage.json`:
the Open Greek publisher combined previously served Proclus OCR with
single-column re-OCR of Diehl/Teubner, and its
`data/ocr_provenance/proclus.in-platonis-timaeum-commentaria.json`
describes the independent OCR runs. The follow-up
`data/corpus_secondary/proclus.in-platonis-timaeum-commentaria.duplicate-read.jsonl`
also documents OCR keep-better/displacement decisions. These are
**edition/read identity distinctions**, not permission for the TF consumer to
merge different readings or assert fine-grained alignment.

### Apollodorus and Heraclides: fragment-level label resets

The DFHG primary Apollodorus file has 794 extra occurrences within 114
collision groups; **all 114 groups contain different text and different
physical `page` values**, with no change in `edition`. For example,
`1.1.1` occurs 30 times with 30 distinct passage texts across many pages
(the first occurrence is source row 8).

Primary Heraclides has 90 extra occurrences in 8 groups, likewise all
different in text and page while the edition remains `dfhg`. Its `2.1`
label occurs 43 times with 43 different text hashes, across pages 208–224.
The displaced older DFHG carve `heraclides-ponticus.fragmenta-fhg2` has
53 extra occurrences in 3 groups and is explicitly described upstream as
a redundant prior carve retained as a secondary witness. Again, the literal
locus is insufficient to identify a fragment or citation.

### Design consequence

The native TF graph must keep a source occurrence distinguished by
`(relative source file, 1-based record ordinal)` as the irreversible
minimal key within a pinned release. `locus`, `edition`, `page`,
`witness` and `source` remain separate, source-faithful TF features
or typed relations. `locus` can be used as a **non-unique lookup label**
but never as the primary node identity. Identical text does not establish
one occurrence, and different text does not prove two works. No source
record is dropped or rewritten.

Citing by `locus` alone is ambiguous for these families. The browser
should display source/edition context (and page where supplied); precise
navigation must resolve a chosen work/edition/occurrence, not guess based
on the label. The corpus-wide audit's other repeated-label files must
obey the same fail-closed occurrence identity contract, even where they have
not been individually classified.

## Reviewable invariants

- Every input record maps to a separate occurrence, regardless of shared
  `locus` or equal text.
- Source row order is conserved independently of citation sorting.
- No synthetic cross-edition passage alignment is created from equal
  `locus` strings.
- Diagnostic reports retain only text hashes and source evidence, not
  wholesale source passages.
