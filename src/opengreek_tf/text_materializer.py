"""One native Text-Fabric graph for all three original textual source families.

This is a thin selector and adapter to the existing source-conserving CV
writer, not a second converter or a claim that 2.29m rows fit available RAM.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .native_composer import NativeRecord, NativeStats, write_native_records
from .primary_materializer import iter_native_primary
from .record_stream import DIR_FAMILY
from .unaligned_materializer import iter_native_unaligned

_FAMILY_DIRECTORIES = ("corpus", "corpus_secondary", "paratext")
_EXPECTED_FILES = (3909, 533, 5)
_PINNED_EMPTY_FILES = frozenset({"data/corpus_secondary/democritus.fragmenta.jsonl"})


@dataclass(frozen=True, slots=True)
class TextInventory:
    """Complete pinned source-file coverage, including zero-record files."""

    files: tuple[str, ...]
    empty_files: frozenset[str]
    file_counts: tuple[int, int, int]


def _validate_files(
    root: Path, relative_files: tuple[str, ...], *,
    allow_empty_files: frozenset[str] = frozenset(),
) -> None:
    if not relative_files:
        raise ValueError("no original textual JSONL files selected")
    if not allow_empty_files.issubset(relative_files):
        raise ValueError("empty-file allowance contains unselected source files")

    physical: set[tuple[int, int]] = set()
    source_root = root.resolve()
    names: set[str] = set()
    for name in relative_files:
        if type(name) is not str:
            raise ValueError("source filename must be a string")
        path = Path(name)
        if (
            path.is_absolute()
            or path.as_posix() != name
            or len(path.parts) != 3
            or path.parts[0] != "data"
            or path.parts[1] not in DIR_FAMILY
            or path.suffix != ".jsonl"
        ):
            raise ValueError(f"noncanonical textual source path: {name!r}")
        if name in names:
            raise ValueError(f"duplicate textual source file: {name}")
        names.add(name)
        original_path = root / path
        if original_path.is_symlink():
            raise ValueError(f"textual source symlink is forbidden: {name}")
        resolved = original_path.resolve()
        if not resolved.is_relative_to(source_root):
            raise ValueError(f"textual source escapes source root: {name}")
        try:
            if not resolved.is_file():
                raise ValueError(f"textual source is missing or not a file: {name}")
            stat = resolved.stat()
        except OSError as exc:
            raise ValueError(f"cannot read textual source: {name}") from exc
        key = (stat.st_dev, stat.st_ino)
        if key in physical:
            raise ValueError(f"duplicate physical textual source file: {name}")
        physical.add(key)
        if (stat.st_size == 0) != (name in allow_empty_files):
            raise ValueError(f"source empty-file allowance disagrees with original: {name}")


def select_all_text_files(
    root: Path, *,
    expected_file_counts: tuple[int, int, int] = _EXPECTED_FILES,
) -> TextInventory:
    """Select every original pinned primary, secondary and paratext JSONL.

    The caller must verify the clean exact source Git checkout. The expected
    census protects against sparse checkouts silently omitting entire works.
    Empty source containers are represented by their original paths in the
    provenance digest; they produce no fabricated Text-Fabric source nodes.
    """
    names: list[str] = []
    sizes: list[int] = []
    empty: set[str] = set()
    for directory in _FAMILY_DIRECTORIES:
        base = root / "data" / directory
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"incomplete pinned textual source directory: {base}")
        found = sorted(base.glob("*.jsonl"))
        sizes.append(len(found))
        for path in found:
            name = path.relative_to(root).as_posix()
            names.append(name)
            if path.is_file() and path.stat().st_size == 0:
                empty.add(name)
    selected = tuple(names)
    _validate_files(root, selected, allow_empty_files=frozenset(empty))
    if tuple(sizes) != expected_file_counts:
        raise ValueError(
            f"incomplete pinned textual source inventory: "
            f"expected {expected_file_counts}, got {tuple(sizes)}"
        )
    if frozenset(empty) != _PINNED_EMPTY_FILES:
        raise ValueError(
            "pinned original empty textual source inventory mismatch: "
            f"expected {sorted(_PINNED_EMPTY_FILES)}, got {sorted(empty)}"
        )
    return TextInventory(
        selected, frozenset(empty), (sizes[0], sizes[1], sizes[2]),
    )


def iter_native_texts(
    root: Path, relative_files: tuple[str, ...], *,
    allow_empty_files: frozenset[str] = frozenset(),
) -> Iterator[NativeRecord]:
    """Keep original file/row order; no witness/paratext lexical alignment."""
    _validate_files(root, relative_files, allow_empty_files=allow_empty_files)
    for relative in relative_files:
        directory = Path(relative).parts[1]
        if directory == "corpus":
            yield from iter_native_primary(root, (relative,))
        else:
            yield from iter_native_unaligned(root, (relative,))


def materialize_texts(
    root: Path, relative_files: tuple[str, ...], destination: Path, *,
    allow_empty_files: frozenset[str] = frozenset(),
) -> NativeStats:
    """Write selected original text families into ONE genuine native TF graph.

    Still all-at-once at the source-record and TF CV level. A full 2.29m-row
    build requires a suitable memory budget and an independent complete run.
    """
    records = tuple(
        iter_native_texts(root, relative_files, allow_empty_files=allow_empty_files)
    )
    return write_native_records(records, destination)



@dataclass(frozen=True, slots=True)
class PrimaryRung:
    """Reproducible complete-file original primary benchmark selection."""

    files: tuple[str, ...]
    primary_rows: int

    @property
    def file_count(self) -> int:
        return len(self.files)


def select_whole_primary_rung(
    root: Path, *, minimum_rows: int, maximum_rows: int,
) -> PrimaryRung:
    """Choose intact primary JSONL files in canonical filename order.

    The input checkout must first be verified at its immutable Git revision
    and its *complete* original inventory checked with select_all_text_files.
    This is deliberately only a benchmark selection, not release completeness.
    Refuse oversized source files instead of silently dropping source rows.
    """
    if (
        type(minimum_rows) is not int
        or type(maximum_rows) is not int
        or minimum_rows < 1
        or maximum_rows < minimum_rows
    ):
        raise ValueError("invalid minimum/maximum original-source row bounds")
    source = root / "data" / "corpus"
    if not source.is_dir() or source.is_symlink():
        raise ValueError("original primary corpus directory is unavailable")
    files: list[str] = []
    rows = 0
    for original in sorted(source.glob("*.jsonl")):
        relative = original.relative_to(root).as_posix()
        files.append(relative)
        # Do not dereference symlinks even temporarily while counting.
        # Check physical duplicate aliases together when the rung is selected.
        if original.is_symlink() or not original.is_file():
            raise ValueError(f"symlink or missing original source file: {relative}")
        with original.open("rb") as handle:
            count = sum(1 for _ in handle)
        if count == 0:
            raise ValueError(f"empty original primary source file: {relative}")
        rows += count
        if rows > maximum_rows:
            raise ValueError(
                f"complete original primary source files exceed maximum bound "
                f"{maximum_rows} at {relative} ({rows} records)"
            )
        if rows >= minimum_rows:
            _validate_files(root, tuple(files))
            return PrimaryRung(tuple(files), rows)
    raise ValueError(
        f"insufficient original primary source rows: {rows} < {minimum_rows}"
    )
