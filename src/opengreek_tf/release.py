"""Immutable upstream release identity used by the bootstrap contract."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    repository: str
    tag: str
    commit: str
    release_id: str
    corpus_sha256: str
    catalog_sha256: str | None
    generated_from_commit: str | None
    works: int
    passages: int
    greek_tokens: int
    manifest_path: str | None = None
    release_date: str | None = None


SUPPORTED_RELEASE = ReleaseIdentity(
    repository="https://github.com/open-greek/open-greek-corpus.git",
    tag="corpus-2026-09-15.2",
    commit="338aa27310b3cfe2588a993b4d113b503597d70f",
    release_id="corpus-2026-09-15.2",
    corpus_sha256="7369350964b5baa948595a5b4ac45165ccf0c5f6812a07565233be11a4c32071",
    catalog_sha256="91d4300cbe900929a2fbe0a33db51e51791da7a0e2cd724645a3513781b7a6d9",
    generated_from_commit="1d12c09340aa3309e8bfc0075070c0d7b90f4523",
    works=3909,
    passages=1_970_947,
    greek_tokens=65_285_435,
)


# Opt-in candidate: tagged 2026-11-17 source, NOT YET a converted TF release.
# GitHub's annotated tag object c06aecc... is not its publishing commit.
NOVEMBER_RELEASE = ReleaseIdentity(
    repository="https://github.com/open-greek/open-greek-corpus.git",
    tag="corpus-2026-11-17",
    commit="122f2cba907dbac0af63f75cf1a54fa3309f36ba",
    release_id="corpus-2026-11-17",
    corpus_sha256="0690bc3e43365b021ec7b201689456b5fe0f9e9d1abae3b846e6158d7cd09e33",
    catalog_sha256=None,
    generated_from_commit=None,
    works=3_939,
    passages=1_913_683,
    greek_tokens=65_271_607,
    manifest_path="data/public_export.json",
    release_date="2026-11-17",
)


def release_by_tag(tag: str) -> ReleaseIdentity:
    """Resolve only known immutable source snapshots; never an arbitrary Git ref."""
    if tag == SUPPORTED_RELEASE.tag:
        return SUPPORTED_RELEASE
    if tag == NOVEMBER_RELEASE.tag:
        return NOVEMBER_RELEASE
    raise ValueError(f"unsupported Open Greek source release: {tag!r}")
