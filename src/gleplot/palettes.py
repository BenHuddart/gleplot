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

``gray`` (GLE grayscale default) and ``rainbow``/``jet`` (GLE built-in
``color`` rainbow) need no subroutine at all.

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
    "palette_sub_text",
    "colorbar_sub_name",
    "colorbar_sub_text",
    "contour_labels_sub_name",
    "contour_labels_sub_text",
]


# ---------------------------------------------------------------------------
# Supported colour-map names (matplotlib-facing) and their canonical form.
# ---------------------------------------------------------------------------
#
# "jet" is an alias for "rainbow" (both map to GLE's built-in ``color``
# rainbow); it is canonicalized to "rainbow" at store time so the object model
# only ever holds canonical names.
_CMAP_ALIASES: Dict[str, str] = {"jet": "rainbow"}

#: Every cmap name accepted by ``imshow``/``tripcolor`` (before alias
#: canonicalization).  Canonical names are the values of :data:`_CMAP_ALIASES`
#: plus every key of :data:`PALETTE_STOPS` plus ``gray``/``rainbow``/``coolwarm``.
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
)


# ---------------------------------------------------------------------------
# RGB stop tables (18 nodes each), transcribed verbatim from
# gle-library/include/palettes.gle lines 56-136 (inferno/magma/plasma/viridis)
# and 140-157 (cividis).  Each entry is (r, g, b) with components in [0, 1].
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


# ---------------------------------------------------------------------------
# cmap -> emission-mode helpers
# ---------------------------------------------------------------------------


def canonical_cmap(cmap: str) -> str:
    """Canonicalize a user-facing cmap name (lowercase; ``jet`` -> ``rainbow``).

    Raises
    ------
    ValueError
        If ``cmap`` is not one of :data:`SUPPORTED_CMAPS`.
    """
    key = str(cmap).strip().lower()
    key = _CMAP_ALIASES.get(key, key)
    valid = {_CMAP_ALIASES.get(c, c) for c in SUPPORTED_CMAPS}
    if key not in valid:
        supported = ", ".join(sorted(valid))
        raise ValueError(f"Unknown cmap {cmap!r}; supported palettes: {supported}")
    return key


def cmap_needs_sub(cmap: str) -> bool:
    """True if ``cmap`` (canonical) requires an emitted ``gleplot_<name>`` sub.

    ``gray`` (grayscale default) and ``rainbow`` (built-in ``color``) do not.
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


def palette_sub_text(cmap: str) -> Optional[str]:
    """Canonical ``sub gleplot_<name> z ... end sub`` text for ``cmap``.

    Returns ``None`` for ``gray``/``rainbow`` (no sub needed).
    """
    c = canonical_cmap(cmap)
    if not cmap_needs_sub(c):
        return None
    if c == "coolwarm":
        return _COOLWARM_SUB
    return _stops_sub_text(c, PALETTE_STOPS[c])


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
