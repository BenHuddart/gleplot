"""G18-lite: a materialized guide comes back a guide, keyed on its marker.

A ``RefLine``/``Span`` whose spanned axis resolves is written as a literal
two-point dataset plus an ordinary ``dN line`` / ``fill dA,dB`` command
(``Axes.materialize_reflines`` / ``materialize_spans``). Nothing in those bytes
says "guide", so every ``.gle`` re-import used to demote it to the plain
``LineSeries``/``FillSeries`` it had materialized into -- same picture, no
identity: not editable as a guide, and re-resolved against whatever range the
reparse produced rather than tracking the axis.

G18-lite closes that with a ``! gleplot:guide ...`` **comment** over the
emission (see :mod:`gleplot.guides` for the grammar and for the rule about
what may live in it -- the model residue, never anything a visible command
already states). Two properties are the whole design, and this module is where
they are pinned:

1. **Recognition keys off the literal marker, never off shape.** A
   hand-written two-point line, and every ``.gle`` gleplot wrote before
   G18-lite, parses exactly as it did before -- no inference, no guessing.
2. **A marker that disagrees with the commands beside it is dropped, with a
   note.** A file edited on one side only degrades to the plain-series parse
   that was the pre-G18-lite behaviour; the guide identity (the only thing
   already inconsistent with the file) is what is lost, and it is never
   guessed at.

The round trip they buy -- emit -> parse -> model -> emit, byte-identical
*including* the marker -- is the new fixed point, and is asserted here over
the same battery ``tests/unit/_refline_battery.py`` pins the bytes of.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import gleplot as glp
from gleplot.guides import GUIDE_MARKER_PREFIX
from gleplot.parser.recognizer import parse_gle_figure

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

import _refline_battery as rb  # noqa: E402  (path set up just above)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _write(tmp_path, text, files, stem="fig"):
    """Lay a generated figure out on disk (script + sidecars) and return it."""
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    script = tmp_path / f"{stem}.gle"
    script.write_text(text, encoding="utf-8")
    return script


def _roundtrip(fig, tmp_path, stem="fig"):
    """``(original_text, reparsed_figure, notes)`` for a generated figure."""
    text, files = fig._generate_gle_with_files()
    script = _write(tmp_path, text, files, stem)
    recognized = parse_gle_figure(str(script))
    return text, recognized.figure, recognized.warnings


def _marker_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(GUIDE_MARKER_PREFIX)
    ]


def _strip_markers(text):
    """The same script as gleplot wrote before G18-lite."""
    return re.sub(
        r"^[ \t]*" + re.escape(GUIDE_MARKER_PREFIX) + r"[^\n]*\n",
        "",
        text,
        flags=re.MULTILINE,
    )


def _four_kinds(**style):
    """A figure with one of each guide kind, over limits that resolve."""
    fig = glp.figure(data_prefix="gm")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 4.0, 9.0])
    ax.axvline(1.5, **style.get("vline", {}))
    ax.axhline(2.0, **style.get("hline", {}))
    ax.axvspan(0.5, 1.0, **style.get("vspan", {}))
    ax.axhspan(3.0, 5.0, **style.get("hspan", {}))
    return fig


# --------------------------------------------------------------------------- #
# The marker itself
# --------------------------------------------------------------------------- #


def test_every_materialized_guide_carries_exactly_one_marker():
    text, _files = _four_kinds()._generate_gle_with_files()
    assert _marker_lines(text) == [
        "! gleplot:guide span v range 0.5,1 extent 0,1",
        "! gleplot:guide span h range 3,5 extent 0,1",
        "! gleplot:guide refline v value 1.5 extent 0,1",
        "! gleplot:guide refline h value 2 extent 0,1",
    ]


def test_the_marker_stands_immediately_over_its_own_data_statement():
    text, _files = _four_kinds()._generate_gle_with_files()
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith(GUIDE_MARKER_PREFIX):
            assert lines[i + 1].startswith("data "), lines[i + 1]


def test_a_labelled_band_carries_the_label_the_fill_command_cannot():
    """``fill dA,dB`` has no ``key``; the marker keeps the span's identity.

    The legend swatch is a separate ``keyfill`` on the first fill dataset.
    """
    text, _files = _four_kinds(vspan={"label": "band"})._generate_gle_with_files()
    assert (
        '! gleplot:guide span v range 0.5,1 extent 0,1 label "band"'
        in _marker_lines(text)
    )
    assert "keyfill" in text and 'key "band"' in text


def test_a_reflines_label_is_not_duplicated_into_its_marker():
    """One source of truth: the label is already on the ``key`` clause."""
    text, _files = _four_kinds(vline={"label": "threshold"})._generate_gle_with_files()
    assert 'key "threshold"' in text
    assert all("label" not in line for line in _marker_lines(text))


def test_a_marker_carries_a_negative_coordinate_and_a_quote(tmp_path):
    fig = glp.figure(data_prefix="gm")
    ax = fig.add_subplot(111)
    ax.plot([-5.0, 5.0], [-5.0, 5.0])
    ax.axvline(-2.5)
    ax.axvspan(-4.0, -3.0, label='a "quoted" band')
    _text, parsed, notes = _roundtrip(fig, tmp_path)

    assert notes == []
    ax2 = parsed.axes_list[0]
    assert ax2.reflines[0]["value"] == pytest.approx(-2.5)
    assert (ax2.spans[0]["start"], ax2.spans[0]["end"]) == (-4.0, -3.0)
    assert ax2.spans[0]["label"] == 'a "quoted" band'


@pytest.mark.parametrize("label", ['say "hi"', '5"', "C:\\dir\\"])
def test_a_marker_label_ending_in_a_quote_or_backslash_comes_back(label, tmp_path):
    """The marker's backslash escape is read apart from GLE's string rules."""
    fig = glp.figure(data_prefix="gm")
    fig.add_subplot(111).axvspan(1.0, 2.0, label=label)
    text, parsed, notes = _roundtrip(fig, tmp_path)
    assert notes == []
    assert parsed.axes_list[0].spans[0]["label"] == label
    assert parsed._generate_gle_with_files()[0] == text


# --------------------------------------------------------------------------- #
# Emit -> parse -> the same model
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "style",
    [
        pytest.param({}, id="plain"),
        pytest.param(
            {
                "vline": {"ymin": 0.25, "ymax": 0.75},
                "hline": {"xmin": 0.1, "xmax": 0.4},
                "vspan": {"ymin": 0.2, "ymax": 0.6},
                "hspan": {"xmin": 0.3, "xmax": 0.9},
            },
            id="fractional-extents",
        ),
        pytest.param(
            {
                "vline": {
                    "color": "red",
                    "linestyle": "--",
                    "linewidth": 2.0,
                    "label": "threshold",
                },
                "hline": {"color": "#336699", "linestyle": ":", "linewidth": 0.5},
                "vspan": {"color": "orange", "label": "band"},
                "hspan": {"color": "lightgray"},
            },
            id="styled-and-labelled",
        ),
    ],
)
def test_all_four_kinds_survive_the_round_trip_as_the_model_they_started_as(
    style, tmp_path
):
    fig = _four_kinds(**style)
    original = [dict(g) for g in fig.axes_list[0].reflines + fig.axes_list[0].spans]

    _text, parsed, notes = _roundtrip(fig, tmp_path)
    assert notes == []

    ax = parsed.axes_list[0]
    recovered = [dict(g) for g in ax.reflines + ax.spans]
    # Only the plotted data series is left among the plain series: all four
    # guides came back as declarations, not as what they materialized into.
    assert len(ax.lines) == 1 and ax.fills == []
    assert len(recovered) == 4
    for before, after in zip(original, recovered):
        # The one documented deviation, and it predates guides entirely: a
        # linewidth of 1 means "the style default" to the writer, which emits
        # the number (1.5 pt) and so reads it back as itself. Every other
        # field, marker-carried or command-carried, is identical.
        if before.get("linewidth") == 1:
            before = dict(before, linewidth=after["linewidth"])
        # Call order and the recovered begin-key order are how the legend
        # is sequenced. They are not part of the guide declaration.
        for key in ("_draw_seq", "legend_seq"):
            before.pop(key, None)
            after.pop(key, None)
        assert after == before


def test_a_translucent_band_comes_back_folded_exactly_as_a_plain_fill_does():
    """Not a guide deviation: apply_alpha's round trip, shared with G17.

    ``alpha`` is folded into the emitted colour, and comes back as alpha 1.0
    over the folded colour text -- which is what keeps the next save
    byte-identical. The marker deliberately does not carry ``alpha``: doing so
    would need the unfolded colour too, i.e. two sources of truth for one
    visible token (see :mod:`gleplot.guides`).
    """
    fig = _four_kinds(vspan={"color": "orange", "alpha": 0.35})
    text, files = fig._generate_gle_with_files()
    assert "rgba255(255,165,0,89)" in text
    assert all("alpha" not in line for line in _marker_lines(text))


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_the_whole_guide_battery_is_a_fixed_point_including_its_markers(name, tmp_path):
    """The new fixed point: emit -> parse -> emit, byte-identical WITH markers.

    The pre-G18-lite fixed point was over files with no markers in them, and
    ``tests/parser/test_fixed_point.py`` still holds it for the golden and
    project batteries. This is the marker-preserving half: a file gleplot
    wrote must re-emit itself, marker lines and all, or the marker is not a
    round-trip carrier at all.
    """
    provider_factory = rb.PROVIDERS.get(name)
    provider = provider_factory() if provider_factory else None
    fig = dict(zip(rb.BUILDER_IDS, rb.BUILDERS))[name]()
    text, files = fig._generate_gle_with_files(data_provider=provider)

    script = _write(tmp_path, text, files)
    recognized = parse_gle_figure(str(script))
    assert recognized.warnings == []

    again, again_files = recognized.figure._generate_gle_with_files(
        data_provider=provider
    )
    assert again == text
    assert again_files == files


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_no_marker_ever_reaches_passthrough(name, tmp_path):
    """A marker is gleplot's byte: consumed, never preserved as raw text.

    A marker that survived as passthrough would be re-emitted wherever
    passthrough lands -- possibly over a dataset it does not describe, which
    is the one way a marker could ever tell a lie.
    """
    provider_factory = rb.PROVIDERS.get(name)
    provider = provider_factory() if provider_factory else None
    fig = dict(zip(rb.BUILDER_IDS, rb.BUILDERS))[name]()
    text, files = fig._generate_gle_with_files(data_provider=provider)

    recognized = parse_gle_figure(str(_write(tmp_path, text, files)))
    for ax in recognized.figure.axes_list:
        assert not any(GUIDE_MARKER_PREFIX in line for line in ax.passthrough)


def test_a_hidden_guide_emits_no_marker_because_it_emits_nothing(tmp_path):
    fig = _four_kinds()
    fig.axes_list[0].reflines[0]["visible"] = False
    text, _files = fig._generate_gle_with_files()
    assert _marker_lines(text) == [
        "! gleplot:guide span v range 0.5,1 extent 0,1",
        "! gleplot:guide span h range 3,5 extent 0,1",
        "! gleplot:guide refline h value 2 extent 0,1",
    ]


# --------------------------------------------------------------------------- #
# No shape inference: what is NOT a guide stays not a guide
# --------------------------------------------------------------------------- #


#: The exact shape a materialized ``axvline`` emits -- a two-point dataset at
#: one x, spanning the whole y range -- with no marker over it. ``{meta}`` is
#: how the file declares the sidecar an import rather than a reference, which
#: is the difference between a ``LineSeries`` and a ``FileSeries`` and has
#: nothing to do with guides.
_HAND_WRITTEN = """{meta}size 20.32 15.24
amove 1.69312 1.26984
begin graph
   size 17.992 13.3352
   scale 1 1
   xaxis min 0 max 3
   yaxis min 0 max 9
   data hand.dat d1=c1,c2
   d1 line color BLACK lwidth 0.05292 key ""
end graph
"""

_IMPORT_META = """! gleplot-meta-begin v2
! gleplot: import-data = hand.dat
! gleplot-meta-end

"""


@pytest.mark.parametrize(
    "meta, attr",
    [
        pytest.param("", "file_series", id="file-reference"),
        pytest.param(_IMPORT_META, "lines", id="imported-series"),
    ],
)
def test_an_unmarked_two_point_line_is_still_just_a_line(meta, attr, tmp_path):
    """The shape of a guide is not evidence of one. Recognition needs the marker."""
    (tmp_path / "hand.dat").write_text("1.5 0\n1.5 9\n", encoding="utf-8")
    (tmp_path / "hand.gle").write_text(
        _HAND_WRITTEN.format(meta=meta), encoding="utf-8"
    )

    recognized = parse_gle_figure(str(tmp_path / "hand.gle"))
    ax = recognized.figure.axes_list[0]
    assert ax.reflines == [] and ax.spans == []
    assert len(getattr(ax, attr)) == 1


def test_a_pre_g18_lite_gleplot_file_parses_exactly_as_it_used_to(tmp_path):
    """Old files carry no markers, so they keep the old (lossy) recovery."""
    text, files = _four_kinds()._generate_gle_with_files()
    script = _write(tmp_path, _strip_markers(text), files)

    recognized = parse_gle_figure(str(script))
    ax = recognized.figure.axes_list[0]
    assert ax.reflines == [] and ax.spans == []
    assert len(ax.lines) == 3  # the data series and the two guide lines
    assert len(ax.fills) == 2  # the two bands
    assert not any(GUIDE_MARKER_PREFIX in w for w in recognized.warnings)


# --------------------------------------------------------------------------- #
# Tampering: the marker and its emission disagree
# --------------------------------------------------------------------------- #


def _tampered(tmp_path, mutate_text=None, mutate_files=None, stem="fig"):
    """Emit ``_four_kinds()``, edit one side of it, and parse the result."""
    text, files = _four_kinds()._generate_gle_with_files()
    if mutate_files is not None:
        files = mutate_files(dict(files))
    if mutate_text is not None:
        text = mutate_text(text)
    recognized = parse_gle_figure(str(_write(tmp_path, text, files, stem)))
    return recognized


def _guide_notes(recognized):
    return [w for w in recognized.warnings if GUIDE_MARKER_PREFIX in w]


def test_a_guide_moved_in_its_sidecar_degrades_to_a_plain_line(tmp_path):
    """The marker says 1.5, the rows say 2.5: the file was edited. No guess."""

    def move_the_rows(files):
        for name, content in list(files.items()):
            if content.startswith("x y\n1.5"):
                files[name] = content.replace("1.5", "2.5")
        return files

    recognized = _tampered(tmp_path, mutate_files=move_the_rows)
    ax = recognized.figure.axes_list[0]

    # The vline is gone from the guides and back among the plain lines --
    # with the user's own coordinate, not the marker's.
    assert [g["orient"] for g in ax.reflines] == ["h"]
    assert any(list(line["x"]) == [2.5, 2.5] for line in ax.lines)

    notes = _guide_notes(recognized)
    assert len(notes) == 1
    assert notes[0].startswith("structure:")
    assert "refline v value 1.5" in notes[0]


def test_a_band_moved_in_its_sidecar_degrades_to_a_plain_fill(tmp_path):
    def move_the_band(files):
        for name, content in list(files.items()):
            if content.startswith("x upper lower\n0.5"):
                files[name] = content.replace("0.5", "0.75")
        return files

    recognized = _tampered(tmp_path, mutate_files=move_the_band)
    ax = recognized.figure.axes_list[0]
    assert [g["orient"] for g in ax.spans] == ["h"]
    assert len(ax.fills) == 1
    assert len(_guide_notes(recognized)) == 1


def test_a_restyled_guide_line_that_no_guide_could_have_emitted_degrades(tmp_path):
    """A marker on a marker-carrying series: nothing gleplot ever wrote."""

    def add_a_marker_symbol(text):
        return text.replace(
            "d5 line color BLACK lwidth 0.05292",
            "d5 line marker circle msize 0.2 color BLACK lwidth 0.05292",
        )

    recognized = _tampered(tmp_path, mutate_text=add_a_marker_symbol)
    ax = recognized.figure.axes_list[0]
    assert [g["orient"] for g in ax.reflines] == ["h"]
    assert len(_guide_notes(recognized)) == 1


def test_a_marker_whose_display_command_was_deleted_degrades(tmp_path):
    def delete_the_line(text):
        return "\n".join(
            line
            for line in text.splitlines()
            if not line.strip().startswith("d5 line color BLACK")
        )

    recognized = _tampered(tmp_path, mutate_text=delete_the_line)
    ax = recognized.figure.axes_list[0]
    assert [g["orient"] for g in ax.reflines] == ["h"]
    assert len(_guide_notes(recognized)) == 1


def test_a_mangled_marker_is_dropped_and_noted_not_half_read(tmp_path):
    def mangle(text):
        return text.replace(
            "! gleplot:guide refline v value 1.5 extent 0,1",
            "! gleplot:guide refline v value 1.5 extent 0,",
        )

    recognized = _tampered(tmp_path, mutate_text=mangle)
    ax = recognized.figure.axes_list[0]
    assert [g["orient"] for g in ax.reflines] == ["h"]
    assert len(ax.lines) == 2  # the data series and the demoted guide
    notes = _guide_notes(recognized)
    assert len(notes) == 1
    assert "not a readable gleplot guide marker" in notes[0]


def test_a_marker_over_the_wrong_statement_is_dropped_and_noted(tmp_path):
    """Moved away from its ``data`` line, a marker claims nothing at all."""

    def move_the_marker(text):
        marker = "    ! gleplot:guide refline v value 1.5 extent 0,1"
        return text.replace(marker + "\n", "").replace(
            "    data gm_0.dat", marker + "\n    data gm_0.dat"
        )

    recognized = _tampered(tmp_path, mutate_text=move_the_marker)
    ax = recognized.figure.axes_list[0]
    assert [g["orient"] for g in ax.reflines] == ["h"]
    assert len(_guide_notes(recognized)) == 1


def test_a_dropped_marker_never_survives_as_raw_text(tmp_path):
    """Degrading loses the marker, not the commands -- and loses it cleanly."""

    def mangle(text):
        return text.replace("refline v value 1.5", "refline v value")

    recognized = _tampered(tmp_path, mutate_text=mangle)
    figure = recognized.figure
    for ax in figure.axes_list:
        assert not any(GUIDE_MARKER_PREFIX in line for line in ax.passthrough)
    assert GUIDE_MARKER_PREFIX not in "\n".join(figure.passthrough_trailer)
    # The demoted series is still there, and still draws the same picture.
    assert len(figure.axes_list[0].lines) == 2
