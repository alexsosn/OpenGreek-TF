# Opt-in compact passage-slot Text-Fabric experiment (#78)

## Research and explicit ontology trade-off

The default native OpenGreek-TF writer uses one genuine `atom` slot for each **maximal Unicode whitespace/non-whitespace run** in a Greek primary passage, plus an authentic source-row anchor slot. It creates no `word` node and makes no lexical analysis or linguistic token assertions. In the genuine pinned 82,024-record mixed-source benchmark, 24,817,584 original text codepoints and 625,821 native `sourceFact` nodes generated **6.2+ GiB** peak conversion RSS. The reference Text-Fabric 13 walker builds `oslots`, node/edge feature dictionaries and canonical node remapping in memory; the number of source text slots is an important but not yet isolated memory factor.

Text-Fabric's reference `tf.core.helpers.tfFromValue` encodes backslashes, tabs and newlines in textual node features; a **single slot with `form` equal to an entire original Greek passage** is representable in native TF. However, it **changes node/slot ontology and query granularity**. One passage slot cannot act as separate word-like or whitespace-run addresses. Run-level annotations, slot-level concordance and within-passage TF navigation would be unavailable even though every original source string, ordered typed fact, feature and original identity remain inspectable. Neither option invents lexically analyzed words.

### User-facing experimental option

```bash
# Existing run-level graph, unchanged:
opengreek-tf convert-texts upstream/open-greek-corpus \
  --file data/corpus/abydenus.fragmenta.jsonl \
  --output generated/abydenus-runs

# Explicitly different TF slot layout:
opengreek-tf convert-texts upstream/open-greek-corpus \
  --file data/corpus/abydenus.fragmenta.jsonl \
  --file data/corpus_secondary/abydenus.fragmenta.jsonl \
  --file data/paratext/edition_apparatus.jsonl \
  --slot-layout passage \
  --output generated/abydenus-passages
```

`convert-texts --all --slot-layout passage` is a supported selection *interface*, **not a claim that the complete 2,293,990 original text-family records have been converted**. A full-CV graph is still memory-resident. This is an experimental source-carriage mode, not a finalized scholarly ontology or substitute for true lexical tokenization.

### Native F/E source contract

The default `runs` layout has **no new feature or `otext` metadata** and must preserve the historical exact canonical SHA-256 of all pinned reference datasets. The opt-in `passage` layout writes `@slotLayout=passage` in native `otext.tf`; no separate data files, application-only JSON metadata, or hidden feature conventions are introduced.

For each *nonempty* primary source passage, the compact graph creates one `atom_kind=text` slot with `form` containing the **complete exact** UTF-8/Unicode original Greek source passage, followed by the same physical `source-row` anchor as the default; empty primary passages retain only the genuine source-row anchor and empty `form`. Secondary witnesses and editorial paratext remain sourceFact-attached `metadataRecord` nodes without guessed lexical alignment. All source-root nodes, ordered nested typed sourceFact nodes, numeric/boolean/null distinctions, `has_fact` and `oslots` F/E edges, source_seq and physical source identity remain present and independently checkable.

The independently loaded `tf.fabric.Fabric` reader must reject any native `slotLayout` other than missing legacy default or exact `passage`, as well as an incorrect number/order/value of text slots for the declared mode, forged otext formats, unexpected node/edge feature surfaces, orphaned facts or original Unicode changes. Default run-level TF output remains byte-for-byte unchanged.

### TDD, pinned source gates and release boundary

The test-only commit preceded the implementation, requiring opt-in writer/API/CLI, literal original Unicode—including punctuation, tabs, newlines and backslash—genuine sourceFact restoration, empty passages, mixed unaligned witnesses, canonical default hashes and adversarial forged `slotLayout` changes. The implementation uses the existing Text-Fabric 13 CV composer and independent stock-JSONL-to-loaded-native-Fabric verifier, not a new serialization engine. [Pull request #79](https://github.com/alexsosn/OpenGreek-TF/pull/79) carries tests, pinned E2E and logically independent adversarial review.

The real pinned benchmark uses original source `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`. Compare the *same 82,024 original physical rows* (81,864 original primary passages from 307 complete JSONL files; 47 secondary and 113 paratext) in the original `runs` layout vs compact `passage`: per-mode native `F.otype` text-slot and sourceFact counts, independent original stock UTF-8 JSONL vs genuine Fabric F/E conservation, exact source hash, canonical native TF hash, output disk, elapsed time, and isolated builder+verifier RSS. Existing run-layout reference: **6,238.41 MiB** builder peak at 82,024 rows, 215,686,572 TF bytes, canonical `0b6550e112476ab5a9bc2699abb3c2df68df94c38344f9223e7e4961864f6513`; original-source digest `a644858e5ada9907b8e2c8fe8f28aa574ce6c9f0b9b144667c3c0548600ca806`. Different runs are not controlled CPU benchmarks; memory improvements must be measured and reported, not guessed.

## Measured 82,024-row pinned result and next whole-file rung

The existing compact-mode real-source GitHub Actions [run 42796361626](https://github.com/alexsosn/OpenGreek-TF/actions/runs/42796361626) **passed** for 81,864 complete original primary passages (307 original primary JSONL files), 47 original secondary-witness records and 113 original paratext records. It independently compared stock UTF-8 JSONL with actual loaded native Fabric F/E, retaining **625,821** typed source facts and **24,817,584** original source Unicode codepoints. Its exact original-source digest remained `a644858e5ada9907b8e2c8fe8f28aa574ce6c9f0b9b144667c3c0548600ca806`.

| Actual isolated process metric, original 82,024-row source | Previous run-slot mode | Opt-in compact passage-slot mode |
| --- | ---: | ---: |
| Native TF bytes | 215,686,572 | **165,435,404** |
| Builder peak RSS (MiB) | 6,238.41 | **2,281.46** |
| Independently checked verifier peak RSS (MiB) | ~4,915.39 | **2,160.28** |
| Canonical native TF SHA-256 | `0b6550e112476ab5a9bc2699abb3c2df68df94c38344f9223e7e4961864f6513` | `c2b51974b6ca3d16f0d1422c1b8f080827c8024f3817d324c2f8b836b9ecb13e` |

That is an observed ~63% reduction in **builder** high-water RSS and ~23% smaller native feature files for this one original-source rung. Source facts/Unicode and original-source digest agree, but the native graph hash necessarily differs because TF slot addresses and query semantics differ. Distinct GitHub runner invocations are **not** controlled speed comparisons. The compact builder took 54.247 s on its own run including internal validation. No whole-corpus peak-RSS extrapolation is warranted because row lengths, nested fact counts and source family distributions vary.

### Genuine larger-rung result: 131,981 original records

[PR #87](https://github.com/alexsosn/OpenGreek-TF/pull/87)'s extended whole-file rung passed the unchanged public CLI, independent original stock JSONL/loaded TF Fabric F/E comparison and all loaded source-fact, text, identity and slot-count checks in [Actions run 44318388997](https://github.com/alexsosn/OpenGreek-TF/actions/runs/44318388997). The selected data are **382 entire primary JSONL files / 131,821 real primary passages**, plus the same 47 secondary witnesses and 113 paratext records, for **131,981 records / 385 original files**. The independently conserved output carried **1,003,224 native source facts**, **30,434,149 original Unicode codepoints** and exactly **263,802 native atom slots** (131,821 primary text slots + one actual source-row slot per original row).

| Isolated measured property | Extended compact result |
| --- | ---: |
| Builder peak RSS | **3,615.16 MiB** |
| Independently reloaded verifier process peak RSS | **3,427.44 MiB** |
| Builder wall time, including writer's internal validation | **130.425 s** |
| Separate stock JSONL/Fabric verification wall time | **22.123 s** |
| Native TF feature bytes | **221,482,878** |
| Original source SHA-256 | `06119f5e48700aeb44b2f06edc7f3dcf4149e06277bd333947e4c0c0d808f21a` |
| Canonical native TF SHA-256 | `6f3aac47b8606dacb03561a723f66f4249de95b06de81fe61e8a3397320d3dec` |

The existing 82,024-row benchmark was rerun in parallel and passed again, with identical native and original hashes and a **2,281.36 MiB** builder peak. Both source/TF hashes on both rungs are now regression-gated. The extension covers only **5.75% of the complete 2,293,990 textual original records**; selected row lengths and source fact density differ substantially between rungs. The result improves measured feasible sample coverage but does **not** establish the full graph's peak memory, allow a default word/run query replacement, or close #75.

**No release gate automatically closes.** #3 ontology and query semantics require a substantive decision; #75/#6/#8/#9/#13/#14 still require a measured **complete** 2,293,990-record source-to-native-Fabric build, source and typed F/E global integrity, native disk/runtime/memory, author/work/citation navigation and researcher-facing browser smoke tests.
