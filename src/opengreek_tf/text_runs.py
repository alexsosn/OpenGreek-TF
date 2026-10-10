"""Unicode-exact source layout runs; a research primitive, not TF tokenization.

A run is a maximal contiguous sequence of either all Unicode whitespace
characters or all non-whitespace characters. Offsets are Python codepoint
indices (not byte, grapheme, lexical-token or visual-column offsets).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceRun:
    """Nonempty exact slice of the source text, with half-open codepoint offsets."""

    start: int
    end: int
    value: str
    is_space: bool


def segment_runs(text: str) -> Iterator[SourceRun]:
    """Yield nonempty maximal whitespace/non-whitespace runs without normalization.

    Empty text produces zero runs. This is intentionally *not* a linguistic
    tokenizer: punctuation stays attached to adjacent non-whitespace text.
    """

    if not text:
        return
    start = 0
    current_is_space = text[0].isspace()
    for pos in range(1, len(text)):
        is_space = text[pos].isspace()
        if is_space != current_is_space:
            yield SourceRun(
                start=start,
                end=pos,
                value=text[start:pos],
                is_space=current_is_space,
            )
            start = pos
            current_is_space = is_space
    yield SourceRun(
        start=start,
        end=len(text),
        value=text[start:],
        is_space=current_is_space,
    )
