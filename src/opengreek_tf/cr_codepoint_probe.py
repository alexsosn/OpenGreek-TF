"""Native integer CR-codepoint TF representation probe (issue #29).

This does not establish Text-Fabric's *default browser rendering* supports CR.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class CRCodepointError(ValueError):
    """The source text or reconstructed native TF graph is not lossless."""


@dataclass(frozen=True, slots=True)
class CRProbeResult:
    source_file: str
    source_ordinal: int
    text: str
    cr_count: int
    text_slot_count: int


def write_cr_codepoint_probe(
    text: str,
    destination: Path,
    *,
    source_file: str,
    source_ordinal: int,
) -> None:
    raise NotImplementedError


def read_cr_codepoint_probe(destination: Path) -> CRProbeResult:
    raise NotImplementedError
