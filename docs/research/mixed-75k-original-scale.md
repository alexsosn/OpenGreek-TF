# #13 — Whole-file mixed original Greek scale rung (memory reality check)

## Research question

Can OpenGreek-TF's existing *single native Text-Fabric graph* writer, without introducing any semantic sidecars, reproduce more than 32,137 real original Greek / secondary / paratext rows on GitHub Actions while preserving every original source fact? How does memory consumption change when we select a larger, different textual workload?

The upstream release is **immutable**: `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`. The existing verified complete source inventory comprises **3,909 original primary JSONL, 533 secondary, 5 paratext files**, with 1,970,947 / 307,085 / 15,958 original rows respectively, including the physically empty Democritus witness. Previous `convert-texts` smoke proved 166-row and 32,137-row genuine mixed single graphs. A complete **2,293,990**-row native graph has *not* been built.

## Test-first design

The exact feature under test is **original file completeness**, not a conjectured edition/work identity. `select_whole_primary_rung(root, minimum_rows, maximum_rows)` deterministically takes an ascending path-ordered prefix of whole physical primary JSONL files, rejecting invalid target bounds, symlinks, hardlink aliases, zero-row selected originals, absent corpus, insufficient original rows, or a file that causes the selection to overshoot the budget. No original file is cropped or transformed. The pinned real-source benchmark first checks the **complete** source file inventory against Git and only then selects a bounded prefix. It appends the known full 47-row Abydenus secondary file and both genuine paratext files (56 + 57 rows).

The new tests were committed **before** the selection helper. Test-only [Actions #39448413296](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39448413296) observed a **RED missing-selection-API mypy error**; there was also an unused-ignore diagnostic caused by the same missing import. Final implementation uses the existing public `opengreek-tf convert-texts --file ... --output ...` command in a new subprocess. It makes **no changes to Text-Fabric's CV writer, graph schema, feature values, node identities, or independent stock JSONL/Fabric validator**.

## Pinned real original-source result

[Actions #39448797786](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39448797786) succeeded on an Ubuntu Actions worker (Python 3.11, original Text-Fabric engine). The benchmark selected **307 entire original primary source files** with **81,864 original primary passages**, and appended **47 secondary** + **113 paratext** original source rows: **82,024 total**.

| Reproducible measurement | Actual source-conserved result |
| --- | ---: |
| Selected original primary source files | 307 |
| Original primary/secondary/paratext rows | 81,864 / 47 / 113 |
| Total original source records | **82,024** |
| Ordered typed source-fact nodes | **625,821** |
| Original Unicode text codepoints | **24,817,584** |
| Serialized native Text-Fabric F/E | **215,686,572 bytes** |
| Isolated installed-CLI builder peak RSS | **6,312.98 MiB** |
| Separate independent stock JSONL/Fabric verifier peak RSS | **4,907.62 MiB** |
| Installed-CLI build + in-process conservation | **237.094 seconds** |
| Separately reloading/checking original JSONL against native F/E | **31.737 seconds** |

Deterministic original file selection SHA-256: `cdd890b0603891af144f6ef4a6eb3a14da8a1e9438e93443c605d1a4f1c83e28`.

Independently derived stock original-source SHA-256: `a644858e5ada9907b8e2c8fe8f28aa574ce6c9f0b9b144667c3c0548600ca806`.

Canonical native TF SHA-256: `0b6550e112476ab5a9bc2699abb3c2df68df94c38344f9223e7e4961864f6513`.

The separately loaded, writer-independent Text-Fabric reader verified **every** original row, type, source filename/ordinal, text codepoint, original field member order, nested typed fact and native owner/edge mapping. It rejected any fabricated word-level interpretation and checked the exact unchanged pinned Git revision afterward. A completed native TF file checksum and a final explicit `not_a_full_corpus_build=true` distinguish this proof from a release.

## Interpretation and next required architecture

| Genuine mixed original-text workload | 32,137-record earlier rung (#73) | 82,024-record new rung (#74) |
| --- | ---: | ---: |
| Original text codepoints | 2,402,648 | 24,817,584 |
| Source-fact nodes | 239,274 | 625,821 |
| Native TF bytes | 32,078,599 | 215,686,572 |
| Isolated builder process peak RSS | 1,170.54 MiB | **6,312.98 MiB** |
| Independent validator peak RSS | ~1,063 MiB | **4,907.62 MiB** |

The source samples differ in lengths and feature distributions. The new sample has only ~2.55 times as many rows, yet more than **10 times** the original text codepoints. Therefore **do not linearly extrapolate bytes or memory per row**. It is an alphabetical source prefix, **not a statistically representative corpus random sample**, and its whole-file selection alone does not prove all files of a scholarly edition/work have been selected.

Text-Fabric `CV.walk` retains Python dictionaries of node/edge feature mappings before serialization, and the current OpenGreek converter also stores all input `NativeRecord` items and loads the generated graph during validation. The 6.3 GiB builder peak at **82,024 / 2,293,990 ≈ 3.6% of original text-family rows** is already too close to the memory available on common hosted runners to justify a blind all-in-one `--all` attempt. The next task under #13/#71 must evaluate a **supported memory-bounded/native TF serialization strategy** or a genuinely sufficiently provisioned full build, retaining independently verifiable all-source semantic equality. Do not delete original facts, merge witnesses into primary words, silently normalize Greek text, or invent missing work/locus alignments to meet memory constraints.

**Unfinished release gates:** one successful whole 2,293,990-row original-text F/E build, exact original source-to-Fabric validator, full author/work/crosswalk ontology (beyond text-family records), standard TF browser E2E and release performance report. #6, #8, #9, #13, #14, #20, #71 remain open.
