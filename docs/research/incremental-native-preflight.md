# #13 — Incremental source-FactGraph preflight: bounded graph retention, measured limits

## Evidence and plan

The generic native composer already receives a tuple of typed `NativeRecord` items, validates them before output, emits real F/E using `tf.convert.walker.CV`, and independently reloads and reconstructs **the entire** graph using the standard `tf.fabric.Fabric`. Prior writer `_preflight()` also built and returned a **tuple of every record's source `FactGraph`** and retained it to discover only `fact_key`, `fact_text` and `fact_int` feature presence and to sum fact counts. Previous PR #64 released that graph tuple before `CV.walk` but still allocated every graph together during the earlier preflight stage.

This bounded change retains fail-before-output validation (including a malformed *last* record), physical identity and duplicate checks, typed recursive fields, rejected CR source bytes, optional feature metadata and deterministic source order, but folds per-record fact counts and feature presence into a small summary. Each temporary `FactGraph` is released before validating the next record. **There is no new writer, intermediate graph format, identity scheme, sidecar or output file.**

## RED-first and independent source checks

- Test-only PR commit `533cf53` proved RED in [CI #39336953250](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39336953250): **32 simultaneously retained source-FactGraphs**, where <=2 were permitted. A second new test initially contained a malformed fixture with a literal `\\r`, subsequently corrected to an actual U+000D *before production implementation*. The final-memory suite instruments real source-FactGraph construction with weak references during actual `CV.walk` and independent Fabric reload; it does not replace conversion/validation with mocks. Existing memory gates were updated to instrument graph creation rather than a now-absent full-graph-return private contract.
- Native `write_native_records`, public `validate_native_records`, output `Fabric`, source-feature placement and edge checks, `NativeStats`, and phase names remain unchanged. The full suite includes adversarial forged metadata/fact/edge/CR and mixed-source tests.
- **Independent pinned Greek evidence:** unchanged `open-greek/open-greek-corpus@338aa27310b3cfe2588a993b4d113b503597d70f` epic/prose/lexicon sources, exactly **31,977 passages / 237,664 facts / 749,590 total source+layout slots / 2,326,212 original Greek codepoints**, validated by an independently implemented stock-JSON/loaded-Fabric source reader. Native output **31,811,763 bytes** and canonical SHA-256 `fa9e5eddcb2a46e0ccc1c8437cace0460514b7c2b313ccb33c1a9418379b82c1` unchanged.
- **Independent pinned registry evidence:** complete **3,315 authors and 11,075 works / 252,276 typed facts**, preserving 12,735 source JSON nulls and every source occurrence, loaded TF graph, and canonical SHA-256 `6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e` unchanged.

## Actual isolated Linux GitHub Actions measurements

Baseline is [PR #64 exact-head pinned stratified CI #38240409829](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38240409829) and [full-registry CI #38240410027](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38240410027). New implementation is [stratified CI #39337694935](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39337694935) and [full-registry CI #39337694910](https://github.com/alexsosn/OpenGreek-TF/actions/runs/39337694910). Runners are not identical controlled environments, so small RSS/time differences are observational only.

| Measurement | Prior #64 | Incremental preflight | Interpretation |
| --- | ---: | ---: | --- |
| Full registry **live RSS at preflight completion**, MiB | 110.0 | **92.8** | ~17.2 MiB fewer retained allocations at this phase |
| Full registry **builder peak** RSS, MiB | 838.56 | 839.09 | **No** significant peak improvement |
| Full registry builder+own-validation, seconds | 19.96 | 14.27 | Variable CI; not a controlled throughput speedup |
| Original Greek **builder peak** RSS, MiB | 977.85 | 977.96 | **No** significant peak improvement |
| Original Greek builder+own-validation, seconds | 31.96 | 32.19 | No improvement |

The registry builder actually reaches its highest memory at **`load-validated`**, not preflight. This remains the larger problem. CV's node/edge assembly and the independently loaded Text-Fabric reader are not streamable through this incremental preflight change; the primary source adapter also retains all selected `NativeRecord` instances. The actual 31,977-row run reaches **~978 MiB**, so extrapolating to 1,970,947 passages is unsafe.

## Next research target for #13/#6

Before claiming full-corpus capability, investigate actual native TF `CV.walk` serialization and postwrite `read_native_records` memory separately, and whether incremental native source reconstruction can preserve *all* existing reader corruption-detection invariants while reducing graph retention. A safe design must retain deterministic node IDs, literal Greek text, nested typed source field order, duplicate/missing/fabricated feature detection, and independent raw JSON source-to-TF verification. Measure a **larger real pinned corpus rung** and build/load high-water marks before choosing a writer architecture. Do not switch canonical validation to Rust CF rc1 based on its small-corpus read benchmark or claim a complete 65M-token converter.

The relevant full-corpus issues (#6, #9, #13, #14) remain open.
