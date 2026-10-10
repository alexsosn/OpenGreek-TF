# #20: pinned identity-ledger atoms — narrow native-TF experiment

Status: research/plan for a **bounded proof**, not a production ontology or full-corpus identity conversion.

## Source evidence (immutable commit `338aa27310b3cfe2588a993b4d113b503597d70f`)

Inspected actual `data/author_ids.json` and `data/work_ids.json` at that revision. Their `_meta.scheme` respectively declares `oga` and `ogc`; the `authors` and `works` mappings contain source-declared `slug`, `former_slugs` (ordered array), and `status`.

- Author ID ledger: **1,516** records = 1,500 `served`, 16 `retired`. Source examples: `oga000001` (`abas`, served) and `oga000330` (`cedrenus-et-psellus-pg122`, retired).
- Work ID ledger: **3,944** records = 3,909 `served`, 35 `retired`. Examples: `ogc000772` (`choerilus.fragmenta-epica`, former slug `choerilus.tituli-p-oxy-11-1399`, served) and `ogc000839` (`cogPG.PG003`, retired).
- Exactly six work-ID entries in this release have non-empty `former_slugs`; no author-ID entries do. Distinguish ledger size (3,944 works, 1,516 authors) from broader catalog/registry cardinalities (11,075 works, 3,315 authors) established in the corpus audit. Do **not** conflate a registry identity with a served passage.
- These ledger JSONs are not JSONL passage records, so they cannot be blindly passed to the strict `ParsedRecord` text-stream parser. Their full nested source semantics require a future registry-specific typed IR / common fact graph interface.

## Text-Fabric 13.1 behavior already proven by #22

The repository has executable tests in `tests/test_metadata_only_nodes.py` and `tests/test_source_atom_slots.py`: `CV` drops unlinked non-slot nodes, and direct `Fabric.save` with genuinely empty `oslots` fails on reload. Metadata-only records can be modeled as **genuine metadata source atom slots**, clearly marked `atom_kind=registry-record`, with their catalog nodes having only those non-text atoms, not Greek words or fabricated passage spans. This differs deliberately from BHSA's word slotType precedent; it is an explicit hypothesis pending #3 and #13.

## Plan / invariants for this PR

Build a small, **real source data-backed** proof rather than another fake catalog entity:

1. Parse the exact two source ledger files with strict shape/typed `slug`, `status`, `former_slugs` validation, correct namespace, uniqueness and source order. Missing IDs, invalid statuses, duplicates and unknown scalar types fail closed. Do not silently discard aliases.
2. For selected source IDs, create exactly **one** `atom` for each real ledger entry with `atom_kind=registry-record`, provenance `source_file` and `source_record_id`. Native `registryAuthor`/`registryWork` nodes retain opaque ID, exact slug and status; **no text or `form` features** on these atoms. `formerSlug` nodes map via `has_former_slug` typed edge to their *parent record atom* without extra slots, with numeric index to preserve source array order and multiplicity.
3. The independent reader loads `F.otype`, node features and edge features from `Fabric.load` (not the original JSONs), reconstructs selected ledger entries and rejects duplicates, aliases out of order, lost node/atom links, wrong source file/kind, spurious text slots or missing values.
4. RED-first tests with synthetic source ledgers covering served and retired authors/works, ordered repeated former slugs, corruption, duplicate IDs, malformed ledger, and no lexical slots. Use actual pinned sample IDs and one alias in independent pinned workflow: source `author_ids.json`, `work_ids.json`, `corpus_release.json`; `verify_source` must prove exact immutable commit and provenance before TF creation.
5. Exact-head Ruff, mypy, pytest and pinned real-source native TF; logically independent adversarial review, especially whether alias cardinality/ordering, IDs, license/provenance or fabricated text semantics were lost. Do not merge green-only fixtures without real source evidence.

## Explicit non-goals

This proof does *not* cover the 11,075-work broader catalog, 3,315-author registry, alternative IDs/crosswalks, complete source nested fact graph, scalable full-corpus materialization, generic registry metadata, browser usability, or freeze #3. Keep parent #20 open until broader catalog/retired identity conservation, browser and performance gates are proven. No semantic sidecars, invented word tokens, phantom passages or guessed source authorship.

## Real TF 13.1 conversion caveat surfaced by initial pinned run

The first immutable-ledger workflow [run 38082602449](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38082602449) fetched and verified the actual two ledgers and passed source cardinalities, but the native `CV.walk` failed in `_prepareMeta` with `UnboundLocalError: textFormats` when passed `otext={}`. An absent text *format declaration* is therefore not a viable TF 13.1 CV configuration, even for a corpus consisting of genuinely non-textual source records.

The supported bounded solution declares `fmt:metadata-id={source_record_id}`. This formats an **existing opaque source identifier**, not a fake Greek word, phantom text span or empty passage. The per-source metadata atom still has **no `form`**; the test explicitly checks `T.text(registry_node, fmt="metadata-id")` equals the actual source ID after native `Fabric.load()`. A production advanced app must prominently distinguish registry metadata display from Greek textual editions; the default web text format remains part of #3/#10.
