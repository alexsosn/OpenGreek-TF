"""RED-first November 2026 immutable source manifest compatibility (#88)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from opengreek_tf.cli import main
from opengreek_tf.release import NOVEMBER_RELEASE, SUPPORTED_RELEASE, release_by_tag
from opengreek_tf.source import SourceAcquisitionError, verify_source


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def _new_source(tmp_path: Path) -> tuple[Path, Any]:
    root = tmp_path / "new-source"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Pinned source fixture")
    _git(root, "remote", "add", "origin", NOVEMBER_RELEASE.repository)
    data = root / "data"
    data.mkdir()
    (data / "public_export.json").write_text(
        json.dumps({"corpus_sha256": NOVEMBER_RELEASE.corpus_sha256, "files": {}}),
        encoding="utf-8",
    )
    (data / "corpus_release.json").write_text(
        json.dumps({
            "release_id": NOVEMBER_RELEASE.release_id,
            "release_date": "2026-11-17",
            "pin": {
                "corpus_sha256": NOVEMBER_RELEASE.corpus_sha256,
                "manifest": "data/public_export.json",
            },
            "corpus": {
                "works": NOVEMBER_RELEASE.works,
                "passages": NOVEMBER_RELEASE.passages,
                "tokens": NOVEMBER_RELEASE.greek_tokens,
            },
        }),
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "new release fixture")
    return root, replace(NOVEMBER_RELEASE, commit=_git(root, "rev-parse", "HEAD"))


def _commit_manifest_mutation(root: Path, mutator: Any) -> str:
    path = root / "data" / "corpus_release.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    mutator(obj)
    path.write_text(json.dumps(obj), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "mutate new release manifest")
    return _git(root, "rev-parse", "HEAD")


def test_new_published_pin_is_a_peeled_commit_not_tag_object() -> None:
    assert NOVEMBER_RELEASE.tag == "corpus-2026-11-17"
    assert NOVEMBER_RELEASE.commit == "122f2cba907dbac0af63f75cf1a54fa3309f36ba"
    assert NOVEMBER_RELEASE.commit != "c06aecc445d88d6dbc3f7d0830c6ca930c10b4fc"
    assert NOVEMBER_RELEASE.corpus_sha256 == (
        "0690bc3e43365b021ec7b201689456b5fe0f9e9d1abae3b846e6158d7cd09e33"
    )
    assert (NOVEMBER_RELEASE.works, NOVEMBER_RELEASE.passages,
            NOVEMBER_RELEASE.greek_tokens) == (3939, 1913683, 65271607)
    assert NOVEMBER_RELEASE.catalog_sha256 is None
    assert NOVEMBER_RELEASE.generated_from_commit is None
    assert NOVEMBER_RELEASE.manifest_path == "data/public_export.json"
    assert NOVEMBER_RELEASE.release_date == "2026-11-17"


def test_new_release_is_explicit_and_old_pin_remains_default() -> None:
    assert release_by_tag(SUPPORTED_RELEASE.tag) is SUPPORTED_RELEASE
    assert release_by_tag(NOVEMBER_RELEASE.tag) is NOVEMBER_RELEASE
    with pytest.raises(ValueError, match="unknown|unsupported"):
        release_by_tag("main")


def test_new_release_manifest_verified_without_removed_legacy_fields(
    tmp_path: Path,
) -> None:
    root, identity = _new_source(tmp_path)
    assert verify_source(root, identity=identity).revision == identity.commit
    with pytest.raises(SourceAcquisitionError, match="release id|revision"):
        verify_source(root, identity=replace(SUPPORTED_RELEASE, commit=identity.commit))


@pytest.mark.parametrize(("mutator", "message"), [
    (lambda m: m.__setitem__("release_id", "other"), "release id"),
    (lambda m: m.__setitem__("release_date", "2026-11-16"), "release date"),
    (lambda m: m["pin"].__setitem__("corpus_sha256", "0" * 64), "corpus hash"),
    (lambda m: m["pin"].__setitem__("manifest", "data/other.json"), "manifest path"),
    (lambda m: m["corpus"].__setitem__("works", 3938), "work count"),
    (lambda m: m["corpus"].__setitem__("passages", 1), "passage count"),
    (lambda m: m["corpus"].__setitem__("tokens", 10), "token count"),
])
def test_new_release_manifest_mutation_rejected_even_on_matching_git_commit(
    tmp_path: Path, mutator: Any, message: str,
) -> None:
    root, identity = _new_source(tmp_path)
    new_sha = _commit_manifest_mutation(root, mutator)
    with pytest.raises(SourceAcquisitionError, match=message):
        verify_source(root, identity=replace(identity, commit=new_sha))


def test_new_manifest_rejects_missing_or_forged_public_export(
    tmp_path: Path,
) -> None:
    root, identity = _new_source(tmp_path)
    exported = root / "data/public_export.json"
    exported.write_text('{"corpus_sha256":"wrong","files":{}}', encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "forge public export")
    with pytest.raises(SourceAcquisitionError, match="public export|manifest corpus"):
        verify_source(root, identity=replace(identity, commit=_git(root, "rev-parse", "HEAD")))
    exported.unlink()
    _git(root, "add", "-u")
    _git(root, "commit", "-qm", "remove public export")
    with pytest.raises(SourceAcquisitionError, match="public export|manifest"):
        verify_source(root, identity=replace(identity, commit=_git(root, "rev-parse", "HEAD")))


def test_cli_can_select_new_verified_identity_without_changing_old_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["source-info"]) == 0
    old = json.loads(capsys.readouterr().out)
    assert old["revision"] == SUPPORTED_RELEASE.commit
    assert main(["source-info", "--release", "corpus-2026-11-17"]) == 0
    new = json.loads(capsys.readouterr().out)
    assert new["revision"] == NOVEMBER_RELEASE.commit
    assert new["catalog_sha256"] is None
    assert new["manifest_path"] == "data/public_export.json"
    with pytest.raises(SystemExit):
        main(["source-info", "--release", "main"])
