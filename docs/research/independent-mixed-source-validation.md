# #9: Writer-independent native TF / original JSONL conservation gate

## Research (live merged code, 2026-10-11)

`main=01a661fd24d90425c92e8084bd39d9daf3f62e30` has independently loaded full native Text-Fabric graphs (`read_native_records`) and pinned real-source checks, but critical source-vs-F/E comparison lives in separate inline workflows for primary (PR #55/#57) and unaligned secondary/paratext (PR #58). All three source families share the same strictly typed `NativeRecord` and `F/E sourceFact` topology; there is no reusable source-independent validator able to check *mixed* original JSONL families in one graph. Source-family materializers are **not** appropriate validators of themselves.

## Plan and RED-first tests

1. Add public `validate_native_jsonl_sources` with source root, ordered canonical relative-file paths, native TF directory. Original bytes are independently decoded with stock `json.loads`, no `record_stream.parse_file`, no source-family writer and no inferred alignment. Report original-source SHA-256, exact row/family counts, nested fact counts and original Unicode text codepoints; metrics only, never a semantic query sidecar.
2. RED-first tests using genuine native F/E with one original primary file (2 passages, including empty text and `False`), one secondary witness file, one paratext file. Challenge type equality (`False == 0`, `True == 1`), field ordering, text mutation, swapped/dropped/extra physical rows, source file reordering, duplicate JSON keys, nonstandard NaN/float, invalid UTF-8, missing files, and same physical file selected via a hardlink alias. Validate no output mutation by an independent read-only checker.
3. Implement recursive exact ordered JSON-vs-FieldObject/FieldArray comparison; enforce type before comparing values, preserving explicit JSON nulls and arrays; reject duplicate or out-of-root physical aliases. Match physical source row identity and expected semantic class: `primary-passage` and `text` only for primary; nonlexical `secondary-witness` / `paratext-record` with `text=None` but original source text retained as typed fact. Match every row in original selected file order, with no missing/excess TF records; `read_native_records` independently reconstructs F/E, digest and exact TF Greek `T.text`.
4. Real pinned CI checks four genuine original upstream files at immutable `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`: 6 primary Greek passages in `abydenus.fragmenta`, 47 secondary original witnesses, 56 apparatus entries, 57 Latin-in-Greek-script paratext records. Compose all **166 source occurrences into one native TF graph**, independently verify stock source bytes / every loaded source fact, exact primary Greek display, no fake witness alignment or lexical words. Record source digest and canonical TF digest.
5. Exact-head pytest/Ruff/mypy, pinned actual-source CI, independently skeptical adversarial review rooted in the source decoder, error behaviors and native TF loader; correct and re-review before merge.

## Boundaries

This is a **mixed-source subset** conservation validator, not the still-unbuilt complete 1,970,947 primary rows or a release certificate. No new authority/CTS equivalence or syntactic tokens. #9 remains open until full source snapshot and release coverage are proven; #3, #6, #8, #13 and #29 still have unresolved requirements.
