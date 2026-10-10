# #34 — immutable Git-object cache for pinned CI source

Status: scoped experiment; do not claim a speedup until a real restored run is measured.

## Empirical baseline (actual GitHub Actions job logs)

Run [38068853288](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38068853288),
job 114262012534, acquired the **same immutable source** between
2026-10-10 16:44:35.856 (start of sparse Git fetch step) and 16:47:43.036
(detached checkout complete): approximately **187.2 seconds** before the
corpus scan. The complete pinned input consists of 3,909 primary, 533
secondary, and 5 paratext JSONL files, 2,293,990 physical rows, plus the
release manifest at source commit
`338aa27310b3cfe2588a993b4d113b503597d70f`.

These are elapsed wall-clock logs, **not** a measured transfer byte count.
Without the cache, this checkout is repeatedly performed across
`control-census-pinned.yml`, `record-census.yml`,
`source-cr-census.yml` and multiple source-backed PR iterations.

## Research and threat model

GitHub's [dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
documents key matching and PR cache scoping. Caches restored from the
default branch may be visible to untrusted PRs; caches must contain no
secrets. PR-triggered saves are scoped to the PR merge ref and are not
accessible to main or unrelated PRs. We must **not** use
`pull_request_target` with untrusted checkout or override low-trust
read-only cache policies.

Do **not** cache a mutable complete worktree with executable local
`.git/config`, hooks or credentials. Only cache Git's content-addressed
`.git/objects`. Build a **new** local Git repo and origin/sparse spec on
each job before restoring objects. Never cache `.git/index`, `.git/config`,
`.git/hooks`, source working files, source artefacts, test output or
credentials. The object cache key must derive from canonical repo identity,
full pinned revision, exact ordered sparse scope, operating system, and
version; never use generic prefix restore keys.

Cached files are untrusted: reject symlinks, alternates and anomalous
objects before invoking Git. An invalid cache must be discarded and the
pinned origin fetched afresh (once only); it must never silently downgrade
the pinned SHA or bypass source provenance and snapshot completeness.
After **every** checkout run `verify_source` (full HEAD, clean status,
canonical origin, manifest fields/hash) and check all audited family counts.
Run `git fsck` and independently verify tracked worktree content against
the pinned commit, not merely a mutable cached index.

## Plan and TDD gates

1. RED-first tests for a deterministic cache key: another SHA/repo/scope
   gives a different key; order of scope entries is normalized and
   duplicate/unknown patterns are rejected.
2. RED-first test that setup always creates an independent fresh Git
   worktree configuration; prior paths and symlink targets must fail closed.
3. RED-first local Git fixture: populate object cache, clone/fetch from
   local bare origin, verify genuine source file exact bytes, wrong pinned
   revision, damaged objects, symlink/alternates, missing scope and
   dirty worktree, with one bounded recovery; no network required.
4. Wire the common 3-family scope to at least one pinned CI workflow and
   then reuse exactly that key in the other matching workflows.
5. Measure miss/hit restore, Git fetch/checkout, cached pack directory
   size, post-cache provenance time, and total acquisition wall time on
   exact successive PR heads. Preserve all independent corpus scan gates.
6. Exact-head Ruff, mypy, pytest and pinned-source check; independent
   skeptical review of code, shell injection/file handling and actual
   cache results before merging.

## Bounds and follow-up

- This phase targets the **shared 3-family scope** only. The small
  source subsets and full 31-inventory semantic audit have different sparse
  contracts and cannot reuse the same key without revalidation.
- A GitHub cache is a performance hint, never source authority. On cache
  eviction or restore failure, the job may be slower but remains correct.
- Do not infer network bytes saved merely from elapsed timings. Record
  actual compressed cache size when GitHub reports it; quota/eviction and
  protected cache access remain ongoing performance concerns under #13.
