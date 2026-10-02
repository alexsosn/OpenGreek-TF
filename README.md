# OpenGreek-TF

OpenGreek-TF materializes the [Open Greek Corpus](https://github.com/open-greek/open-greek-corpus) as a native [Text-Fabric](https://annotation.github.io/text-fabric/) corpus.

## Status

**Pre-0.1 / research and converter bootstrap.** There is not yet a released TF corpus.

This repository stores only software, tests, documentation, Text-Fabric advanced-app configuration, and source-acquisition helpers. It intentionally does **not** store the Open Greek source checkout or generated TF corpus files.

Initial supported upstream release:

- repository: `open-greek/open-greek-corpus`
- tag: `corpus-2026-09-15.2`
- publishing commit: `338aa27310b3cfe2588a993b4d113b503597d70f`
- corpus SHA-256: `7369350964b5baa948595a5b4ac45165ccf0c5f6812a07565233be11a4c32071`
- 3,909 works / 1,970,947 passages / 65,285,435 Greek tokens in the upstream release manifest

The upstream default branch is not a build identity.

## Target architecture

The release target is a complete native TF model of the supported Open Greek corpus semantics:

- no raw JSON/XML blobs in features;
- no delimiter-packed pseudo-lists;
- no semantic sidecars required for research queries;
- structured and multi-valued information represented through TF nodes, node features, edge features, and text formats;
- upstream work/author identity, source/edition/licence information, citation labels, quality/correction metadata, secondary witnesses, paratext, and supported crosswalks preserved according to the audited source;
- provenance/build reports may exist outside TF, but they may not be the only place where a research-semantic fact survives.

When source semantics leave several valid TF designs, ETCBC/BHSA is the preferred precedent. Compatibility means equivalent semantics, not copying Hebrew-specific feature names.

The build architecture is:

```text
pinned Open Greek release
        ↓
source audit / typed parser
        ↓
canonical IR
        ↓
native Text-Fabric graph
        ↓
independent semantic conservation
        ↓
standard TF advanced app/browser
        ↓
Agora materializer
```

## Source acquisition

Development and Agora both build from the immutable supported Open Greek release, not from the moving default branch.

```bash
python -m pip install -e '.[dev]'
opengreek-tf source-info
opengreek-tf fetch upstream/open-greek-corpus
opengreek-tf verify-source upstream/open-greek-corpus
```

`fetch` installs the exact supported publishing commit as a detached checkout and verifies the repository origin plus `data/corpus_release.json` identity before returning it. The destination must be absent or empty. The upstream repository is large, so acquisition is intentionally separate from ordinary unit tests.

Network access belongs to acquisition only. Later conversion commands receive a verified local checkout and must not fetch or repair source data.

## Text-Fabric app / web browser

A standard Text-Fabric advanced app under `app/` is part of the release. Its section and text-format configuration is intentionally deferred until the native graph schema is frozen. The standard TF browser is the default web application; a custom web stack needs a demonstrated requirement.

## Agora

OpenGreek-TF owns parsing, scholarly semantics, TF construction, validation, app configuration, and source-specific documentation.

Agora owns marketplace registration/discovery, acquisition/execution orchestration, sandbox/trust UX, artifact publication/provenance, and consumer composition. Conversion itself must run network-free on a verified local source checkout.

## Development process

Every semantic or behavioral change follows:

**research → plan/design → RED-first TDD → implementation → exact-head tests → logically independent adversarial review**

See `AGENTS.md` and `docs/agentic-dev-loop.md`. GitHub issues are executable work units; issue #14 is the 0.1.0 release gate.

## Licensing

Repository-authored software is MIT licensed. The generated corpus is an adaptation of upstream data and retains the applicable upstream terms; the supported Open Greek release declares the aggregate corpus CC BY-SA 4.0 with component-specific attribution/licensing.

See `LICENSE_SCOPE.md`.
