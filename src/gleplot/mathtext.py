"""Translate matplotlib-style ``$...$`` mathtext into GLE's native text markup.

Matplotlib users write axis labels, titles and legend keys such as
``r"$\\chi$ (emu/mol)"`` or ``r"emu mol$^{-1}$"``. GLE's text engine speaks a
TeX-like markup of its own that natively understands LaTeX symbol macros
(``\\alpha`` ... ``\\Omega``, ``\\chi``, ``\\times`` ...), braced sub/superscripts
(``^{}`` / ``_{}``) and a handful of spacing/font commands. This module bridges
the two so matplotlib users get Greek/math rendering without learning GLE
markup.

Design (see the feature brief / CLAUDE.md conventions):

* **Translate at STORE time**, exactly like the colour/marker mappings: the
  object model stores the *translated* GLE-markup string and the writer stays
  untouched. A ``.gle`` file re-parsed by the recognizer already contains GLE
  markup, so writer -> recognizer -> writer stays a byte-identical fixed point.
* **Idempotent.** A string with no ``$`` is returned unchanged (round-tripped
  labels are already GLE markup), so ``translate(translate(s)) == translate(s)``.
* **Graceful degradation.** An odd number of unescaped ``$`` (which matplotlib
  would reject) leaves the string completely unchanged rather than guessing.

Only the text *inside* ``$...$`` segments is translated; text outside passes
through verbatim (it may already be GLE markup). ``\\$`` is a literal dollar
sign everywhere and never opens/closes a math segment.

The supported-macro tables below are derived from the GLE 4.3.10 manual:

* LaTeX symbol macros (Greek etc.): ``appendix/fig/symbols.csv`` /
  ``appendix/sym.tex`` ("LaTeX Symbols").
* Text commands (``^{}`` ``_{}`` ``\\,`` ``\\:`` ``\\;`` ``\\!`` ``\\_`` ``{\\rm}``
  ``{\\it}`` ``{\\bf}`` ``{\\tt}``): ``appendix/sym.tex`` ("LaTeX Macros") and
  ``primitives/cmds.tex`` (the ``text`` primitive).

Examples
--------
>>> mathtext_to_gle(r"$\\chi$ (emu/mol)")
'\\\\chi{} (emu/mol)'
>>> mathtext_to_gle(r"emu mol$^{-1}$")
'emu mol^{-1}'
>>> mathtext_to_gle(r"$x_i^2$")
'x_{i}^{2}'
>>> mathtext_to_gle(r"$T$ (\\degree C)")   # already GLE markup outside math
'T (\\\\degree C)'
>>> mathtext_to_gle(r"cost \\$5")            # escaped dollar -> literal
'cost $5'
>>> mathtext_to_gle(r"$x = 5")               # unmatched $ -> unchanged
'$x = 5'
>>> mathtext_to_gle(r"\\chi{} (emu/mol)")    # no $ -> identity
'\\\\chi{} (emu/mol)'
"""

import re
from typing import List, Optional, Tuple

__all__ = ["mathtext_to_gle"]


# ---------------------------------------------------------------------------
# Supported-macro tables (provenance: GLE 4.3.10 manual)
# ---------------------------------------------------------------------------

# LaTeX symbol macros GLE renders natively -> passed through verbatim as
# ``\name``. Verbatim copy of the manual's symbol table
# (gle-manual/appendix/fig/symbols.csv, rendered by appendix/sym.tex).
# Includes Greek letters plus the common math symbols matplotlib users reach
# for (\times, \cdot, \pm, \infty, \degree, \circ, \approx, \leq, \geq ...).
GLE_SYMBOL_MACROS = frozenset(
    {
        "AA",
        "AE",
        "Delta",
        "Downarrow",
        "Gamma",
        "Im",
        "L",
        "Lambda",
        "Leftarrow",
        "Leftrightarrow",
        "O",
        "OE",
        "Omega",
        "P",
        "Phi",
        "Pi",
        "Psi",
        "Re",
        "Rightarrow",
        "S",
        "Sigma",
        "Theta",
        "Uparrow",
        "Updownarrow",
        "Upsilon",
        "Xi",
        "aa",
        "ae",
        "aleph",
        "alpha",
        "amalg",
        "approx",
        "ast",
        "asymp",
        "backslash",
        "beta",
        "bigcap",
        "bigcirc",
        "bigcup",
        "bigodot",
        "bigoplus",
        "bigotimes",
        "bigsqcup",
        "bigtriangledown",
        "bigtriangleup",
        "biguplus",
        "bigvee",
        "bigwedge",
        "bot",
        "bullet",
        "cap",
        "cdot",
        "chi",
        "circ",
        "clubsuit",
        "coprod",
        "cup",
        "dag",
        "dagger",
        "dashv",
        "ddag",
        "ddagger",
        "degree",
        "delta",
        "diamond",
        "diamondsuit",
        "div",
        "downarrow",
        "ell",
        "emptyset",
        "epsilon",
        "equiv",
        "eta",
        "exists",
        "flat",
        "forall",
        "frown",
        "gamma",
        "geq",
        "gg",
        "heartsuit",
        "i",
        "imath",
        "in",
        "infty",
        "intop",
        "iota",
        "j",
        "jmath",
        "kappa",
        "l",
        "lambda",
        "land",
        "leftarrow",
        "leftharpoondown",
        "leftharpoonup",
        "leftrightarrow",
        "leq",
        "lhook",
        "ll",
        "lor",
        "mapsto",
        "mapstochar",
        "mid",
        "minus",
        "mp",
        "mu",
        "nabla",
        "natural",
        "nearrow",
        "neg",
        "neq",
        "ni",
        "not",
        "nu",
        "nwarrow",
        "o",
        "odot",
        "oe",
        "ointop",
        "omega",
        "ominus",
        "oplus",
        "oslash",
        "otimes",
        "owns",
        "parallel",
        "partial",
        "perp",
        "phi",
        "pi",
        "pm",
        "prec",
        "preceq",
        "prime",
        "prod",
        "propto",
        "psi",
        "rho",
        "rhook",
        "rightarrow",
        "rightharpoondown",
        "rightharpoonup",
        "searrow",
        "setminus",
        "sharp",
        "sigma",
        "sim",
        "simeq",
        "smallint",
        "smile",
        "spadesuit",
        "sqcap",
        "sqcup",
        "sqsubseteq",
        "sqsupseteq",
        "ss",
        "star",
        "subset",
        "subseteq",
        "succ",
        "succeq",
        "sum",
        "supset",
        "supseteq",
        "swarrow",
        "tau",
        "theta",
        "times",
        "top",
        "triangle",
        "triangleleft",
        "triangleright",
        "uparrow",
        "updownarrow",
        "uplus",
        "upsilon",
        "varepsilon",
        "varphi",
        "varpi",
        "varrho",
        "varsigma",
        "vartheta",
        "vdash",
        "vee",
        "wedge",
        "wp",
        "wr",
        "xi",
        "zeta",
    }
)

# ``\mathXX{...}`` / ``\textXX{...}`` font macros -> GLE inline font groups
# ``{\rm ...}`` / ``{\it ...}`` / ``{\bf ...}`` / ``{\tt ...}``
# (gle-manual/appendix/sym.tex "LaTeX Macros"; primitives/cmds.tex text cmds).
# matplotlib's default math font is italic, so ``\mathrm``/``\text`` force
# upright roman. Families GLE has no simple inline equivalent for (sans-serif)
# degrade to their contents (braces stripped) to preserve the text.
FONT_MACROS = {
    "mathrm": "rm",
    "mathit": "it",
    "mathbf": "bf",
    "mathtt": "tt",
    "text": "rm",
    "textrm": "rm",
    "textit": "it",
    "textbf": "bf",
    "texttt": "tt",
    "mathsf": None,  # no inline sans-serif in GLE -> strip to contents
    "mathcal": None,  # no calligraphic font -> strip to contents
    "mathbb": None,  # no blackboard-bold font -> strip to contents
    "operatorname": "rm",
}

# Backslash + single non-letter symbol macros handled explicitly inside math.
# GLE natively supports the spacing macros ``\, \: \; \!`` and the literal
# underscore ``\_`` (appendix/sym.tex). Others map to the bare character.
_SYMBOL_ESCAPES = {
    ",": "\\,",  # thin space (GLE: 0.5em)
    ":": "\\:",  # medium space (GLE: 1em)
    ";": "\\;",  # thick space (GLE: 2em)
    "!": "\\!",  # negative thin space (GLE: -0.5em)
    " ": "\\,",  # LaTeX control space -> thin space
    "_": "\\_",  # literal underscore (GLE native escape)
    "%": "%",
    "&": "&",
    "#": "#",
    "{": "{",
    "}": "}",
    "$": "$",
}

# A GLE token that ends in a bare macro name (``\word``). Used to decide whether
# a math->text boundary needs a ``{}`` terminator so GLE does not swallow the
# following space or merge the macro with following letters.
_TRAILING_MACRO = re.compile(r"\\[A-Za-z]+$")


def mathtext_to_gle(s: Optional[str]) -> Optional[str]:
    """Translate matplotlib mathtext (``$...$``) in *s* into GLE text markup.

    Parameters
    ----------
    s : str or None
        A display string as a matplotlib user would write it. Non-strings
        (including ``None``) are returned unchanged, so callers may pass an
        optional label straight through.

    Returns
    -------
    str or None
        The string with every ``$...$`` math segment rewritten in GLE markup.
        Text outside math segments is preserved verbatim. Returned unchanged
        when *s* contains no ``$`` (idempotent on already-translated GLE
        markup) or when the unescaped ``$`` count is odd (matplotlib would
        error; we degrade gracefully rather than guess).
    """
    if not isinstance(s, str) or "$" not in s:
        return s

    segments = _split_segments(s)
    if segments is None:
        # Unbalanced ``$`` -> leave the caller's string exactly as given.
        return s

    # Translate each segment, then stitch, inserting ``{}`` after a math
    # segment that ends in a bare macro when the *next emitted character*
    # (across any following segments) is a letter or whitespace.
    rendered: List[Tuple[str, bool]] = []
    for kind, text in segments:
        if kind == "math":
            gle = _translate_math(text)
            rendered.append((gle, bool(_TRAILING_MACRO.search(gle))))
        else:
            rendered.append((text, False))

    out: List[str] = []
    for idx, (text, trailing_macro) in enumerate(rendered):
        out.append(text)
        if trailing_macro:
            nxt = _next_char(rendered, idx + 1)
            if nxt is not None and (nxt.isalpha() or nxt.isspace()):
                out.append("{}")
    return "".join(out)


def _next_char(rendered: List[Tuple[str, bool]], start: int) -> Optional[str]:
    """First character of the concatenation of segments from *start* onward."""
    for text, _ in rendered[start:]:
        if text:
            return text[0]
    return None


def _split_segments(s: str) -> Optional[List[Tuple[str, str]]]:
    """Split *s* into alternating ``('text'|'math', content)`` segments.

    ``\\$`` is treated as a literal ``$`` (in both text and math) and never
    acts as a delimiter. Returns ``None`` when the unescaped ``$`` count is
    odd (an unterminated math segment).
    """
    segments: List[Tuple[str, str]] = []
    buf: List[str] = []
    in_math = False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] == "$":
            buf.append("$")  # literal dollar, not a delimiter
            i += 2
            continue
        if c == "$":
            segments.append(("math" if in_math else "text", "".join(buf)))
            buf = []
            in_math = not in_math
            i += 1
            continue
        buf.append(c)
        i += 1
    if in_math:
        return None
    segments.append(("text", "".join(buf)))
    return segments


def _translate_math(m: str) -> str:
    """Translate the interior of one ``$...$`` segment into GLE markup."""
    out: List[str] = []
    i, n = 0, len(m)
    while i < n:
        c = m[i]
        if c == "\\":
            token, i = _read_macro(m, i)
            out.append(token)
        elif c in "^_":
            token, i = _read_script(m, i)
            out.append(token)
        elif c == "{":
            # Bare TeX grouping (invisible in matplotlib). Strip the braces so
            # GLE does not render literal braces; keep the translated contents.
            group, i = _read_brace_group(m, i)
            out.append(_translate_math(group))
        elif c == "}":
            i += 1  # stray closing brace: drop it
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _read_macro(m: str, i: int) -> Tuple[str, int]:
    """Read a ``\\...`` macro starting at index *i* (m[i] == '\\')."""
    j = i + 1
    if j >= len(m):
        return "", j  # trailing backslash -> drop
    # Backslash + non-letter: spacing / escaped-symbol macro.
    if not m[j].isalpha():
        ch = m[j]
        return _SYMBOL_ESCAPES.get(ch, ch), j + 1
    # Backslash + letters: a named macro.
    k = j
    while k < len(m) and m[k].isalpha():
        k += 1
    name = m[j:k]

    if name == "frac":
        return _read_frac(m, k)

    if name in FONT_MACROS:
        group, after = _read_optional_group(m, k)
        if group is None:
            # No brace group followed: emit as a bare pass-through macro.
            return "\\" + name, k
        inner = _translate_math(group)
        font = FONT_MACROS[name]
        if font is None:
            return inner, after  # unsupported family -> strip to contents
        return "{\\" + font + " " + inner + "}", after

    # Known GLE symbol macro, or an unknown macro we pass through verbatim
    # (GLE understands more than we enumerate; passing through preserves
    # user intent). Either way emit ``\name``.
    return "\\" + name, k


def _read_script(m: str, i: int) -> Tuple[str, int]:
    """Read a ``^``/``_`` script at index *i* and return a braced GLE form."""
    op = m[i]  # '^' or '_'
    j = i + 1
    if j >= len(m):
        return op, j  # dangling ^ or _ : emit literally
    c = m[j]
    if c == "{":
        group, after = _read_brace_group(m, j)
        return op + "{" + _translate_math(group) + "}", after
    if c == "\\":
        token, after = _read_macro(m, j)
        return op + "{" + token + "}", after
    # Single character token.
    return op + "{" + c + "}", j + 1


def _read_frac(m: str, i: int) -> Tuple[str, int]:
    """Degrade ``\\frac{a}{b}`` (no GLE inline equivalent) to ``a/b``."""
    num, i = _read_optional_group(m, i)
    den, i = _read_optional_group(m, i)
    num_s = _translate_math(num) if num is not None else ""
    den_s = _translate_math(den) if den is not None else ""
    return num_s + "/" + den_s, i


def _read_optional_group(m: str, i: int) -> Tuple[Optional[str], int]:
    """If m[i] opens a ``{...}`` group return (contents, index_after); skips
    leading whitespace. Otherwise return (None, i)."""
    j = i
    while j < len(m) and m[j].isspace():
        j += 1
    if j < len(m) and m[j] == "{":
        return _read_brace_group(m, j)
    return None, i


def _read_brace_group(m: str, i: int) -> Tuple[str, int]:
    """Read a balanced ``{...}`` group at index *i* (m[i] == '{').

    Returns (inner_contents_without_outer_braces, index_after_closing_brace).
    Tolerates an unclosed group by consuming to end of string.
    """
    assert m[i] == "{"
    depth = 0
    j = i
    n = len(m)
    while j < n:
        ch = m[j]
        if ch == "\\":
            j += 2  # skip escaped char
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return m[i + 1 : j], j + 1
        j += 1
    return m[i + 1 :], n  # unterminated -> take the rest
