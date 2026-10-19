# #13 — Rust Context-Fabric 0.6.0rc1: original Greek native-F/E compatibility experiment

## Research and decision

- OpenGreek-TF currently writes **native** Text-Fabric 13.1 feature files. Its canonical writer, independent source JSONL/Fabric verifier, and normal CI run under Python 3.11. Do not silently substitute an unrelated storage/model layer.
- [Context-Fabric 0.6.0rc1](https://pypi.org/project/context-fabric/0.6.0rc1/) was released on October 15, 2026. It is **pre-release** and requires Python **>=3.13**. `from cfabric import Fabric` reads native `.tf` files, compiles a memory-mapped `.cfr` cache, and advertises a TF-compatible F/E/L/T/S API. It is not expected to accelerate **writing** OpenGreek's native TF through `tf.convert.walker.CV`.
- The upstream BHSA performance figures are not measurements of this corpus. Their first-compile cache sizes and warm-load results must not be silently compared as the same workload.
- The only new artifact here is a read-only **probe**, not another converter, normal-CI requirement or semantic sidecar. The canonical open-Greek schema is untouched.

## Research → plan → RED-first → test

1. RED-first unit tests request a deliberately absent `opengreek_tf.engine_probe` API and build a real three-level native Greek Text-Fabric F/E graph from allowed audited source fields, including accents, two consecutive spaces, line endings, repeated array members, a boolean false, and empty text. Verify that the native graph's probe hash changes when the Greek text changes. The first test-only CI was stopped by an import-order Ruff finding, so it did **not** reach pytest, despite the implementation being genuinely absent at that test commit. This is not claimed as an observed semantic RED run.
2. Implement a minimal read-only CLI `python -m opengreek_tf.engine_probe --engine tf|cf --corpus <generated-native-TF>`. Each run imports exactly one engine and reads **all discovered native node/edge features**, every integer node in original TF order, `E.has_fact` relations, `E.oslots` for non-slots, `T.text(..., fmt="text-orig-full")` and `T.sectionFromNode`. It canonicalizes these into the same SHA-256 signature. It does not use stringified Python objects, flatten nested facts, discard empty Unicode, or make up any Greek morphological structure.
3. In a separate **opt-in Python 3.13** workflow, sparse-fetch the unchanged four genuinely pinned source files from `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`. Materialize native TF with existing Python/Text-Fabric, independently validate all 232 original JSONL source records, **1,642 source fact nodes** and **131,738 text codepoints** via the existing trusted validator.
4. Launch three isolated processes: TF reference load, CF first compile/load, CF subsequent fresh-process warm-cache load. Require equality of canonical F/E/T hash, every feature name, native node/slot/source count, source passage-text codepoints. Report elapsed engine load time, **peak RSS of the entire probe process (including feature scan)** and engine cache bytes on disk. Failed import or mismatch fails the experimental CI job.
5. Do **not** treat a green load compatibility proof as a replacement for TF conversion, the independently validating JSONL reader, the TF advanced app or full-corpus release gate. Later experiments must cover genuine metadata-only author/work registers, mixed witnesses and paratext, the stratified 31,977-passage sample, and large-corpus query throughput.

## Initial genuine pinned CI measurements (Linux, Python 3.13)

First successful full experiment: [Actions #39333758894](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39333758894); reference Text-Fabric 13.1.1 versus context-fabric 0.6.0rc1. All three runs agreed on **45,116 nodes (43,242 atoms, 232 passages, 1,642 sourceFact)**, every original native node/edge feature, and SHA-256 `e2432ccd1d932af1759fcc69de6a61d2659af870016434c156b9fe16a7f75cf9`.

| Independent process | Engine load time | Peak total probe RSS | On-corpus engine cache size |
| --- | ---: | ---: | ---: |
| Text-Fabric reference | 32.4 ms | 42.4 MiB | 647,020 B |
| Rust CF, first compile + load | 323.3 ms | 82.5 MiB | 3,709,830 B |
| Rust CF, precompiled cache, fresh process | 0.67 ms | 38.6 MiB | 3,709,830 B |

A repeat on head `ba1cd90...` [Actions #39333909408](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39333909408) again matched *the same entire source F/E/T signature*: TF 33.1ms, CF first compile 322.1ms, CF warm 0.68ms; whole-probe RSS 42.3 / 86.9 / 38.7 MiB respectively.

**Interpretation / limitations:** These are only two single-GitHub-run observations on a small selected source. TF's preexisting `.tf` cache was created by the mandatory writer/validator step, while the initial CF process had to compile its cache. These stages are **not** apples-to-apples cold-load or warm-load comparisons; measured times include only Fabric `explore` + `load` (no Python process startup, pip install, Git checkout or full feature-scan time). Peak process RSS includes the hash scan and runtime overhead; it is **not** delta memory attributable to loading. CF's warm-load speed is attractive when a compiled cache persists, but it needs extra disk and Python 3.13, and full-corpus scaling/feature-query performance remain unknown.

**Recommendation:** keep this optional regression as an interoperability smoke test. Do not switch ordinary CI or canonical TF reader/writer to CF rc1 until complete-source workloads and a stable version demonstrate that it is faster for the *actual* OpenGreek tasks.

## Explicit nonclaims

This experiment does not prove complete `1,970,947`-passage corpus loading, text token/lemma queries, section ontology completion, source-registry unanchored identity, secondary/paratext preservation by CF, agent MCP server ergonomics, or compiled-cache reuse in ephemeral CI. All those remain separate existing issues. No corpus/TF files are committed.
