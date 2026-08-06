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
Qt-free functions so both the library's own compile path
(:meth:`gleplot.figure.Figure.savefig`) and the GUI's async preview/export
paths (:mod:`gleplot.gui.preview`, :mod:`gleplot.gui.export_dialog`) can
share exactly one policy instead of re-deriving it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Union

#: The Cairo/TeX-safe font GLE itself substitutes for a rejected PostScript
#: font when ``-cairo`` is on the command line (empirically verified: GLE
#: 4.3.10 prints ``PostScript fonts not supported with '-cairo'; using
#: 'texcmr' instead`` and completes successfully). This is the exact font
#: gleplot's SVG preview has injected as ``set font texcmr`` since Track E2
#: (see ``gleplot.gui.preview._SVG_SAFE_FONT``, which now aliases this
#: constant) -- promoted here so the general compile path can reuse the same
#: choice instead of re-deriving it.
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
    callers that already hold one (the GUI's async compile paths always
    snapshot before rendering -- SPEC's "render always works from a
    to_dict() snapshot") can reuse it instead of re-serializing; see
    :meth:`gleplot.figure.Figure.requires_cairo` for the convenience
    wrapper that calls ``self.to_dict()`` for you.
    """
    return _value_requires_cairo(snapshot)


#: Matches a top-level ``set font ...`` line, so :func:`inject_svg_safe_font`
#: never overrides an explicit user choice.
_SET_FONT_RE = re.compile(r"^\s*set\s+font\b", re.IGNORECASE)
#: Matches the ``size W H`` line every gleplot-generated script emits near
#: the top -- the anchor :func:`inject_svg_safe_font` inserts its ``set
#: font`` line immediately after.
_SIZE_LINE_RE = re.compile(r"^\s*size\s+[-+0-9.]+\s+[-+0-9.]+\s*$", re.IGNORECASE)


def inject_svg_safe_font(
    script_path: Union[str, Path], safe_font: str = CAIRO_SAFE_FONT
) -> bool:
    """Insert ``set font <safe_font>`` after ``script_path``'s ``size`` line.

    Shared script-side substitution mechanism (Track E2/G6 follow-up):
    GLE's Cairo SVG backend (``gle -d svg``) rejects PostScript fonts
    outright -- and, unlike every other Cairo-backed device, it engages
    regardless of the ``-cairo`` command-line flag, so GLE's own graceful
    fallback (see :func:`cairo_font_warning`'s docstring, point 2) never
    runs for it. Left alone, an SVG compile against the default (or any
    other PostScript) font exits ``0`` while silently dropping the
    affected text (SPEC "no silent drops"). Forcing ``safe_font`` into the
    script before compiling avoids the error entirely rather than relying
    on GLE's post-hoc substitution.

    No-op -- returns ``False`` without touching the file -- if
    ``script_path`` already contains an explicit ``set font`` line (a
    user's own font choice always wins; a caller that wants the "was this
    font actually unsafe" verdict independently should consult
    :func:`is_cairo_safe_font`/:func:`cairo_font_warning`) or if no ``size``
    line is found to anchor the insertion on (should not happen for a
    gleplot-generated script; left untouched rather than guessing where to
    insert).

    Originally ``gleplot.gui.preview.PreviewController._inject_svg_font``
    (Track E2); promoted here so the export dialog's SVG path (Track H
    follow-up) can reuse the exact same mechanism instead of re-deriving
    it.

    Parameters
    ----------
    script_path : str or Path
        The ``.gle`` script to modify in place. Callers are expected to
        pass a throwaway/temp copy (preview's session script, or export's
        just-written snapshot copy) -- this never touches a user's saved
        file directly.
    safe_font : str, optional
        The font to inject. Defaults to :data:`CAIRO_SAFE_FONT`.

    Returns
    -------
    bool
        ``True`` if a ``set font`` line was inserted (a real substitution
        happened), ``False`` on a no-op.
    """
    path = Path(script_path)
    text = path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    raw_lines = text.split(newline)

    if any(_SET_FONT_RE.match(line) for line in raw_lines):
        return False  # explicit user font already present; do not override

    for idx, line in enumerate(raw_lines):
        if _SIZE_LINE_RE.match(line):
            raw_lines.insert(idx + 1, f"set font {safe_font}")
            path.write_text(newline.join(raw_lines), encoding="utf-8")
            return True
    # No `size` line found (should not happen for a gleplot-generated
    # script): leave the script untouched rather than guess where to insert.
    return False
