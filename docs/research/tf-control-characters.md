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
and ordered objects. It counts every Unicode Cc control (C0, DEL and C1, excluding TAB and LF),
distinguishes CRLF pairs, and reports affected physical rows.
It uses 0-based Python Unicode-codepoint offsets within the leaf field value
and preserves the exact `relative_file:ordinal:field_path` source location.
Field names are schema-audited and not treated as source text.

The CLI has bounded aggregate memory: it retains counts and no more than
`--sample-limit` diagnostic locations. When
`--locations-output controls.jsonl` is supplied it streams **all** locations
to a separate diagnostics-only JSONL, without keeping them in memory.
The diagnostic output path must be outside the source checkout and must not
already exist; the CLI uses exclusive creation to avoid overwriting corpus or
prior evidence. No source text or generated corpus is committed.

Example (after verifying the local checkout):

```bash
python -m opengreek_tf.control_census upstream/open-greek-corpus \
  --locations-output control-locations.jsonl > control-summary.json
```

The `Pinned source control-codepoint census` workflow performs the scan
against exactly the supported release and fails if the three-family row/file
counts differ. An independent raw-JSONL pass walks decoded objects
without using the typed parser and checks Unicode category `Cc`, affected
row counts and CRLF counts against the scanner's report. It uploads the
diagnostics and prints the counts to its job summary. The result is evidence about **this pinned release only**; the
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

A later [C1-inclusive pinned run 38060929665](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38060929665)
repeated the complete 2,293,990-row census and independently reread all
source JSONL via a separate Unicode-category `Cc` implementation. Both
scanners agreed: **52 distinct affected records; 93 field occurrences**;
**0 CR/CRLF**; **2 DEL** and **91 C1 occurrences**. The observed C1
codepoints and field-occurrence counts were:

| Codepoint | Count | Codepoint | Count |
|---|---:|---|---:|
| U+0081 | 3 | U+0086 | 2 |
| U+0088 | 2 | U+008C | 3 |
| U+008D | 20 | U+008E | 5 |
| U+008F | 4 | U+0090 | 4 |
| U+0098 | 12 | U+009A | 17 |
| U+009C | 4 | U+009D | 11 |
| U+009E | 4 | | |

The C1-inclusive run's own *overall conclusion was failure*, because the
real DEL Text-Fabric proof fixture had omitted mandatory TF section metadata.
Its raw-source census and independent cross-check steps **did pass**. It
cannot count as an exact-head green release gate. Subsequent corrections
give TF fixtures genuine passage section nodes/features and require
`F.form` and `T.text` identity on the DEL passage, alongside synthetic
round-trip probes for every observed distinct C1/DEL codepoint.

The two DEL field occurrences remain a single physical source row, and the
reported C1 counts are *field occurrences* rather than unique textual glyphs:
nested `text_lines` may repeat a character already present in `text`.

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
