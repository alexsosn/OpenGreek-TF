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

**No release gate automatically closes.** #3 ontology and query semantics require a substantive decision; #75/#6/#8/#9/#13/#14 still require a measured **complete** 2,293,990-record source-to-native-Fabric build, source and typed F/E global integrity, native disk/runtime/memory, author/work/citation navigation and researcher-facing browser smoke tests.
