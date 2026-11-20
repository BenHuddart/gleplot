"""The ``! gleplot:`` metadata comment block: emit and parse (pure module).

``.gle`` has no native concept of a few gleplot-specific, non-GLE-semantic
settings (canvas DPI, whether subplots share axes, the marker-size scale
factor, the style's default line width and colours, and which series were plotted from an *imported* copy of an external
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
    ! gleplot: default_linewidth = 1.5
    ! gleplot: default_color = BLUE
    ! gleplot: default_marker_color = BLUE
    ! gleplot: import-data = data_0.dat, data_1.dat
    ! gleplot: insets = 3
    ! gleplot-meta-end

``insets`` lists, by 1-based graph block number, the axes placed outside the
subplot grid by :meth:`gleplot.Figure.add_axes`. It is written only when the
figure has such an axes.

This module is intentionally standalone: it does not import the writer, and
nothing wires it into ``GLEWriter`` yet (that is a later phase). It only
defines the ``emit_metadata`` / ``parse_metadata`` pair plus the shared
default/type knowledge they both use so the two can never drift apart.

Versions
--------
The version marker does **not** describe the ``key = value`` lines. It
records the *page geometry* of the file the block sits in: since ``v2`` every
graph block carries an explicit frame rectangle (``amove x y``, ``size w h``
and ``scale 1 1``, SPEC 3.3), which the recognizer reads back into
:attr:`gleplot.Axes.placement`.

:func:`emit_metadata` always writes :data:`VERSION`. :func:`parse_metadata`
reads a ``v2`` block, or one with no version. A block of an older version is
not read: the file loads as hand-written GLE, and saving it writes a ``v2``
block. A newer or unparseable marker is reported and its lines are read
anyway.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "LINE_PREFIX",
    "DEFAULTS",
    "ALWAYS_EMIT",
    "VERSION",
    "emit_metadata",
    "parse_metadata",
]

# -- Format constants ---------------------------------------------------

#: Version written by :func:`emit_metadata`, and the only one
#: :func:`parse_metadata` reads (see the module docstring).
VERSION = 2

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
    "default_linewidth": 1.5,
    # None: the colour cycle (see GLEStyleConfig).
    "default_color": None,
    "default_marker_color": None,
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
        if value.is_integer():
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
    if key == "insets":
        return ", ".join(str(int(n)) for n in value)
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
        ``sharex`` / ``sharey`` (bool, or 'row'/'col'), ``msize_scale`` and
        ``default_linewidth`` (float), ``default_color`` and
        ``default_marker_color`` (GLE colour tokens),
        ``import-data`` (list of str filenames), ``insets`` (list of int
        graph numbers, emitted only when present). Unknown keys are emitted
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
    known_order = (
        "dpi",
        "sharex",
        "sharey",
        "msize_scale",
        "default_linewidth",
        "default_color",
        "default_marker_color",
    )
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
        lines.append(
            f"{LINE_PREFIX} import-data = {_format_value('import-data', data['import-data'])}"
        )

    # Any remaining (unknown / forward-compat) keys, in insertion order.
    for key, value in data.items():
        if key in seen:
            continue
        lines.append(f"{LINE_PREFIX} {key} = {_format_value(key, value)}")

    lines.append(END_MARKER)
    return lines


def _older_version(marker: str) -> bool:
    """True if ``marker`` (after ``! gleplot-meta-begin``) is ``vN``, N < VERSION."""
    match = re.fullmatch(r"v([0-9]+)", marker)
    return match is not None and int(match.group(1)) < VERSION


def _version_warnings(marker: str) -> List[str]:
    """Warnings for a ``! gleplot-meta-begin`` marker's version suffix.

    ``marker`` is everything after ``! gleplot-meta-begin`` (e.g. ``"v2"``),
    already stripped; an empty string means the marker carried no version.
    The current :data:`VERSION`, or no suffix at all, is silent.
    """
    if not marker or marker == f"v{VERSION}":
        return []
    if _older_version(marker):
        return [
            f"file uses gleplot metadata {marker}, which gleplot no longer "
            f"reads; it loads as hand-written GLE, and saving writes a "
            f"v{VERSION} block."
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
    if key == "insets":
        return [int(n) for n in _split_list(raw)]
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
    A block of a version older than :data:`VERSION` is not read: it yields
    no data and one warning saying the file loads as hand-written GLE. A
    newer or unparseable version yields the "unrecognized version" warning
    and its lines are read anyway. Neither raises. See the module docstring.
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
                rest = stripped[len("! gleplot-meta-begin") :].strip()
                warnings.extend(_version_warnings(rest))
                if _older_version(rest):
                    return {}, warnings
            continue

        if stripped == END_MARKER:
            break

        if not stripped.startswith(LINE_PREFIX):
            warnings.append(f"Skipping malformed metadata line: {line!r}")
            continue

        payload = stripped[len(LINE_PREFIX) :].strip()
        if "=" not in payload:
            warnings.append(f"Skipping malformed metadata line (no '='): {line!r}")
            continue

        key, _, raw_value = payload.partition("=")
        key = key.strip()
        if not key:
            warnings.append(f"Skipping malformed metadata line (empty key): {line!r}")
            continue

        try:
            data[key] = _parse_value(key, raw_value)
        except ValueError:
            warnings.append(f"Skipping malformed metadata line (bad value): {line!r}")

    if not found_block:
        return {}, []

    return data, warnings
