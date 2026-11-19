"""Legend visibility semantics.

``Axes.legend_on`` is tri-state:

* ``None`` (default) — auto: a legend is shown iff any series has a label.
* ``True`` — always show (what ``Axes.legend()`` sets).
* ``False`` — never show; the writer must emit ``key off`` because GLE
  draws an implicit key from per-dataset ``key "label"`` tokens.

Regression tests for the GUI legend toggle having no effect.
"""

import pytest

import gleplot as glp
from gleplot.parser.units import fontsize_pt_to_cm
from gleplot.writer import GLEWriter


def _generate_gle(fig, tmp_path):
    out = tmp_path / "legend_test.gle"
    fig.savefig_gle(str(out))
    return out.read_text()


def _labeled_figure():
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="squares")
    return fig, ax


def test_auto_legend_shown_when_labels_present(tmp_path):
    fig, ax = _labeled_figure()
    assert ax.legend_on is None
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" in gle
    assert "key off" not in gle


def test_auto_no_legend_without_labels(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4])
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" not in gle
    assert "key off" not in gle


def test_explicit_off_emits_key_off_for_labeled_series(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend_on = False
    gle = _generate_gle(fig, tmp_path)
    assert "key off" in gle
    assert "key pos" not in gle
    # the label token is still present; only the key display is suppressed
    assert 'key "squares"' in gle


def test_explicit_on_without_labels_emits_key_pos(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.legend_on = True
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" in gle


def test_legend_call_sets_explicit_on():
    fig, ax = _labeled_figure()
    ax.legend()
    assert ax.legend_on is True


def test_tristate_survives_round_trip():
    from gleplot.figure import Figure

    for state in (None, True, False):
        fig, ax = _labeled_figure()
        ax.legend_on = state
        restored = Figure.from_dict(fig.to_dict())
        assert restored.axes_list[0].legend_on is state


# ---------------------------------------------------------------------------
# legend() keyword arguments
#
# GLE's graph-block ``key`` command understands ``pos``, ``hei`` (text height
# in cm), ``nobox`` and ``offset`` (GLE 4.3.10 manual, "The Key Module").
# ``fontsize`` and ``frameon`` map onto ``hei``/``nobox``; everything else
# matplotlib offers has no GLE counterpart and must warn rather than vanish.
# ---------------------------------------------------------------------------


def _hei(points):
    """The exact ``hei`` token the writer emits for a point size."""
    return GLEWriter._format_number(fontsize_pt_to_cm(points))


def test_fontsize_emits_key_hei(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(fontsize=6.5)
    gle = _generate_gle(fig, tmp_path)
    # 6.5 pt / 28.35 = 0.229 cm, the same pt->cm conversion 'set hei' uses
    assert f"key pos tr hei {_hei(6.5)}\n" in gle


def test_fontsize_omitted_leaves_key_line_unchanged(tmp_path):
    """No fontsize -> no 'hei' token, i.e. byte-identical legacy output."""
    fig, ax = _labeled_figure()
    ax.legend()
    gle = _generate_gle(fig, tmp_path)
    assert "    key pos tr\n" in gle
    assert "hei" not in gle.split("key pos tr")[1].split("\n")[0]


def test_fontsize_accepts_matplotlib_relative_names(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(fontsize="small")
    assert ax.legend_fontsize == pytest.approx(fig.style.fontsize * 0.833)


def test_fontsize_rejects_nonsense():
    fig, ax = _labeled_figure()
    with pytest.raises(ValueError):
        ax.legend(fontsize="ginormous")
    with pytest.raises(ValueError):
        ax.legend(fontsize=0)


def test_frameon_false_emits_nobox(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(frameon=False)
    gle = _generate_gle(fig, tmp_path)
    assert "key pos tr nobox" in gle


def test_frameon_true_is_the_default(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(frameon=True)
    gle = _generate_gle(fig, tmp_path)
    assert "nobox" not in gle


@pytest.mark.parametrize(
    "loc,expected",
    [
        ("best", "tr"),
        ("upper right", "tr"),
        ("upper left", "tl"),
        ("upper center", "tc"),
        ("lower left", "bl"),
        ("lower right", "br"),
        ("lower center", "bc"),
        ("center left", "lc"),
        ("center right", "rc"),
        ("right", "rc"),
        ("center", "cc"),
        ("br", "br"),  # GLE short form passes through
    ],
)
def test_every_matplotlib_loc_maps_to_a_gle_anchor(tmp_path, loc, expected):
    fig, ax = _labeled_figure()
    ax.legend(loc=loc)
    gle = _generate_gle(fig, tmp_path)
    assert f"key pos {expected}" in gle


def test_unknown_loc_warns_and_falls_back():
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="not a recognized matplotlib location"):
        ax.legend(loc="middle-ish")
    assert ax.legend_pos == "top right"


def test_ncol_one_is_accepted_silently(recwarn):
    fig, ax = _labeled_figure()
    ax.legend(ncol=1)
    assert not recwarn.list


def test_ncol_above_one_is_stored():
    fig, ax = _labeled_figure()
    ax.legend(ncol=2)
    assert ax.legend_ncol == 2


def test_ncols_wins_when_both_are_passed():
    fig, ax = _labeled_figure()
    ax.legend(ncol=3, ncols=2)
    assert ax.legend_ncol == 2


@pytest.mark.parametrize("ncol", [0, -1, 1.5, True, "2"])
def test_ncol_rejects_a_non_positive_integer(ncol):
    fig, ax = _labeled_figure()
    with pytest.raises(ValueError):
        ax.legend(ncol=ncol)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"framealpha": 0.5},
        {"edgecolor": "black"},
        {"shadow": True},
        {"labelspacing": 0.8},
        {"markerscale": 2.0},
        {"title": "Models"},
        {"bbox_transform": None},
    ],
)
def test_unsupported_kwargs_warn(kwargs):
    """Silent parameter swallowing was the bug; every survivor must speak."""
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match=r"legend\(\) ignores unsupported keyword"):
        ax.legend(**kwargs)


def test_handles_sequence_warns_instead_of_crashing():
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="handles/labels"):
        ax.legend(["squares"])
    assert ax.legend_pos == "top right"


def test_legend_style_survives_serialization_round_trip():
    from gleplot.figure import Figure

    fig, ax = _labeled_figure()
    ax.legend(loc="lower left", fontsize=7.0, frameon=False)
    restored = Figure.from_dict(fig.to_dict()).axes_list[0]
    assert restored.legend_pos == "bottom left"
    assert restored.legend_fontsize == 7.0
    assert restored.legend_frameon is False


def test_legend_style_survives_gle_round_trip(tmp_path):
    """key pos/hei/nobox must be modelled, not kept as raw passthrough."""
    from gleplot import open_gle

    fig, ax = _labeled_figure()
    ax.legend(loc="lower left", fontsize=7.0, frameon=False)
    path = tmp_path / "legend_round_trip.gle"
    fig.savefig_gle(str(path))

    recovered = open_gle(str(path))
    rax = recovered.axes_list[0]
    assert rax.legend_pos == "bottom left"
    # The height goes out in cm at the writer's 6-significant-digit precision,
    # so it comes back as points to within that rounding, not bit-exactly.
    assert rax.legend_fontsize == pytest.approx(7.0, abs=1e-3)
    assert rax.legend_frameon is False

    out = tmp_path / "legend_round_trip2.gle"
    recovered.savefig_gle(str(out))
    assert f"key pos bl hei {_hei(7.0)} nobox" in out.read_text()


def test_broken_axes_legend_forwards_kwargs(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    bax = fig.add_broken_xaxes([(0, 1), (5, 6)])
    bax.plot([0, 0.5, 5.5], [1, 2, 3], label="series")
    bax.legend(loc="upper left", fontsize=6.0, segment=0)
    assert bax[0].legend_fontsize == 6.0
    assert bax[0].legend_pos == "top left"


def test_column_breaks_match_matplotlib_split():
    from gleplot.writer import legend_column_breaks

    # np.array_split: first n % ncol columns are one longer.
    assert legend_column_breaks(5, 2) == {3}
    assert legend_column_breaks(4, 2) == {2}
    assert legend_column_breaks(3, 2) == {2}
    assert legend_column_breaks(2, 2) == {1}
    assert legend_column_breaks(2, 5) == {1}
    assert legend_column_breaks(1, 3) == set()
    assert legend_column_breaks(4, 1) == set()


def test_ncol_emits_separator_between_columns(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1], [0, 1], label="a")
    ax.plot([0, 1], [1, 0], label="b")
    ax.plot([0, 1], [0, 0], label="c")
    ax.legend(ncol=2)
    gle = _generate_gle(fig, tmp_path)
    # Three entries, two columns: the break is after the second.
    assert gle.index('key "b"') < gle.index("key separator") < gle.index('key "c"')
    assert gle.count("key separator") == 1
    # Three lines were added in the order they are drawn, so the graph key
    # can carry the columns. A begin key is only for the other case.
    assert "begin key" not in gle


def test_legend_off_emits_no_separator(tmp_path):
    fig, ax = _labeled_figure()
    ax.plot([0, 1], [1, 0], label="other")
    ax.legend(ncol=2)
    ax.legend_on = False
    gle = _generate_gle(fig, tmp_path)
    assert "key off" in gle
    assert "key separator" not in gle


def test_bar_and_fill_labels_are_swatches(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.bar([0, 1, 2], [1, 2, 3], color="C0", label="control")
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 2, 1], label="band", alpha=0.3)
    ax.legend(ncol=2)
    gle = _generate_gle(fig, tmp_path)
    assert 'key "control"' in gle
    assert "keyfill" in gle
    assert 'key "band"' in gle
    # The fill swatch uses the same colour token as the fill command.
    fill_line = next(
        line for line in gle.splitlines() if line.strip().startswith("fill ")
    )
    color = fill_line.split("color ", 1)[1]
    assert f'keyfill {color} key "band"' in gle
    # The bar was added first. GLE draws the fill first, so the columns
    # live in a begin key rather than in the dataset order.
    assert "key off" in gle
    block = gle.split("begin key", 1)[1]
    assert (
        block.index('text "control"')
        < block.index("separator")
        < block.index('text "band"')
    )


def test_a_hatched_bar_swatch_is_hatched_in_a_begin_key(tmp_path):
    """The in-graph key copies the bar's pattern; a ``begin key`` restates it.

    Not the background: inside ``begin key`` that colours the whole key.
    """
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.bar([0, 1, 2], [1, 2, 3], color="yellow", hatch="/", label="hatched")
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 2, 1], label="band")
    ax.legend()
    gle = _generate_gle(fig, tmp_path)
    block = gle.split("begin key", 1)[1]
    assert 'text "hatched" fill BLACK pattern SHADE\n' in block
    assert "background" not in block


def test_unlabeled_bar_and_fill_still_suppress_header_keys(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.bar([0, 1], [1, 2])
    ax.fill_between([0, 1], [0, 0], [1, 2])
    gle = _generate_gle(fig, tmp_path)
    assert 'key "control"' not in gle
    assert "keyfill" not in gle
    assert gle.count('key ""') == 3  # one bar dataset, two fill datasets
    assert "key pos" not in gle


def test_compact_and_facecolor_share_the_key_line(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(compact=True, facecolor="green")
    gle = _generate_gle(fig, tmp_path)
    assert "key pos tr compact background GREEN" in gle


def test_engine_range_span_and_refline_keep_their_swatches(tmp_path):
    """No data and no limits: the guides are drawn after the graph, and the
    swatches are data-free bridges in it."""
    from gleplot import open_gle

    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.axvspan(0.2, 0.4, color="orange", label="window")
    ax.axvline(0.3, color="red", linestyle="--", label="cut")
    path = tmp_path / "bridge.gle"
    fig.savefig_gle(str(path))
    gle = path.read_text()
    assert "\nbox " in gle
    assert "\ngraph_vline 0.3" in gle
    assert "keyfill" in gle and 'key "window"' in gle
    assert 'key "cut"' in gle
    # The span swatch is the data-free bridge, not a fill command.
    assert "\n    fill " not in gle

    recovered = open_gle(str(path))
    rax = recovered.axes_list[0]
    assert any(s.get("label") == "window" for s in rax.spans)
    assert any(s.get("label") == "cut" for s in rax.reflines)
    out = tmp_path / "bridge2.gle"
    recovered.savefig_gle(str(out))
    assert out.read_text() == gle


#: Names ``d.dat`` gleplot's own file, so a bar or fill on it is loaded as a
#: series; on a file of the user's own it would be a file reference.
_D_DAT_IMPORTED = (
    "! gleplot-meta-begin v2\n! gleplot: import-data = d.dat\n! gleplot-meta-end\n"
)


def test_a_bar_dataset_line_that_is_not_a_swatch_is_not_consumed(tmp_path):
    """``key`` plus anything else is not the writer's swatch line."""
    from gleplot.parser.recognizer import parse_gle_figure

    src = tmp_path / "odd.gle"
    src.write_text(
        _D_DAT_IMPORTED + "size 10 8\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2\n"
        "   bar d1 fill red\n"
        '   d1 key "control" lstyle 1\n'
        "end graph\n",
        encoding="utf-8",
    )
    (tmp_path / "d.dat").write_text("1 2\n3 4\n", encoding="utf-8")
    rec = parse_gle_figure(str(src))
    ax = rec.figure.axes_list[0]
    # Not the bar's swatch: the extra token keeps it a dataset line of its own.
    assert ax.bars[0].get("label") is None
    assert any(s.get("label") == "control" for s in ax.lines)


def test_unresolved_bar_keeps_its_legend_label(tmp_path):
    from gleplot.parser.recognizer import parse_gle_figure

    src = tmp_path / "missing.gle"
    src.write_text(
        "size 10 8\n"
        "begin graph\n"
        "   data missing.dat d1=c1,c2\n"
        "   bar d1 fill red\n"
        '   d1 key "control"\n'
        "end graph\n",
        encoding="utf-8",
    )
    rec = parse_gle_figure(str(src))
    ax = rec.figure.axes_list[0]
    assert ax.file_series[0]["series_type"] == "bar"
    assert ax.file_series[0]["label"] == "control"
    out = tmp_path / "missing2.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert 'key "control"' in text
    assert "bar d1 fill red" in text


def test_boxcolor_warns_and_is_not_the_box_fill():
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="boxcolor"):
        ax.legend(boxcolor="red")
    assert ax.legend_facecolor is None


def test_swatches_and_columns_survive_gle_round_trip(tmp_path):
    from gleplot import open_gle

    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1], [0, 1], label="a")
    ax.bar([0, 1], [1, 2], color="red", label="control")
    ax.fill_between([0, 1], [0, 0], [1, 2], color="blue", alpha=0.3, label="band")
    ax.axvspan(0.2, 0.4, color="orange", alpha=0.5, label="window")
    ax.legend(ncol=2, compact=True, facecolor="#112233")
    path = tmp_path / "swatch.gle"
    fig.savefig_gle(str(path))
    first = path.read_text()

    recovered = open_gle(str(path))
    rax = recovered.axes_list[0]
    assert rax.bars[0]["label"] == "control"
    assert rax.fills[0]["label"] == "band"
    assert any(s.get("label") == "window" for s in rax.spans)
    assert rax.legend_ncol == 2
    assert rax.legend_compact is True
    assert rax.legend_facecolor is not None

    out = tmp_path / "swatch2.gle"
    recovered.savefig_gle(str(out))
    assert out.read_text() == first


def test_a_quote_in_a_bar_or_fill_label_round_trips(tmp_path):
    """GLE embeds a quote by doubling it. A backslash does not."""
    from gleplot import open_gle

    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.bar([0, 1], [1, 2], label='5"')
    ax.fill_between([0, 1], [0, 0], [1, 2], label='a"b')
    path = tmp_path / "quotes.gle"
    fig.savefig_gle(str(path))
    gle = path.read_text()
    assert 'key "5"""' in gle
    assert 'key "a""b"' in gle

    recovered = open_gle(str(path))
    rax = recovered.axes_list[0]
    assert rax.bars[0]["label"] == '5"'
    assert rax.fills[0]["label"] == 'a"b'
    out = tmp_path / "quotes2.gle"
    recovered.savefig_gle(str(out))
    assert out.read_text() == gle


def test_a_keyfill_colour_unlike_the_fill_is_kept(tmp_path):
    """A swatch that is not the fill colour must not be repainted on save."""
    from gleplot.parser.recognizer import parse_gle_figure

    src = tmp_path / "swatch.gle"
    src.write_text(
        _D_DAT_IMPORTED + "size 10 8\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2 d2=c1,c3\n"
        "   fill d1,d2 color blue\n"
        '   d1 keyfill red key "band"\n'
        "   key pos tr\n"
        "end graph\n",
        encoding="utf-8",
    )
    (tmp_path / "d.dat").write_text("0 0 1\n1 0 2\n", encoding="utf-8")
    rec = parse_gle_figure(str(src))
    fill = rec.figure.axes_list[0].fills[0]
    assert fill["label"] == "band"
    assert fill["color"] == "blue"
    assert fill["swatch_color"] == "red"
    out = tmp_path / "swatch2.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "fill d1,d2 color blue" in text
    assert 'keyfill red key "band"' in text


def _cm(units, points):
    """The token for a spacing of ``units`` font sizes at ``points``."""
    return GLEWriter._format_number(units * fontsize_pt_to_cm(points))


def test_spacing_keywords_go_on_the_key_line_in_cm(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(handlelength=1.5, handletextpad=0.5, columnspacing=1.0, borderpad=0.3)
    size = fig.style.fontsize
    pad = _cm(0.3, size)
    assert (
        f"key pos tr llen {_cm(1.5, size)} dist {_cm(0.5, size)} "
        f"coldist {_cm(1.0, size)} margins {pad} {pad}"
    ) in _generate_gle(fig, tmp_path)


def test_spacing_scales_with_the_legend_fontsize(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(fontsize=8, handlelength=2.0)
    assert f"hei {_hei(8)} llen {_cm(2.0, 8)}" in _generate_gle(fig, tmp_path)


def test_spacing_none_restores_gle_spacing(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(handlelength=2.0)
    ax.legend(handlelength=None)
    assert "llen" not in _generate_gle(fig, tmp_path)


def test_spacing_rejects_a_non_number():
    fig, ax = _labeled_figure()
    with pytest.raises(TypeError, match="handlelength"):
        ax.legend(handlelength="long")


def test_bbox_to_anchor_is_justify_and_absolute_after_the_graph(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    gle = _generate_gle(fig, tmp_path)
    assert "    key off" in gle
    block = gle[gle.index("end graph") :]
    assert block.startswith("end graph\nbegin key\n    justify tl\n")
    assert (
        "    absolute min(xg(xgmin),xg(xgmax))+1.02*abs(xg(xgmax)-xg(xgmin)) "
        "min(yg(ygmin),yg(ygmax))+1*abs(yg(ygmax)-yg(ygmin))\n"
    ) in block


@pytest.mark.parametrize(
    "loc, anchor",
    [
        ("lower left", (0.0, 1.02)),
        ("upper right", (1.0, 1.22)),
        ("center", (0.5, 1.12)),
        ("lower center", (0.5, 1.02)),
    ],
)
def test_a_bbox_puts_the_loc_corner_on_the_same_corner_of_the_box(loc, anchor):
    fig, ax = _labeled_figure()
    ax.legend(loc=loc, bbox_to_anchor=(0, 1.02, 1, 0.2))
    assert ax.legend_bbox_to_anchor == pytest.approx(anchor)


@pytest.mark.parametrize("anchor", [(1.0,), (1, 2, 3), "12", 5, (1.0, "a")])
def test_bbox_to_anchor_rejects_anything_but_a_point_or_a_box(anchor):
    fig, ax = _labeled_figure()
    with pytest.raises(ValueError, match="bbox_to_anchor"):
        ax.legend(bbox_to_anchor=anchor)


def test_offset_warns_while_an_anchor_places_the_legend(tmp_path):
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="offset"):
        ax.legend(bbox_to_anchor=(1, 1), offset=(0.5, 0.5))
    assert "offset" not in _generate_gle(fig, tmp_path)


def test_labelcolor_is_textcolor_on_every_entry(tmp_path):
    fig, ax = _labeled_figure()
    ax.plot([0, 1], [1, 0], label="other")
    ax.legend(labelcolor="red")
    gle = _generate_gle(fig, tmp_path)
    assert "    position tr\n" in gle
    texts = [line for line in gle.splitlines() if line.startswith("    text ")]
    assert len(texts) == 2
    assert all(line.endswith(" textcolor RED") for line in texts)


@pytest.mark.parametrize("labelcolor", ["linecolor", "mec", ["red", "blue"]])
def test_per_entry_labelcolor_warns_and_is_ignored(labelcolor):
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="labelcolor"):
        ax.legend(labelcolor=labelcolor)
    assert ax.legend_labelcolor is None


def test_an_rgb_tuple_labelcolor_is_one_colour():
    fig, ax = _labeled_figure()
    ax.legend(labelcolor=(0.0, 0.0, 1.0))
    assert ax.legend_labelcolor == "rgb255(0,0,255)"


def test_anchor_labelcolor_and_spacing_survive_gle_round_trip(tmp_path):
    from gleplot import open_gle

    fig, ax = _labeled_figure()
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        labelcolor="gray",
        borderpad=0.2,
        frameon=False,
    )
    path = tmp_path / "anchored.gle"
    fig.savefig_gle(str(path))
    first = path.read_text()

    rax = open_gle(str(path)).axes_list[0]
    assert rax.legend_pos == "left center"
    assert rax.legend_bbox_to_anchor == (1.05, 0.5)
    assert rax.legend_labelcolor == "GRAY"
    # Out in cm at 6 significant figures, back in font sizes.
    assert rax.legend_spacing == {"borderpad": pytest.approx(0.2, rel=1e-5)}
    assert rax.legend_frameon is False

    out = tmp_path / "anchored2.gle"
    rax.figure.savefig_gle(str(out))
    assert out.read_text() == first

    copy = glp.Figure.from_dict(fig.to_dict()).axes_list[0]
    assert copy.legend_bbox_to_anchor == (1.05, 0.5)
    assert copy.legend_labelcolor == "GRAY"
    assert copy.legend_spacing == {"borderpad": 0.2}


def test_a_bbox_object_warns_and_is_ignored():
    class Bbox:
        bounds = (0.0, 0.0, 1.0, 1.0)

    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="Bbox"):
        ax.legend(bbox_to_anchor=Bbox())
    assert ax.legend_bbox_to_anchor is None


def test_a_call_without_bbox_to_anchor_clears_it():
    # The anchor was resolved against that call's loc, which a new call resets.
    fig, ax = _labeled_figure()
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    ax.legend(fontsize=8)
    assert ax.legend_bbox_to_anchor is None


def test_an_anchor_without_entries_writes_no_key_block(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.legend(bbox_to_anchor=(1.02, 1.0), labelcolor="red")
    assert "begin key" not in _generate_gle(fig, tmp_path)


def test_a_figure_wide_offset_warns_when_an_anchor_places_the_legend(tmp_path):
    fig = glp.figure(
        data_prefix="legtest",
        graph=glp.GLEGraphConfig(legend_offset_x=0.5, legend_offset_y=0.5),
    )
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="squares")
    ax.legend(bbox_to_anchor=(1.02, 1.0))
    with pytest.warns(UserWarning, match="legend_offset_x"):
        gle = _generate_gle(fig, tmp_path)
    assert "offset" not in gle


def test_labelcolor_none_restores_the_text_colour(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend(labelcolor="red")
    ax.legend(labelcolor=None)
    assert "textcolor" not in _generate_gle(fig, tmp_path)
