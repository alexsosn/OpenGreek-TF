# CI source object cache rollout acceptance

Pilot: `control-census-pinned.yml` on PR #39. The cache restores only `upstream/.git/objects` into a new Git directory, then fetches pinned SHA and verifies it. A verified cache is saved only after the complete corpus census/independent raw JSONL recount and native TF checks pass; untrusted fork PR triggers cannot write the shared cache. Other identical-scope workflows must wait until the pilot proves a genuine hit and improvement.

Do not weaken any existing full-corpus or source identity assertions. Cache miss/corruption is not a semantic failure if a clean pinned fetch succeeds; save no credentials.

## Observed pilot and expanded rollout

The pilot completed a real cold and warm run on the same PR head
`b2c74dd225e7f61ea36ce9a35561d427ba1c4ec8`:
**182.958 s** acquisition+verification on miss, **12.482 s** on an exact
cache hit; both fully validated pinned Greek corpus. Approximate
93.2% acquisition-time saving, not an end-to-end job speedup.

An independent adversarial review ([PR #39 review](https://github.com/alexsosn/OpenGreek-TF/pull/39))
identified that a PR-scoped cache cannot be restored by unrelated PRs.
Acceptance therefore additionally requires a narrow protected-main
`push` seeder and two read-only shared-key consumers
(`record-census.yml`, `source-cr-census.yml`). Both consumers retain
the full parsing/census gates and independent `verify_source`; they
must never skip verification when `cache-hit` is true. Confirm each
expanded workflow on the exact final PR head before merging.
