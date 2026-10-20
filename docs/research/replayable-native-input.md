# #75 — Replay original Greek source rows, preserve native TF semantics

## Research and design

The original `materialize_texts` command built `tuple(iter_native_texts(...))` and retained *all* immutable nested source records throughout validation and conversion. This duplicated a large subset of the source in RAM next to Text-Fabric's own `CV.walk` F/E maps and the separately reloaded postwrite source verifier.

The new `write_native_record_factory(factory, output)` accepts a **replayable source-iterator factory**, not a live single-use iterator. It runs three independent passes, without retaining a collection of input records:

1. **Preflight**: parse every original source row, check physical occurrence uniqueness, strict types, textual source field/layout agreement, nested recursive typed FactGraphs, carriage returns, optional TF feature inventory and final malformed rows. Summarize counts and a SHA-256 over the actual typed source graph digest, physical identity, row kind and passage-presence indicator. **No destination exists before preflight succeeds.**
2. **Actual native TF writing**: replay the same source with the existing TF13 `CV.walk`, rebuilding one typed source graph per record and adding exactly the same passage/sourceFact/atom F/E and Greek text runs. The director rechecks passage text against the typed source field and must match the preflight source/order signature before TF is saved. Source mutation is not treated as successful conversion.
3. **Writer postwrite conservation**: independently reload genuine `tf.fabric.Fabric` F/E and compare all reconstructed source records with a newly parsed third pass, preserving exact nested field order, scalar **types** (`False` vs `0`), source file/ordinal, record kind and Greek text. Exhaust the loaded generator so its global orphan/feature/edge integrity checks run before returning success. The installed CLI separately decodes original stock JSONL a fourth time, checks every original record against a fresh loaded TF graph, and verifies pinned clean Git source again before emitting a success summary.

The existing `write_native_records(tuple, destination, ...)` API is unchanged, implemented by the new replayable writer over `lambda: iter(records)`. Its `NativeStats`, callback phases, F/E schema, supported mixed source kinds and deterministic native TF content remain unchanged. No new serialization format, spool files, invented word nodes, lossy Greek normalization or research sidecars were introduced.

**Limits:** `CV.walk` itself still retains node and edge feature maps; native TF `Fabric.load` retains loaded features. This is **not an out-of-core TF serializer**, does not prove that `convert-texts --all` completes, and does not eliminate the full author/work and section modeling release gates.

## RED-first tests and adversarial review

- **Test-only RED**: commit `acfe596`, [CI #39461547490](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39461547490) observed strict-mypy missing writer-factory API before implementation.
- A genuine TF test sends 48 original-like records from newly allocated weakref-observed Python objects; no more than two source row objects coexist and the factory is traversed three times. Another produces a malformed final row and verifies fail-before-output.
- A replay mutation test changes all typed Greek text between preflight and TF writing and must fail. Independent adversarial review identified a second, subtler **layout-only text mutation** problem: `NativeRecord.text` (which controls text slots) can change while the nested source `fields['text']` remains identical. Regression tests for changed Greek layout and passage-to-metadata drift were added test-first, then the CV director was fixed to recheck the field/layout equality and passage-presence signature. A transient GitHub rerun of the added test-only commit was canceled by workflow concurrency, so **no observed RED claim is made for that particular regression**. The final implementation must pass exact-head normal and pinned tests.
- Original F/E builder and independent stock source verifier remain distinct. The installed mixed-source CLI E2E checks real primary, 47 witnesses, and 113 paratext, with no invented semantic alignment or XML blob.

## Measured pinned real-source benchmark

The immutable upstream corpus pin is `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f`. Compared using the *same exact canonical native TF and original-source hashes* from genuine GitHub Actions Linux runs, with distinct runners and noncontrolled time/memory observations:

| Measurement | Prior all-input-tuple writer (#74) | Replayable input writer (#76, preliminary) |
| --- | ---: | ---: |
| 32,137 original mixed source records, builder peak RSS | 1,170.54 MiB | 1,182.04 MiB |
| 82,024 original mixed source records, builder peak RSS | 6,316.65 MiB | **6,245.79 MiB** |
| 82,024-row builder+internal conservation wall time | 233.928 s | **198.957 s** |
| 82,024-row separate independent stock JSONL/Fabric verifier peak RSS | 4,915.69 MiB | 4,915.39 MiB |
| 82,024-row native TF bytes | 215,686,572 | 215,686,572 |

The genuine **82,024** source rows are **81,864 original primary passages from 307 complete original JSONL files**, 47 secondary witnesses and 113 paratext. Every original **625,821** typed source fact and **24,817,584** source text Unicode codepoints is independently conserved.

Original-source SHA-256: `a644858e5ada9907b8e2c8fe8f28aa574ce6c9f0b9b144667c3c0548600ca806`.

Canonical TF feature SHA-256: `0b6550e112476ab5a9bc2699abb3c2df68df94c38344f9223e7e4961864f6513`.

The replayable-input benchmark in [Actions #39462658510](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39462658510) passed independent original-source/Fabric conservation and preserved *both* exact hashes. The 32,137-row original mixed run also preserved native TF hash `3457bab1a10966ea8682b7794739edb66f04c41dcbac057792b6e9dec023cc35`.

**Interpretation:** at 82k rows the original-source tuple removal reduced observed builder peak by about **70.86 MiB (1.1%)**. The difference in wall time cannot be assigned causally from one runner per condition. At the smaller 32k rung, no improvement in peak RSS was observed. The huge memory cost remains the graph's many native slots, facts, TF feature dictionaries and loaded native data, not just the Python input tuple.

## P0 architectural next steps

Official [TF walker documentation](https://annotation.github.io/text-fabric/tf/convert/walker.html) and [FabricCore feature saving](https://annotation.github.io/text-fabric/tf/core/fabric.html) describe dictionary-backed conversion/saving, not streaming native F/E from source. Official [TF volumes documentation](https://annotation.github.io/text-fabric/tf/about/volumes.html) explicitly states extracting volumes currently **requires loading the full original work first**; merely splitting input into volumes does not solve initial corpus creation.

Next bounded research under #75: measure actual `F.otype.maxSlot` and source/slot/fact counts at the 82k original rung; independently evaluate a single-TF-native **out-of-core serializer** against reference TF13 output and real original JSONL, or a **separately reviewed** alternative text-slot granularity that preserves original source content while openly changing the existing run-level atom contract. Neither is approved by this PR; avoid silent schema drift, dropped text nodes/facts, arbitrary untracked shards or false all-corpus completion claims.

The **2,293,990**-row original text-family build and final ontology/browser/release acceptance remain unverified. Keep issues #75/#71/#13/#6/#9/#14 open until they are separately proven.
