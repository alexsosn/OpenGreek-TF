# #37 — Recognize live advisory issue claims with attached research plans

## Real incident and research

The merged `src/opengreek_tf/dev_claim.py` claim preflight uses `_MARKER.fullmatch(body.strip())` against an entire GitHub issue comment. The claim CLI itself posts a marker-only comment, so old tests pass. In **actual** OpenGreek-TF development issue comments (#6, #9, #52, #37), the first line is the machine claim marker followed by two newlines and a full Markdown research/plan/TDD description. These comments were **silently invisible to `assess`**, allowing a concurrent loop to decide `unclaimed` and duplicate work. GitHub comments are already advisory, but this parser bug negated even advisory conflict detection.

The contract remains explicit: an authoritative claim header must appear as **exactly the first line** of the comment and must pass the existing strict JSON shape, author, server `created_at`, unique comment ID, token and **≤60-minute** expiration rules. Optional human-readable prose can follow the first line. A marker in a quote, Markdown fence, second line or arbitrary discussion cannot claim work. More than one claim marker anywhere in the comment is ambiguous and must not grant authority. Longer manual claims remain invalid rather than silently extending the safe lease; workers should use the CLI's short lease and renew/recheck for longer tasks.

## Plan / TDD / gates

1. RED-first tests show a real first-line claim followed by an embedded Markdown plan is detected and blocks other workers; the current code is expected to fail these tests.
2. Include independent oldest-comment adversarial race tests, quoted/buried marker rejection, duplicate marker rejection, and long/expired claims.
3. Narrowly change only the parser to split the leading marker line from optional prose, fail on second claim marker, and keep all existing validity and security checks unchanged. The `claim_body` CLI output and GitHub wire format do not change.
4. Exact-head unit suite + Ruff + mypy; grounded PR diff review examining malformed JSON/token/expiry and spoofing. If any issue arises, fix and rerun before merge.
5. Issue #37 stays open: an advisory GitHub issue-comment lease is **not an atomic mutex**; there is still an inherent server consistency/claim race and no established cross-process lock.

## Measurements

Use actual issue comment styles as cases. Test count and CI run IDs are recorded on the PR and parent issue after the checks. This change does **not** claim an estimate of CI minutes saved; that would require a controlled collision study.
