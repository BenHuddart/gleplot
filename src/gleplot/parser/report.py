"""Structured import report: typed notes behind :class:`RecognizedFigure`.

``parse_gle_figure`` used to hand back only a flat list of prefix-tagged
strings (``"structure: ..."``, ``"data: ..."``, ...). GLEstudio's import
report (SPEC 8.1.5 / 10.4) needs to group, filter and locate those recovery
notes -- categorize by kind, and where possible point at the original source
lines that produced them -- which a bare string cannot support. This module
defines the typed record; :mod:`gleplot.parser.recognizer` is the only
producer (see its module docstring, "Warnings taxonomy").

:class:`RecognizedFigure.warnings` (the string form every existing consumer
was written against) is now a *derived* view: :attr:`ImportNote.rendered`
reproduces exactly the ``"category: message"`` string the un-typed API used
to build directly, so ``warnings`` stays byte-identical for the whole
existing test corpus with the notes as the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

__all__ = ["ImportCategory", "ImportNote"]


class ImportCategory(str, Enum):
    """The recovery-note categories the recognizer emits.

    Members match the string prefixes documented in the recognizer's
    "Warnings taxonomy" exactly (``ImportCategory.DATA.value == "data"``),
    so :attr:`ImportNote.rendered` reproduces the historical
    ``"data: ..."``-style warning strings unchanged. ``mathtext`` (SPEC
    8.1.5) is a v1.1 category with no current emission site -- listed here
    only in the sense that adding it later is a matter of a new member plus
    emission sites, not a taxonomy redesign.
    """

    METADATA = "metadata"
    STRUCTURE = "structure"
    DATA = "data"
    LEGEND = "legend"
    LAYOUT = "layout"
    SMOOTH = "smooth"
    PROGRAMMATIC = "programmatic"


@dataclass(frozen=True)
class ImportNote:
    """One recovered ambiguity or loss from a ``.gle`` import.

    Attributes
    ----------
    category : ImportCategory
        What kind of recovery this is (see :class:`ImportCategory`).
    message : str
        Human-readable description, exactly the text that used to follow
        ``"category: "`` in the old warning string.
    source_span : (int, int) or None
        1-indexed, inclusive ``(start_line, end_line)`` into the *original*
        file, when the recognizer can point at the source that produced the
        note. ``None`` when no single location is responsible -- either the
        note is a whole-figure aggregate (e.g. mixed ``smooth`` flags across
        every line dataset) or the underlying helper is shared by too many
        call sites to attribute a location without guessing. See
        :mod:`gleplot.parser.recognizer`'s module docstring for the
        per-category span-coverage table. A single-line note has
        ``start_line == end_line``.
    """

    category: ImportCategory
    message: str
    source_span: Optional[Tuple[int, int]] = None

    @property
    def rendered(self) -> str:
        """The historical ``"category: message"`` warning string."""
        return f"{self.category.value}: {self.message}"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.rendered
