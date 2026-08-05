"""The ``! gleplot:`` metadata comment block: emit and parse (pure module).

``.gle`` has no native concept of a few gleplot-specific, non-GLE-semantic
settings (canvas DPI, whether subplots share axes, the marker-size scale
factor, and which series were plotted from an *imported* copy of an external
data file vs. a live *reference* to it). These are persisted as a small,
versioned block of GLE comment lines so a ``.gle`` file round-trips through
gleplot without losing them, while remaining perfectly valid (and harmless)
GLE source to any other tool that opens it.

Format (fixed, versioned)::

    ! gleplot-meta-begin v2
    ! gleplot: dpi = 100
    ! gleplot: sharex = false
    ! gleplot: sharey = false
    ! gleplot: msize_scale = 1.0
    ! gleplot: import-data = data_0.dat, data_1.dat
    ! gleplot-meta-end

This module is intentionally standalone: it does not import the writer, and
nothing wires it into ``GLEWriter`` yet (that is a later phase). It only
defines the ``emit_metadata`` / ``parse_metadata`` pair plus the shared
default/type knowledge they both use so the two can never drift apart.

Versions and the geometry migration
-----------------------------------
The version marker does **not** describe the ``key = value`` lines (those have
never changed and are parsed identically for every known version). It describes
the *page geometry* of the file the block sits in:

``v1``
    Graph geometry is implicit. A single-plot figure was written as a bare
    ``scale auto`` (GLE auto-fits the graph to the page) and a subplot grid's
    ``amove``/``size`` cells were only reproducible by re-deriving them from
    the recovered grid + ``figsize``, so a ``subplots_adjust`` override could
    not survive a round trip.
``v2``
    Every graph block carries an explicit frame rectangle -- ``amove x y`` +
    ``size w h`` + ``scale 1 1`` (SPEC 3.3) -- which the recognizer reads back
    into :attr:`gleplot.Axes.placement`.

:func:`parse_metadata` accepts every version in :data:`SUPPORTED_VERSIONS`
without complaint; :func:`emit_metadata` always writes :data:`VERSION`.

**Migration policy.** A v1 file loads fine: its implicit geometry becomes
"auto" placement (``placement = None``) exactly as before. The first time it is
saved, the writer emits the v2 explicit placement it computes for the figure,
so the file changes geometry once -- a deliberate, one-time byte diff, with a
``metadata:`` warning on load saying so. There is no v2 -> v1 downgrade path
and none is planned: older gleplot builds parse a v2 file's marker with a
warning and still read every key, and the ``amove``/``size``/``scale 1 1``
triple they do not model is preserved verbatim rather than dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "LINE_PREFIX",
    "DEFAULTS",
    "ALWAYS_EMIT",
    "VERSION",
    "SUPPORTED_VERSIONS",
    "emit_metadata",
    "parse_metadata",
]

# -- Format constants ---------------------------------------------------

#: Version written by :func:`emit_metadata`. See the module docstring for what
#: each version means and for the v1 -> v2 geometry migration policy.
VERSION = 2

#: Versions :func:`parse_metadata` reads without complaint. Every one of them
#: uses the same ``! gleplot: key = value`` line format, so the parse itself is
#: version-independent; the marker only records how the file's page geometry
#: was written.
SUPPORTED_VERSIONS = (1, 2)

BEGIN_MARKER = f"! gleplot-meta-begin v{VERSION}"
END_MARKER = "! gleplot-meta-end"
LINE_PREFIX = "! gleplot:"

#: Known keys and their default values (used to decide what counts as
#: "non-default" for emission). ``import-data`` has no meaningful scalar
#: default -- it is handled separately (see :data:`ALWAYS_EMIT`).
DEFAULTS: Dict[str, Any] = {
    "dpi": 100,
    "sharex": False,
    "sharey": False,
    "msize_scale": 1.0,
}

#: Keys that are always emitted regardless of whether they equal their
#: default, per the spec: "Only NON-DEFAULT values need emitting except dpi
#: and the import-data list".
ALWAYS_EMIT = frozenset({"dpi", "import-data"})


def _format_scalar(value: Any) -> str:
    """Render a single metadata value as it appears after ``key = ``."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # Keep an explicit decimal point (e.g. "1.0" not "1") so re-parsing
        # infers float, not int, matching the documented example.
        if value == int(value):
            return f"{value:.1f}"
        return repr(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


def _quote_list_item(name: str) -> str:
    """Quote a list entry when a bare comma-join would corrupt it.

    Entries containing a comma, a double quote, or leading/trailing
    whitespace are wrapped in double quotes, with embedded quotes escaped
    as ``\\"``, so they survive emit -> parse unchanged.
    """
    if any(ch in name for ch in ',"') or name != name.strip():
        return '"' + name.replace('"', '\\"') + '"'
    return name


def _split_list(raw: str) -> List[str]:
    """Split a comma-list, honoring the quoting from :func:`_quote_list_item`."""
    items: List[str] = []
    i, n = 0, len(raw)
    while i < n:
        while i < n and raw[i] in " \t":
            i += 1
        if i >= n:
            break
        if raw[i] == '"':
            i += 1
            buf: List[str] = []
            while i < n:
                ch = raw[i]
                if ch == "\\" and i + 1 < n and raw[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            items.append("".join(buf))
            while i < n and raw[i] != ",":
                i += 1
            i += 1
        else:
            j = raw.find(",", i)
            if j == -1:
                j = n
            item = raw[i:j].strip()
            if item:
                items.append(item)
            i = j + 1
    return items


def _format_value(key: str, value: Any) -> str:
    if key == "import-data":
        names = value or []
        return ", ".join(_quote_list_item(str(n)) for n in names)
    return _format_scalar(value)


def emit_metadata(data: Dict[str, Any]) -> List[str]:
    """Build the ``! gleplot:`` comment block lines for ``data``.

    Parameters
    ----------
    data : dict
        Metadata values to persist. Recognized keys: ``dpi`` (int),
        ``sharex`` / ``sharey`` (bool), ``msize_scale`` (float),
        ``import-data`` (list of str filenames). Unknown keys are emitted
        verbatim (as strings) so callers can round-trip forward-compatible
        extra fields; a bare list/tuple value is rendered as a comma-list,
        anything else via ``str()``.

    Returns
    -------
    list of str
        The full block, from ``! gleplot-meta-begin v1`` through
        ``! gleplot-meta-end`` inclusive. Returns an empty list only if
        ``data`` is falsy (no block at all is emitted for an empty figure).

    Notes
    -----
    Only non-default values are emitted, except ``dpi`` and ``import-data``
    which are always emitted (``dpi`` because "no dpi line" is ambiguous
    with "dpi omitted", and ``import-data`` because an empty list is itself
    meaningful: it says no series are in import mode). A key is considered
    "default" only when it is a *known* key (present in :data:`DEFAULTS`)
    and its value equals that default; unknown keys are always emitted since
    they have no known default to compare against.
    """
    if not data:
        return []

    lines = [BEGIN_MARKER]

    # Emit known keys in the documented, stable order first.
    known_order = ("dpi", "sharex", "sharey", "msize_scale")
    seen = set()
    for key in known_order:
        seen.add(key)
        if key not in data:
            continue
        value = data[key]
        if key not in ALWAYS_EMIT and key in DEFAULTS and value == DEFAULTS[key]:
            continue
        lines.append(f"{LINE_PREFIX} {key} = {_format_value(key, value)}")

    # import-data always emitted if the key is present at all (even empty).
    if "import-data" in data:
        seen.add("import-data")
        lines.append(f"{LINE_PREFIX} import-data = {_format_value('import-data', data['import-data'])}")

    # Any remaining (unknown / forward-compat) keys, in insertion order.
    for key, value in data.items():
        if key in seen:
            continue
        lines.append(f"{LINE_PREFIX} {key} = {_format_value(key, value)}")

    lines.append(END_MARKER)
    return lines


def _version_warnings(marker: str) -> List[str]:
    """Warnings for a ``! gleplot-meta-begin`` marker's version suffix.

    ``marker`` is everything after ``! gleplot-meta-begin`` (e.g. ``"v1"``),
    already stripped; an empty string means the marker carried no version.

    Three cases:

    * the current :data:`VERSION`, or no suffix at all -- silent;
    * an older but supported version -- one ``metadata:``-free informational
      line naming the geometry migration that the next save performs (see the
      module docstring). Recovery is unaffected: the keys parse identically;
    * anything else (a newer or unparseable marker) -- the historical
      "unrecognized version" warning. Parsing still proceeds line by line.
    """
    if not marker or marker == f"v{VERSION}":
        return []
    for known in SUPPORTED_VERSIONS:
        if marker == f"v{known}" and known < VERSION:
            return [
                f"file uses gleplot metadata v{known}, in which graph geometry "
                f"is implicit; saving rewrites it as v{VERSION} with an "
                f"explicit placement rectangle per axes (a one-time geometry "
                f"change)."
            ]
    return [
        f"Unrecognized gleplot metadata version marker {marker!r}; "
        f"expected 'v{VERSION}'. Parsing line contents anyway."
    ]


def _parse_scalar(raw: str) -> Any:
    """Parse a single scalar value token: bool, int, float, else string."""
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_value(key: str, raw: str) -> Any:
    raw = raw.strip()
    if key == "import-data":
        if not raw:
            return []
        return _split_list(raw)
    return _parse_scalar(raw)


def parse_metadata(lines: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Parse a ``! gleplot:`` metadata block out of a list of source lines.

    Parameters
    ----------
    lines : list of str
        Source lines to scan (typically the whole ``.gle`` file, or just the
        preamble). Only the content between a ``! gleplot-meta-begin vN``
        line and the next ``! gleplot-meta-end`` line is considered; lines
        outside a block are ignored. If multiple blocks are present, only
        the first is parsed.

    Returns
    -------
    (dict, list of str)
        A tuple of ``(data, warnings)``. ``data`` maps each recognized key to
        its typed value (``int``/``float``/``bool``/``str``/``list[str]``);
        unknown keys are preserved with their parsed scalar value so callers
        can round-trip forward-compatible fields. If no metadata block is
        found at all, returns ``({}, [])``. Malformed lines inside a found
        block (missing ``=``, blank key) are skipped and recorded in
        ``warnings`` rather than raising.

    Notes
    -----
    Tolerant by design: the begin marker's version never affects how the block
    is read, because the ``! gleplot: key = value`` line format is identical in
    every version. A version in :data:`SUPPORTED_VERSIONS` that is older than
    :data:`VERSION` yields one informational warning about the geometry
    migration the next save performs; an unknown version yields the historical
    "unrecognized version" warning. Neither raises. See the module docstring.
    """
    data: Dict[str, Any] = {}
    warnings: List[str] = []

    in_block = False
    found_block = False
    for line in lines:
        stripped = line.strip()

        if not in_block:
            if stripped.startswith("! gleplot-meta-begin"):
                in_block = True
                found_block = True
                rest = stripped[len("! gleplot-meta-begin"):].strip()
                warnings.extend(_version_warnings(rest))
            continue

        if stripped == END_MARKER:
            break

        if not stripped.startswith(LINE_PREFIX):
            warnings.append(f"Skipping malformed metadata line: {line!r}")
            continue

        payload = stripped[len(LINE_PREFIX):].strip()
        if "=" not in payload:
            warnings.append(f"Skipping malformed metadata line (no '='): {line!r}")
            continue

        key, _, raw_value = payload.partition("=")
        key = key.strip()
        if not key:
            warnings.append(f"Skipping malformed metadata line (empty key): {line!r}")
            continue

        data[key] = _parse_value(key, raw_value)

    if not found_block:
        return {}, []

    return data, warnings
