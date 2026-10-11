# #52 — Independent process isolation for pinned TF scale validation

## Research / observed root cause

OpenGreek-TF's [merged PR #53](https://github.com/alexsosn/OpenGreek-TF/pull/53) retains the complete source-native Text-Fabric conservation guarantees, while reducing transient FactGraph retention. But [full pinned Actions #38139140044](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38139140044) still peaked at ~1,243.8 MiB in one Python process even though the writer's after-validation *live* RSS snapshot was ~856.7 MiB.

Direct investigation of `.github/workflows/full-registry-native-scale.yml` reveals the CI process: (i) parse full upstream standard JSON for ground truth; (ii) `materialize_registry` parses *another* complete typed registry, builds native TF and independently `Fabric.load`-verifies; (iii) load and restore native TF a second time; (iv) `Fabric.load` the whole feature inventory *yet again* to check edge counts/otype. Thus the measured 1.24 GiB **does not isolate** the intrinsic composer from the test harness's extra memory. It is irresponsible to claim true production bounded-memory behavior before factoring these costs.

## Plan and test gates

1. **RED-first:** subprocess integration tests against a real schema-complete 2-author/1-work registry source, preserving ordered nested edition facts, nulls and Unicode. Assert child PID differs from parent, report measured child peak RSS and lifecycle snapshots, output native TF equals independent parent `read_native_records` and its canonical feature SHA-256. Repeat across separate child runs to prove semantic stability. Assert bad late source and existing output fail without partial overwrite; paths with spaces are supported.
2. Implement one small **source-exact CLI child adapter**, not a new TF serializer. Child imports the merged strict `registry_materializer.materialize_registry`, outputs one JSON report with stats, wall time, `resource.ru_maxrss` and `/proc/self/status` live phase RSS; reports canonical TF feature manifest from the *same* native output. Parent `run_isolated_registry_build` starts the module through `sys.executable, "-m"` using explicit argument array (no shell/interpolated user input), requires successful exit and valid report.
3. Modify the pinned 14,390-record GitHub Actions workflow to run the child builder **before** independently reconstructing the entire native graph in the parent verifier, retaining every existing source-grounded, type-sensitive/order-sensitive assertion, TF loaded edge/node census, 12,735 explicit nulls, and pinned canonical SHA `6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e`. Log **child builder maxrss** and **independent verifier maxrss** separately; do not call the lower maximum the writer's memory limit, since the original peak included a mixed process.
4. Require original pinned **mixed Greek passage plus metadata** workflow, plus full mypy/Ruff/pytest and exact-head independent skeptical code/data review; address findings before merge. Include actual full-registry output size and count constraints. Keep #52, #13, #6 and #9 OPEN for primary corpus scale, true bounded-memory streaming and production validation.

## Interpretation boundary

A smaller maximum of isolated child/parent process peaks demonstrates that the **validation orchestration** need not retain all phases simultaneously. It does **not** prove a Text-Fabric streaming writer, lower intrinsic native TF F/E assembly peak, or the capability to materialize 65 million Greek tokens in bounded memory. All output data remain native TF; no lossy JSON metadata sidecar is introduced. The JSON process report contains only metrics, not corpus content.


## First full pinned result (branch CI)

[Actions #38143300486](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38143300486) succeeded on complete real `data/source_registry.json`, independently confirming **14,390** metadata records/atoms, **252,276** source facts and edges, **12,735** explicit nulls, **18 TF files / 14,454,531 bytes**, and exactly the prior canonical SHA-256 `6dec2456986793999f8f1fe98408d00a8c4c73c98e6c066b6c8f24e0aa57565e`.

The **child build process** peaked at **839.53 MiB** resident memory (19.566 seconds inside child; ~19.971 seconds wall including process startup). Its live RSS by phases was ~92.7 MiB after typed input load, ~110.1 MiB after source preflight, ~196.9 MiB after native TF walk, and ~832.7 MiB after independently loaded writer validation. The **parent source-verification process** peaked at **1,039.9 MiB** (separate reloaded TF reconstruction ~3.854 seconds). The old combined process observed ~1,243.8 MiB [Actions #38139140044](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38139140044).

These are single-run observations on GitHub-hosted Linux runners. Compared with the previous combined process, the maximum of the two new peaks is about **204 MiB lower (~16.4%)**, but this is a reduction of CI **orchestration** live process footprint, not proof that the underlying writer has become streaming or that larger textual corpora fit in memory. Repeated runs and host differences may change the exact figures.

## Additional skeptical test audit

During RED-first CI, tests for the preexisting CR-codepoint Text-Fabric experiment failed intermittently when the UTC hour in `@dateWritten` contained `13`: their corruption fixture used an unrestricted `content.replace("13", ...)` and could change timestamp metadata instead of the intended *integer codepoint feature row*. PR #54 fixes the test to partition the TF header from body, then mutate an actual tab-prefixed codepoint value. This preserves the intended fail-closed unit test and prevents time-of-day false negatives. It does not change the CR-codepoint serializer's semantics or resolve the broader CR compatibility issue #29.
