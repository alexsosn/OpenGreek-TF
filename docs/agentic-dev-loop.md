# Autonomous development loop

OpenGreek-TF follows the strict issue-driven loop used across the related Text-Fabric conversion projects.

## 1. Select an issue

Choose an unblocked issue that advances #14. Read the issue, linked discussion and existing PRs.

For every *new* issue, run the live GitHub preflight **before branching or
starting expensive code/CI work**:

```bash
python -m opengreek_tf.dev_claim check --issue 37
GITHUB_TOKEN=... python -m opengreek_tf.dev_claim claim --issue 37
```

The claim command prints a unique `your_token` on success. Preserve it for
your run, not in repository files. A blocked check (exit 2) means inspect the
active PR or claimant and contribute review/tests instead of duplicating work.
An API/pagination error (exit 3) means **do not proceed**.

Use `check` again before opening a PR, before major new commits, and before
merging. Once your own PR exists, an authenticated caller can exempt *only that
PR*, not someone else's, using:

```bash
GITHUB_TOKEN=... python -m opengreek_tf.dev_claim check \
  --issue 37 --own-pr 38 --token YOUR_TOKEN
GITHUB_TOKEN=... python -m opengreek_tf.dev_claim release \
  --issue 37 --token YOUR_TOKEN
```

The lease is advisory: winner is the oldest active server-dated claim
comment, and even a successful claim has a race window before a competing
comment or PR appears. GitHub comments are **not an atomic lock**; the
protocol never grants permission to overwrite/close another worker's branch.
A claim expires within 60 minutes, even if the purported expiry is later.
See `docs/research/issue-claims.md`.

## 2. Research

Inspect real upstream files, current upstream code/docs, Text-Fabric behavior, BHSA precedent, and Agora contracts relevant to the issue.

Record material findings in `research.md` or a focused document under `docs/research/`.

Research may create new issues when evidence reveals a separate concern.

## 3. Plan/design

Before implementation, state intended behavior, invariants, failure policy, interfaces and tests.

For corpus-semantic changes state:

- exact source construct;
- exact native TF representation;
- identity/order/multiplicity preservation;
- missing/unsupported behavior;
- independent validation strategy;
- applicable BHSA precedent and any deliberate divergence.

## 4. RED-first test

Add a deterministic test that fails for the intended reason before production behavior changes.

A test that only checks mocks or duplicates the implementation is not enough for a semantic claim.

## 5. Implement

Make the smallest coherent change satisfying the researched contract. Do not hide unrelated semantic changes in cleanup.

## 6. Verify exact head

Run all relevant unit/integration/full-corpus gates against the exact final head. For corpus changes, validate real source evidence and load generated data with Text-Fabric.

## 7. Independent adversarial review

Review the exact final head from a logically independent perspective. Try to falsify the PR using real source data, generated TF, public APIs and current docs.

Questions include:

- Did any source field or record disappear?
- Was a list/mapping flattened?
- Was source order changed?
- Was missingness normalized away?
- Did a slug become confused with an opaque ID or CTS URN?
- Was a heterogeneous citation syntax forced into a false common hierarchy?
- Were secondary witnesses or paratext silently discarded?
- Was an inferred alignment presented as source fact?
- Does validation independently test the writer?
- Would the same bug exist outside Agora?

## 8. Iterate or merge

Behavior-changing review fixes require a new RED/GREEN cycle and re-review of the new exact head.

Merge only when the exact head is green and reviewed.
