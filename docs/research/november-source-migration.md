# #88 — November 2026 immutable source pin (acquisition phase)

## Research: real upstream release and changed manifest schema

The official [corpus-2026-11-17 release](https://github.com/open-greek/open-greek-corpus/releases/tag/corpus-2026-11-17) was published on 2026-11-18. Its **annotated tag object** `c06aecc445d88d6dbc3f7d0830c6ca930c10b4fc` peels to actual Git **commit** `122f2cba907dbac0af63f75cf1a54fa3309f36ba`. Only the commit is a checkout/build identity.

| Source manifest field | September converter pin | November candidate pin |
| --- | --- | --- |
| Release ID | `corpus-2026-09-15.2` | `corpus-2026-11-17` |
| Publishing commit | `338aa27310b3cfe2588a993b4d113b503597d70f` | `122f2cba907dbac0af63f75cf1a54fa3309f36ba` |
| Works | 3,909 | 3,939 |
| Primary passages | 1,970,947 | 1,913,683 |
| Eligible tokens | 65,285,435 | 65,271,607 |
| Corpus SHA-256 | `7369350964b5baa948595a5b4ac45165ccf0c5f6812a07565233be11a4c32071` | `0690bc3e43365b021ec7b201689456b5fe0f9e9d1abae3b846e6158d7cd09e33` |
| Source identity extras | `pin.catalog_sha256` and `generated_from.commit` | `release_date=2026-11-17`, `pin.manifest=data/public_export.json` |

The November `data/corpus_release.json` **does not have** the old independent `pin.catalog_sha256` or `generated_from.commit` fields. The new `data/public_export.json` carries the same corpus hash and an explicit per-work exported file manifest. A universal verification rule that accepts absent catalog hashes would weaken the old release contract. The source verifier therefore selects the **strict published manifest format based on the explicit immutable release identity** and checks the actual referenced export file for the November pin.

This opt-in phase does not silently change `SUPPORTED_RELEASE` or the existing converter's original-source inventory, native TF golden hashes and research semantics. Full conversion still uses September and refuses a November checkout until the source schema, counts, aliases, original-text conservation, and app behaviour have been separately migrated.

## Actual immutable old-vs-new Git tree census (pre-conversion)

I compared complete Git blob inventories from the **two exact publishing commits**, using GitHub's recursively listed Git trees (both returned `truncated=false`). This establishes filename membership and byte-level Git blob changes, **not** per-record content semantics or corpus conservation:

| Original textual family | September files | November files | Added files | Removed files | Existing files with changed Git blob |
| --- | ---: | ---: | ---: | ---: | ---: |
| `data/corpus/*.jsonl` | 3,909 | 3,939 | 38 | 8 | 1,224 |
| `data/corpus_secondary/*.jsonl` | 533 | 560 | 32 | 5 | 0 |
| `data/paratext/**/*.jsonl` (including subdirectories) | 5 | 17 | 12 | 0 | 0 |
| **All three textual families** | **4,447** | **4,516** | **82** | **13** | **1,224** |

The `data/paratext/` Git prefix includes a README, which changed but is excluded from the JSONL counts. **Three** of the twelve new paratext JSONL are nested at `data/paratext/gutenberg/{32549,37641,66595}.jsonl`. The current strict source parser requires exactly three path components, while `select_all_text_files` uses a top-level-only `glob("*.jsonl")`, so it would **omit these real source files** and reject direct selection. Other new file kinds/fields may require further audited schema changes. The existing `_EXPECTED_FILES=(3909,533,5)` and `_PINNED_ALL_TEXT_ROWS` cannot be reused for the November release.

The new release's **3939 work manifest count is not a physical passage record count**. No complete November textual row census or graph build has yet been proved. Every new file and changed blob must be classified by actual source records before treating the new snapshot as ready for materialization.

## Complete real November source-family schema census (#88, PR #92)

The existing pinned [November source CI workflow](../../.github/workflows/november-source-pin.yml) now scans **every original JSONL row** at the immutable November publishing commit. It reports exact per-family field/type occurrences, distinct record keysets, nested key shapes, CR and nested file paths, without storing any corpus data in this repository.

| Original family | JSONL files | Original rows | Nonempty files |
| --- | ---: | ---: | ---: |
| Primary | 3,939 | **1,913,683** | 3,939 |
| Secondary | 560 | **338,245** | 559 |
| Paratext | 17 | **23,969** | 17 |
| **Total** | **4,516** | **2,275,897** | **4,515** |

The empty Democritus secondary source still exists. The November complete original-text physical-row count **is not** the release manifest's primary-passage count, and neither is the September 2,293,990-row total.

New semantic fields are substantial: **15,834** primary `analysis_segments/analysis_text` rows, **547** primary `tokens` arrays and `critical_markup` objects, **27,913** secondary Dubner provenance structures, **4,235** secondary Meibom-style six-field `source_page` objects with `evidence`, **8** alternate cropped-image `source_page` structures with *floating-point scan coordinates*, **3,139** paratext Westermann editorial review structures, **419** paratext `ocr_consensus` records containing 53,093 nested token/slot objects, and **1,170** distinct paratext scan page objects.

**CR census:** 73 U+000D codepoints, confined to paratext `text`, zero in primary and secondary text. Standard Text-Fabric feature serialization is not CR-lossless. Do not normalize CR, misrepresent the default native text view as faithful, omit affected original rows, or claim full November migration. Issue #29 remains an actual source-backed blocker.

The first **selected-file** compatibility slice reuses the generic typed source fact graph and writer for the six-key Meibom `source_page` with explicit JSON null/boolean and the complete original Gutenberg `locus/source/source_sha256/text` records in `data/paratext/gutenberg/`. The original September reader remains strict. Version-specific unsupported November fields, cropped-image source page floats, complex token/editorial structures and CR-containing files **fail closed**, rather than being flattened or ignored. The real-source acceptance test selects one complete primary source file, a complete 65-row Nicomachus witness and a complete 9-row nested Gutenberg file, then independently compares the loaded native TF source facts to stock original JSONL.

## Opt-in researcher/developer commands

```bash
opengreek-tf source-info --release corpus-2026-11-17
opengreek-tf fetch upstream/open-greek-november --release corpus-2026-11-17
opengreek-tf verify-source upstream/open-greek-november --release corpus-2026-11-17

# Historical September commands still work with exactly their old default:
opengreek-tf source-info
opengreek-tf verify-source upstream/open-greek-september
```

An arbitrary revision, moving `main`, absent export manifest, wrong corpus checksum or mismatched release ID/count/date fails. Source acquisition may use the network; verification and all future conversion remain offline.

## New source semantic changes needing native TF decisions

The [new release notes](https://github.com/open-greek/open-greek-corpus/releases/tag/corpus-2026-11-17) report a corpus reduction in passages despite 30 more served works. This is not a monotonic append. Dioscorides, *De materia medica*, has redivided and corrected textual locations, **six** source-declared direct locus redirects, and **five** explicitly withdrawn addresses. The exact original concordance is `data/corpus_changes/dioscorides-pedanius.de-materia-medica.printed-divisions.json`. It reports source-authored former/new loci, including a case requiring one-to-many division and a withdrawal without destination. The new `data/passage_aliases.json` and `data/work_index.json` are broader upstream authority sources and must be audited before mapping any aliases into native nodes/edges. Withdrawal cannot be represented by silently dropping a previously resolvable source address or inventing a new passage.

The official annotations archive also patches four corrected works; it is a separate release asset and must not be opportunistically aligned against older native TF slots.

## Research → plan → RED-first → implementation → test gates

1. RED-first tests created before implementation require old/new strict identity selection and reject wrong peeled-commit assumptions, wrong manifest path/date, changed counts, bad/missing public-export hash and an old manifest misidentified as new.
2. Minimal implementation adds only immutable November acquisition/verification and source-info UI, preserving the established September default and hash checks.
3. A new opt-in [pinned November source CI workflow](../../.github/workflows/november-source-pin.yml) sparse-fetches the **exact real commit** and validates the actual corpus release/export JSON and source-declared Dioscorides redirect/withdrawal counts, with no source data bundled in this repository. It is an acquisition/evidence smoke, **not** a native TF build.
4. Exact-head Ruff/mypy/pytest, real pinned source CI, independent skeptical code/data review, and post-merge main CI are required before the phase is finalized.

## Still open before switching the canonical source release

- Audit the actual changed text file inventory, primary/secondary/paratext record schemas, registry/catalog/ID ledgers, changed work counts, and source corrections from the immutable November checkout.
- Model source-declared passage redirects, one-to-many redivision and withdrawn addresses as queryable native TF facts; prove downstream researcher citation navigation, not only parsing of a concordance JSON.
- Verify newly supported source and original text records against genuine generated and independently loaded TF, without accepting stale September output hashes as November evidence.
- Re-run native corpus memory feasibility, complete work/author/crosswalk graph, browser smoke, Agora and actual release gate.

**Do not close #88, #3, #6, #9, #10, #14 or #75 on source acquisition alone.**
