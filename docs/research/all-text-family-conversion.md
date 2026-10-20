# Full primary + secondary + paratext text-family conversion: next release rung (#8/#6)

## Proven original textual scope

Open Greek pinned release `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` contains three independently audited JSONL source families. The full pinned source-stream census (not a TF output count) is:

| Original family | Physical files | Original rows | Native TF record kind |
| --- | ---: | ---: | --- |
| `data/corpus` | 3,909 | 1,970,947 | `primary-passage` (genuine Greek text layout slots) |
| `data/corpus_secondary` | 533 | 307,085 | `secondary-witness` (unaligned, text remains a typed fact) |
| `data/paratext` | 5 | 15,958 | `paratext-record` (unaligned editorial/original textual facts) |
| **All original texts** | **4,447** | **2,293,990** | One native F/E graph when successfully built |

The exact genuine pinned zero-row secondary JSONL is `data/corpus_secondary/democritus.fragmenta.jsonl` (proven by the full 4,447-file source census), and the full selector rejects any unexpected substituted or additional empty source. Complete source provenance must include its actual path, while fabricating zero-row TF nodes is prohibited. The default selected-file original-source validator still rejects empty inputs; only the pinned full inventory may explicitly allow these verified empty containers. Original source digest includes every selected file name even when its source record count is zero.

## User-facing commands

Selected source files of ANY of the three families can now be materialized into one native TF output directory:

```bash
opengreek-tf fetch upstream/open-greek-corpus
opengreek-tf convert-texts upstream/open-greek-corpus \
  --file data/corpus/abydenus.fragmenta.jsonl \
  --file data/corpus_secondary/abydenus.fragmenta.jsonl \
  --file data/paratext/edition_apparatus.jsonl \
  --file data/paratext/latin_in_greek_script.jsonl \
  --output generated/mixed-original-texts
```

Full selected physical source inventory conversion (high-memory, **not yet a demonstrated complete-corpus run**):

```bash
opengreek-tf convert-texts upstream/open-greek-corpus --all \
  --output generated/all-2293990-original-texts
```

The command takes no network actions during conversion. It verifies a clean exact pinned Git checkout before and after the build, rejects existing or inside-checkout outputs, validates canonical source names, physical duplicates, aliases and path escapes, and refuses to print success until **the complete resulting native F/E is independently loaded and every original UTF-8 JSONL row (nested ordered source fields and scalar types) agrees**. Complete mode requires the pinned 3,909/533/5 physical-file inventory **before** writing and the 1,970,947/307,085/15,958 independent original textual row census **after** native graph validation. Success output carries source SHA, canonical native TF hash, per-family counts and empty source-file count; file-level paths in selection mode; complete mode avoids dumping 4,447 paths to stdout.

Secondary witnesses and paratext are intentionally **not** fabricated into primary Greek word slots or guessed to align with the primary rendition. Their complete original textual contents survive as typed source fact nodes. The standard TF native `passage` sections currently describe primary source rows, not the final author/work/locus hierarchy. Author/work registry, TLG crosswalks, and final scholarly ontology are outside this *text-family-only* command; those must be explicitly integrated for the release.

## Research → RED-first → implementation → actual source tests

- RED-first tests required selected mixed source CLI conversion and complete source inventory selection before the new `text_materializer` module existed. Tests cover exact source identity/typed fact restoration, duplicate path and physical hardlink rejection, missing/bogus family paths, outside-checkout targets, final source re-verification, and physically empty source files preserved in source provenance while normal selected-file requests remain strictly nonempty.
- The implementation reuses `primary_materializer.iter_native_primary`, `unaligned_materializer.iter_native_unaligned`, the **same** `native_composer.write_native_records` CV writer, and independent stock JSONL/loaded real TF `validate_native_jsonl_sources`. No parallel writer, lexical fiction, source-normalizing conversion, JSON research sidecar or custom browser.
- Pinned GitHub Actions tests use an installed CLI on **166 original physical text rows** from four source files (6 primary, 47 secondary, 113 paratext) and independently reload actual F/E and query all three original kinds. A second pinned-source workflow verifies the complete **4,447-file inventory, zero-byte source filenames and all 2,293,990 original rows** without claiming that an entire native graph was built. Existing regression workflows retain the 31,977-passages original-source Greek full validation and full 14,390-record author/work registry checks.



### Measured larger combined Text-Fabric result

The pinned installed CLI also independently converted a **single** 32,137-row actual original Greek/unaligned TF graph from three different textual primary strata (15,683 Homer, 4,335 Herodotus, 11,959 Moeris), 47 secondary-witness rows, and 113 paratext rows. Its raw original stock-JSONL/loaded-Fabric check passed all **239,274 original typed source facts** and **2,402,648 original Unicode text codepoints** (source SHA-256 `ab87e7e29deea26fd8523747ffaf26b2aa36dff493305da44ef15297dc327030`). Genuine output was **32,078,599 native TF feature bytes**, canonical SHA-256 `3457bab1a10966ea8682b7794739edb66f04c41dcbac057792b6e9dec023cc35`. On one GitHub Linux runner, the isolated installed-CLI builder process peaked at **1,170.57 MiB RSS** and completed in **39.815 s** (inclusive of its internal validation); the separately loaded independent stock-JSONL/Fabric verifier peaked at **1,062.79 MiB**. The scale is **32,137 / 2,293,990 original rows (about 1.4%)**, so this does not validate a complete-corpus build.

The separate full original pinned inventory job scanned **3,909 / 533 / 5** physical files and independently typed-parsed **1,970,947 / 307,085 / 15,958** source records, including the single empty Democritus witness. **This was an inventory/source parse, not a full TF build.**

## Explicit nonclaims / next required proof

`--all` is a complete-scope *conversion path*, not a measured scalable production converter. Its internal native CV converter still materializes a whole `tuple[NativeRecord]` and loads Text-Fabric F/E into RAM during full postwrite checks. The genuine 31,977-passage Greek builder already reaches ~978 MiB peak; extrapolating to 2,293,990 original rows could cause OOM. Do **not** promote full release or claim all 65 million Greek tokens successfully converted on the basis of the file/row census or selected E2E.

Next gate: a genuine **larger rung** of the combined original text corpus, isolated measured builder peak RSS and native F/E verification with all three kinds, followed by full 2,293,990-row build on adequately provisioned CI/self-hosted runner with independent stock JSONL-to-loaded TF checks and reproducible hashes, registry/work-author/section graph and standard TF browser E2E. Issues #6/#8/#9/#13/#14/#71 remain open until those facts are demonstrated.