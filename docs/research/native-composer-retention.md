# #52 — Remove duplicate native TF graph retention, profile full pinned registry

## Research (actual merged code)

PR #51 demonstrates all 14,390 registry entries and 252,276 source facts survive a native TF roundtrip exactly, yet GitHub Actions peak RSS is about **1,239–1,242 MiB** for an 8,233,353-byte registry. The writer in `src/opengreek_tf/native_composer.py` calls `_preflight(records)` once, retains the returned graphs through the function, and then calls `validate_native_records(records, output)`. That publicly useful validator **calls `_preflight(records)` again**, creating a second set of graphs while the first is still live. Separately, `all_facts = tuple(node for graph in graphs for node in graph.nodes)` creates **252,276 additional tuple references** just to inspect whether `fact_key`, `fact_text`, and `fact_int` features occur.

These are grounded, removable allocations, but the previously measured 1.24-GiB high-water mark also includes Text-Fabric's F/E assembly and loaded graph; avoiding Python duplication is not evidence of proportional peak RSS improvement. Never extrapolate to 1,970,947 primary source rows / ~65 million Greek tokens from a metadata-only build.

## TDD and implementation plan

1. **RED first:** tests instrument `_preflight` and require exactly one call during `write_native_records`, while `validate_native_records` remains independently usable. Add opt-in ordered, low-overhead `on_phase` diagnostics and prove canonical feature SHA, exact source content, and invalid-input/no-output behaviour are unchanged.
2. Scan existing `graphs` with a generator rather than allocate all flattened fact references. After successful `CV.walk`, independently call `read_native_records(output)` and compare the loaded records to the original typed input. Reuse first-pass graphs only for `NativeStats`; **do not suppress, shortcut or bypass independent Fabric reconstruction**.
3. Add an optional `on_phase` callback at validated graph, completed native-walk, and independently loaded/compared boundaries; never invoke before preflight. Propagate from the full-registry adapter only as optional keyword. Instrument phase live RSS using Linux `/proc/self/status` in the pinned job, along with process `resource.ru_maxrss` peak and all existing exact source checks.
4. Run full pinned 14,390-entry native TF CI and compare the **same canonical feature digest** `6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e`; keep source values, order, 12,735 nulls, 252,276 graph edges, nonlexical atoms, real Greek mixed test, and 354+ existing tests untouched.
5. Log actual before/after peak RSS and times. Independent skeptical review must scrutinize whether instrumentation is trustworthy, whether full TF reload occurs, and any subtle type/order/race regressions. Fix blockers, rerun exact-head checks and only then merge.

## Explicit non-goals

No streaming or bounded-memory guarantee. `on_phase` is opt-in diagnostics only and cannot capture within-phase instantaneous peaks; `ru_maxrss` remains the **whole-process peak**. The phase snapshots are live RSS at boundaries, not causal allocation attribution. Full primary corpus still unbuilt and issues #52, #13, #6 and #9 remain open.

## Real pinned measurements (do not treat as a bounded-memory claim)

Before graph-lifetime release, an independently instrumented complete pinned run [Actions #38138721552](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38138721552) succeeded with exactly the baseline canonical serialized feature hash, **1,305.5 MiB process-wide peak**, and the following **live RSS at phase boundaries**: before native build 69.4 MiB, after registry parse 146.9 MiB, after preflight 164.4 MiB, after CV.walk 138.3 MiB, after writer's loaded validation 883.1 MiB. Its phase *high-water* at the last boundary was 888.8 MiB. This is a whole-process validation run; its final peak occurs during further independently loaded source and third-party TF checks, after the writer returns.

After the code additionally released the original `FactGraph` tuple before `Fabric.load` and enforced strict nested boolean/integer equality, [Actions #38138967751](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38138967751) independently passed all **14,390 genuine registry entries**, **252,276 native F/E facts/edges**, **12,735 nulls** and the identical canonical feature hash `6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e`. Phase live RSS was 69.6, 147.1, 164.6, 138.4 and **856.8 MiB** respectively, with last phase *high-water* 863.6 MiB. The **process-wide peak was 1,243.8 MiB** (build+writer validation 19.808s; separate loaded source check 4.247s). These are not controlled repetitions on the same host or separate subprocesses. They suggest less retained memory in the writer's loaded-check phase, but there is **no proven material reduction in total peak process RSS**. Follow-up #52 still needs separate child-process and phase-isolated profiling and streaming design.

The regression test also checks object lifetime using weak references (source graph objects must be unreachable before independent `Fabric.load`); a further adversarial review found ordinary nested `FieldObject` equality conflated `False` and integer `0`. Source-to-loaded conservation now compares exact recursive types and array/object order; the *public* external validator uses the same strict check. No source facts or sections are omitted.


## #13 follow-up — release preflight FactGraphs before the CV serialization phase

The previous #52 change released the writer's full `FactGraph` tuple **after** `CV.walk` and before its independent `Fabric.load`. It did not eliminate overlap between the complete set of parsed nested facts and the memory used by Text-Fabric's `CV.walk` node/edge accumulator.

Original-source baseline from #61's pinned epic/prose/lexicon run (31,977 genuine passages; 237,664 source-fact nodes; 749,590 native atoms; 31,811,763 native TF bytes): process-isolated writer peak **1,003.31 MiB**, child build wall **18.079 s**, independent verifier peak **1,068.37 MiB**, canonical TF digest `fa9e5eddcb2a46e0ccc1c8437cace0460514b7c2b313ccb33c1a9418379b82c1`. Different runner speed and Python allocator behaviour can affect subsequent timings/RSS; only exact native source/text/fact/hash conservation is a hard acceptance invariant.

This bounded #13 experiment still invokes **full fail-closed** `_preflight(records)` before writing anything, uses its validated graph set to derive exact counts and feature presence, then releases that complete set **before entering `CV.walk`**. During CV, one record's `FactGraph` is rebuilt from the original typed source for the same native node/edge emission. Postwrite validation continues to independently load all TF features and compare exact recursive scalar types, structure, order and Greek text against the original records. Public `validate_native_records` remains unchanged. No JSON blobs, inferred lexical nodes, semantic sidecars or invented alignments.

A RED-first test instruments the *actual* Text-Fabric `CV.walk` entry and tracks preflight graph object liveness with weak references; the previous code holds those graphs at entry, while the proposed implementation must free them. Pinned original-source workflows must additionally demonstrate **identical canonical TF hashes** and all original source counts. Rebuilding source facts adds CPU work; measured total build time and peak RSS must be evaluated, not assumed better.

**Limit:** The writer still holds all original `NativeRecord` objects, and preflight itself temporarily holds all `FactGraph` objects; Text-Fabric CV/Fabric also assemble large structures. This change therefore makes no general streaming, bounded-memory or 65-million-token feasibility claim. Full-corpus optimization remains issue #13.
