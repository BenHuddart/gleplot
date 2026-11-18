"""Per-series visibility -- the ``visible`` field (G11; GLEstudio SPEC 14.6).

The rule, stated once and asserted here from every angle: **a hidden series
affects nothing rendered.** The writer skips its *entire* emission -- its
``.dat`` sidecar, its ``dN``/``data`` display commands and its ``key "..."``
legend entry -- and it drops out of auto-limit computation, so limits may
re-fit when a series is hidden. Explicit limits are untouched.

What is deliberately NOT affected: the model. A hidden series keeps its
arrays, its label, its reserved data-file name and its place in the series
list, which is what makes un-hiding restore byte-identical output (the
``.glez`` round trip is lossless by construction -- SPEC 5 never parses the
informative ``figure.gle`` back).

Hidden is orthogonal to dangling (SPEC 3.2): "hidden because asked" and
"skipped because broken" are different states and neither is reported as the
other -- a hidden series produces no ``DanglingSourceRef``, whatever its
reference does.
"""

import copy
import json

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure
from gleplot import axes as _gleplot_axes
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.series import SERIES_CLASSES, is_visible
from gleplot.sources import ColumnRef, DictDataProvider, TableData
from gleplot.writer import resolve_figure

# -- helpers ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_counter():
    """Deterministic global data-file counter around every test."""
    _gleplot_axes._global_data_file_counter = 0
    glp.close()
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        glp.close()


def _generate(fig, **kwargs):
    """``(gle_text, {sidecar: content})`` for ``fig``."""
    return fig._generate_gle_with_files(**kwargs)


def _from(snapshot):
    """A fresh figure rebuilt from a ``to_dict`` snapshot.

    Generation resolves auto-limits back onto the axes (the snapshot
    discipline GLEstudio SPEC 6.1 exists for), so every state under
    comparison has to start from the same unresolved snapshot rather than
    from a figure some earlier generation already baked limits into.
    """
    return Figure.from_dict(copy.deepcopy(snapshot))


def _hide(payload, attr, index):
    """Set ``visible = False`` on one series of a ``to_dict`` payload."""
    payload = copy.deepcopy(payload)
    payload["figure"]["axes"][0][attr][index]["visible"] = False
    return payload


def _two_line_figure():
    fig = glp.figure(figsize=(8, 6), data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.0, 2.0], color="red", label="kept")
    ax.plot([1.0, 2.0], [3.0, 4.0], color="blue", label="gone")
    return fig, ax


# -- the model: absent means visible ------------------------------------------


def test_visible_is_absent_by_default_on_every_drawable_kind():
    """The InlineData rule again: absent is the default, not ``True``.

    Storing ``visible = True`` on construction would put a new key into every
    series ever serialized, changing the ``to_dict`` bytes of every existing
    project for no gain.
    """
    for series_cls in SERIES_CLASSES.values():
        if "visible" not in series_cls.FIELDS:
            continue
        blank = series_cls()
        assert "visible" not in blank
        assert is_visible(blank) is True


def test_is_visible_reads_the_field():
    line = SERIES_CLASSES["lines"](visible=False)
    assert is_visible(line) is False
    line["visible"] = True
    assert is_visible(line) is True


def test_is_visible_treats_a_null_as_visible():
    """A malformed value must not silently hide a series (SPEC 8.1.4)."""
    assert is_visible(SERIES_CLASSES["lines"](visible=None)) is True


def test_the_plotting_api_leaves_visible_absent():
    _fig, ax = _two_line_figure()
    assert "visible" not in ax.lines[0]
    assert "visible" not in ax.lines[1]


# -- writer: the entire emission is skipped -----------------------------------


def test_hidden_series_omits_dataset_draw_command_and_sidecar():
    """The filed G11 acceptance: the ``.gle`` loses the series entirely...

    ...while the model keeps its numbers, ready for a later un-hide.
    """
    fig, ax = _two_line_figure()
    hidden_file = ax.lines[1]["data_file"]
    kept_file = ax.lines[0]["data_file"]
    ax.lines[1]["visible"] = False

    text, data_files = _generate(fig)

    assert hidden_file not in data_files
    assert hidden_file not in text
    assert kept_file in data_files
    assert kept_file in text
    # Exactly one dataset survives, so exactly one display command is emitted.
    assert len([ln for ln in text.splitlines() if ln.strip().startswith("d1 ")]) == 1
    assert not [ln for ln in text.splitlines() if ln.strip().startswith("d2 ")]

    # The model is untouched: the hidden series still has its data.
    assert np.array_equal(ax.lines[1]["y"], np.array([3.0, 4.0]))
    assert ax.lines[1]["label"] == "gone"
    assert ax.lines[1]["data_file"] == hidden_file


def test_hidden_series_key_is_absent_from_the_legend():
    """SPEC 14.6: the legend omits hidden entries."""
    fig, ax = _two_line_figure()
    ax.legend()
    ax.lines[1]["visible"] = False

    text, _files = _generate(fig)

    assert 'key "kept"' in text
    assert 'key "gone"' not in text
    assert "key pos" in text


def test_hiding_the_only_labelled_series_drops_the_auto_legend():
    """An auto legend exists because labels do; hide them all and it goes."""
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.0, 2.0], label="only")
    assert "key pos" in _generate(_from(fig.to_dict()))[0]

    hidden = _hide(fig.to_dict(), "lines", 0)
    text, _files = _generate(_from(hidden))
    assert "key pos" not in text
    # Nothing labelled is left, so there is no implicit key to switch off.
    assert "key off" not in text


def test_hidden_series_leaves_an_explicit_legend_alone():
    """``legend(on)`` is a user choice about the key, not about the series."""
    fig, ax = _two_line_figure()
    ax.legend()
    ax.lines[0]["visible"] = False
    ax.lines[1]["visible"] = False

    text, _files = _generate(fig)
    assert "key pos" in text


# -- auto-limits ---------------------------------------------------------------


def test_auto_limits_refit_when_the_only_wide_ranged_series_is_hidden():
    """SPEC 14.6, stated as the rule: hidden series do not hold the axes open."""
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0], label="narrow")
    ax.plot([0.0, 100.0], [0.0, 100.0], label="wide")
    snapshot = fig.to_dict()

    shown = _from(snapshot)
    _generate(shown)
    assert shown.axes_list[0].xmax == 100.0
    assert shown.axes_list[0].ymax == 100.0

    hidden = _from(_hide(snapshot, "lines", 1))
    text, _files = _generate(hidden)
    assert hidden.axes_list[0].xmax == 1.0
    assert hidden.axes_list[0].ymax == 1.0
    assert "max 100" not in text


def test_explicit_limits_are_untouched_by_hiding():
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.plot([0.0, 100.0], [0.0, 100.0])
    ax.set_xlim(-5.0, 250.0)
    ax.set_ylim(-5.0, 250.0)
    snapshot = fig.to_dict()

    hidden = _from(_hide(snapshot, "lines", 1))
    _generate(hidden)
    assert (hidden.axes_list[0].xmin, hidden.axes_list[0].xmax) == (-5.0, 250.0)
    assert (hidden.axes_list[0].ymin, hidden.axes_list[0].ymax) == (-5.0, 250.0)


def test_a_hidden_vertical_guide_does_not_hold_the_x_axis_open():
    """Guides autoscale like matplotlib's axvline -- unless they are hidden."""
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.axvline(50.0)
    snapshot = fig.to_dict()

    shown = _from(snapshot)
    _generate(shown)
    assert shown.axes_list[0].xmax == 50.0

    hidden = _from(_hide(snapshot, "reflines", 0))
    _generate(hidden)
    assert hidden.axes_list[0].xmax == 1.0


def test_hidden_heatmap_extent_does_not_hold_the_axes_open():
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.imshow(np.arange(12, dtype=float).reshape(3, 4), extent=(0, 40, 0, 30))
    snapshot = fig.to_dict()

    hidden = _from(_hide(snapshot, "heatmaps", 0))
    text, data_files = _generate(hidden)
    assert hidden.axes_list[0].xmax == 1.0
    assert "colormap" not in text
    assert not [name for name in data_files if name.endswith(".z")]


# -- every drawable kind -------------------------------------------------------


def _one_of_each_kind():
    """A figure with exactly one series of every visibility-bearing kind."""
    fig = glp.figure(figsize=(8, 10), data_prefix="vis")
    ax = fig.add_subplot(211)
    ax.plot([1.0, 2.0], [3.0, 4.0], marker="o", label="line")
    ax.scatter([1.0, 2.0], [3.0, 4.0], label="scatter")
    ax.bar([1.0, 2.0], [3.0, 4.0], color="red", label="bar")
    ax.fill_between([1.0, 2.0], [0.0, 1.0], [3.0, 4.0], label="fill")
    ax.errorbar([1.0, 2.0], [3.0, 4.0], yerr=[0.1, 0.2], capsize=3, label="err")
    ax.line_from_file("ext.dat", 1, 2, label="fline")
    ax.axvline(1.5, label="vline")
    ax.axvspan(1.0, 1.2, label="vspan")
    ax.hist([0.0, 0.4, 0.8], bins=4, range=(0, 1), histtype="step", label="hist")
    ax.function("sin(x)", xmin=1, xmax=2, label="fn")

    ax2 = fig.add_subplot(212)
    ax2.imshow(np.arange(12, dtype=float).reshape(3, 4), extent=(0, 4, 0, 3))
    ax2.contour(
        np.linspace(0, 4, 4),
        np.linspace(0, 3, 3),
        np.arange(12, dtype=float).reshape(3, 4),
        levels=[2.0, 6.0],
    )
    return fig


def _visibility_bearing_attrs():
    return [attr for attr, cls in SERIES_CLASSES.items() if "visible" in cls.FIELDS]


def test_every_visibility_bearing_kind_can_be_hidden_out_of_the_script():
    """Hiding every series of every kind empties the script of all of them.

    Kind-by-kind rather than wholesale, so a kind whose emission path does
    not consult ``visible`` fails on its own line rather than hiding behind
    the others.
    """
    covered = set()
    for attr in _visibility_bearing_attrs():
        fig = _one_of_each_kind()
        shown_text, shown_files = _generate(fig)

        fig = _one_of_each_kind()
        found = False
        for ax in fig.axes_list:
            for series in getattr(ax, attr):
                series["visible"] = False
                found = True
        assert found, f"the coverage figure produces no {attr!r} series"
        covered.add(attr)

        hidden_text, hidden_files = _generate(fig)
        assert hidden_text != shown_text, (
            f"hiding every {attr!r} series changed nothing in the emitted "
            "script; its emission path does not consult 'visible'"
        )
        assert len(hidden_files) <= len(shown_files)

    assert covered == set(_visibility_bearing_attrs())


def _hide_everything(fig):
    for ax in fig.axes_list:
        for attr in _visibility_bearing_attrs():
            for series in getattr(ax, attr):
                series["visible"] = False
    return fig


def test_hiding_everything_still_writes_a_valid_empty_script():
    text, data_files = _generate(_hide_everything(_one_of_each_kind()))
    assert data_files == {}
    assert "begin graph" in text and "end graph" in text
    assert not [ln for ln in text.splitlines() if ln.strip().startswith("d1 ")]


@pytest.mark.gle
def test_a_figure_with_everything_hidden_compiles(tmp_path):
    """Emptying a graph block of its data must not emit a script GLE rejects.

    The script-level checks above prove what is *absent*; only the engine
    proves that what is left is still a legal document.
    """
    out = tmp_path / "hidden.pdf"
    _hide_everything(_one_of_each_kind()).savefig(str(out))
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.gle
def test_a_partly_hidden_figure_compiles(tmp_path):
    """Some hidden, some not -- the case the GUI checkbox actually produces."""
    fig = glp.figure(figsize=(6, 4), data_prefix="part")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0, 3.0], [1.0, 4.0, 9.0], label="shown")
    ax.plot([1.0, 2.0, 3.0], [9.0, 4.0, 1.0], label="hidden")
    ax.bar([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], label="bars")
    ax.axvline(2.0, label="guide")
    ax.axhspan(1.0, 2.0, label="band")
    ax.legend()

    ax.lines[1]["visible"] = False
    ax.reflines[0]["visible"] = False

    out = tmp_path / "partial.pdf"
    fig.savefig(str(out))
    assert out.exists() and out.stat().st_size > 0


# -- round trips ---------------------------------------------------------------


def test_hide_then_unhide_round_trips_to_byte_identical_gle():
    """SPEC 14.6's sharpened rule, and the whole point of keeping the model."""
    fig, _ax = _two_line_figure()
    snapshot = fig.to_dict()

    shown_text, shown_files = _generate(_from(snapshot))
    hidden_text, hidden_files = _generate(_from(_hide(snapshot, "lines", 1)))

    toggled_back = _hide(snapshot, "lines", 1)
    toggled_back["figure"]["axes"][0]["lines"][1]["visible"] = True
    back_text, back_files = _generate(_from(toggled_back))

    assert hidden_text != shown_text
    assert back_text == shown_text
    assert back_files == shown_files


def test_hiding_a_series_emits_exactly_what_removing_it_would():
    """ "Affects nothing rendered", stated as an equality rather than a list.

    Every consequence checked one at a time above -- no sidecar, no display
    command, no key, re-fitted limits -- collapses into this: the script for
    a figure with a hidden series is byte-identical to the script for the
    same figure with that series deleted outright.
    """
    fig, ax = _two_line_figure()
    ax.plot([1.0, 2.0], [5.0, 60.0], color="green", label="third")
    snapshot = fig.to_dict()

    hidden = _from(_hide(snapshot, "lines", 1))
    hidden_text, hidden_files = _generate(hidden)

    removed = _from(snapshot)
    del removed.axes_list[0].lines[1]
    removed_text, removed_files = _generate(removed)

    assert hidden_text == removed_text
    assert hidden_files == removed_files


def test_an_explicit_visible_true_emits_exactly_what_an_absent_one_does():
    fig, _ax = _two_line_figure()
    snapshot = fig.to_dict()

    absent_text, absent_files = _generate(_from(snapshot))

    explicit = copy.deepcopy(snapshot)
    for line in explicit["figure"]["axes"][0]["lines"]:
        line["visible"] = True
    explicit_text, explicit_files = _generate(_from(explicit))

    assert explicit_text == absent_text
    assert explicit_files == absent_files


def test_visible_survives_a_to_dict_from_dict_round_trip_as_a_bool():
    fig, ax = _two_line_figure()
    ax.lines[1]["visible"] = False

    once = fig.to_dict()
    json.dumps(once)
    restored = Figure.from_dict(once)
    assert restored.to_dict() == once
    assert restored.axes_list[0].lines[1]["visible"] is False
    assert "visible" not in restored.axes_list[0].lines[0]


def test_a_figure_with_a_hidden_series_is_a_writer_recognizer_fixed_point(tmp_path):
    """The battery's invariant, checked on the one shape it cannot build.

    ``figure.gle`` is informative and simply omits the hidden series, so the
    parsed-back figure has one series fewer -- but the *text* must still be a
    fixed point, which is what the empty-exemption-set fixed-point test
    guarantees for everything else.
    """

    def _save(fig, directory):
        directory.mkdir()
        gle_path = directory / "figure.gle"
        fig.savefig_gle(str(gle_path))
        return (
            gle_path.read_text(encoding="utf-8"),
            {p.name: p.read_bytes() for p in directory.iterdir() if p.suffix == ".dat"},
        )

    fig, ax = _two_line_figure()
    hidden_file = ax.lines[1]["data_file"]
    ax.lines[1]["visible"] = False
    text1, data1 = _save(fig, tmp_path / "first")
    assert hidden_file not in data1

    _gleplot_axes._global_data_file_counter = 0
    recognized = parse_gle_figure(tmp_path / "first" / "figure.gle")
    text2, data2 = _save(recognized.figure, tmp_path / "second")

    assert text2 == text1
    assert data2 == data1


# -- hidden is not dangling ----------------------------------------------------


def _provider():
    return DictDataProvider(
        {"t1": TableData.from_mapping({"a": [1.0, 2.0], "b": [3.0, 4.0]})}
    )


def test_a_hidden_series_is_skipped_without_a_dangling_record():
    """Hidden and dangling are orthogonal and must never be reported as one.

    GLEstudio's structure tree badges dangling references from a live model
    query, not from write-time records, so suppressing the record here loses
    no signal -- it only stops every render warning about a series the user
    deliberately switched off.
    """
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.0, 2.0])
    ax.lines[0]["data_source"] = ColumnRef("nope", {"x": "a", "y": "b"})
    ax.lines[0]["visible"] = False

    resolution = resolve_figure(fig, _provider())
    assert resolution.warnings == []
    assert resolution.data(ax.lines[0]) is None
    assert resolution.visible(ax.lines) == []


def test_a_visible_series_with_a_broken_reference_still_reports_dangling():
    """The other half of the orthogonality: hiding is not how you silence it."""
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.0, 2.0])
    ax.lines[0]["data_source"] = ColumnRef("nope", {"x": "a", "y": "b"})

    resolution = resolve_figure(fig, _provider())
    assert len(resolution.warnings) == 1
    assert resolution.warnings[0].series_attr == "lines"


def test_a_hidden_series_does_not_donate_the_shared_sidecar_name():
    """ "Affects nothing rendered" includes not naming other series' files.

    Two series on one table share ONE sidecar, named after the first of them.
    Hide that first series and the name comes from the survivor instead --
    exactly what happens when it is dangling, and what makes the emitted
    sidecar depend only on what is actually drawn.
    """
    fig = glp.figure(data_prefix="vis")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.0, 2.0])
    ax.plot([1.0, 2.0], [3.0, 4.0])
    first_file, second_file = ax.lines[0]["data_file"], ax.lines[1]["data_file"]
    assert first_file != second_file
    for line in ax.lines:
        line["data_source"] = ColumnRef("t1", {"x": "a", "y": "b"})

    _text, shared = _generate(fig, data_provider=_provider())
    assert set(shared) == {first_file}

    # Same figure again from scratch: the reserved names have to match, so the
    # shared-sidecar name is the only thing that differs between the two runs.
    _gleplot_axes._global_data_file_counter = 0
    fig2 = glp.figure(data_prefix="vis")
    ax2 = fig2.add_subplot(111)
    ax2.plot([1.0, 2.0], [1.0, 2.0])
    ax2.plot([1.0, 2.0], [3.0, 4.0])
    for line in ax2.lines:
        line["data_source"] = ColumnRef("t1", {"x": "a", "y": "b"})
    ax2.lines[0]["visible"] = False

    _text2, shared2 = _generate(fig2, data_provider=_provider())
    assert set(shared2) == {second_file}
