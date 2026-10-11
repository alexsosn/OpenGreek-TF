# #20 — complete author authority to native Text-Fabric

Scope: all **2,240 TLG source entries** in data/author_authority.json at Open Greek commit 338aa27310b3cfe2588a993b4d113b503597d70f. This is *not* the 1,516-row OGA ID ledger or all 3,315 catalog authors. No inferred mapping between TLG and OGA.

## Research evidence

The source JSON maps exactly 2,240 TLG keys to ordered field objects. Observed values: birth 1,232 integers; death 1,148 integers; floruit 791 integers; gnd 2,112 strings; isni 1,092 strings; viaf 2,154 strings; wikidata 2,240 strings; _multi 16 ordered string arrays. Negative years and leading zeros of external identifier strings must survive. Source keys are *TLG authority IDs*, not OGA IDs. A separately researched work_authority.json has 4,062 work entries grouped under 585 TLG parent keys, a distinct structural batch after this PR.

Earlier native TF experiments #41 and #43 establish that TF 13.1 CV removes unlinked nodes, empty oslots cannot reload, and metadata-only CV requires explicit section config and fmt:text-orig-full; do not introduce invented text to appease these requirements.

## Plan / acceptance gates

1. **RED-first** strict source parser: reject duplicate JSON keys, malformed TLG keys, unsupported field values/types (null/float/bool/object), unknown semantically important keys, and count inconsistencies. Preserve source entry/field order, exact signed integers and string-array item order/multiplicity, including empty arrays.
2. Batch writer: exactly one *genuine authority source record* atom per TLG key; authorAuthority node rooted on it; native authorityField nodes with source field key, position, typed scalar value; authorityArrayItem nodes for declared _multi elements, anchored to the *same authentic source record* atom with ordered has_authority_item links. Typed has_authority_field edges from each author node. Zero fake Greek word/passage/lexical features and zero semantic sidecars. No guessed text occurrence, TLG-to-OGA crosswalk or bibliography.
3. Independent Fabric.load reader reconstructs all source records and validates atom ownership, source file/id/ordinal, typed scalar, field index/uniqueness, array item membership/order/duplicates, and absence of orphan features or phantom text nodes. Compare full native output against original source to detect lost rows and corruption.
4. Test source mutation after output, missing TF value, duplicate JSON key, subset output, repeated and empty arrays, negative birth year, 0 and leading-zero ISNI values. RED first, then implementation.
5. Real pinned workflow fetches only data/corpus_release.json and data/author_authority.json under exact immutable upstream SHA and calls verify_source. Verify 2,240 records and known per-field frequency counts, 16 _multi arrays, 2,240 genuine nontext slots, all nested values after reloading TF; publish actual build/load time and size. Standard exact-head pytest, Ruff, mypy.
6. Independent adversarial code-and-data review; only merge after all checks green. Keep #20 open for broader 3,315-author/11,075-work catalog, nested work-authority (585 groups / 4,062 records), source registry, crosswalks, advanced TF browser and #3 ontology freeze.

Risk: metadata text format may display source ID labels by TF default-format contract; it is not Greek text. A small native metadata-only corpus benchmark does not prove performance of the full text+metadata corpus.
