# #37 — premerge gate on immutable head, live base and required runs

Status: scoped dev-loop safety increment; does not perform GitHub merges.

## Grounded incident and reviewed APIs

The concurrent implementations of issue #33 created merged PR #35 and
superseded PR #36. Each passed expensive tests independently, but after
#35 merged, the other PR's base was stale. The existing
`dev_claim check --own-pr` allows a worker to continue its claimed issue
without checking whether (a) `main` moved, (b) required CI runs are on
the *latest exact head*, or (c) an adversarial review still applies.

The GitHub REST APIs provide `GET /pulls/{number}` with `head.sha`
and `base.sha`, `GET /branches/main` with `commit.sha`,
`GET /pulls/{number}/reviews` with `commit_id` and `state`,
and `GET /actions/runs?head_sha=...` with `workflow_runs` containing
`name`, `head_sha`, `status`, `conclusion`, `event`,
`pull_requests`, and `run_attempt`. Workflow runs are paginated and
must be filtered by *actual pull-request number*, not only by a SHA.

Sources: actual [PR #35](https://github.com/alexsosn/OpenGreek-TF/pull/35),
[PR #36](https://github.com/alexsosn/OpenGreek-TF/pull/36), and
[Actions run 38080258460](https://github.com/alexsosn/OpenGreek-TF/actions/runs/38080258460).

## Design

Expose a **read-only** `python -m opengreek_tf.dev_gate --pr N
--issue M --require-workflow CI [--require-workflow ...]`. The caller must
explicitly list all workflows relevant to this PR (e.g., CI and a
pinned census); the tool cannot infer path-sensitive workflows reliably.
Never claim that a bare green CI job proves corpus correctness.

Before returning success:
1. Load complete live GitHub issue, open PRs and claims through the
   existing `GithubAPI.snapshot` and `assess` (with `--token` and
   actor verification); this blocks another implementing PR or lease.
2. Fetch PR and target base branch **live**; require open, non-draft,
   correct issue reference, same base owner/repo, and exact
   `pull.base.sha == branch.commit.sha` with no force/stale bypass.
3. For each named required workflow, require one successful **completed**
   `pull_request` workflow with exact PR number + current head SHA.
   Any queued/in-progress rerun or failed newer attempt for the same
   workflow blocks: sort by latest run ID/attempt as available.
   Reject malformed/incomplete pagination instead of guessing.
4. Require at least one meaningful, non-empty `COMMENTED` or
   `APPROVED` GitHub review on exactly the PR head. A latest-head
   `CHANGES_REQUESTED` review cannot be overruled by an older approval.
   This proves review provenance *only*, not the content's independence.
5. Take one final PR/base re-read to detect changes during evaluation.
   Because independent REST reads aren't atomic, CLI must state a
   merge immediately afterward still requires `expected_head_sha`,
   and post-merge main validation.
6. On blocked review/CI/rebase, exit nonzero; never merge/modify
   another worker's branch.

## Research → plan → RED tests → implementation → exact-head CI → review

RED cases: stale base after another PR merges, changed head during read,
missing/different-head green workflow, duplicate run attempts with older
success but newest failure, missing required workflow, same SHA on another
PR, review for an older head, unresolved request-changes, draft/closed PR,
racing other-issue claimant, and an allowed exact-head green case.

A regression test must construct GitHub-like JSON payloads without
network and demonstrate the intended failures before implementing the
gate. Run Ruff, strict mypy, pytest on the exact head. Post an independent
skeptical code/real-GitHub-state review before merge. This is an advisory
preflight (not an atomic distributed lock or substitute for CI branch
protection).
