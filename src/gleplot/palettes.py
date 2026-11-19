"""Self-contained GLE colour palettes for gleplot's heatmap/contour support.

gleplot emits **self-contained** palette subroutines directly into the ``.gle``
script (no ``include "palettes.gle"`` / ``include "color.gle"`` dependency), so
a generated script compiles anywhere GLE is installed without the gle-library
on the include path.

Palette RGB stop tables
-----------------------
The perceptually-uniform ramps (``viridis``, ``magma``, ``inferno``,
``plasma``, ``cividis``) are transcribed VERBATIM -- 18 RGB nodes each -- from
gle-library ``include/palettes.gle`` (palettes ported by Francois Tonneau,
2025; original data from https://github.com/BIDS/colormap and, for cividis,
https://github.com/pnnl/cmaputil). The emitted sub reproduces that file's
linear-interpolation-in-RGB semantics (``palettes_r``/``_g``/``_b`` +
``palettes_hue``) but inlined as a self-contained piecewise-linear function so
no shared globals/helpers are required.

``coolwarm`` is the ``palette_blue_white_red`` subroutine transcribed from
gle-library ``include/color.gle`` (Modified BSD, (C) 2009 GLE) -- a
blue->white->red diverging ramp defined by an explicit formula rather than a
stop table, so it is emitted as a near-verbatim copy of that formula.

The ColorBrewer maps (``YlOrRd``, ``RdBu``, ``Set1``, ...) are transcribed
from gle-library ``include/brewer.gle`` (palettes ported by Francois Tonneau,
2025; colours from ColorBrewer, https://colorbrewer2.org, (C) Cynthia Brewer).
That file's subs are indexed by colour number rather than by ``z`` in [0, 1],
so only their colours are taken: for each name, the sub with the most colours,
which is the table matplotlib builds the same-named colormap from. Sequential
and diverging maps interpolate between those colours, like matplotlib's
``LinearSegmentedColormap``; qualitative maps are stepped, one band per colour,
like matplotlib's ``ListedColormap``.

``gray`` (GLE grayscale default) and ``rainbow``/``jet`` (GLE built-in
``color`` rainbow) need no subroutine at all.

Reversed maps
-------------
Every name also has a reversed form with ``_r`` appended, as in matplotlib
(``RdBu_r`` is ``RdBu`` read from 1 down to 0). Each is its own
``gleplot_<name>_r`` sub, so the colorbar subs, which take only the palette
name, draw it reversed too: the forward body with ``z = 1-z`` first, or, for a
stepped (qualitative) map, its colours listed backwards. GLE's
``colormap ... invert`` switch flips the normalized z in the same way but only
for the image, and gleplot already exposes it as ``imshow(invert=True)``; the
colorbar of an inverted image draws the reversed palette instead (see
:func:`colorbar_cmap`).
``gray_r`` and ``rainbow_r`` have no built-in switch to fall back on, so they
are subs too, reproducing GLE's grayscale ramp and its ``color`` rainbow.

Canonical text
--------------
:func:`palette_sub_text` is a pure function of the palette name, so the emitted
sub body is deterministic -- essential for the writer -> recognizer -> writer
byte-identical fixed point (the recognizer recognizes ``gleplot_<name>`` subs
by name and regenerates their bodies from here rather than trying to preserve
the original bytes).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

__all__ = [
    "SUPPORTED_CMAPS",
    "PALETTE_STOPS",
    "canonical_cmap",
    "cmap_needs_sub",
    "palette_sub_name",
    "palette_call_name",
    "colorbar_cmap",
    "palette_sub_text",
    "colorbar_sub_name",
    "colorbar_sub_text",
    "colorbar_h_sub_text",
    "contour_labels_sub_name",
    "contour_labels_sub_text",
]


# ---------------------------------------------------------------------------
# ColorBrewer colours, keyed by matplotlib name, from the largest-count sub of
# each name in gle-library/include/brewer.gle (e.g. YlOrRd <- YlOrRdSeq9,
# RdBu <- RdBuDiv11, Paired <- PairedQual12).  Each value is the sub's hex
# colours in order, space-separated.
# ---------------------------------------------------------------------------
#: Sequential and diverging maps, interpolated between their colours.
_BREWER_RAMPS: Dict[str, str] = {
    "Blues": "f7fbff deebf7 c6dbef 9ecae1 6baed6 4292c6 2171b5 08519c 08306b",
    "BuGn": "f7fcfd e5f5f9 ccece6 99d8c9 66c2a4 41ae76 238b45 006d2c 00441b",
    "BuPu": "f7fcfd e0ecf4 bfd3e6 9ebcda 8c96c6 8c6bb1 88419d 810f7c 4d004b",
    "GnBu": "f7fcf0 e0f3db ccebc5 a8ddb5 7bccc4 4eb3d3 2b8cbe 0868ac 084081",
    "Greens": "f7fcf5 e5f5e0 c7e9c0 a1d99b 74c476 41ab5d 238b45 006d2c 00441b",
    "Greys": "ffffff f0f0f0 d9d9d9 bdbdbd 969696 737373 525252 252525 000000",
    "Oranges": "fff5eb fee6ce fdd0a2 fdae6b fd8d3c f16913 d94801 a63603 7f2704",
    "OrRd": "fff7ec fee8c8 fdd49e fdbb84 fc8d59 ef6548 d7301f b30000 7f0000",
    "PuBu": "fff7fb ece7f2 d0d1e6 a6bddb 74a9cf 3690c0 0570b0 045a8d 023858",
    "PuBuGn": "fff7fb ece2f0 d0d1e6 a6bddb 67a9cf 3690c0 02818a 016c59 014636",
    "PuRd": "f7f4f9 e7e1ef d4b9da c994c7 df65b0 e7298a ce1256 980043 67001f",
    "Purples": "fcfbfd efedf5 dadaeb bcbddc 9e9ac8 807dba 6a51a3 54278f 3f007d",
    "RdPu": "fff7f3 fde0dd fcc5c0 fa9fb5 f768a1 dd3497 ae017e 7a0177 49006a",
    "Reds": "fff5f0 fee0d2 fcbba1 fc9272 fb6a4a ef3b2c cb181d a50f15 67000d",
    "YlGn": "ffffe5 f7fcb9 d9f0a3 addd8e 78c679 41ab5d 238443 006837 004529",
    "YlGnBu": "ffffd9 edf8b1 c7e9b4 7fcdbb 41b6c4 1d91c0 225ea8 253494 081d58",
    "YlOrBr": "ffffe5 fff7bc fee391 fec44f fe9929 ec7014 cc4c02 993404 662506",
    "YlOrRd": "ffffcc ffeda0 fed976 feb24c fd8d3c fc4e2a e31a1c bd0026 800026",
    "BrBG": "543005 8c510a bf812d dfc27d f6e8c3 f5f5f5 c7eae5 80cdc1 35978f 01665e 003c30",
    "PiYG": "8e0152 c51b7d de77ae f1b6da fde0ef f7f7f7 e6f5d0 b8e186 7fbc41 4d9221 276419",
    "PRGn": "40004b 762a83 9970ab c2a5cf e7d4e8 f7f7f7 d9f0d3 a6dba0 5aae61 1b7837 00441b",
    "PuOr": "7f3b08 b35806 e08214 fdb863 fee0b6 f7f7f7 d8daeb b2abd2 8073ac 542788 2d004b",
    "RdBu": "67001f b2182b d6604d f4a582 fddbc7 f7f7f7 d1e5f0 92c5de 4393c3 2166ac 053061",
    "RdGy": "67001f b2182b d6604d f4a582 fddbc7 ffffff e0e0e0 bababa 878787 4d4d4d 1a1a1a",
    "RdYlBu": "a50026 d73027 f46d43 fdae61 fee090 ffffbf e0f3f8 abd9e9 74add1 4575b4 313695",
    "RdYlGn": "a50026 d73027 f46d43 fdae61 fee08b ffffbf d9ef8b a6d96a 66bd63 1a9850 006837",
    "Spectral": "9e0142 d53e4f f46d43 fdae61 fee08b ffffbf e6f598 abdda4 66c2a5 3288bd 5e4fa2",
}

#: Qualitative maps, one stepped band per colour.
_BREWER_QUALITATIVE: Dict[str, str] = {
    "Accent": "7fc97f beaed4 fdc086 ffff99 386cb0 f0027f bf5b17 666666",
    "Dark2": "1b9e77 d95f02 7570b3 e7298a 66a61e e6ab02 a6761d 666666",
    "Paired": "a6cee3 1f78b4 b2df8a 33a02c fb9a99 e31a1c fdbf6f ff7f00 cab2d6 6a3d9a ffff99 b15928",
    "Pastel1": "fbb4ae b3cde3 ccebc5 decbe4 fed9a6 ffffcc e5d8bd fddaec f2f2f2",
    "Pastel2": "b3e2cd fdcdac cbd5e8 f4cae4 e6f5c9 fff2ae f1e2cc cccccc",
    "Set1": "e41a1c 377eb8 4daf4a 984ea3 ff7f00 ffff33 a65628 f781bf 999999",
    "Set2": "66c2a5 fc8d62 8da0cb e78ac3 a6d854 ffd92f e5c494 b3b3b3",
    "Set3": "8dd3c7 ffffb3 bebada fb8072 80b1d3 fdb462 b3de69 fccde5 d9d9d9 bc80bd ccebc5 ffed6f",
}


def _hex_stops(colours: str) -> List[Tuple[str, str, str]]:
    """``"ffffcc 800026"`` -> ``[("1.000000", "1.000000", "0.800000"), ...]``."""
    stops = []
    for h in colours.split():
        r, g, b = (f"{int(h[i:i + 2], 16) / 255:.6f}" for i in (0, 2, 4))
        stops.append((r, g, b))
    return stops


# ---------------------------------------------------------------------------
# Supported colour-map names (matplotlib-facing) and their canonical form.
# ---------------------------------------------------------------------------
#
# "jet" is an alias for "rainbow" (both map to GLE's built-in ``color``
# rainbow); it is canonicalized to "rainbow" at store time so the object model
# only ever holds canonical names.
_CMAP_ALIASES: Dict[str, str] = {"jet": "rainbow"}

#: Every cmap name accepted by ``imshow``/``tripcolor`` (before alias
#: canonicalization), each also accepted with ``_r`` appended for its reversed
#: form.  Names are matched case-insensitively; canonical names are lowercase:
#: the values of :data:`_CMAP_ALIASES`, every key of :data:`PALETTE_STOPS` and
#: :data:`_LISTED_STOPS`, and ``gray``/``rainbow``/``coolwarm``, each with or
#: without the ``_r`` suffix.
SUPPORTED_CMAPS: Tuple[str, ...] = (
    "gray",
    "rainbow",
    "jet",
    "viridis",
    "magma",
    "inferno",
    "plasma",
    "cividis",
    "coolwarm",
    *_BREWER_RAMPS,
    *_BREWER_QUALITATIVE,
)


# ---------------------------------------------------------------------------
# RGB stop tables, interpolated by _stops_sub_text.  The literal below holds
# the 18-node ramps transcribed verbatim from gle-library/include/palettes.gle
# lines 56-136 (inferno/magma/plasma/viridis) and 140-157 (cividis); the
# ColorBrewer ramps from _BREWER_RAMPS are added after it.  Each entry is
# (r, g, b) with components in [0, 1].
# ---------------------------------------------------------------------------
PALETTE_STOPS: Dict[str, List[Tuple[str, str, str]]] = {
    # palettes.gle lines 56-73
    "inferno": [
        ("0.001462", "0.000466", "0.013866"),
        ("0.037668", "0.025921", "0.132232"),
        ("0.116656", "0.047574", "0.272321"),
        ("0.217949", "0.036615", "0.383522"),
        ("0.316282", "0.053490", "0.425116"),
        ("0.410113", "0.087896", "0.433098"),
        ("0.503493", "0.121575", "0.423356"),
        ("0.596940", "0.154848", "0.398125"),
        ("0.688653", "0.192239", "0.357603"),
        ("0.775059", "0.239667", "0.303526"),
        ("0.851384", "0.302260", "0.239636"),
        ("0.912966", "0.381636", "0.169755"),
        ("0.956852", "0.475356", "0.094695"),
        ("0.981895", "0.579392", "0.026250"),
        ("0.987464", "0.690366", "0.079990"),
        ("0.973088", "0.805409", "0.216877"),
        ("0.947594", "0.917399", "0.410665"),
        ("0.988362", "0.998364", "0.644924"),
    ],
    # palettes.gle lines 77-94
    "magma": [
        ("0.001462", "0.000466", "0.013866"),
        ("0.035520", "0.028397", "0.125209"),
        ("0.102815", "0.063010", "0.257854"),
        ("0.191460", "0.064818", "0.396152"),
        ("0.291366", "0.064553", "0.475462"),
        ("0.384299", "0.097855", "0.501002"),
        ("0.475780", "0.134577", "0.507921"),
        ("0.569172", "0.167454", "0.504105"),
        ("0.664915", "0.198075", "0.488836"),
        ("0.761077", "0.231214", "0.460162"),
        ("0.852126", "0.276106", "0.418573"),
        ("0.925937", "0.346844", "0.374959"),
        ("0.969680", "0.446936", "0.360311"),
        ("0.989363", "0.557873", "0.391671"),
        ("0.996580", "0.668256", "0.456192"),
        ("0.996727", "0.776795", "0.541039"),
        ("0.992440", "0.884330", "0.640099"),
        ("0.987053", "0.991438", "0.749504"),
    ],
    # palettes.gle lines 98-115
    "plasma": [
        ("0.050383", "0.029803", "0.527975"),
        ("0.186213", "0.018803", "0.587228"),
        ("0.287076", "0.010855", "0.627295"),
        ("0.381047", "0.001814", "0.653068"),
        ("0.471457", "0.005678", "0.659897"),
        ("0.557243", "0.047331", "0.643443"),
        ("0.636008", "0.112092", "0.605205"),
        ("0.706178", "0.178437", "0.553657"),
        ("0.768090", "0.244817", "0.498465"),
        ("0.823132", "0.311261", "0.444806"),
        ("0.872303", "0.378774", "0.393355"),
        ("0.915471", "0.448807", "0.342890"),
        ("0.951344", "0.522850", "0.292275"),
        ("0.977856", "0.602051", "0.241387"),
        ("0.992541", "0.687030", "0.192170"),
        ("0.992505", "0.777967", "0.152855"),
        ("0.974443", "0.874622", "0.144061"),
        ("0.940015", "0.975158", "0.131326"),
    ],
    # palettes.gle lines 119-136
    "viridis": [
        ("0.267004", "0.004874", "0.329415"),
        ("0.281924", "0.089666", "0.412415"),
        ("0.280255", "0.165693", "0.476498"),
        ("0.263663", "0.237631", "0.518762"),
        ("0.237441", "0.305202", "0.541921"),
        ("0.208623", "0.367752", "0.552675"),
        ("0.182256", "0.426184", "0.557120"),
        ("0.159194", "0.482237", "0.558073"),
        ("0.137770", "0.537492", "0.554906"),
        ("0.121148", "0.592739", "0.544641"),
        ("0.128087", "0.647749", "0.523491"),
        ("0.180653", "0.701402", "0.488189"),
        ("0.274149", "0.751988", "0.436601"),
        ("0.395174", "0.797475", "0.367757"),
        ("0.535621", "0.835785", "0.281908"),
        ("0.688944", "0.865448", "0.182725"),
        ("0.845561", "0.887322", "0.099702"),
        ("0.993248", "0.906157", "0.143936"),
    ],
    # palettes.gle lines 140-157
    "cividis": [
        ("0.000000", "0.126200", "0.301500"),
        ("0.000000", "0.168500", "0.403100"),
        ("0.000000", "0.207300", "0.432900"),
        ("0.156600", "0.249800", "0.423600"),
        ("0.237500", "0.292000", "0.420000"),
        ("0.301400", "0.334000", "0.422400"),
        ("0.358200", "0.376300", "0.430200"),
        ("0.411400", "0.418900", "0.443000"),
        ("0.462200", "0.462200", "0.462000"),
        ("0.515800", "0.506500", "0.473600"),
        ("0.573500", "0.552200", "0.472000"),
        ("0.632800", "0.599300", "0.464100"),
        ("0.693600", "0.647800", "0.449900"),
        ("0.756000", "0.697900", "0.429000"),
        ("0.820000", "0.749700", "0.400700"),
        ("0.885800", "0.803500", "0.362700"),
        ("0.953600", "0.859300", "0.311600"),
        ("1.000000", "0.916900", "0.273100"),
    ],
}
PALETTE_STOPS.update(
    {name.lower(): _hex_stops(colours) for name, colours in _BREWER_RAMPS.items()}
)

#: Canonical form of every name in :data:`SUPPORTED_CMAPS`.
_CANONICAL_CMAPS = frozenset(
    _CMAP_ALIASES.get(c.lower(), c.lower()) for c in SUPPORTED_CMAPS
)

#: Stepped (qualitative) palettes: one band per colour, no interpolation.
_LISTED_STOPS: Dict[str, List[Tuple[str, str, str]]] = {
    name.lower(): _hex_stops(colours) for name, colours in _BREWER_QUALITATIVE.items()
}


# ---------------------------------------------------------------------------
# cmap -> emission-mode helpers
# ---------------------------------------------------------------------------


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


def cmap_needs_sub(cmap: str) -> bool:
    """True if ``cmap`` (canonical) requires an emitted ``gleplot_<name>`` sub.

    ``gray`` (grayscale default) and ``rainbow`` (built-in ``color``) do not;
    their reversed forms do.
    """
    return canonical_cmap(cmap) not in ("gray", "rainbow")


def palette_sub_name(cmap: str) -> Optional[str]:
    """GLE subroutine name for ``cmap``'s palette, or ``None`` if none is needed."""
    c = canonical_cmap(cmap)
    if not cmap_needs_sub(c):
        return None
    return f"gleplot_{c}"


def palette_call_name(cmap: str) -> str:
    """The ``palette$`` value passed to the colorbar sub for ``cmap``.

    ``gray`` -> ``"gray"`` (grayscale branch), ``rainbow`` -> ``"color"``
    (GLE built-in rainbow branch), everything else -> ``"gleplot_<name>"``.
    """
    c = canonical_cmap(cmap)
    if c == "gray":
        return "gray"
    if c == "rainbow":
        return "color"
    return f"gleplot_{c}"


def colorbar_cmap(cmap: str, invert: bool) -> str:
    """The cmap a colorbar draws for an image in ``cmap``.

    GLE's ``colormap ... invert`` flips only the image, so the bar of an
    inverted image draws the reversed palette (``viridis`` <-> ``viridis_r``)
    to match it. Without ``invert`` it is ``cmap`` unchanged.
    """
    if not invert:
        return cmap
    c = canonical_cmap(cmap)
    return c[:-2] if c.endswith("_r") else c + "_r"


# ---------------------------------------------------------------------------
# Palette subroutine text (deterministic, canonical)
# ---------------------------------------------------------------------------


def _stops_sub_text(name: str, stops: List[Tuple[str, str, str]]) -> str:
    """Build a self-contained ``sub gleplot_<name> z`` from an RGB stop table.

    Reproduces palettes.gle's linear-interpolation-in-RGB semantics inline:
    for ``z`` in [0, 1], position ``p = z * (N-1)`` selects segment
    ``k = floor(p)`` and fraction ``f`` within it; each RGB component is
    ``stop[k] + (stop[k+1] - stop[k]) * f``.  Emitted as disjoint single-line
    ``if`` guards (matching gle-library ``color.gle`` style, known to compile),
    with the first stop as the default (covers ``z = 0``).
    """
    n = len(stops)
    seg = n - 1
    lines: List[str] = []
    lines.append(f"sub gleplot_{name} z")
    # Clamp z into [0, 1] before the piecewise-linear lookup. GLE's fitz/Akima
    # gridding can overshoot the data range, and a normalized z outside [0, 1]
    # would otherwise fall through every segment guard below and stick at the
    # first stop (the darkest colour) -- rendering as stray dark speckles. With
    # the clamp, out-of-range values saturate at the nearest extreme stop, like
    # matplotlib's default colormap "over"/"under" -> end-colour behaviour.
    lines.append("   if z < 0 then z = 0")
    lines.append("   if z > 1 then z = 1")
    r0, g0, b0 = stops[0]
    lines.append(f"   local r = {r0}")
    lines.append(f"   local g = {g0}")
    lines.append(f"   local b = {b0}")
    for k in range(seg):
        rk, gk, bk = stops[k]
        rk1, gk1, bk1 = stops[k + 1]
        lo = k
        cond = f"(z >= {lo}/{seg}) and (z <= {k + 1}/{seg})"
        frac = f"(z-{lo}/{seg})*{seg}"
        lines.append(f"   if {cond} then r = {rk}+({rk1}-{rk})*{frac}")
        lines.append(f"   if {cond} then g = {gk}+({gk1}-{gk})*{frac}")
        lines.append(f"   if {cond} then b = {bk}+({bk1}-{bk})*{frac}")
    lines.append("   return rgb(r,g,b)")
    lines.append("end sub")
    return "\n".join(lines)


def _listed_sub_text(name: str, stops: List[Tuple[str, str, str]]) -> str:
    """Build a stepped ``sub gleplot_<name> z`` from a qualitative colour list.

    Matches matplotlib's ``ListedColormap``: ``N`` colours split [0, 1] into
    ``N`` equal bands, and ``z`` outside [0, 1] takes the nearest end colour
    (the first guard catches ``z < 0``, the final ``return`` ``z >= 1``).
    """
    n = len(stops)
    lines = [f"sub gleplot_{name} z"]
    for k, (r, g, b) in enumerate(stops[:-1]):
        lines.append(f"   if z < {k + 1}/{n} then return rgb({r},{g},{b})")
    r, g, b = stops[-1]
    lines.append(f"   return rgb({r},{g},{b})")
    lines.append("end sub")
    return "\n".join(lines)


#: The ``coolwarm`` palette, transcribed near-verbatim from gle-library
#: ``include/color.gle`` (``sub palette_blue_white_red``; Modified BSD,
#: (C) 2009 GLE) -- a blue->white->red diverging ramp defined by formula.
_COOLWARM_SUB = "\n".join(
    [
        "sub gleplot_coolwarm z",
        "   ! blue->white->red diverging ramp",
        "   ! transcribed from gle-library include/color.gle palette_blue_white_red",
        "   ! clamp z into [0,1] so fitz/Akima overshoot saturates at the end",
        "   ! colour instead of falling through to the default (see palettes.py)",
        "   if z < 0 then z = 0",
        "   if z > 1 then z = 1",
        "   local r = 0",
        "   local g = 0",
        "   local b = 0",
        "   if (z > 0.25) and (z <= 0.50) then r = (z-0.25)*4",
        "   if (z > 0.50) and (z <= 0.75) then r = 1",
        "   if (z > 0.75)                 then r = 1-(123/255)*4*(z-0.75)",
        "   if (z > 0.25) and (z <= 0.50) then g = (z-0.25)*4",
        "   if (z > 0.50) and (z <= 0.75) then g = 1-4*(z-0.5)",
        "   if (z > 0.75)                 then g = 0",
        "   if (z <= 0.25)                 then b = 132/255+(123/255)*4*z",
        "   if (z >  0.25) and (z <= 0.50) then b = 1",
        "   if (z >  0.50) and (z <= 0.75) then b = 1-4*(z-0.5)",
        "   if (z >  0.75)                 then b = 0",
        "   return rgb(r,g,b)",
        "end sub",
    ]
)


#: The body (every line after ``sub gleplot_<name> z``) of GLE's grayscale
#: ramp, black at 0 and white at 1. Only ``gray_r`` is a sub: ``gray`` itself is
#: the ``colormap`` default.
_GRAY_BODY = "\n".join(
    [
        "   if z < 0 then z = 0",
        "   if z > 1 then z = 1",
        "   return rgb(z,z,z)",
        "end sub",
    ]
)

#: The body of GLE's built-in ``color`` rainbow, transcribed from
#: ``GLEBitmapCreateColorPalette`` (GLE ``src/gle/bitmap/img2ps.cpp``): six
#: equal linear segments black->violet->blue->cyan->green->yellow->red->white,
#: the first split in thirds. Only ``rainbow_r`` is a sub: ``rainbow`` itself
#: is the ``colormap ... color`` switch.
_RAINBOW_BODY = "\n".join(
    [
        "   ! GLE's built-in colormap color rainbow (see palettes.py)",
        "   if z < 0 then z = 0",
        "   if z > 1 then z = 1",
        "   local s = 6*z",
        "   if s < 1/3 then return rgb(s,0,s)",
        "   if s < 2/3 then return rgb(1/3,0,s)",
        "   if s < 1 then return rgb(1-s,0,s)",
        "   if s < 2 then return rgb(0,s-1,1)",
        "   if s < 3 then return rgb(0,1,3-s)",
        "   if s < 4 then return rgb(s-3,1,0)",
        "   if s < 5 then return rgb(1,5-s,0)",
        "   return rgb(1,s-5,s-5)",
        "end sub",
    ]
)


def palette_sub_text(cmap: str) -> Optional[str]:
    """Canonical ``sub gleplot_<name> z ... end sub`` text for ``cmap``.

    Returns ``None`` for ``gray``/``rainbow`` (no sub needed). A reversed
    stepped map lists its colours backwards, so a band boundary ``k/N`` falls
    in the band above it as in matplotlib. Any other reversed name is the
    forward body with ``z = 1-z`` as its first statement.
    """
    c = canonical_cmap(cmap)
    if not cmap_needs_sub(c):
        return None
    if c == "coolwarm":
        return _COOLWARM_SUB
    if c in _LISTED_STOPS:
        return _listed_sub_text(c, _LISTED_STOPS[c])
    if c in PALETTE_STOPS:
        return _stops_sub_text(c, PALETTE_STOPS[c])
    base = c[:-2]
    if base in _LISTED_STOPS:
        return _listed_sub_text(c, _LISTED_STOPS[base][::-1])
    if base == "gray":
        body = _GRAY_BODY
    elif base == "rainbow":
        body = _RAINBOW_BODY
    else:
        body = str(palette_sub_text(base)).split("\n", 1)[1]
    return f"sub gleplot_{c} z\n   z = 1-z\n{body}"


def point_palette_sub_text(cmap: str) -> str:
    """The ``sub gleplot_<name> z`` a per-point colour calls for ``cmap``.

    :func:`palette_sub_text`, plus the forward ``gray`` and ``rainbow`` subs
    that a colormap does not need: a marker's colour is a function call, not
    a ``colormap`` palette switch.
    """
    c = canonical_cmap(cmap)
    text = palette_sub_text(c)
    if text is not None:
        return text
    body = _GRAY_BODY if c == "gray" else _RAINBOW_BODY
    return f"sub gleplot_{c} z\n{body}"


# ---------------------------------------------------------------------------
# Colorbar subroutine (vertical colour range drawn after the graph)
# ---------------------------------------------------------------------------


def colorbar_sub_name() -> str:
    return "gleplot_colorbar_v"


def colorbar_sub_text() -> str:
    """Canonical ``sub gleplot_colorbar_v ... end sub`` text.

    A self-contained vertical colour range adapted from gle-library
    ``include/color.gle`` ``color_range_vertical`` (Modified BSD, (C) 2009 GLE),
    extended with an optional rotated axis ``label$``.  Called with GLE
    named-argument style (``zmin V zmax V ...``) so its arguments are directly
    recoverable from the call line.
    """
    return "\n".join(
        [
            "sub gleplot_colorbar_v zmin zmax zstep palette$ wd hi format$ label$",
            "   default zstep 0",
            "   default wd 0.5",
            '   default format "fix 1"',
            '   default label ""',
            "   ! Guard a degenerate (constant-field) range: zmax = zmin would",
            "   ! divide by zero in the tick-position math below and abort the",
            "   ! render. Expand to a nominal unit span so the bar still draws.",
            "   if zmax = zmin then",
            "      zmax = zmin+1",
            "   end if",
            "   if zstep = 0 then",
            "      zstep = (zmax-zmin)/5",
            "   end if",
            "   begin box name gleplot_cbar",
            '      if palette$ = "gray" then',
            '         colormap "y" 0 1 0 1 1 200 wd hi',
            '      else if palette$ = "color" then',
            '         colormap "y" 0 1 0 1 1 200 wd hi color',
            "      else",
            '         colormap "y" 0 1 0 1 1 200 wd hi palette palette$',
            "      end if",
            "   end box",
            "   amove pointx(gleplot_cbar.bl) pointy(gleplot_cbar.bl)",
            "   box wd hi",
            "   set just lc",
            "   local zp = zmin",
            "   while zp <= zmax+(zmax-zmin)/1e6",
            "      local yy = pointy(gleplot_cbar.bc)+(zp-zmin)/(zmax-zmin)*hi",
            "      amove pointx(gleplot_cbar.rc) yy",
            "      rline wd/3 0",
            "      rmove 0.1 0",
            "      write format$(zp,format$)",
            "      zp = zp+zstep",
            "   next",
            '   if label$ <> "" then',
            "      amove pointx(gleplot_cbar.rc)+1.3 pointy(gleplot_cbar.cc)",
            "      begin rotate 90",
            "         set just cc",
            "         write label$",
            "      end rotate",
            "   end if",
            "end sub",
        ]
    )


def colorbar_h_sub_text() -> str:
    """Canonical ``sub gleplot_colorbar_h ... end sub`` text.

    The horizontal twin of :func:`colorbar_sub_text`, adapted from gle-library
    ``include/color.gle`` ``color_range_horizontal`` (Modified BSD, (C) 2009
    GLE). ``wd`` and ``hi`` keep their geometric meaning: ``wd`` is the bar's
    length along x and ``hi`` its thickness. The call starts at the bar's
    top-left corner and draws downward: the bar, then the ticks and numbers
    under it, then the centred ``label$`` just below the numbers' measured
    extent, so it clears them at any font size.
    """
    return "\n".join(
        [
            "sub gleplot_colorbar_h zmin zmax zstep palette$ wd hi format$ label$",
            "   default zstep 0",
            "   default hi 0.5",
            '   default format "fix 1"',
            '   default label ""',
            "   if zmax = zmin then",
            "      zmax = zmin+1",
            "   end if",
            "   if zstep = 0 then",
            "      zstep = (zmax-zmin)/5",
            "   end if",
            "   rmove 0 -hi",
            "   begin box name gleplot_cbar",
            '      if palette$ = "gray" then',
            '         colormap "x" 0 1 0 1 200 1 wd hi',
            '      else if palette$ = "color" then',
            '         colormap "x" 0 1 0 1 200 1 wd hi color',
            "      else",
            '         colormap "x" 0 1 0 1 200 1 wd hi palette palette$',
            "      end if",
            "   end box",
            "   amove pointx(gleplot_cbar.bl) pointy(gleplot_cbar.bl)",
            "   box wd hi",
            "   set just tc",
            "   begin name gleplot_cbticks",
            "      local zp = zmin",
            "      while zp <= zmax+(zmax-zmin)/1e6",
            "         local xx = pointx(gleplot_cbar.bl)+(zp-zmin)/(zmax-zmin)*wd",
            "         amove xx pointy(gleplot_cbar.bl)",
            "         rline 0 -hi/3",
            "         rmove 0 -0.1",
            "         write format$(zp,format$)",
            "         zp = zp+zstep",
            "      next",
            "   end name",
            '   if label$ <> "" then',
            "      amove pointx(gleplot_cbar.bc) pointy(gleplot_cbticks.bc)-0.2",
            "      write label$",
            "   end if",
            "end sub",
        ]
    )


# ---------------------------------------------------------------------------
# Contour-label subroutine
# ---------------------------------------------------------------------------


def contour_labels_sub_name() -> str:
    return "gleplot_contour_labels"


def contour_labels_sub_text() -> str:
    """Canonical ``sub gleplot_contour_labels file$ format$ ... end sub`` text.

    Self-contained copy of gle-library ``include/contour.gle``
    ``sub contour_labels`` (Modified BSD, (C) 2009 GLE): reads ``x y i v`` rows
    from a ``-clabels.dat`` file and writes the formatted level value in a
    white-filled box at each label position.
    """
    return "\n".join(
        [
            "sub gleplot_contour_labels file$ format$",
            '   default format "fix 1"',
            "   set just cc hei 0.25 color black",
            "   fopen file$ f1 read",
            "   until feof(f1)",
            "      fread f1 x y i v",
            "      amove xg(x) yg(y)",
            "      s$ = format$(v,format$)",
            "      begin box add 0.05 fill white",
            "         write s$",
            "      end box",
            "      write s$",
            "   next",
            "   fclose f1",
            "end sub",
        ]
    )
