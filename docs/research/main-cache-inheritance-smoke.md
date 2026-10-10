# #34 — cross-PR default-branch Git-object cache inheritance

## Research: exact observed state, 2026-10-10

- PR #39 (head `e799fcabca36420be907558508cb8656de03142a`) merged as `53c9bfc2522974dea31ece92ac7239cebe80fd80`.
- Pinned control-census on protected `main` [run 38080617792](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38080617792) finished green and **saved** the immutable Git-object cache key `opengreek-gitobjects-v1-Linux-338aa27310b3cfe2588a993b4d113b503597d70f-c7d7dda563babaa43268aa6d`.
- PR #39 warm tests proved same-PR cache reuse, including a second workflow, but not inheritance by a **different PR** from the protected default branch. This is the explicit remaining gate on issue #34.
- GitHub dependency-cache permissions/scopes: PR-originated archives are scoped to the corresponding merge ref; caches created on the default branch are eligible for subsequent PRs on that base. Testing actual restore through a fresh PR is required. The cache is immutable upstream **Git objects only**, not worktree/config/index/credentials. Never save a cache from this smoke workflow.

## Plan and acceptance criteria

1. RED-first static policy test: a dedicated workflow `.github/workflows/main-cache-inheritance-smoke.yml` exists, runs on PR changes to itself or its policy test, and uses the same `opengreek_tf.ci_source_cache prepare upstream` key generation as the protected seeder. It must use `actions/cache/restore@v4` **without any save step**, assert an exact-key hit, then run `ci_source_cache checkout` with the real exact release checkout identity and inventory verification. `GITHUB_TOKEN` is never used for privileged Git operations.
2. A separate PR (not PR #39), with no local cache archive, runs the workflow. On a trusted `main` cache, `steps.objects.outputs.cache-hit == 'true'` must be observed in real runner logs. A miss must **fail immediately** with an explanatory error rather than falling back to a 3-minute fetch; this smoke is specifically a test of cross-PR cache visibility, not the general production fallback path.
3. Verify full immutable SHA and canonical repository through `verify_source`, source `corpus_release.json`, `git fsck`, worktree status and 3909/533/5 filename counts through the same production helper. Inspect an actual Greek JSONL sample whose complete bytes come from restored Git objects.
4. Preserve standard exact-head Ruff, mypy, pytest; run independent adversarial review targeting scope, untrusted PR behavior, provenance, and GitHub Actions YAML. Merge only green and exact reviewed head.
5. After verified success, close issue #34 with links to the protected `main` save and distinct PR hit. Future cache quota/eviction checks belong to #13, not an assertion of infinite persistence.

## Scope and caution

This workflow runs only when its own YAML/policy test changes or when dispatched; it must not become an unconditional full corpus check on every code PR. It holds no secrets and never restores worktree or Git config. Cache eviction may cause this **diagnostic** smoke to fail; normal consumers retain safe fetch fallback. Do not confuse the 303 MB cache network restore with total absence of traffic or quote prior 170-second reduction as whole-CI speedup.
