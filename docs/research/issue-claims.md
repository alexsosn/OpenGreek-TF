# #37 — advisory issue ownership and live PR preflight

Status: research/prototype; **not** an atomic distributed lock.

## Observed failure and ground truth

On 2026-10-10 issue #33 had two independent implementing branches: PR
[#35](https://github.com/alexsosn/OpenGreek-TF/pull/35) and PR
[#36](https://github.com/alexsosn/OpenGreek-TF/pull/36). Both incurred
research, edits, standard CI and expensive pinned-source verification.
After #35 merged, #36 had to close unmerged due to overlapping files.
Existing `docs/agentic-dev-loop.md` asks workers to check overlaps, but
provides no executable gate; closed PRs and open issues alone do not prove
exclusive work.

## Minimum enforceable contract for this increment

- Before issue selection, branch creation or major edits, GET the **live**
  issue, all open PRs (including drafts), and all issue comments, using
  GitHub API pagination. Fail closed on HTTP errors, malformed responses,
  excessive pages, rate limiting and an issue that is closed.
- An active PR naming the exact issue through title reference,
  closing keyword, explicitly declared implementation claim, or
  `issue/<number>` / `dev/<number>` / `feature/<number>` branch segment
  blocks a new worker. Incidental text such as `related to #37`, substring
  `#370`, and a closed PR must not hold the issue.
- Advisory claim is a machine-readable issue comment with owner (GitHub's
  **server-provided** comment author), unique UUID token and expiry.
  A client can only post a claim when there is no live PR/claim. After
  posting, it MUST reread the issue and all claims and proceed only if its
  claim is the oldest live claim, comparing server comment IDs. Other
  concurrent attempts lose even if each initially saw an empty issue.
- The oldest-comment rule is **convergent** but not linearizable. One worker
  can start editing before a concurrent comment arrives. Therefore every
  worker MUST repeat preflight before opening a PR and again before merging,
  and stop if a different active PR/claim appears. Direct REST comments
  alone cannot guarantee transactional exclusion.
- Short claims expire automatically. Limit the maximum honored lifetime
  to one hour from server-created time, regardless of any future expiry
  claimed by a client. Support explicit relinquishing of one's own lease
  without modifying other users' comments. Never force-push or close
  someone else's PR/branch.
- CI runs do not imply an issue is unclaimed: a linked open PR still blocks.
  An advanced provider-integrated mutex would be needed for hard atomic
  branch creation/PR merges; treat this as **advisory only**.
- Run-token and comment metadata are coordination information, never
  authentication secrets or authority to bypass GitHub ACLs.

## Plan, RED tests, acceptance gates

1. Pure deterministic parser/evaluator: live PR exact-link detection,
   issue state, stable claim-winner election, expired/forged/future leases,
   permission to continue when the token is already the winner.
2. API layer with full pagination and fail-closed HTTP handling, backed
   by mocked transport tests. Never interpret a partial first page as
   a complete active-work census.
3. Command-line `check`, `claim`, `release` using GitHub REST and
   `GITHUB_TOKEN` for writes. Explicitly show blocked ownership and
   avoid falsely declaring a successful reservation.
4. RED tests first and record actual pytest failures; implementation
   only after those tests; exact-head Ruff, mypy, pytest, then logically
   separate adversarial review.
5. Document CLI usage and limitations. On user-visible claims or lease
   collisions, advise contributing review/tests to the existing PR.

## Deferred or separately actionable

Cross-repository coordination shared with `tf-build`, atomic remote lock
provider, heartbeat/long-running lease renewal, CI cancellation across
different tickets, and quantified monthly savings. Those require a
separate real-workload measurement and should not block this bounded
preflight increment.
