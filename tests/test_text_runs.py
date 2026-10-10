"""RED-first test specification for text-exact layout runs, issue #25."""

from __future__ import annotations

import random
import unicodedata

import pytest

from opengreek_tf.text_runs import SourceRun, segment_runs


def _check(text: str) -> tuple[SourceRun, ...]:
    runs = tuple(segment_runs(text))
    assert "".join(run.value for run in runs) == text
    cursor = 0
    for i, run in enumerate(runs):
        assert run.start == cursor
        assert run.end > run.start
        assert run.value == text[run.start : run.end]
        assert all(character.isspace() == run.is_space for character in run.value)
        if i > 0:
            assert runs[i - 1].is_space != run.is_space
        cursor = run.end
    assert cursor == len(text)
    return runs


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "\t\n\r\n",
        "λόγος",
        "λόγος· κόσμος  ",
        "  Ἀθηναῖοι\tτὸ μὲν\r\nἐξ ἀρχῆς. ",
        "   ·;※…   ",
        "α\u0301\u0313β  ἅλφα",
        "\u00a0\u2009κόσμος\u2028",
        "\u200bλόγος\ufeff",
        "ⲡⲉⲧⲛⲁⲥⲱⲧⲙ  λόγος",
        "𝄞 🤦🏽‍♂️ \n𐎀",
        "\r\n\r\n\\t",
        "\u0000\u0001 \u2060",
    ],
)
def test_runs_roundtrip_without_normalization(text: str) -> None:
    assert _check(text) == tuple(segment_runs(text))


def test_first_real_dfhg_source_fragment_remains_exact() -> None:
    # Source: open-greek/open-greek-corpus, pinned DFHG Heraclides 2.1
    text = (
        "Ἀθηναῖοι τὸ μὲν ἐξ ἀρχῆς ἐχρῶντο βασιλείᾳ· "
        "συνοικήσαντος δὲ Ἴωνος αὐτοῖς, τότε πρῶτον Ἴωνες ἐκλήθησαν."
    )
    runs = _check(text)
    assert runs[0].value == "Ἀθηναῖοι"
    assert any("βασιλείᾳ·" in r.value for r in runs)
    assert "".join(r.value for r in runs) == text


def test_codepoint_offsets_are_not_utf8_byte_offsets() -> None:
    text = "ἀ\u0301 𐎀"
    runs = _check(text)
    assert runs[0].start == 0
    assert runs[0].end == 2
    assert runs[1].start == 2
    assert runs[2].start == 3
    assert runs[2].end == len(text)
    assert len(text.encode("utf-8")) > len(text)


def test_nfd_and_nfc_are_distinct_and_unchanged() -> None:
    nfc = "ἄνθρωπος"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert "".join(r.value for r in _check(nfc)) == nfc
    assert "".join(r.value for r in _check(nfd)) == nfd


def test_empty_string_does_not_fabricate_slot() -> None:
    assert tuple(segment_runs("")) == ()


def test_large_unicode_randomized_roundtrips() -> None:
    rng = random.Random(25)
    alphabet = "ἅάα\u0301\u0300Ωⲁ𐎀λ·.()!?\n\t\r \u00a0\u200b𐌰"
    for size in (0, 1, 2, 3, 15, 100, 10_000):
        _check("".join(rng.choices(alphabet, k=size)))


def test_input_is_not_normalized_or_lexically_reclassified() -> None:
    runs = _check("ἄνθρωπος,καὶ.λόγος")
    assert len(runs) == 1
    assert runs[0] == SourceRun(
        start=0, end=len("ἄνθρωπος,καὶ.λόγος"),
        value="ἄνθρωπος,καὶ.λόγος", is_space=False,
    )
