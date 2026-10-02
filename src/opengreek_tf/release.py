"""Immutable upstream release identity used by the bootstrap contract."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    repository: str
    tag: str
    commit: str
    release_id: str
    corpus_sha256: str
    catalog_sha256: str
    generated_from_commit: str
    works: int
    passages: int
    greek_tokens: int


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
