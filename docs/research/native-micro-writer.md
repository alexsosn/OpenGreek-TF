# #27 — Fail-closed primary-to-native-TF micro-writer experiment

Status: **prototype**, stacked on #25's Unicode layout-run work. Not the final
ontology, full corpus builder, web app or Agora materializer. Source parser is
the merged #23 code. No source material is bundled with this repository.

## Evidence / research

TF 13.1's walker removes unlinked nodes; the proven alternative (#20/PR #22)
uses genuine metadata-record slots under a generic `atom` slot type. These
must not masquerade as Greek words. Unicode layout runs (#25/PR #26) preserve
every original codepoint but are not linguistically analysed word tokens.

The pinned primary source has nonunique `locus` labels: in Proclus a second
OCR edition repeats 2,415 loci, while fragment collections repeat labels for
different fragments. Use `(source_file, physical_1_based_row)` as stable
passage identity, keep original `locus` only as literal citation metadata.

The selected writer will consume a **bounded sample** of actual parsed primary
records, not a whole 65M-token corpus. This bound is explicit; a full writer
needs streaming/batching and an ontology ADR.

## Plan / TDD gate

1. RED: synthetic adjacent passages sharing literal `locus`, empty-text row,
   leading/trailing/newline Greek and decomposed Greek, plus one real source
   paragraph; require loaded TF exact original text, positive query features,
   and genuine source-record atom per row.
2. Support scalar `str` and `int` source fields *as native typed TF passage
   features*. Retain `urn`, `edition`, `source`, `license`, `locus` as
   literal fields. `text` is split into exact `form`-bearing layout runs,
   not stored as a redundant big text feature.
3. **Fail closed** before creating any TF output on every structured,
   boolean, diplomatic `text_orig`, and mixed-work/secondary field. A
   prototype that quietly drops the correction/metadata layer is worse than
   refusing unsupported input. Nested arrays/objects will need native TF
   nodes/edges in production #5/#6/#7/#8.
4. Add true source-row atom (not artificial Greek word) per passage so an
   original empty text row still has a loaded and queryable passage node.
5. Test standard `CV.walk`, `Fabric.load`, `T.text`, native section labels,
   exact slot reconstruction, and section navigation. No fake `book/chapter`
   hierarchy.
6. Run exact-head CI and pinned-source smoke; independently scrutinize code
   and true data before merging. Compare performance and user-facing browser
   results later in #13/#10.

## Explicit limitations

The `atom` slot type and a per-row metadata atom are *one tested candidate*.
The entire Open Greek semantic surface is not yet expressible by this narrow
writer. It intentionally raises `UnsupportedSourceStructure` rather than
pretending to materialize rows with `corrections`, `merged_read`, `provenance`,
`text_lines` or `text_orig`, and it does not invent author identities.
