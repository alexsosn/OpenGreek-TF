from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from opengreek_tf.cli import main
from opengreek_tf.release import SUPPORTED_RELEASE
from opengreek_tf.source import SourceSnapshot


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "opengreek-tf 0.1.0.dev0"


def test_source_info_reports_supported_release() -> None:
    output = StringIO()
    with patch("sys.stdout", output):
        assert main(["source-info"]) == 0

    payload = json.loads(output.getvalue())
    assert payload == {
        "repository": SUPPORTED_RELEASE.repository,
        "tag": SUPPORTED_RELEASE.tag,
        "revision": SUPPORTED_RELEASE.commit,
        "release_id": SUPPORTED_RELEASE.release_id,
        "corpus_sha256": SUPPORTED_RELEASE.corpus_sha256,
        "catalog_sha256": SUPPORTED_RELEASE.catalog_sha256,
        "works": SUPPORTED_RELEASE.works,
        "passages": SUPPORTED_RELEASE.passages,
        "greek_tokens": SUPPORTED_RELEASE.greek_tokens,
    }


def test_verify_source_cli_uses_supported_identity() -> None:
    output = StringIO()
    snapshot = SourceSnapshot(
        path=Path("/verified/source"),
        revision=SUPPORTED_RELEASE.commit,
    )
    with (
        patch("opengreek_tf.cli.verify_source", return_value=snapshot) as verify,
        patch("sys.stdout", output),
    ):
        assert main(["verify-source", "/candidate/source"]) == 0

    verify.assert_called_once_with("/candidate/source", identity=SUPPORTED_RELEASE)
    assert json.loads(output.getvalue()) == {
        "path": "/verified/source",
        "revision": SUPPORTED_RELEASE.commit,
    }


def test_fetch_cli_uses_supported_identity() -> None:
    output = StringIO()
    snapshot = SourceSnapshot(
        path=Path("/acquired/source"),
        revision=SUPPORTED_RELEASE.commit,
    )
    with (
        patch("opengreek_tf.cli.fetch_source", return_value=snapshot) as fetch,
        patch("sys.stdout", output),
    ):
        assert main(["fetch", "/target/source"]) == 0

    fetch.assert_called_once_with("/target/source", identity=SUPPORTED_RELEASE)
    assert json.loads(output.getvalue()) == {
        "path": "/acquired/source",
        "revision": SUPPORTED_RELEASE.commit,
    }
