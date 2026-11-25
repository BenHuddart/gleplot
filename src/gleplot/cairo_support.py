"""Cairo-device support shared by the compile pipeline (Track G6).

GLE's ``-cairo`` device flag is required for two things gleplot cares about:

1. **Semi-transparency.** Any ``rgba(...)``/``rgba255(...)`` colour --
   notably the one :func:`gleplot.colors.apply_alpha` composes for a
   ``fill_between``/``axvspan``/``axhspan`` whose ``alpha`` is below 1 --
   makes GLE fail outright (``semi-transparency only supported with command
   line option '-cairo'``, exit code 1) on every device except ``-d svg``
   (which is *always* rendered through GLE's Cairo backend regardless of the
   flag; see below).
2. **PostScript-font rejection.** GLE's Cairo backend cannot draw PostScript
   fonts. *With* ``-cairo`` on the command line, GLE substitutes gleplot's
   long-standing SVG-preview fallback font (:data:`CAIRO_SAFE_FONT`) itself
   and only prints an informational note (verified against GLE 4.3.10 --
   exit code 0, output complete); *without* the flag -- which is exactly
   what happens when ``-d svg`` forces the Cairo backend on but gleplot has
   not asked for it explicitly -- the same substitution logic never runs and
   GLE instead raises a hard, non-fatal-but-content-dropping error
   (``PostScript fonts not supported with '-cairo'``) that silently omits
   the affected text from the output. This is why gleplot must decide,
   itself, whenever a Cairo-backed render is about to happen, whether the
   configured font needs the same substitution -- and say so out loud
   (SPEC's "no silent drops": a font swap must never happen without a
   reported warning).

:func:`figure_requires_cairo` and :func:`is_cairo_safe_font` are pure,
Qt-free functions shared by :meth:`gleplot.figure.Figure.savefig` and other
compile callers so Cairo policy is not re-derived in multiple places.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .colors import _gle_code_pieces

#: The Cairo/TeX-safe font GLE itself substitutes for a rejected PostScript
#: font when ``-cairo`` is on the command line (empirically verified: GLE
#: 4.3.10 prints ``PostScript fonts not supported with '-cairo'; using
#: 'texcmr' instead`` and completes successfully). Named here so Cairo
#: substitution warnings can cite the same font GLE picks.
CAIRO_SAFE_FONT = "texcmr"

#: Font names GLE's Cairo backend draws natively -- the ``texcm*`` LaTeX
#: Computer Modern family (plus its ``texmi``/``texsy``/``texex`` aliases,
#: which point at the same ``.fve`` vector files -- see
#: ``font/font.dat`` in a GLE install) and ``glemark`` (GLE's own marker
#: glyph font, not a text face). Verified empirically against GLE 4.3.10:
#: compiling one ``set font <name>`` per entry here with ``-cairo`` and a
#: semi-transparent fill produces *no* ``PostScript fonts not supported``
#: note, while every other font in GLE's table (the ``rm``/``ss``/``tt``
#: aliases, the explicit ``ps*`` PostScript families, and the bitmap
#: ``arial8``/``cour8``/``times8`` Cyrillic faces) does.
#:
#: Not included: GLE's legacy ``pl*`` "Plotter" vector fonts, which also
#: tested Cairo-safe but are obscure enough (and distinct enough from
#: anything gleplot's own :class:`~gleplot.config.GLEStyleConfig` would set)
#: that treating them as unsafe -- one spurious substitution warning, never
#: a silent misrender -- is the safer default than growing this table to
#: chase every legacy name.
_CAIRO_SAFE_FONTS = frozenset(
    {
        "texcmr",
        "texcmb",
        "texcmti",
        "texcmss",
        "texcmssb",
        "texcmssi",
        "texcmtt",
        "texcmitt",
        "texcmsy",
        "texcmex",
        "texcmmi",
        "texmi",
        "texsy",
        "texex",
        "glemark",
    }
)


def is_cairo_safe_font(font: Optional[str]) -> bool:
    """Whether ``font`` is drawn natively by GLE's Cairo backend.

    An empty/``None`` font -- gleplot's own "use GLE's built-in default"
    sentinel (see ``GLEStyleConfig.font``) -- resolves to GLE's default font
    (``rm``, PostScript Times), which is **not** Cairo-safe, so this
    correctly returns ``False`` for it: a figure that never set a font still
    needs the substitution-and-warning treatment the moment Cairo is active.
    """
    name = (font or "").strip().lower()
    return name in _CAIRO_SAFE_FONTS


def cairo_font_warning(font: Optional[str]) -> Optional[str]:
    """A warning message if ``font`` will be silently swapped under Cairo.

    Returns ``None`` when ``font`` is already Cairo-safe (nothing to report).
    Callers are expected to only call this once they've established Cairo is
    actually active for the render at hand (see :func:`figure_requires_cairo`)
    -- this function does not re-check that, so it always answers purely in
    terms of the font.
    """
    if is_cairo_safe_font(font):
        return None
    shown = font if font else "(GLE default)"
    return (
        f"Font {shown!r} is not supported by GLE's Cairo backend "
        f"(PostScript fonts are rejected); GLE will substitute "
        f"{CAIRO_SAFE_FONT!r} when compiling with -cairo."
    )


#: The TeX Computer Modern text fonts in OT1 encoding (verified against GLE
#: 4.3.10): ``<``, ``>``, ``\_``, ``|``, ``\{`` and ``\}`` draw as other
#: glyphs in them. ``texcmtt`` and ``texcmitt`` keep the ASCII layout.
_OT1_FONTS = frozenset(
    {"texcmr", "texcmb", "texcmti", "texcmss", "texcmssb", "texcmssi"}
)

#: What draws each misdrawn character in an OT1 font: the math italic for
#: ``<``/``>``, the typewriter face for the rest.
_OT1_ESCAPES = {
    "<": r"{\setfont{texmi}<}",
    ">": r"{\setfont{texmi}>}",
    r"\_": r"{\setfont{texcmtt}\_}",
    "|": r"{\setfont{texcmtt}|}",
    r"\{": r"{\setfont{texcmtt}\{}",
    r"\}": r"{\setfont{texcmtt}\}}",
}

#: Non-ASCII characters no ``texcm*`` font draws (GLE writes their code
#: instead), with GLE's macro for each.
_TEXCM_MACROS = {"≥": r"\geq{}", "≤": r"\leq{}"}

#: The quoted strings of a GLE script: where gleplot writes all its text.
_QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")

#: An escape from :data:`_OT1_ESCAPES` already written in the text.
_ESCAPED_RE = re.compile(r"\{\\setfont\{(?:texmi|texcmtt)\}(?:[<>|]|\\[_{}])\}")


def drawn_font(font: Optional[str], cairo: bool) -> str:
    """The font GLE draws page text in: ``font``, or its Cairo substitute."""
    if cairo and not is_cairo_safe_font(font):
        return CAIRO_SAFE_FONT
    return (font or "").strip().lower()


def text_glyph_warning(font: str, script: str) -> Optional[str]:
    """A warning when text in ``script`` has characters ``font`` misdraws.

    ``font`` is the font the text is drawn in (:func:`drawn_font`). Every
    string quoted in ``script`` is checked; None when nothing is misdrawn.
    """
    if not font.startswith("texcm"):
        return None
    fixes = dict(_TEXCM_MACROS)
    if font in _OT1_FONTS:
        fixes.update(_OT1_ESCAPES)
    text = _ESCAPED_RE.sub("", "".join(_QUOTED_RE.findall(script)))
    found = [char for char in fixes if char in text]
    if not found:
        return None
    # The text holds gleplot's escapes; the user typed the bare character.
    hints = ", ".join(f"{char.lstrip(chr(92))} as {fixes[char]}" for char in found)
    return (
        f"Font {font!r} draws some characters in this figure's text as other "
        f"glyphs. Write {hints} in the text instead, or choose another font "
        "with GLEStyleConfig(font=...)."
    )


#: Matches a GLE colour expression that already carries its own alpha --
#: ``rgba(...)`` or ``rgba255(...)`` -- wherever it can appear as a string in
#: the object model: a resolved colour token on a fill/span/line/marker/text
#: (see :func:`rgb_to_gle`'s "already a GLE colour expression" pass-through),
#: *or* embedded inside a raw ``passthrough`` line the parser could not fully
#: model (e.g. a hand-written ``fill dA,dB color rgba255(...)`` the
#: recognizer fell back on) -- so ``search`` rather than a start-anchored
#: ``match``, with a negative lookbehind so it does not fire on a longer
#: identifier that merely ends in ``rgba``.
_RGBA_COLOR_RE = re.compile(r"(?<![A-Za-z0-9_])rgba(255)?\s*\(", re.IGNORECASE)


def _value_requires_cairo(obj: Any) -> bool:
    """Recursive worker for :func:`figure_requires_cairo`.

    Walks a JSON-safe structure (as produced by ``Figure.to_dict()``) looking
    for either of Cairo's two triggers (module docstring): a numeric
    ``"alpha"`` field below 1.0 (today only ``FillSeries``/``Span`` declare
    one, but this is a generic walk rather than a hardcoded field list, so a
    future series kind that grows an ``alpha`` field is covered automatically
    -- no second place to remember to update), or any string value that is
    already a ``rgba(...)``/``rgba255(...)`` colour expression, wherever it
    appears (fill/line/marker/text colour, ...).
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "alpha":
                try:
                    if value is not None and float(value) < 1.0:
                        return True
                except (TypeError, ValueError):
                    pass
            if _value_requires_cairo(value):
                return True
        return False
    if isinstance(obj, (list, tuple)):
        return any(_value_requires_cairo(item) for item in obj)
    if isinstance(obj, str):
        return bool(_RGBA_COLOR_RE.search(obj))
    return False


def script_requires_cairo(script: str) -> bool:
    """Whether a written GLE script draws a translucent colour, which only
    GLE's ``-cairo`` device can. Used for a figure with
    ``GLEStyleConfig.opaque_backdrop`` set, whose snapshot keeps the alpha
    values the script no longer has. A colour in a string or a comment,
    such as the metadata block's ``default_color``, draws nothing."""
    return any(
        code and _RGBA_COLOR_RE.search(text)
        for line in script.splitlines()
        for text, code in _gle_code_pieces(line)
    )


def figure_requires_cairo(snapshot: dict) -> bool:
    """Whether a ``Figure.to_dict()`` snapshot needs GLE's ``-cairo`` device.

    True when the figure uses transparency anywhere it can appear: a
    ``fill_between``/``axvspan``/``axhspan`` with ``alpha < 1`` (the common
    case), or any colour field already expressed as a raw
    ``rgba(...)``/``rgba255(...)`` GLE expression (a user can pass one
    directly to any colour parameter -- :func:`gleplot.colors.rgb_to_gle`
    passes an already-formed colour expression through verbatim -- and a
    ``.gle`` file recovered by the parser round-trips one the same way).

    Operates on the plain-dict snapshot rather than a live ``Figure`` so
    callers that already hold one can reuse it instead of re-serializing;
    see :meth:`gleplot.figure.Figure.requires_cairo` for the convenience
    wrapper that calls ``self.to_dict()`` for you.
    """
    return _value_requires_cairo(snapshot)
