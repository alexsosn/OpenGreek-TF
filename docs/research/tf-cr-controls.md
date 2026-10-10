# #29: Native Text-Fabric carriage returns and the pinned source corpus

Status: **active research; native serialization limitation is NOT resolved**.

## Research gate

The pinned source release is `open-greek/open-greek-corpus` at
`338aa27310b3cfe2588a993b4d113b503597d70f`. The record parser
introduced by #23 already accepts the *exact* original JSON string values
and recursively typed `FieldObject`/`FieldArray` without normalization.

In Text-Fabric 13.1, `tf.core.helpers.tfFromValue` escapes backslash, TAB
and LF, **not CR**. TF `tf.core.files.fileOpen` uses Python's default text
newline handling, and `Data._readTf` iterates lines. This means CR in a
native TF string field can create a physical line break and corrupt or
normalize the loaded feature. Direct source text may include CRLF after
JSON decoding even where raw source files use LF physical lines.

The limited `mini_writer.py` (merged #28) deliberately rejects CR in every
source string before beginning output. This is correct for the bounded proof,
but must not be mistaken for a full-corpus text-conservation solution.

## Plan and test gates

1. RED: implement nested-string CR occurrence census tests against primary,
   secondary and paratext; verify field path and exact count, including
   `provenance.note`, `text_lines[0]`, and no false positives for literal
   `\\r` (two characters).
2. Scan all 2,293,990 source records at the **pinned** immutable Git SHA
   with a streaming bounded-memory implementation. Print counts per family,
   per field path and a capped set of physical record keys. Independently
   count every physical `.jsonl` file, including the zero-byte secondary
   witness file; verify file and record count against the audit.
3. RED: directly exercise native TF `form` round-trip for ordinary LF/TAB
   versus CR/CRLF. Record whether `Fabric.load` rejects or changes the data.
   Do not hide the failure by expecting a successful rewrite.
4. Decide how to encode real CR source values **natively** after the census;
   retain #29 open until a proven representation and text/browser contract
   passes. No sidecar blobs, monkeypatch or normalization is permissible.

The scanner is a diagnostic for a future **independent conservation validator**
(#9); it does not itself materialize TF or decide the ontology (#3).
