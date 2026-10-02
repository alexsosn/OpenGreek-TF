# Research

This file records evidence that constrains implementation. It is not a frozen TF schema.

## R-001 — Open Greek release reconnaissance

Date: 2026-10-03

### Supported upstream identity

Repository: `https://github.com/open-greek/open-greek-corpus`

Initial supported release:

- tag: `corpus-2026-09-15.2`
- publishing commit: `338aa27310b3cfe2588a993b4d113b503597d70f`
- release manifest: `data/corpus_release.json`
- manifest `generated_from.commit`: `1d12c09340aa3309e8bfc0075070c0d7b90f4523`
- release id: `corpus-2026-09-15.2`
- corpus SHA-256: `7369350964b5baa948595a5b4ac45165ccf0c5f6812a07565233be11a4c32071`
- catalog SHA-256: `91d4300cbe900929a2fbe0a33db51e51791da7a0e2cd724645a3513781b7a6d9`

The tag/publishing commit is the immutable source checkout identity. The manifest's `generated_from` value is provenance about the content build and is not a substitute for the checkout revision.

Release counts:

- 3,909 served works
- 1,970,947 passages
- 65,285,435 Greek tokens
- 63,438,253 lemmatized tokens

The current upstream default branch can move independently. OpenGreek-TF must not silently build from "latest".

### Primary served record shape

Open Greek describes `data/corpus/<slug>.jsonl` as one locus-keyed file per served work. Source code demonstrates a common record core:

- `urn` — historically the work slug, not a CTS URN
- `edition`
- `locus`
- `source`
- `license`
- `text`

Different source families add fields. Direct code evidence includes optional examples such as:

- `page`
- `work`
- `witness`
- `dfhg_flag`
- `section`
- nested `provenance`
- correction stamps/quality-related metadata

Therefore a six-field parser is not acceptable. Issue #2 must inventory the exact tagged release corpus-wide.

### Identity layer

Open Greek explicitly moved away from human-readable slugs as permanent identity. It publishes opaque work/author ledgers and a work index, while slugs remain filenames and practical keys. CTS/TLG and other external identifiers are crosswalks, not synonyms for the opaque Open Greek ID.

OpenGreek-TF must preserve each identity namespace distinctly and preserve redirects/renames where upstream exposes them.

### Source precedence and witnesses

Open Greek chooses a primary served text with an explicit source-precedence policy. Better open TEI/manual editions may displace OCR/Migne material. Upstream also retains secondary witnesses under `data/corpus_secondary` in at least some cases, and publishes paratext for material deliberately excluded from the served reading.

A complete TF adaptation cannot assume `data/corpus` is the only semantically relevant text family. Issue #2 must classify secondary witnesses, paratext, dropped/archived material, and audit-only artifacts before #3 freezes the graph.

### Corrections and quality

The release manifest publishes per-work correction states and corpus-level quality caveats. Current release counts include:

- 888 auto-corrected works
- 129 manual works
- 2,497 non-OCR works
- 395 raw-OCR works

Quality measurements are explicitly estimates/triage signals, not ground truth. OpenGreek-TF must preserve the upstream distinction and must not transform a quality score into a certainty claim.

### Tokenization warning

Open Greek's own corpus-wide token counts use a broad Greek-run regular expression in its build scripts, while its public lexicon has a stricter tokenizer with normalization/exclusion rules. Neither should automatically become the TF slot contract.

The TF design needs a tokenization/text-reconstruction rule that:

- preserves the exact served passage text;
- handles punctuation, whitespace, numerals, non-Greek spans and source anomalies;
- does not silently normalize Unicode;
- can reconstruct source text deterministically;
- scales to ~65M Greek runs.

BHSA's word-slot + trailer/text-format approach is a design precedent, not evidence that the same segmentation is automatically correct here.

### Annotation products

Open Greek also publishes standardized annotation exports and related annotation datasets. Those products have their own release/version/alignment contracts and are not automatically part of the base `open-greek-corpus` release.

Issue #2 must classify them explicitly. No annotation layer may be attached to TF slots merely because work IDs look compatible; exact text/token alignment must be proved.

## R-002 — BHSA precedent

Current ETCBC/BHSA uses:

- `word` slots;
- larger textual/linguistic objects as nodes;
- warp features `otype` and `oslots`;
- three configured section levels;
- text formats assembled from word-form features plus trailers;
- an advanced app in `app/` using `apiVersion: 3`;
- provenance and type-display configuration in `app/config.yaml`.

Use these patterns when Open Greek has equivalent semantics. Do not copy Hebrew-specific feature names or BHSA linguistic analyses for cosmetic API similarity.

## R-003 — Agora boundary

Agora's existing materializer contract allows a third-party package to:

- declare immutable Git acquisition;
- accept a local acquired source directory;
- run a Python module with network denied during conversion;
- require Text-Fabric output plus provenance/validation evidence.

OpenGreek-TF should therefore make direct conversion authoritative. Agora integration stays thin and must not reimplement parsing or corpus semantics.

## Open research questions

Issue #2 must answer at least:

- exact files/directories included in the base release's scholarly semantic surface;
- complete field/type/cardinality census for primary, secondary, and paratext record families;
- exact schema of published work/author IDs, redirects, crosswalks, source registry, edition metadata and citation-scheme metadata;
- which nested provenance/correction data are semantic versus build-only provenance;
- which derived statistics are exactly recomputable and should not be duplicated in TF;
- whether any source records contain non-Greek running text that affects slot choice;
- exact Unicode/whitespace/punctuation behavior needed for text reconstruction;
- whether locus strings have source-specific parseable structure or must remain opaque labels in some families;
- licensing and attribution obligations for each in-scope layer;
- whether separate Open Greek annotation products belong in 0.1 or later independently versioned modules/materializers.


## R-004 — pinned source acquisition contract

Date: 2026-10-03  
Issue: #4

Open Greek's release tag is stronger than a branch name but the converter should still build from the tag's immutable publishing commit. For `corpus-2026-09-15.2` that commit is `338aa27310b3cfe2588a993b4d113b503597d70f`.

A local source checkout is accepted only when all of these agree:

1. Git `HEAD` is the supported full 40-hex publishing commit;
2. the checkout is clean, including untracked files;
3. `origin` identifies `open-greek/open-greek-corpus` (canonical HTTPS and GitHub SSH forms are equivalent for verification);
4. `data/corpus_release.json` exists and parses as JSON;
5. the manifest reports release id `corpus-2026-09-15.2`;
6. its corpus and catalog SHA-256 values match the supported release;
7. its work/passage/token counts match the supported release;
8. its `generated_from.commit` matches the recorded content-build provenance.

The manifest checks are intentionally redundant with Git identity. They turn accidental checkout mistakes, stale release metadata, or a future repository-history anomaly into an explicit failure before a multi-gigabyte conversion starts.

Acquisition is allowed to use the network. Parsing/conversion must not. The fetch helper therefore installs a detached checkout atomically into an empty/nonexistent destination and validates it before exposing it to the converter.

This initial contract supports one release rather than a free-form `--revision` option. Supporting another release means adding an explicit supported release identity and tests, not passing an arbitrary SHA that bypasses release-manifest expectations.
