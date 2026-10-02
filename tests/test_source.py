from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from opengreek_tf.release import SUPPORTED_RELEASE, ReleaseIdentity
from opengreek_tf.source import (
    SourceAcquisitionError,
    SourceSnapshot,
    fetch_source,
    validate_revision,
    verify_source,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _manifest(identity: ReleaseIdentity) -> dict[str, object]:
    return {
        "corpus": {
            "works": identity.works,
            "passages": identity.passages,
            "tokens": identity.greek_tokens,
        },
        "generated_from": {"commit": identity.generated_from_commit},
        "release_id": identity.release_id,
        "pin": {
            "corpus_sha256": identity.corpus_sha256,
            "catalog_sha256": identity.catalog_sha256,
        },
    }


def _make_source(tmp_path: Path) -> tuple[Path, ReleaseIdentity]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "opengreek-tf@example.invalid")
    _git(source, "config", "user.name", "OpenGreek-TF tests")
    _git(source, "remote", "add", "origin", SUPPORTED_RELEASE.repository)
    data = source / "data"
    data.mkdir()
    manifest_path = data / "corpus_release.json"

    provisional = replace(
        SUPPORTED_RELEASE,
        tag="test-release",
        commit="0" * 40,
        release_id="test-release",
        corpus_sha256="1" * 64,
        catalog_sha256="2" * 64,
        generated_from_commit="3" * 40,
        works=2,
        passages=3,
        greek_tokens=5,
    )
    manifest_path.write_text(
        json.dumps(_manifest(provisional), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(source, "add", "data/corpus_release.json")
    _git(source, "commit", "-m", "source fixture")
    revision = _git(source, "rev-parse", "HEAD")
    identity = replace(provisional, commit=revision)
    return source, identity


@pytest.mark.parametrize(
    "revision",
    ["main", "HEAD", "v1", "338aa27", "g" * 40, "0" * 39, "0" * 41],
)
def test_revision_must_be_full_immutable_commit(revision: str) -> None:
    with pytest.raises(SourceAcquisitionError, match="full 40-hex"):
        validate_revision(revision)


def test_supported_revision_is_valid() -> None:
    assert validate_revision(SUPPORTED_RELEASE.commit) == SUPPORTED_RELEASE.commit


def test_verify_source_accepts_exact_clean_checkout(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)

    snapshot = verify_source(source, identity=identity)

    assert snapshot == SourceSnapshot(path=source.resolve(), revision=identity.commit)


def test_verify_source_accepts_github_ssh_origin(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)
    _git(source, "remote", "set-url", "origin", "git@github.com:open-greek/open-greek-corpus.git")

    assert verify_source(source, identity=identity).revision == identity.commit


def test_verify_source_rejects_wrong_origin(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)
    _git(source, "remote", "set-url", "origin", "https://github.com/example/not-open-greek.git")

    with pytest.raises(SourceAcquisitionError, match="repository mismatch"):
        verify_source(source, identity=identity)


def test_verify_source_rejects_revision_mismatch(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)

    with pytest.raises(SourceAcquisitionError, match="revision mismatch"):
        verify_source(source, identity=replace(identity, commit="f" * 40))


def test_verify_source_rejects_dirty_checkout(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)
    (source / "untracked.txt").write_text("x\n", encoding="utf-8")

    with pytest.raises(SourceAcquisitionError, match="dirty"):
        verify_source(source, identity=identity)


def test_verify_source_rejects_missing_manifest(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)
    (source / "data" / "corpus_release.json").unlink()
    _git(source, "add", "-u")
    _git(source, "commit", "-m", "remove manifest")
    identity = replace(identity, commit=_git(source, "rev-parse", "HEAD"))

    with pytest.raises(SourceAcquisitionError, match="release manifest"):
        verify_source(source, identity=identity)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda m: m.__setitem__("release_id", "wrong"), "release id mismatch"),
        (lambda m: m["pin"].__setitem__("corpus_sha256", "9" * 64), "corpus hash mismatch"),
        (lambda m: m["pin"].__setitem__("catalog_sha256", "9" * 64), "catalog hash mismatch"),
        (lambda m: m["corpus"].__setitem__("works", 999), "work count mismatch"),
        (lambda m: m["corpus"].__setitem__("passages", 999), "passage count mismatch"),
        (lambda m: m["corpus"].__setitem__("tokens", 999), "token count mismatch"),
        (
            lambda m: m["generated_from"].__setitem__("commit", "9" * 40),
            "generated-from mismatch",
        ),
    ],
)
def test_verify_source_rejects_manifest_identity_drift(
    tmp_path: Path, mutator, message: str
) -> None:
    source, identity = _make_source(tmp_path)
    manifest_path = source / "data" / "corpus_release.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutator(manifest)
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    _git(source, "add", "data/corpus_release.json")
    _git(source, "commit", "-m", "mutate manifest")
    identity = replace(identity, commit=_git(source, "rev-parse", "HEAD"))

    with pytest.raises(SourceAcquisitionError, match=message):
        verify_source(source, identity=identity)


def test_verify_source_rejects_invalid_manifest_json(tmp_path: Path) -> None:
    source, identity = _make_source(tmp_path)
    path = source / "data" / "corpus_release.json"
    path.write_text("{not-json\n", encoding="utf-8")
    _git(source, "add", "data/corpus_release.json")
    _git(source, "commit", "-m", "break manifest")
    identity = replace(identity, commit=_git(source, "rev-parse", "HEAD"))

    with pytest.raises(SourceAcquisitionError, match="invalid release manifest"):
        verify_source(source, identity=identity)


def test_fetch_rejects_nonempty_destination_before_git() -> None:
    with TemporaryDirectory() as temp:
        target = Path(temp) / "source"
        target.mkdir()
        (target / "sentinel").write_text("keep", encoding="utf-8")
        with patch("opengreek_tf.source._run_git") as run_git:
            with pytest.raises(SourceAcquisitionError, match="not empty"):
                fetch_source(target)
        run_git.assert_not_called()


def test_fetch_rejects_symlink_destination_before_git(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = tmp_path / "source"
    target.symlink_to(real, target_is_directory=True)
    with patch("opengreek_tf.source._run_git") as run_git:
        with pytest.raises(SourceAcquisitionError, match="symlink"):
            fetch_source(target)
    run_git.assert_not_called()


def test_fetch_uses_exact_commit_and_verifies_before_install() -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], *, capture_output: bool = False):
        calls.append(args)
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    with TemporaryDirectory() as temp:
        target = Path(temp) / "source"
        verified = SourceSnapshot(path=Path("/staging"), revision=SUPPORTED_RELEASE.commit)
        with (
            patch("opengreek_tf.source._run_git", side_effect=fake_run),
            patch("opengreek_tf.source.verify_source", return_value=verified) as verify,
        ):
            snapshot = fetch_source(target)

        assert snapshot.path == target.resolve()
        assert snapshot.revision == SUPPORTED_RELEASE.commit
        verify.assert_called_once()
        assert verify.call_args.kwargs["identity"] == SUPPORTED_RELEASE

    assert any(
        args[-5:] == ["fetch", "--depth", "1", "origin", SUPPORTED_RELEASE.commit]
        for args in calls
    )
    assert any(args[-3:] == ["checkout", "--detach", "FETCH_HEAD"] for args in calls)


def test_fetch_failure_does_not_leave_partial_destination() -> None:
    def fail_fetch(args: list[str], *, capture_output: bool = False):
        if "fetch" in args:
            raise SourceAcquisitionError("fetch failed")
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    with TemporaryDirectory() as temp:
        target = Path(temp) / "source"
        with patch("opengreek_tf.source._run_git", side_effect=fail_fetch):
            with pytest.raises(SourceAcquisitionError, match="fetch failed"):
                fetch_source(target)
        assert not target.exists()
