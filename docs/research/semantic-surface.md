# Open Greek semantic-surface audit

Status: research for issue #2  
Pinned upstream: `open-greek/open-greek-corpus@corpus-2026-09-15.2`

This document classifies evidence before the Text-Fabric ontology is frozen. The
classification is deliberately conservative: an artifact is not dismissed as
"build machinery" when it contains a scholarly fact that is absent from the
reader-facing corpus surface.

## Current evidence

### Primary served text

`data/corpus/*.jsonl` is the primary served corpus: one file per current work
slug, one record per served passage. The common row core is `urn`, `edition`,
`locus`, `source`, `license`, and `text`, but upstream ingest and
correction code demonstrates source-specific optional fields and structured
fields such as correction stamps/provenance. A fixed six-column parser is
therefore ruled out before the full census.

The row field named `urn` is historically the work slug. It must not be
reinterpreted as a CTS URN.

### Identity and WEMI metadata

Open Greek documents `data/work_index.json` as the downstream consumer view.
For each served expression it carries:

- canonical `ogc......` expression id;
- current and former slugs;
- title;
- author `oga......` id, slug, display name and authority aliases;
- Work-level CTS/TLG/Wikidata anchors;
- manifestation edition/source/license and passage/token counts;
- optional metadata remap provenance;
- optional serving-deficit information;
- redirects from former slug to current slug.

The persistent `work_ids.json` / `author_ids.json` ledgers additionally retain
retired/tombstoned ids. Whether retired entities become TF nodes or remain build
provenance is a schema decision for #3; they must first be counted/audited.

### Registry metadata is not subsumed by the work index

`source_registry.json` contains work/author scholarly metadata and edition
metadata used to build the index. The current `build_work_index.py` output does
not copy registry tags such as genre/century into `work_index.json`.

This matters because a complete TF adaptation cannot discard those tags merely
because `work_index.json` is called the reader-facing join. The audit must
measure the served subset of registry tags/editions/aliases separately and #3
must decide their native TF representation.

A nearby upstream comment in `work_metadata_remaps.json` says the work-index
builder takes title, author, *tags*, and anchors from the registry, but the
current builder does not emit tags. Treat executable code/output as the stronger
evidence and record the discrepancy rather than silently choosing one.

### Citation/locus heterogeneity

`data/served_scheme_inference.json` classifies all 3,909 served works at the
pinned release:

- 2,614 `logical-numeric`;
- 986 `edition-prefixed`;
- 309 `mixed`.

The inference uses a 90% dominance threshold. A logical-numeric work can have
depth 1, 2, 3, etc.; level names may come from a Canon scheme only where depth
matches, otherwise upstream emits generic `ref.sub...` names.

Consequences:

- a universal book/chapter/section parse would fabricate semantics;
- mixed works need the raw ordered locus preserved even if some loci can be
  parsed;
- edition-prefixed coordinates are physical/edition references, not logical
  sections;
- upstream inference is useful evidence/validation but is itself derived from
  loci plus registry/inventory metadata.

### Secondary witnesses

`data/corpus_secondary/*.jsonl` is not disposable cache data. Upstream uses it
for displaced but deliberately retained editions/witnesses, including Migne,
OCR, alternate scans and superseded editions. Rows commonly add:

- `rank = secondary`;
- `secondary_reason`;
- `witness` where several witnesses can share one work slug.

Upstream explicitly warns that secondary witnesses are often **not locus
aligned** to the primary edition. A TF design must not attach their tokens to
primary slots unless an exact source-declared or independently validated
alignment exists.

### Paratext

`data/paratext/` exists specifically so source-volume text excluded from the
primary Greek corpus is not silently lost. Its README identifies at least:

- Latin apparatus/translations (`lang=la`);
- modern-language introductions/translations (`de|fr|en`);
- Greek-script edition apparatus, including some actually Latin read as Greek;
- Latin transliterated into Greek script, sometimes split out of mixed rows;
- recovered Greek candidates not yet promoted to the served text.

Paratext therefore contains textual research material with language/class/
exclusion-reason semantics. It cannot be represented solely in a provenance
JSON sidecar.

### Derived summaries versus semantic authorities

`data/corpus_catalog.tsv` is explicitly documented by upstream as a
deterministic join: it introduces no new measurement. It combines work index,
corpus editions, token totals, OCR quality, row correction stamps, locus
classification and file SHA-256. It is valuable as an independent validation
surface, but should not become a second semantic authority in TF.

`data/corpus_release.json` is release identity/provenance and validation
evidence.

`data/served_scheme_inference.json` is derived but may carry classification
needed to decide safe citation behavior; #3 must distinguish preserved raw locus
facts from converter-side parsing decisions.

### Annotation exports

Open Greek annotation exports/datasets are separately versioned products with
their own text/token alignment contracts. They are not implicitly part of the
base `open-greek-corpus` release and must not be attached to base TF slots on
work-id similarity alone. They remain outside the base 0.1 semantic surface
unless a later issue proves exact compatibility and defines a separately
versioned TF module/materializer.

## Audit implementation plan

The executable audit for #2 will scan the exact pinned checkout and emit a
deterministic diagnostic/provenance report. It will not be part of the generated
research corpus.

It will census:

1. all primary `data/corpus/*.jsonl` rows;
2. all `data/corpus_secondary/*.jsonl` rows;
3. all `data/paratext/*.jsonl` rows;
4. identity/index/registry/crosswalk and edition metadata JSON artifacts needed
   to decide the TF graph;
5. the release manifest/catalog as independent count/hash validation surfaces.

For JSONL families it records file/row counts, top-level and nested JSON path
types, presence/nullability, list cardinalities, object-key inventories, exact
source/edition/license vocabularies, per-file ordered hashes, slug/row-urn
relationships, and duplicate locus/record-key evidence.

For metadata JSON it records recursive path/type/cardinality structure and
semantic collection sizes. Large values are represented by counts/hashes rather
than copied wholesale into the report.

The audit is fail-closed on malformed JSON/JSONL and missing required artifacts.
It must never normalize or rewrite upstream source data.
