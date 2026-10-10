"""RED-first Git object cache correctness and adversarial restoration tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from opengreek_tf.ci_source_cache import (
    PinnedCacheError,
    cache_key,
    check_cached_objects,
    checkout_source,
    prepare_source,
    verify_checkout,
)
from opengreek_tf.release import SUPPORTED_RELEASE, ReleaseIdentity


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def source_release(tmp_path: Path) -> tuple[ReleaseIdentity, tuple[str, ...]]:
    """A real local bare Git origin; no network or upstream stubbed calls."""
    work = tmp_path / "producer"
    work.mkdir()
    _git("-C", str(work), "init", "-q")
    _git("-C", str(work), "config", "user.email", "test@example.invalid")
    _git("-C", str(work), "config", "user.name", "CI fixture")
    primary = work / "data" / "corpus" / "one.jsonl"
    primary.parent.mkdir(parents=True)
    primary.write_text('{"text":"ἀρχή"}\n', encoding="utf-8")
    for family in ("corpus_secondary", "paratext"):
        file = work / "data" / family / "one.jsonl"
        file.parent.mkdir()
        file.write_text('{"text":"α"}\n', encoding="utf-8")
    manifest = {
        "release_id": "synthetic",
        "pin": {"corpus_sha256": "corpus", "catalog_sha256": "catalog"},
        "corpus": {"works": 1, "passages": 1, "tokens": 1},
        "generated_from": {"commit": "synthetic-producer"},
    }
    (work / "data" / "corpus_release.json").write_text(json.dumps(manifest))
    _git("-C", str(work), "add", ".")
    _git("-C", str(work), "commit", "-qm", "synthetic pinned source")
    commit = _git("-C", str(work), "rev-parse", "HEAD")
    bare = tmp_path / "origin.git"
    _git("clone", "--bare", "--quiet", str(work), str(bare))
    identity = ReleaseIdentity(
        repository=str(bare), tag="synthetic", commit=commit,
        release_id="synthetic", corpus_sha256="corpus",
        catalog_sha256="catalog",
        generated_from_commit="synthetic-producer",
        works=1, passages=1, greek_tokens=1,
    )
    return identity, (
        "/data/corpus_release.json", "/data/corpus/",
        "/data/corpus_secondary/", "/data/paratext/",
    )


def test_cache_key_is_specific_to_full_revision_origin_scope_and_os(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]],
) -> None:
    identity, patterns = source_release
    original = cache_key(identity, patterns, platform="Linux")
    assert original == cache_key(identity, tuple(reversed(patterns)), platform="Linux")
    assert original != cache_key(replace(identity, commit="1" * 40), patterns)
    assert original != cache_key(replace(identity, repository="https://other/repo"), patterns)
    assert original != cache_key(identity, patterns[:-1])
    assert original != cache_key(identity, patterns, platform="Windows")
    with pytest.raises(PinnedCacheError):
        cache_key(identity, patterns + (patterns[0],))
    with pytest.raises(PinnedCacheError):
        cache_key(identity, ("/data/../../secret",))


def test_fresh_origin_and_scope_round_trip_real_git_objects(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]], tmp_path: Path,
) -> None:
    identity, patterns = source_release
    first = tmp_path / "first"
    assert prepare_source(first, identity=identity, patterns=patterns)
    cold = checkout_source(first, identity=identity, patterns=patterns,
                           expected_files=(1, 1, 1))
    assert not cold.recovery_attempted
    assert (first / "data" / "corpus" / "one.jsonl").read_text(
        encoding="utf-8"
    ) == '{"text":"ἀρχή"}\n'
    assert cold.object_bytes > 0
    objects = tmp_path / "saved-objects"
    shutil.copytree(first / ".git" / "objects", objects)

    warm_root = tmp_path / "second"
    prepare_source(warm_root, identity=identity, patterns=patterns)
    shutil.copytree(objects, warm_root / ".git" / "objects", dirs_exist_ok=True)
    warm = checkout_source(warm_root, identity=identity, patterns=patterns,
                           expected_files=(1, 1, 1))
    assert not warm.recovery_attempted
    verify_checkout(warm_root, identity=identity, expected_files=(1, 1, 1))
    assert (warm_root / "data" / "corpus" / "one.jsonl").read_bytes() == (
        first / "data" / "corpus" / "one.jsonl"
    ).read_bytes()


@pytest.mark.parametrize("poison", ("alternates", "symlink", "unexpected"))
def test_cache_poison_is_rejected_and_fresh_git_acquisition_recovers(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]],
    tmp_path: Path, poison: str,
) -> None:
    identity, patterns = source_release
    root = tmp_path / "checkout"
    prepare_source(root, identity=identity, patterns=patterns)
    objects = root / ".git" / "objects"
    if poison == "alternates":
        (objects / "info" / "alternates").write_text(str(tmp_path))
    elif poison == "symlink":
        (objects / "pack" / "escape").symlink_to(tmp_path)
    else:
        (objects / "pack" / "evil.sh").write_text("echo unsafe")
    with pytest.raises(PinnedCacheError):
        check_cached_objects(root)
    result = checkout_source(root, identity=identity, patterns=patterns,
                             expected_files=(1, 1, 1))
    assert result.recovery_attempted
    verify_checkout(root, identity=identity, expected_files=(1, 1, 1))


def test_wrong_revision_never_falls_back_to_latest(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]],
    tmp_path: Path,
) -> None:
    identity, patterns = source_release
    nonexistent = replace(identity, commit="1" * 40)
    root = tmp_path / "checkout"
    prepare_source(root, identity=nonexistent, patterns=patterns)
    with pytest.raises(PinnedCacheError):
        checkout_source(root, identity=nonexistent, patterns=patterns,
                        expected_files=(1, 1, 1))


def test_scope_tampering_and_dirty_worktree_are_never_accepted(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]],
    tmp_path: Path,
) -> None:
    identity, patterns = source_release
    root = tmp_path / "checkout"
    prepare_source(root, identity=identity, patterns=patterns)
    sparse = root / ".git" / "info" / "sparse-checkout"
    sparse.write_text("/data/corpus_release.json\n", encoding="utf-8")
    with pytest.raises(PinnedCacheError, match="scope"):
        checkout_source(root, identity=identity, patterns=patterns,
                        expected_files=(1, 1, 1))
    sparse.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    checkout_source(root, identity=identity, patterns=patterns,
                    expected_files=(1, 1, 1))
    text = root / "data" / "corpus" / "one.jsonl"
    text.write_text('{"text":"altered"}\n', encoding="utf-8")
    with pytest.raises((PinnedCacheError, Exception)):
        verify_checkout(root, identity=identity, expected_files=(1, 1, 1))


def test_source_directory_must_be_new_and_not_symlink(
    source_release: tuple[ReleaseIdentity, tuple[str, ...]],
    tmp_path: Path,
) -> None:
    identity, patterns = source_release
    root = tmp_path / "existing"
    root.mkdir()
    with pytest.raises(PinnedCacheError):
        prepare_source(root, identity=identity, patterns=patterns)
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(PinnedCacheError):
        prepare_source(link, identity=identity, patterns=patterns)
