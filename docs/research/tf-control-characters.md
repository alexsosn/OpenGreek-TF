# #29 — Control-codepoint serialization boundary and pinned census

Status: research/TDD slice; **not** native CR support, not a production schema decision.

## Research evidence and failure mode

In Text-Fabric 13.1, plain string-feature serialization escapes backslash,
TAB and LF, but not CR. Reading `.tf` via standard text-mode file opening
uses universal-newline conversion. A source value containing U+000D or CRLF
therefore cannot be assumed to survive `CV.walk` -> `Fabric.load` ->
`F.form` / `T.text` exactly. The merged bounded primary writer (#27/PR
#28) correctly rejects U+000D before writing anything.

The characterizing integration test writes U+000D into a native TF `form`
feature and checks for the observed non-identity after a genuine TF load.
This is a **negative compatibility proof**, not a permitted normalization.

## Data research before choosing an encoding

The supported Open Greek source is the immutable publishing commit
`338aa27310b3cfe2588a993b4d113b503597d70f`. All observed scholarly
text rows must be examined, not just the primary `text` field:

| Family | JSONL source files | Rows |
|---|---:|---:|
| primary | 3,909 | 1,970,947 |
| secondary | 533 | 307,085 |
| paratext | 5 | 15,958 |

`control_census.py` uses the audited, strictly typed `record_stream`
parser and recursively inspects every nested source string, including arrays
and ordered objects. It counts each Unicode Cc control (C0, DEL and C1, excluding TAB and LF), distinguishes CRLF pairs, and reports affected physical rows.
It uses 0-based Python Unicode-codepoint offsets within the leaf field value
and preserves the exact `relative_file:ordinal:field_path` source location.
Field names are schema-audited and not treated as source text.

The CLI has bounded aggregate memory: it retains counts and no more than
`--sample-limit` diagnostic locations. When
`--locations-output controls.jsonl` is supplied it streams **all** locations
to a separate diagnostics-only JSONL, without keeping them in memory.
No source text or generated corpus is committed.

Example (after verifying the local checkout):

```bash
python -m opengreek_tf.control_census upstream/open-greek-corpus \
  --locations-output control-locations.jsonl > control-summary.json
```

The `Pinned source control-codepoint census` workflow performs the scan
against exactly the supported release and fails if the three-family row/file
counts differ. It uploads the diagnostics and prints the counts to its job
summary. The result is evidence about **this pinned release only**; the
scanner is not permission to accept CR in a later release.

## TDD gates

1. **RED**: import-dependent tests fail before scanner implementation.
2. **GREEN**: synthetic primary/secondary/paratext fixtures prove CR, CRLF,
   nested arrays/objects, NUL, ESC, DEL, field offsets, total counts and
   bounded samples; a second test proves the uncapped callback stream.
3. Exact-head tests: `ruff`, `mypy`, `pytest` (with real TF 13.1), and a
   complete, independently pinned source scan in GitHub Actions.
4. Independent review must challenge: row/file census, non-CRLF CR accounting,
   nested source strings, codepoint indices, and any claim of TF browser
   compatibility.
5. Do **not** close #29 solely from this PR. A nonzero pinned CR census
   prevents claiming lossless native TF until there is a tested representation.

## Pinned-source evidence (initial C0 + DEL implementation)

[Successful run 38060040207](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38060040207)
verified the immutable release and all 3,909 + 533 + 5 files /
1,970,947 + 307,085 + 15,958 records. For controls in U+0000–U+001F
(except TAB/LF) and U+007F, it found:

- **U+000D (CR): 0**; CRLF pairs: 0.
- **U+007F (DEL): 2 source-field occurrences in one physical row**.
  `data/corpus/aelius-herodianus-et-pseudo-herodianus.peri-paqw-n.jsonl`,
  row 1043, `text` offset 570 and `text_lines[2]` offset 57 (all offsets
  zero-based Unicode codepoints). These are two source representations of a
  single passage, not evidence of two independent primary text passages.
- All other C0 controls except TAB/LF: 0. One affected source row.

That early successful run predates expansion of the scanner to the complete
C1 range U+0080–U+009F. The exact-head C1-inclusive run is a distinct
acceptance gate; the counts above must not be extrapolated to C1.

The observed DEL has its own RED-first TF `form` / `T.text` round-trip
test. A pass for DEL would not establish CR or browser compatibility.

## Open decisions

If the pinned corpus contains CR, compare a first-class native integer
codepoint atom with a minimally scoped upstream Text-Fabric fix. Any proposed
representation must independently reconstruct original values, including
`F.form` or an explicitly supported text format plus advanced browser
rendering, without silently using replacement characters or JSON sidecars.
If the pinned corpus has zero CR, retain the fail-closed guard and separately
decide whether broad upstream CR support is needed for future versions.

Other source controls need separate Text-Fabric serialization tests before
deciding whether they are safe or require additional guards.
