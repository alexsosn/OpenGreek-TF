# #71 — Stream independently loaded native TF occurrences during conservation

## Research and target

Before this change, the native writer and original JSONL verifier both invoked the complete eager native Fabric reader, retaining all reconstructed source records as a global source_seq dictionary plus a full tuple. The writer retained the input tuple as well; the independent stock JSONL validator eagerly reconstructed every TF row before comparing its first raw original line. No additional research semantics were carried outside native TF.

## Strict reader semantics

The new iter_native_records(destination) reads existing Text-Fabric F/E and restores typed nested facts one source occurrence at a time. It sorts only native root node IDs by genuine F.source_seq because native otype grouping otherwise separates passages from metadata. Checks remain for exact node and feature/edge/config surfaces, otext section and formats, nested typed facts and digest, genuine source anchor/slot/text run identity, Greek T.text, orphaned facts/atoms, F feature placement and E edges, physical source identity, contiguous global ordering, missing or duplicated rows.

The public read_native_records still returns a complete tuple by fully exhausting the iterator. Writer and public validator compare each original record against the independently reconstructed native record, preserving scalar Python types (False is not 0), and demand an extra next() after the last row to force all final integrity checks before reporting success. The independent stock original JSONL validator uses the same loaded Fabric iterator but not the writer's JSON/typed source parser; it wraps any midstream or end-of-stream failure in JsonlConservationError.

**Important:** A client consuming only the first few yielded rows has **not** independently validated the whole native corpus. Use the complete public reader or fully exhaust the iterator before claiming global validation. Text-Fabric F/E itself is still fully loaded in memory, and native CV plus the original source record tuple remain all-at-once. This is not a streaming complete-corpus converter.

## RED-first and adversarial validation

- Original RED-first tests (commit 122f76b) required an absent native TF iterator and returned an expected strict-mypy missing-API failure in [CI #39383382341](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39383382341). A test fixture import annotation was corrected before production implementation.
- Real converted native TF fixtures cover interleaved author/work metadata, primary and secondary Greek passages, whitespace, empty or null values, ordered duplicate array entries and distinct bool/int values. Instrumenting actual Fabric restoration proves one restored source occurrence becomes available before later records are reconstructed.
- A genuine saved forged F.source_file placement on a sourceFact passes the first yield but is rejected during final iterator exhaustion and by the original eager public reader.
- Existing tests still exercise fabricated native features, false extra edges, otext alteration, original Greek reconstruction and per-row source identity. The adversarial False-versus-integer-0 comparator test was retargeted to forge the actual streaming reader, and both public validation and native writer reject the forgery.

## Measured original-source results

Immutable original upstream pin: open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f. Source-conserved original Greek: 31,977 passages; 237,664 typed source facts; 749,590 genuine source/layout atoms; 2,326,212 original Unicode codepoints. The native F/E output remains exactly **31,811,763 bytes**, canonical SHA-256 **fa9e5eddcb2a46e0ccc1c8437cace0460514b7c2b313ccb33c1a9418379b82c1**.

| Whole-process peak RSS | Baseline #70 | Streaming verifier |
| --- | ---: | ---: |
| Isolated builder, original Greek (31,977 rows) | 977.88 MiB | 977.92 MiB |
| Independent stock JSONL / loaded TF verifier, Greek | 1,067.77 MiB | **1,013.61 MiB** |
| Isolated complete registry builder (14,390 records) | 839.11 MiB | **828.17 MiB** |
| Separate complete registry verifier (uses intentionally eager public reader) | ~1,040 MiB | 1,040.1 MiB |

Registry conservation independently verified all **3,315 author / 11,075 work** original records, **252,276 typed source facts**, all known original nulls, **14,454,531 output bytes**, unchanged canonical SHA-256 **6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e**. Greek full original-source gate: [Actions #39384000017](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39384000017). Registry gate: [Actions #39384000214](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39384000214). Exact-head standard [CI #39384000027](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39384000027) passed Ruff, strict mypy and **475 tests**; additionally passed pinned original mixed, primary four-file, and unaligned source workflows.

Single-run GitHub Linux runner memory and timing figures are observations, not statistically controlled evidence of throughput improvements. The original Greek builder peak is **unchanged** despite less postwrite full-record retention. The substantial observed ~54 MiB decrease is in the **independent Greek source verifier**. No whole-corpus memory or release claim follows from this subset.

## Next scaling target

Continue #71 by profiling native TF CV assembly and Fabric feature loading, and evaluating a source-record streaming construction strategy that preserves all native F/E semantics and fail-closed original JSONL-to-loaded-Fabric validation. Keep #6, #9, #13 and #14 open until genuinely building and independently verifying the full 1,970,947 passage corpus.