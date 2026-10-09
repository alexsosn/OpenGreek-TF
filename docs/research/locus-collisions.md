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
