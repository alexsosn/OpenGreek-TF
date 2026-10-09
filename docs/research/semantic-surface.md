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


Open TEI same-locus collisions have an additional published relation:
`data/corpus_loci_disambiguated.json`. Exact duplicate readings are collapsed
upstream; distinct readings keep the first bare locus and later readings receive
a deterministic `~<tag>` locus. The map records each base locus, the complete
set of resulting loci, and whether the disambiguation basis is `recension`,
`ordinal`, or `mixed`. Relocated rows also carry `base_locus` and, where
available, a recension `witness`, but the map is the complete group-level view.

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

## Measured pinned-release census

A complete audit of the pinned release (`corpus-2026-09-15.2`) has run successfully
in GitHub Actions against the verified publishing commit.

Text families:

| family | files | rows |
| --- | ---: | ---: |
| primary `data/corpus` | 3,909 | 1,970,947 |
| secondary `data/corpus_secondary` | 533 | 307,085 |
| paratext `data/paratext` | 5 | 15,958 |

The primary row core is complete: all 1,970,947 rows carry `text`, and the
verified source-release counts agree with the release manifest. The audit found
no primary filename-to-`urn` mismatch.

Primary optional structures are substantial rather than edge-only metadata:

- `corrections`: 149,619 rows, arrays of 1–4 correction stamps;
- `cts`: 443,996 rows;
- `text_lines`: 103,709 rows, up to 517 preserved physical lines;
- structured `provenance`: 7,506 rows;
- `page`: 9,180 rows and `ocr_dpi`: 9,106 rows;
- source-specific `work`: 8,856 rows and `witness`: 7,388 rows;
- `bekker`: 5,727 rows, arrays of 1–9 values;
- `section`: 2,942 rows and `figure`: 1,840 rows;
- structured `merged_read`: 1,757 rows;
  The row-level object records only the merged-read partner and
  substitution/guess counts. Open Greek separately publishes every guessed token
  position with its served reading and losing alternative(s) in
  `data/duplicate_read_merge_guesses.json`; those alternatives are research
  semantics, not discardable build provenance.
- diplomatic/original `text_orig`: 1,226 rows;
- `row_part`: 125 rows;
- `base_locus`: 39 rows and `book`: 35 rows.

The upstream code establishes semantics for several of these fields. `text_orig`
is a diplomatic layer retained beside a regularized SAWS reading. `text_lines`
preserves source physical line boundaries where joining those lines yields the
served text. `row_part` records deliberate splitting of a source row (including
Greek retained after Latin spans move to paratext). `merged_read` records
evidence/guesses when duplicate OCR reads are merged. These cannot be treated as
opaque incidental JSON if the TF corpus is to preserve the source semantics.

Secondary rows use two displacement conventions. 306,674 of 307,085 rows carry
`rank=secondary` plus `secondary_reason`; the remaining 411 rows carry a
structured `displaced_by` block. 15,926 rows carry an explicit `witness` and
5,031 retain correction stamps. This confirms that a secondary file is not one
uniform alternate-edition record type.

Paratext uses languages `de`, `en`, `fr`, `grc`, `la`, and `xx`.
Observed classes are `edition_apparatus`, `latin_in_greek_script`, and
`recovered_pending_merge`; 56 rows carry `why_not_served`, and 57 mixed-row
records carry `script` plus `greek_remaining_in_this_row`. The page key is a
string here, unlike the integer `page` found in some corpus rows.

Identity/metadata cardinalities:

- 3,944 persistent work ids = 3,909 served expressions plus 35 retired ids;
- 1,516 persistent author ids = 1,500 active plus 16 retired;
- 3,909 reader-facing work-index records and 6 redirects;
- 11,075 source-registry works and 3,315 source-registry authors;
- 10,202 edition records nested under registry works;
- 23,254 registry tag occurrences, over the controlled dimensions `era`,
  `century`, `register`, `genre`, `dialect`, and `language`;
- 3,454 TLG/CTS crosswalk entries;
- 1,412 OCR-quality work records, including 196 structured primary/secondary
  witness-comparison blocks;
- 4 explicit work-level partial-ceiling records in the pinned release;
- 6 curated one-to-one historical work renames.

Open Greek also carries a separate multi-source chronology layer. OGA chronology
stores the original estimated date/range, date label, source/link, temporary-date
flag, derived century/era, resolution to a cog slug, and whether the work is
served. The applied report records 122 registry fills, 996 agreements, 466
one-century disagreements left explicitly unresolved, and 39 larger divergences
with curated decisions: 10 keep cog, 10 adopt OGA, and 19 remain disputed with
both readings. Those alternative readings are absent from a single
`century:<n>` registry tag, so TF must not collapse dating to that tag alone.

The OGA PTA↔TLG duplicate map contains 90 external-id pairs in the pinned release:
79 have only one side served and 11 already resolve to the same slug; there are
no live two-slug duplicates. It is identity evidence, not a merge instruction.

The curated collection-serving map currently contains two Libanius collection
records whose TLG collection identities are served through many per-oration or
per-declamation files without shared per-part TLG anchors. The relation is
therefore distinct from ordinary work anchors and must not disappear merely
because the coverage report can recompute token credit.

The work index gives all 3,909 served expressions an `ogc` id and author block.
External Work anchors remain incomplete by design: CTS is present for 3,339
expressions, bare TLG for 3,300, and work-level Wikidata for 517. Author
authorities have substantially better coverage (2,881 Wikidata, 2,784 VIAF,
2,742 GND, 2,418 ISNI occurrences on work-index author blocks). TF must preserve
the Open Greek opaque ids as the canonical identities rather than choosing an
external authority as a replacement key.

The corpus catalog confirms four correction-status classes:
`manual`, `auto-corrected`, `raw-ocr`, and `not-ocr`. OCR-quality
`unattested_rate` is available for 1,406 of 1,412 OCR works, and witness
agreement is measured only for a minority of works; these values are estimates
with the epistemic limitations documented upstream.

### Anomalies requiring classification, not normalization

The first full run measured repeated loci and secondary filename/`urn`
differences. Those aggregate counts are being re-run with per-file evidence
before #2 is closed.

The secondary filename/`urn` difference is at least partly deliberate and must
not be normalized away. Upstream duplicate-read workflows move unchanged work
rows into files named `<work>.duplicate-read.jsonl` or
`<work>.duplicate-read-merged.jsonl`, then add secondary/displacement metadata
while leaving the row's work `urn` intact. Thus a secondary filename can name a
witness container while `urn` names the work it witnesses. #3 needs separate
work identity and witness/container identity.

The second complete audit, at PR head `fb50418c43ad877bf9823a2f6ac9ea41b859f03f`,
measured the following anomalous-key distribution. These counts describe
repeated **source labels**, not repeated text or invalid identities:

| family | repeated `locus` | repeated composite keys | filename ≠ row `urn` |
| --- | ---: | ---: | ---: |
| primary | 4,222 | 1,076 | 0 |
| secondary | 73 | 54 | 10,513 |
| paratext | not locus-keyed | 0 under its family-specific key | not applicable |

Primary repeated loci are concentrated in
`proclus.in-platonis-timaeum-commentaria.jsonl` (2,415),
`apollodorus-atheniensis.fragmenta.jsonl` (794), and
`heraclides-ponticus.fragmenta.jsonl` (90). In the directly inspected
DFHG-derived `apollodorus-atheniensis.fragmenta` rows, the
locus `1.2` appears twice with different passages: one is the initial
Bibliotheca section, the next occurs after `1.1.1`–`1.1.4`.
In the directly inspected `heraclides-ponticus.fragmenta` rows, the
locus `2.1` occurs again on a different printed page with a different
political fragment. This is an upstream source label that is **not unique at
the work level**, and must not be treated as a primary passage ID.

The open-TEI builder explicitly resolves its own same-locus collisions:
exact repeats collapse and distinct readings get deterministic disambiguated
loci with `base_locus` and optional `witness`. The remaining repeated
labels occur in other source paths or later transformations; the precise
origins of every repeated `proclus` label are not established by this audit.
An upstream-source-specific audit should classify them before any feature
claims a universal *citable* identity. The TF graph, however, can already
preserve every record by using a deterministic source file + physical row
ordinal **as an occurrence identity**, while retaining the unchanged
`locus` as scholarly citation metadata. No grouping/collapsing is permitted.

Secondary `heraclides-ponticus.fragmenta-fhg2` similarly repeats `2.1`
across distinct printed pages and passages; the upstream
`secondary_reason` identifies the file as a displaced, stale DFHG carve.
The secondary `theognostus.canones-sive-de-orthographia.duplicate-read` file
illustrates the filename/URN distinction: its rows still have
`urn=theognostus.canones-sive-de-orthographia`, while the filename marks an
alternate OCR-reading container. Retain both identities and source order.

Neither anomaly class authorizes the converter to remove text, rewrite labels,
or infer passage equivalence. The TF schema must represent **occurrences**
and **source-declared citation labels** separately; uniqueness is guaranteed
by source occurrence position rather than by `locus`. All in-scope rows must
be conserved independently of their labels.

## Artifact classification for the schema phase

The audit separates source artifacts by what the eventual materializer must
preserve versus what can remain build evidence:

| upstream artifact | classification for #3 |
| --- | --- |
| `data/corpus/*.jsonl` | native TF research semantics: served text, ordered passage identity, source-specific structural fields, corrections; provenance subfields may use provenance-only output if no research query depends on them |
| `data/corpus_secondary/*.jsonl` | native TF research semantics: alternate/displaced textual witnesses and their witness/displacement relations; never flatten into primary slots without proved alignment |
| `data/paratext/*.jsonl` | native TF research semantics: non-primary textual material with language/class/exclusion semantics |
| `work_index.json` | primary current identity/WEMI authority for served expressions, authors, external anchors, manifestation and redirects |
| served subset of `source_registry.json` | native scholarly metadata not present in work_index, especially controlled tags and edition bibliography/scheme metadata |
| `work_ids.json` / `author_ids.json` | canonical opaque identity ledgers; served ids are native identity, redirects are queryable; retired tombstones/history require an explicit #3 decision |
| `ocr_quality_report.json` | researcher-facing quality evidence with documented uncertainty; represent work-level facts natively if retained, methodology as provenance/documentation |
| `partial_ceilings.json` / serving deficits | curated completeness limitations; explicit work-level limitations are research metadata, while general matching policy/methodology is provenance/documentation |
| `work_metadata_remaps.json` | the resulting `metadata_from` relation is native; explanatory concordance evidence is provenance |
| `pseudo_author_attributions.json` | resulting curated author/title attribution is native; evidentiary notes may remain provenance |
| `work_id_aliases.json` | redirect relation is native; rename script/note/source are historical provenance unless #3 gives them first-class history nodes |
| `oga_dating.json` + dating report/adjudication | native work-level chronology must retain the OGA date/range/label and source plus unresolved/disputed alternative readings; a single registry `century` tag is insufficient |
| `oga_duplicates_tlg_pta.json` | external identity/dedup relation; preserve as crosswalk evidence, never auto-merge. The pinned release currently has no live two-slug duplicates |
| `collection_serving_map.json` | curated collection-to-served-parts relation used where no per-part TLG anchor exists; preserve/classify explicitly rather than treating the collection as an unserved gap |
| `corpus_loci_warnings.json` | current citation/text-quality facts (dropped chars, collapsed/disambiguated loci, division repairs); expose irreducible work-level warnings natively, keep detailed repair mechanics as provenance where reconstructible |
| `duplicate_read_merge_guesses.json` | native textual uncertainty: each record points to a served row/character offset and gives the served token plus rejected reading(s). A `merged_read.guessed` count alone is insufficient; the alternatives must be queryable without this JSON |
| `corpus_editions.json`, `coverage.json` | derived/redundant validation views when the same facts are already represented from stronger authorities |
| `served_scheme_inference.json` | derived citation classification; raw locus is authoritative. Any exposed class/scheme feature must be marked derived and must not turn mixed/edition-prefixed loci into invented section hierarchy |
| `corpus_loci_disambiguated.json` | derived current citation relation for same-base distinct readings; preserve/validate the relation natively if TF exposes alternate-reading groups, rather than reparsing `~` suffixes heuristically |
| `tlg_crosswalk.json` | validation/backstop for external identifiers; current served anchors should follow the curated work-index result where they differ |
| `corpus_catalog.tsv` | independent deterministic validation surface, not a second semantic authority |
| `source_overrides.json` and carve/change plans | source-selection/editorial provenance; the resulting current source/edition/work relations are native, but the build decision trail need not be duplicated into the semantic graph |
| `corpus_release.json` | build/release provenance, hashes and whole-corpus validation |
| separately released Open Greek annotation datasets | out of base 0.1 scope until exact token/text alignment and independent versioning are designed |

This classification is intentionally asymmetric. A value can be reproducible
and still be worth exposing in TF (for example a derived citation class), but a
derived summary must not become the source from which stronger primary facts are
reconstructed.

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
