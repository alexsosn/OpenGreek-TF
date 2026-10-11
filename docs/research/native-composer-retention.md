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
