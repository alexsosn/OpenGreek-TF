# Product goals — OpenGreek-TF

## Users and purpose

Researchers of Greek literature should be able to load, search, compare and cite the complete **supported** Open Greek source release in native Text-Fabric, retaining the original Greek text, identifiers, nested source facts, alternate witnesses and paratext without an external semantic sidecar.

## Representative research journeys

1. Find an author, work, edition or attested passage and retrieve its exact Greek text with a stable original-source reference.
2. Search across works and inspect hits with reliable work, source-file and passage identity.
3. Distinguish primary text, secondary witnesses and paratext, including metadata-only works and genuinely empty source containers.
4. Inspect provenance, source quality and supported metadata without merging different source entities or inventing alignments.
5. Reproduce a complete corpus build and reload on a documented machine with measured memory, disk and runtime requirements.

## Minimum usable release

One complete, loadable native TF graph for the selected immutable upstream release, with all supported physical source rows and nested facts independently checked against original files; documented source identity, resource limits, representative real queries and a working standard TF app/browser. Smaller selected-file conversions are development tools, not a complete release. The November 2026 upstream revision requires explicit migration and semantic checks before becoming the conversion default.

## Current blocking outcome

The documented P0 blocker is full-graph memory feasibility (issue #75): a successful subset conversion is not proof that the entire corpus builds. Prefer measuring and reducing the actual memory bottleneck or using a sufficiently provisioned supported writer over inventing broad serialization frameworks.

## Boundaries

Retain native TF nodes/features/edges and source identities; no opaque JSON facts or unsupported cross-witness links. Source acquisition and conversion are separate. Agora registration follows a usable standalone corpus, not the reverse.

## Autonomous-development decision rules

- Select work by the researcher journeys above, not issue count or the ease of adding tests. Prefer finishing active PRs and releases over opening new tickets.
- Before introducing a new adapter, workflow, registry, protocol, or validation layer, demonstrate that an existing mechanism cannot meet a concrete acceptance need.
- Preserve source fidelity, access controls, security, and applicable upstream rights. Do not invent inferred text or silently weaken correctness gates.
- Batch repetitive data changes and reuse parameterized tests. Keep independent adversarial review proportional to risk, and validate the actual researcher path.
- If two successive cycles do not advance a journey or remove an observed blocker, reconsider the approach. Stop when the scoped deliverable works instead of generating optional infrastructure work.
