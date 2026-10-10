# #25 — Exact Unicode layout-run segmentation (research, not slot freeze)

Status: candidate text-segmentation primitive for #3, **not** a production TF
slot type or lexical tokenization claim. Pin:
`open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`.

## Research source evidence

The release has 1,970,947 primary passage text strings, 307,085 secondary
witness records and 15,958 paratext records. Text strings contain polytonic
Greek, historical spelling and punctuation; 1,226 primary records also have
`text_orig`, which is an independent diplomatic text layer. 103,709 source
records contain physical `text_lines` that must not be inferred from a mere
display wrap. The field `locus` is nonunique for multiple genuine records.

Pinned direct example: `data/corpus/heraclides-ponticus.fragmenta.jsonl`
begins with Greek text `Ἀθηναῖοι τὸ μὲν ἐξ ἀρχῆς ...` (DFHG source,
CC-BY-SA-4.0), confirming whitespace-separated running text with Greek
punctuation. The parser must not manufacture morphological words or
reconstruct normal form from this display text.

## Hypothesis and test gate

A basic Unicode **layout-run** partition can be lossless without classifying
lexical units: group adjacent Python 3.11 `str.isspace()` codepoints together,
and group adjacent non-whitespace codepoints together. This makes every output
segment an actual nonempty slice of source string with exact start/end
codepoint offsets. It is not a Greek tokenizer, does not split punctuation,
and is not necessarily the best TF slot unit.

RED-first tests must demonstrate:
- concatenation of runs reconstructs original input *exactly*, even for NFD,
  combining marks, tabs, CRLF and special invisible characters;
- no whitespace trimming, case-fold, NFC normalization, fabricated words or
  gap/overlap in source codepoint offsets;
- empty string means **zero** runs, not a manufactured text slot;
- `text` and `text_orig` are separate optional layers with no alignment
  claims;
- randomized stress and true source Greek fragment.
- source-loaded TF text rendering, real corpus size and query performance
  remain separate #3/#13/#10 decision gates.

## Plan

1. Research source and group-by-whitespace tradeoff.
2. Commit RED tests before implementation.
3. Implement minimal pure generator and source-independent record-layer helper.
4. Run lint/types/pytest on exact PR head.
5. Independent adversarial review; do not merge if the tested partition
   cannot be reconstructed, or if it is inaccurately advertised as tokens.
