"""Colormap names and the GLE palette routines that draw them.

GLE draws every colormap gleplot writes. ``gray`` is ``colormap``'s default
and ``rainbow`` its ``color`` switch. ``viridis``, ``magma``, ``inferno``,
``plasma`` and ``cividis`` are the routines of the same names in GLE's
``palettes.gle``, ``coolwarm`` is ``palette_blue_white_red`` from its
``color.gle``, and the ColorBrewer maps are the largest palette of each name
in its ``brewer.gle`` (``Set1Qual9``, ``BluesSeq9``, ``RdBuDiv11``, ...). A
script includes the file a routine is in.

A palette is called through a wrapper sub, ``cmap_<name>``
(:func:`palette_sub_text`): GLE passes a palette its value unclamped, and the
``palettes.gle`` routines fail outside [0, 1], so the wrapper clamps it first.
A reversed map (``_r``) is the wrapper of the forward routine at ``1-z``, so a
colorbar, which takes only the palette's name, draws it reversed too.
``gray_r`` is a wrapper returning ``rgb`` itself, and ``gray`` gets one where
a value is coloured outside a ``colormap`` (per-point colours, ``contourf``
bands).

A ``brewer.gle`` routine takes a colour's number, 1 to N, and returns its
name, which the wrapper converts with ``cvtcolor``. For a qualitative map
(``Set1``, ``Paired``, ...) the number is the class ``z`` falls in, as
matplotlib draws it. matplotlib draws the sequential and diverging maps as a
continuous blend of the same 9 or 11 colours; the wrapper takes the nearest.

``rainbow_r`` (and ``jet_r``), and ``rainbow`` where no ``colormap`` draws it,
are drawn with the closest native map (:func:`native_cmap`), which the call
warns about.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

__all__ = [
    "SUPPORTED_CMAPS",
    "NATIVE_CMAPS",
    "canonical_cmap",
    "native_cmap",
    "is_native",
    "colorbar_cmap",
    "cmap_needs_sub",
    "palette_sub_name",
    "palette_call_name",
    "palette_include",
    "palette_sub_text",
]


#: The gleinc file whose ``color_range_vertical``/``_horizontal`` draw a
#: colorbar (``GLEWriter.add_colorbar``), and ``palette_blue_white_red`` the
#: ``coolwarm`` map.
COLOR_INCLUDE = "color.gle"

#: The gleinc file whose routines draw ``viridis``, ``magma``, ``inferno``,
#: ``plasma`` and ``cividis``.
PALETTES_INCLUDE = "palettes.gle"

#: The gleinc file whose routines draw the ColorBrewer maps.
BREWER_INCLUDE = "brewer.gle"

#: The GLE routine behind each native map that is called as a palette sub.
_ROUTINES: Dict[str, str] = {
    "viridis": "viridis",
    "magma": "magma",
    "inferno": "inferno",
    "plasma": "plasma",
    "cividis": "cividis",
    "coolwarm": "palette_blue_white_red",
}

#: Each ColorBrewer map gleplot accepts, its kind in ``brewer.gle`` and the
#: number of colours of the palette that draws it: the most ``brewer.gle``
#: has for the name, which is the count matplotlib's qualitative maps have.
_BREWER: Dict[str, Tuple[str, int]] = {
    **dict.fromkeys(
        (
            "Blues BuGn BuPu GnBu Greens Greys Oranges OrRd PuBu PuBuGn PuRd "
            "Purples RdPu Reds YlGn YlGnBu YlOrBr YlOrRd"
        ).split(),
        ("Seq", 9),
    ),
    **dict.fromkeys(
        "BrBG PiYG PRGn PuOr RdBu RdGy RdYlBu RdYlGn Spectral".split(), ("Div", 11)
    ),
    **dict.fromkeys("Accent Dark2 Pastel2 Set2".split(), ("Qual", 8)),
    **dict.fromkeys("Pastel1 Set1".split(), ("Qual", 9)),
    **dict.fromkeys("Paired Set3".split(), ("Qual", 12)),
}
#: Canonical name -> (the ``brewer.gle`` routine, its colour count).
_BREWER_ROUTINES: Dict[str, Tuple[str, int]] = {
    name.lower(): (f"{name}{kind}{n}", n) for name, (kind, n) in _BREWER.items()
}

#: The maps GLE draws: the two ``colormap`` modes and the routines above.
NATIVE_CMAPS: Tuple[str, ...] = ("gray", "rainbow", *_ROUTINES, *_BREWER_ROUTINES)

# "jet" is an alias for "rainbow" (both are GLE's built-in ``color`` rainbow);
# it is canonicalized to "rainbow" at store time so the object model only ever
# holds canonical names.
_CMAP_ALIASES: Dict[str, str] = {"jet": "rainbow"}

#: Every cmap name accepted by ``imshow``/``tripcolor`` (before alias
#: canonicalization), each also accepted with ``_r`` appended for its reversed
#: form. Names are matched case-insensitively; canonical names are lowercase.
SUPPORTED_CMAPS: Tuple[str, ...] = (
    "gray",
    "rainbow",
    "jet",
    *_ROUTINES,
    *_BREWER,
)

_CANONICAL_CMAPS = frozenset(
    _CMAP_ALIASES.get(c.lower(), c.lower()) for c in SUPPORTED_CMAPS
)


def canonical_cmap(cmap: str) -> str:
    """Canonicalize a user-facing cmap name (lowercase; ``jet`` -> ``rainbow``).

    A reversed name keeps its suffix: ``RdBu_r`` -> ``rdbu_r``,
    ``jet_r`` -> ``rainbow_r``.

    Raises
    ------
    ValueError
        If ``cmap`` is not one of :data:`SUPPORTED_CMAPS`, with or without
        ``_r`` appended.
    """
    key = str(cmap).strip().lower()
    base, suffix = (key[:-2], "_r") if key.endswith("_r") else (key, "")
    base = _CMAP_ALIASES.get(base, base)
    if base not in _CANONICAL_CMAPS:
        supported = ", ".join(SUPPORTED_CMAPS)
        raise ValueError(
            f"Unknown cmap {cmap!r}; supported palettes (any case, and each "
            f"with '_r' appended for its reversed form): {supported}"
        )
    return base + suffix


def native_cmap(cmap: str, sub: bool = False) -> str:
    """The native map GLE draws for ``cmap``: itself, or the closest one.

    ``sub`` is true where the map is called as a palette sub (per-point
    colours, ``contourf`` bands) rather than drawn by a ``colormap``, which
    leaves out ``rainbow``: GLE has it only as ``colormap``'s ``color``
    switch. It is then drawn as ``viridis``. A result other than the
    canonical ``cmap`` is a fallback the caller warns about.
    """
    c = canonical_cmap(cmap)
    if c == "rainbow_r":
        c = "rainbow"
    if sub and c == "rainbow":
        c = "viridis"
    return c


def is_native(cmap: str, sub: bool = False) -> bool:
    """True if ``cmap`` is a canonical name GLE draws as it is."""
    try:
        return native_cmap(cmap, sub) == cmap
    except ValueError:
        return False


def cmap_needs_sub(cmap: str) -> bool:
    """True if a ``colormap`` in ``cmap`` (native) calls a ``cmap_<name>`` sub.

    ``gray`` (grayscale default) and ``rainbow`` (built-in ``color``) do not.
    """
    return cmap not in ("gray", "rainbow")


def palette_sub_name(cmap: str) -> str:
    """The wrapper sub that colours a value in ``cmap`` (native)."""
    return f"cmap_{cmap}"


def palette_call_name(cmap: str) -> str:
    """The ``palette$`` value passed to the colorbar sub for ``cmap`` (native).

    ``gray`` -> ``"gray"`` (grayscale branch), ``rainbow`` -> ``"color"``
    (GLE built-in rainbow branch), everything else its wrapper sub.
    """
    if cmap == "gray":
        return "gray"
    if cmap == "rainbow":
        return "color"
    return palette_sub_name(cmap)


def palette_include(cmap: str) -> Optional[str]:
    """The gleinc file holding the routine ``cmap``'s wrapper calls, if any."""
    base = cmap[:-2] if cmap.endswith("_r") else cmap
    if base in _BREWER_ROUTINES:
        return BREWER_INCLUDE
    if base not in _ROUTINES:
        return None
    return COLOR_INCLUDE if base == "coolwarm" else PALETTES_INCLUDE


def colorbar_cmap(cmap: str, invert: bool) -> str:
    """The cmap a colorbar draws for an image in ``cmap`` (native).

    GLE's ``colormap ... invert`` flips only the image, so the bar of an
    inverted image draws the reversed palette (``viridis`` <-> ``viridis_r``)
    to match it. Without ``invert`` it is ``cmap`` unchanged; ``rainbow`` has
    no reversed form and stays as it is.
    """
    if not invert or cmap == "rainbow":
        return cmap
    return cmap[:-2] if cmap.endswith("_r") else cmap + "_r"


def palette_sub_text(cmap: str) -> str:
    """The ``sub cmap_<name> z ... end sub`` wrapper for ``cmap`` (native).

    It clamps ``z`` to [0, 1], reverses it for an ``_r`` map, and calls the
    GLE routine (:func:`palette_include` names its file); ``gray`` and
    ``gray_r`` return the ``rgb`` grey, and a ColorBrewer map the colour of
    the class ``z`` is in. ``rainbow`` has none.
    """
    base, rev = (cmap[:-2], True) if cmap.endswith("_r") else (cmap, False)
    clamped = "max(0,min(1,z))"
    z = f"1-{clamped}" if rev else clamped
    if base == "gray":
        body = f"   local g = {z}\n   return rgb(g,g,g)"
    elif base in _BREWER_ROUTINES:
        routine, n = _BREWER_ROUTINES[base]
        # The 0-based colour: matplotlib's class for a qualitative map, the
        # nearest of its n blended colours for the others. A reversed map
        # counts it from the other end, as matplotlib reverses the list.
        if "Qual" in routine:
            k = f"min({n - 1},int({clamped}*{n}))"
        else:
            k = f"int({clamped}*{n - 1}+0.5)"
        index = f"{n}-{k}" if rev else f"{k}+1"
        body = f"   return cvtcolor({routine}({index}))"
    else:
        body = f"   return {_ROUTINES[base]}({z})"
    return f"sub {palette_sub_name(cmap)} z\n{body}\nend sub"
