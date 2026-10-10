# CI source object cache rollout acceptance

Pilot: `control-census-pinned.yml` on PR #39. The cache restores only `upstream/.git/objects` into a new Git directory, then fetches pinned SHA and verifies it. A verified cache is saved only after the complete corpus census/independent raw JSONL recount and native TF checks pass; untrusted fork PR triggers cannot write the shared cache. Other identical-scope workflows must wait until the pilot proves a genuine hit and improvement.

Do not weaken any existing full-corpus or source identity assertions. Cache miss/corruption is not a semantic failure if a clean pinned fetch succeeds; save no credentials.
