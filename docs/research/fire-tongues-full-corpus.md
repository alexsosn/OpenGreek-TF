# Full-corpus Greek tongue/fire concordance (2026-10-27)

## Question

Before Acts 2:3, do Greek texts use a literal/figurative *tongue of fire* (γλῶσσα/γλῶττα together with fire terminology), independently of the known 1 Enoch 14:9–15 attestations?

The question requires **corpus-wide recall first**, followed by a **chronological and semantic** audit. It cannot be answered conclusively from GitHub code search or by dating the edition rather than the composed passage.

## Source and coverage

The pinned `open-greek/open-greek-corpus` commit is
`338aa27310b3cfe2588a993b4d113b503597d70f` (release `corpus-2026-09-15.2`).
The scanner asserts inventories against the audited source:
- primary: 3,909 files, 1,970,947 records;
- secondary: 533 files, 307,085 records;
- paratext: 5 files, 15,958 records;
- total: **2,293,990** independent source occurrences across **4,447** files.

All scanning is of the original `text` value in each UTF-8 JSONL occurrence, never a case-folded output substituted for source text.

## Search

The code case-folds and accent-strips the text for matching, not for quotation. It retrieves both `γλωσσ-` and Attic `γλωττ-` alongside `πυρ-`, `φλογ-`, `φλεγ-`, `φλεξ-`, `φλοξ-`, `καιο-`, `καιε-`, `καιει-`, `καυ-`, `αιθ-`, `ἐμπρησ-`, within **160 normalized characters**. Matches are classified as core fire vocabulary or deliberately over-inclusive extended fire vocabulary. The scanner finds *every* pair (not just the first hit in a file), reports source file, source occurrence ordinal, upstream locus, original Unicode context, and cross-row candidates where Greek source passage boundaries bisect a possible phrase.

No presumption of word adjacency, Greek case, number, or word order. This still **cannot guarantee semantic exhaustiveness**: synonyms, indirect fire metaphors, stem omissions, long-distance constructions, and manuscripts absent from Open Greek remain possible. The result is a comprehensive *specified lexical scan*, not proof of non-attestation in all Greek literature.

## Review gates

1. Verify all inventory counts before concluding absence.
2. Examine all pre-Christian and 1st-century candidates **by author and text**, not merely aggregate pair totals.
3. Distinguish tongue of flame as a visible projection of fire from the burning/sinful *human* tongue and from glossography, rhetoric, tongues/languages, and later citations of Acts.
4. Treat 1 Enoch's composition date, Greek translation date, and manuscript attestation as separate questions.
5. For claims about *before Acts*, use independent date estimates and include uncertain or pseudepigraphic attributions in an unresolved category, rather than silently excluding them.
6. Compare omitted traditions such as papyri and texts outside this corpus; bibliographic corpus coverage is a separate limitation.

## Run

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_fire_tongues_scan.py
python -m opengreek_tf.ci_source_cache prepare upstream
python -m opengreek_tf.ci_source_cache checkout upstream
python -m opengreek_tf.fire_tongues_scan upstream --output fire-tongues-results
```

The pinned GitHub Actions workflow performs this using a verified checkout and publishes `candidates.jsonl` and `summary.json` as an auditable artifact.
