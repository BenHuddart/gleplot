"""Unit tests for the series ``data_source`` abstraction (GLEstudio §3.2).

Three things are under test here:

1. **Inline is the default and costs nothing.** Everything the scripting API
   builds has no ``data_source`` at all and is treated as
   :class:`~gleplot.sources.InlineData`. (That the emitted bytes are unchanged
   is the fixed-point/golden battery's job; here we check the model.)
2. **A reference resolves end to end** -- provider table -> ``.dat`` sidecar
   -> the ``dN=cX,cY`` references in the ``.gle`` -- including the rule that
   several series on one table share ONE sidecar.
3. **A dangling reference never crashes a write.** The series is skipped, a
   structured record identifies it, and the script is still valid.
"""

import warnings

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure
from gleplot.series import (
    BarSeries,
    ErrorbarSeries,
    FillSeries,
    HeatmapSeries,
    LineSeries,
)
from gleplot.sources import (
    ColumnRef,
    DanglingSourceRef,
    DanglingSourceWarning,
    DictDataProvider,
    GridRef,
    InlineData,
    TableData,
    is_inline,
    source_from_dict,
    source_of,
)
from gleplot.writer import resolve_figure

# -- helpers ------------------------------------------------------------------


def _provider(**tables):
    """A provider over ``table_id=TableData`` keyword arguments."""
    return DictDataProvider(tables)


def _table(**columns):
    """A table whose column keys are their display names."""
    return TableData.from_mapping(columns)


def _renameable_table():
    """A table whose stable keys differ from its display names.

    The case the whole reference model exists for: a rename changes ``names``
    and leaves ``keys`` (and therefore every reference) untouched.
    """
    return TableData(
        keys=["k_time", "k_signal"],
        names=["time", "signal"],
        columns=[[0.0, 1.0, 2.0], [10.0, 20.0, 30.0]],
    )


def _add_line_ref(ax, table_id, x_key, y_key, data_file, label=None, color="BLUE"):
    series = LineSeries(
        type="line",
        x=None,
        y=None,
        color=color,
        marker=None,
        markersize=0.1,
        linestyle="-",
        linewidth=1.0,
        label=label,
        yaxis="y",
        offset=0.0,
        data_file=data_file,
        column_names=None,
        data_source=ColumnRef(table_id, {"x": x_key, "y": y_key}),
    )
    ax._register_series_draw_meta(series, "line")
    ax.lines.append(series)
    return series


def _generate(fig, provider=None):
    """``(gle_text, {filename: content})`` for one write."""
    return fig._generate_gle_with_files(data_provider=provider)


# -- 1. inline is the default -------------------------------------------------


def test_scripted_series_carry_no_data_source_key():
    """The scripting API produces the historical shape, untouched."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9])
    line = ax.lines[0]
    assert "data_source" not in line
    assert isinstance(source_of(line), InlineData)
    assert is_inline(line)


def test_inline_data_source_is_equivalent_to_no_key():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9])
    baseline, baseline_files = _generate(fig)

    ax.lines[0]["data_source"] = InlineData()
    text, files = _generate(fig)
    assert text == baseline
    assert files == baseline_files
    assert is_inline(ax.lines[0])


def test_resolution_returns_inline_series_unchanged_by_identity():
    """No copying for inline series -- the emission path sees the same object."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [3, 4])
    resolution = resolve_figure(fig, None)
    assert resolution.data(ax.lines[0]) is ax.lines[0]
    assert resolution.warnings == []


# -- 2. ColumnRef resolution end to end ---------------------------------------


def test_column_ref_resolves_to_sidecar_and_gle_reference():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat", label="from table")

    provider = _provider(t1=_table(time=[0.0, 1.0, 2.0], signal=[5.0, 6.0, 7.0]))
    text, files = _generate(fig, provider)

    assert fig.source_warnings == []
    assert set(files) == {"u_0.dat"}
    assert files["u_0.dat"] == "time signal\n0 5\n1 6\n2 7\n"
    assert "data u_0.dat d1=c1,c2" in text
    assert 'key "from table"' in text


def test_column_ref_uses_display_names_not_keys_for_the_header():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "k_time", "k_signal", "u_0.dat")

    _text, files = _generate(fig, _provider(t1=_renameable_table()))
    assert files["u_0.dat"].splitlines()[0] == "time signal"


def test_renaming_a_column_does_not_break_the_reference():
    """Rename is rebind-free (§3.2): keys are stable, names are display."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "k_signal", "k_time", "u_0.dat")

    table = _renameable_table()
    _text, before = _generate(fig, _provider(t1=table))
    assert before["u_0.dat"].splitlines()[0] == "signal time"

    table.names[1] = "amplitude"  # rename 'signal' in the spreadsheet
    _text, after = _generate(fig, _provider(t1=table))

    assert fig.source_warnings == []
    # Same values in the same columns; only the header text changed.
    assert before["u_0.dat"].splitlines()[1:] == after["u_0.dat"].splitlines()[1:]
    assert after["u_0.dat"].splitlines()[0] == "amplitude time"


def test_column_ref_series_autoscales_from_resolved_values():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat")

    _generate(fig, _provider(t1=_table(time=[2.0, 4.0], signal=[-1.0, 9.0])))
    assert (ax.xmin, ax.xmax) == (2.0, 4.0)
    assert (ax.ymin, ax.ymax) == (-1.0, 9.0)


def test_errorbar_column_ref_resolves_every_role():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    series = ErrorbarSeries(
        type="errorbar",
        x=None,
        y=None,
        yerr_up=None,
        yerr_down=None,
        xerr_left=None,
        xerr_right=None,
        color="RED",
        marker="circle",
        markersize=0.1,
        linestyle="none",
        linewidth=1.0,
        label="meas",
        capsize=None,
        gle_capsize=None,
        yaxis="y",
        offset=0.0,
        data_file="u_0.dat",
        column_names=None,
        data_source=ColumnRef(
            "t1", {"x": "t", "y": "v", "yerr_up": "e", "yerr_down": "e"}
        ),
    )
    ax._register_series_draw_meta(series, "errorbar")
    ax.errorbars.append(series)

    provider = _provider(t1=_table(t=[0.0, 1.0], v=[3.0, 4.0], e=[0.5, 0.25]))
    text, files = _generate(fig, provider)

    assert fig.source_warnings == []
    # yerr_up and yerr_down name the SAME column, so the errors are symmetric
    # and the file holds three columns, not four.
    assert files["u_0.dat"] == "t v e\n0 3 0.5\n1 4 0.25\n"
    assert "d1=c1,c2 d2=c1,c3" in text
    assert " err d2" in text


def test_bar_and_fill_column_refs_resolve():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    bar = BarSeries(
        x=None,
        height=None,
        colors=["RED"],
        label=None,
        data_file="u_0.dat",
        column_names=None,
        data_source=ColumnRef("t1", {"x": "pos", "height": "h"}),
    )
    ax._register_series_draw_meta(bar, "bar")
    ax.bars.append(bar)
    fill = FillSeries(
        x=None,
        y1=None,
        y2=None,
        color="LIGHTBLUE",
        alpha=1.0,
        label=None,
        offset=0.0,
        data_file="u_1.dat",
        column_names=None,
        data_source=ColumnRef("t1", {"x": "pos", "y1": "lo", "y2": "hi"}),
    )
    ax.fills.append(fill)

    provider = _provider(
        t1=_table(pos=[0.0, 1.0], h=[2.0, 3.0], lo=[0.0, 0.5], hi=[4.0, 4.5])
    )
    text, files = _generate(fig, provider)

    assert fig.source_warnings == []
    # One table -> one sidecar, holding the union of all four columns.
    assert set(files) == {"u_0.dat"}
    assert files["u_0.dat"].splitlines()[0] == "pos lo hi h"
    # The fill is emitted first (background layer), so it claims d1/d2.
    assert "data u_0.dat d1=c1,c2 d2=c1,c3" in text
    assert "data u_0.dat d3=c1,c4" in text


# -- shared sidecars ----------------------------------------------------------


def test_two_series_on_one_table_share_one_sidecar():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "a", "u_0.dat", label="a")
    _add_line_ref(ax, "t1", "time", "b", "u_1.dat", label="b")

    provider = _provider(t1=_table(time=[0.0, 1.0], a=[1.0, 2.0], b=[3.0, 4.0]))
    text, files = _generate(fig, provider)

    # One file, named after the FIRST referencing series, with one header row
    # and the union of the referenced columns (x written once).
    assert set(files) == {"u_0.dat"}
    assert files["u_0.dat"] == "time a b\n0 1 3\n1 2 4\n"
    assert "data u_0.dat d1=c1,c2" in text
    assert "data u_0.dat d2=c1,c3" in text
    assert "u_1.dat" not in text


def test_series_on_different_tables_get_different_sidecars():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "a", "u_0.dat")
    _add_line_ref(ax, "t2", "time", "a", "u_1.dat")

    provider = _provider(
        t1=_table(time=[0.0, 1.0], a=[1.0, 2.0]),
        t2=_table(time=[5.0, 6.0], a=[7.0, 8.0]),
    )
    _text, files = _generate(fig, provider)
    assert set(files) == {"u_0.dat", "u_1.dat"}


def test_sharing_spans_axes_and_is_stable_across_writes():
    fig = glp.figure(figsize=(8, 8), data_prefix="u")
    ax1 = fig.add_subplot(211)
    ax2 = fig.add_subplot(212)
    _add_line_ref(ax1, "t1", "time", "a", "u_0.dat")
    _add_line_ref(ax2, "t1", "time", "b", "u_1.dat")

    provider = _provider(t1=_table(time=[0.0, 1.0], a=[1.0, 2.0], b=[3.0, 4.0]))
    first_text, first_files = _generate(fig, provider)
    second_text, second_files = _generate(fig, provider)

    assert set(first_files) == {"u_0.dat"}
    assert first_files["u_0.dat"] == "time a b\n0 1 3\n1 2 4\n"
    # Repeating the write is a fixed point: the shared layout is a pure
    # function of the figure, not of write-order state.
    assert (second_text, second_files) == (first_text, first_files)


def test_shared_sidecar_is_listed_in_the_import_data_metadata():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "a", "u_0.dat")
    text, _files = _generate(fig, _provider(t1=_table(time=[0.0], a=[1.0])))
    assert "import-data" in text and "u_0.dat" in text


def test_inline_column_rides_along_in_a_shared_sidecar():
    """A table-backed centre with a constant error column still works."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    series = ErrorbarSeries(
        type="errorbar",
        x=None,
        y=None,
        yerr_up=np.array([0.5, 0.5]),
        yerr_down=np.array([0.5, 0.5]),
        xerr_left=None,
        xerr_right=None,
        color="RED",
        marker="circle",
        markersize=0.1,
        linestyle="none",
        linewidth=1.0,
        label=None,
        capsize=None,
        gle_capsize=None,
        yaxis="y",
        offset=0.0,
        data_file="u_0.dat",
        column_names=None,
        data_source=ColumnRef("t1", {"x": "t", "y": "v"}),
    )
    ax._register_series_draw_meta(series, "errorbar")
    ax.errorbars.append(series)

    _text, files = _generate(fig, _provider(t1=_table(t=[0.0, 1.0], v=[3.0, 4.0])))
    assert files["u_0.dat"] == "t v yerr_up\n0 3 0.5\n1 4 0.5\n"


# -- GridRef ------------------------------------------------------------------


def _heatmap_grid_ref(ax, table_id, z_keys, data_file):
    series = HeatmapSeries(
        type="heatmap",
        source="grid",
        z=None,
        x=None,
        y=None,
        zpts=None,
        extent=[0.0, 3.0, 0.0, 2.0],
        origin="lower",
        cmap="gray",
        vmin=None,
        vmax=None,
        interpolation="nearest",
        pixels=[64, 64],
        invert=False,
        gridsize=None,
        ncontour=None,
        label=None,
        data_file=data_file,
        data_source=GridRef(table_id, {"z": list(z_keys)}),
        colorbar=None,
    )
    ax.heatmaps.append(series)
    return series


def test_grid_ref_heatmap_resolves_to_a_z_sidecar():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _heatmap_grid_ref(ax, "t1", ["c0", "c1", "c2"], "u_heatmap1.z")

    provider = _provider(t1=_table(c0=[1.0, 4.0], c1=[2.0, 5.0], c2=[3.0, 6.0]))
    text, files = _generate(fig, provider)

    assert fig.source_warnings == []
    # The listed columns stack left-to-right into the grid, so the table's
    # rows are the grid's rows.
    assert files["u_heatmap1.z"] == (
        "! nx 3 ny 2 xmin 0 xmax 3 ymin 0 ymax 2\n1 2 3\n4 5 6\n"
    )
    assert "colormap" in text
    # A grid sidecar is raw content, not a columnar import.
    assert "u_heatmap1.z" not in text.split("import-data")[1].split("\n")[0]


def test_grid_ref_heatmap_autoscales_and_survives_a_round_trip():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _heatmap_grid_ref(ax, "t1", ["c0", "c1"], "u_heatmap1.z")

    restored = Figure.from_dict(fig.to_dict())
    source = restored.axes_list[0].heatmaps[0]["data_source"]
    assert isinstance(source, GridRef)
    assert source["columns"] == {"z": ["c0", "c1"]}


def test_dangling_grid_ref_is_skipped_without_a_palette_sub():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _heatmap_grid_ref(ax, "gone", ["c0"], "u_heatmap1.z")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text, files = _generate(fig, _provider())
    assert files == {}
    assert "colormap" not in text
    assert "sub gleplot_palette" not in text
    assert [w.reason for w in fig.source_warnings] == ["unknown-table"]


# -- 3. dangling references ---------------------------------------------------


def test_no_provider_is_a_dangling_reference_not_a_crash():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat", label="orphan")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        text, files = _generate(fig, None)

    assert files == {}
    assert "begin graph" in text and "end graph" in text
    assert "u_0.dat" not in text

    (ref,) = fig.source_warnings
    assert isinstance(ref, DanglingSourceRef)
    assert ref.reason == "no-provider"
    assert ref.series_id == "axes[0].lines[0]"
    assert ref.label == "orphan"
    assert ref.table_id == "t1"
    assert ref.missing_columns == ()
    assert "orphan" in str(ref)

    # The structured record also rides along on the emitted warning.
    (warned,) = [w for w in caught if issubclass(w.category, DanglingSourceWarning)]
    assert warned.message.ref == ref


def test_unknown_table_is_dangling():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "nope", "time", "signal", "u_0.dat")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _generate(fig, _provider(t1=_table(time=[0.0], signal=[1.0])))

    (ref,) = fig.source_warnings
    assert ref.reason == "unknown-table"
    assert ref.table_id == "nope"
    assert ref.missing_columns == ()


def test_missing_column_is_dangling_and_names_the_columns():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "gone", "u_0.dat")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _generate(fig, _provider(t1=_table(time=[0.0], signal=[1.0])))

    (ref,) = fig.source_warnings
    assert ref.reason == "missing-column"
    assert ref.missing_columns == ("gone",)
    assert "'gone'" in str(ref)


def test_unknown_source_kind_is_dangling_not_an_error():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    series = _add_line_ref(ax, "t1", "time", "signal", "u_0.dat")
    series["data_source"] = {"kind": "from-the-future", "table_id": "t1"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text, files = _generate(fig, _provider(t1=_table(time=[0.0], signal=[1.0])))

    assert files == {}
    (ref,) = fig.source_warnings
    assert ref.reason == "unknown-kind"


def test_a_dangling_series_is_skipped_but_its_siblings_are_drawn():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0], label="inline")
    _add_line_ref(ax, "gone", "time", "signal", "u_9.dat", label="broken")
    _add_line_ref(ax, "t1", "time", "signal", "u_8.dat", label="ok")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text, files = _generate(
            fig, _provider(t1=_table(time=[0.0, 1.0], signal=[2.0, 3.0]))
        )

    assert set(files) == {"u_0.dat", "u_8.dat"}
    assert 'key "inline"' in text
    assert 'key "ok"' in text
    assert "broken" not in text
    assert [w.series_index for w in fig.source_warnings] == [1]
    # The skipped series does not drag the autoscale either.
    assert (ax.ymin, ax.ymax) == (0.0, 3.0)


def test_every_series_dangling_still_emits_a_valid_gle(tmp_path):
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "gone", "time", "a", "u_0.dat", label="one")
    _add_line_ref(ax, "gone", "time", "b", "u_1.dat", label="two")
    ax.set_xlabel("x")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        path = fig.savefig_gle(str(tmp_path / "out.gle"), data_provider=_provider())

    text = path.read_text(encoding="utf-8")
    assert text.startswith("! GLE graphics file")
    assert "begin graph" in text and "end graph" in text
    assert "xtitle" in text
    assert not list(tmp_path.glob("*.dat"))
    assert len(fig.source_warnings) == 2


def test_source_warnings_are_reset_by_each_write():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _generate(fig, None)
    assert len(fig.source_warnings) == 1

    _generate(fig, _provider(t1=_table(time=[0.0], signal=[1.0])))
    assert fig.source_warnings == []


def test_source_warnings_is_a_copy():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _generate(fig, None)
    fig.source_warnings.clear()
    assert len(fig.source_warnings) == 1


# -- source objects -----------------------------------------------------------


def test_source_from_dict_round_trips_each_kind():
    for source in (
        InlineData(),
        ColumnRef("t1", {"x": "a", "y": "b"}),
        GridRef("t1", {"z": ["a", "b"]}),
    ):
        assert source_from_dict(dict(source)) == source
        assert type(source_from_dict(dict(source))) is type(source)


def test_source_from_dict_keeps_an_unknown_kind_verbatim():
    payload = {"kind": "from-the-future", "whatever": 1}
    assert source_from_dict(payload) == payload


def test_column_ref_reports_its_column_keys_in_role_order_deduped():
    ref = ColumnRef("t1", {"x": "t", "y": "v", "yerr_up": "e", "yerr_down": "e"})
    assert ref.column_keys() == ["t", "v", "e"]


def test_table_data_rejects_ragged_columns():
    with pytest.raises(ValueError, match="same length"):
        TableData(["a", "b"], ["a", "b"], [[1.0], [1.0, 2.0]])


def test_table_data_from_data_table_keys_positionally_and_drops_text():
    from gleplot.dataio import DataTable

    table = DataTable(
        column_names=["name", "x"],
        columns=[np.array(["a", "b"], dtype=object), np.array([1.0, 2.0])],
        n_rows=2,
        path=None,
        delimiter=",",
        has_header=True,
        is_numeric=[False, True],
    )
    adapted = TableData.from_data_table(table)
    assert adapted.column_keys() == ["c1"]
    assert adapted.column_name("c1") == "x"
    np.testing.assert_array_equal(adapted.column_values("c1"), [1.0, 2.0])


def test_column_ref_figure_survives_a_to_dict_round_trip_and_regenerates():
    """A reference series is serializable state like everything else."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    _add_line_ref(ax, "t1", "time", "signal", "u_0.dat", label="ref")

    provider = _provider(t1=_table(time=[0.0, 1.0], signal=[2.0, 3.0]))
    before = _generate(fig, provider)

    restored = Figure.from_dict(fig.to_dict())
    line = restored.axes_list[0].lines[0]
    assert isinstance(line["data_source"], ColumnRef)
    assert line["x"] is None and line["y"] is None
    assert not is_inline(line)

    assert _generate(restored, provider) == before


def test_sources_api_is_exported_from_the_package_root():
    for name in (
        "DataSource",
        "InlineData",
        "ColumnRef",
        "GridRef",
        "DataProvider",
        "TableData",
        "DictDataProvider",
        "DanglingSourceRef",
        "DanglingSourceWarning",
    ):
        assert hasattr(glp, name), name
        assert name in glp.__all__
