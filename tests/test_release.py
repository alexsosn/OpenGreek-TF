from opengreek_tf import __version__
from opengreek_tf.release import SUPPORTED_RELEASE


def test_package_version_is_pre_release() -> None:
    assert __version__ == "0.1.0.dev0"


def test_supported_release_is_immutable_and_complete() -> None:
    assert SUPPORTED_RELEASE.repository == "https://github.com/open-greek/open-greek-corpus.git"
    assert SUPPORTED_RELEASE.tag == "corpus-2026-09-15.2"
    assert SUPPORTED_RELEASE.commit == "338aa27310b3cfe2588a993b4d113b503597d70f"
    assert len(SUPPORTED_RELEASE.commit) == 40
    assert SUPPORTED_RELEASE.release_id == "corpus-2026-09-15.2"
    assert SUPPORTED_RELEASE.corpus_sha256 == (
        "7369350964b5baa948595a5b4ac45165ccf0c5f6812a07565233be11a4c32071"
    )
    assert SUPPORTED_RELEASE.works == 3909
    assert SUPPORTED_RELEASE.passages == 1_970_947
    assert SUPPORTED_RELEASE.greek_tokens == 65_285_435
