"""Figure-level text and legend: ``Figure.suptitle``, ``Figure.text``,
``Figure.legend``."""

import re
import warnings

import pytest

import gleplot as glp
from gleplot import Figure


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _pair():
    fig, axes = glp.subplots(1, 2, figsize=(8, 4))
    axes[0].plot([0, 1], [0, 1], label="rise")
    axes[1].plot([0, 1], [1, 0], label="fall")
    return fig, axes


def _frame_tops(gle):
    """Top edge in cm of every graph frame, from its ``amove`` and ``size``."""
    starts = re.findall(
        r"^amove ([\d.]+) ([\d.]+)\nbegin graph\n    size ([\d.]+) " r"([\d.]+)",
        gle,
        re.MULTILINE,
    )
    return [float(y) + float(h) for _x, y, _w, h in starts]


# --------------------------------------------------------------------------- #
# suptitle
# --------------------------------------------------------------------------- #


def test_suptitle_is_centred_at_the_top_of_the_page():
    fig, _axes = _pair()
    title = fig.suptitle("Sample A")
    assert (title["x"], title["y"], title["ha"], title["va"]) == (
        0.5,
        0.98,
        "center",
        "top",
    )
    # matplotlib's 'large' is 1.2 times the figure font size.
    assert title["fontsize"] == pytest.approx(1.2 * fig.style.fontsize)
    gle = fig._generate_gle()
    assert (
        "gsave\nset hei 0.507937\nset color BLACK\nset just tc\n"
        'amove pagewidth()*0.5 pageheight()*0.98\nwrite "Sample A"\ngrestore'
    ) in gle
    assert gle.index("end graph") < gle.index('write "Sample A"')


def test_a_second_suptitle_replaces_the_first():
    fig, _axes = _pair()
    fig.suptitle("one")
    fig.suptitle("two", fontsize=20, color="red")
    gle = fig._generate_gle()
    assert 'write "one"' not in gle
    assert 'write "two"' in gle
    assert "set color RED" in gle


def test_suptitle_lowers_the_axes_to_make_room():
    fig, _axes = _pair()
    before = _frame_tops(fig._generate_gle())
    fig.suptitle("Sample A")
    after = _frame_tops(fig._generate_gle())
    page_top = 4 * 2.54
    hei = 1.2 * 12 * 2.54 / 72
    room = 0.02 * page_top + 1.25 * hei
    assert after == pytest.approx([top - room for top in before], abs=1e-4)


def test_subplots_adjust_top_overrides_the_suptitle_room():
    fig, _axes = _pair()
    fig.subplots_adjust(top=0.9)
    before = _frame_tops(fig._generate_gle())
    fig.suptitle("Sample A")
    assert _frame_tops(fig._generate_gle()) == before


def test_suptitle_unsupported_keyword_warns():
    fig = glp.figure()
    with pytest.warns(UserWarning, match=r"suptitle\(fontweight=...\)"):
        fig.suptitle("t", fontweight="bold")


# --------------------------------------------------------------------------- #
# Figure.text
# --------------------------------------------------------------------------- #


def test_figure_text_is_placed_in_figure_fractions_after_every_axes():
    fig, axes = _pair()
    text = fig.text(0.02, 0.98, "(a)", ha="left", va="top")
    assert fig.texts == [text]
    assert axes[0].texts == [] and axes[1].texts == []
    gle = fig._generate_gle()
    assert (
        "gsave\nset color BLACK\nset just tl\n"
        'amove pagewidth()*0.02 pageheight()*0.98\nwrite "(a)"\ngrestore'
    ) in gle
    assert gle.rindex("end graph") < gle.index('write "(a)"')


def test_fontdict_is_overridden_by_keywords():
    fig = glp.figure()
    text = fig.text(0.5, 0.5, "x", {"color": "red", "fontsize": 8}, fontsize=10)
    assert (text["color"], text["fontsize"]) == ("RED", 10.0)


def test_fontdict_must_be_a_dict():
    fig = glp.figure()
    with pytest.raises(TypeError, match="fontdict"):
        fig.text(0.5, 0.5, "x", "red")


def test_figure_text_warns_on_a_transform():
    fig = glp.figure()
    with pytest.warns(UserWarning, match=r"Figure.text\(transform=...\)"):
        fig.text(0.5, 0.5, "x", transform=None)


def test_text_size_names_are_relative_to_the_figure_font_size():
    fig = glp.figure()
    text = fig.text(0.5, 0.5, "x", fontsize="large")
    assert text["fontsize"] == pytest.approx(1.2 * fig.style.fontsize)
    assert fig.suptitle("t", fontsize=None)["fontsize"] == text["fontsize"]
    ax = fig.add_subplot(111)
    ax.text(0, 0, "y", fontsize="small")
    assert ax.texts[0]["fontsize"] == pytest.approx(0.833 * fig.style.fontsize)


def test_figure_text_rejects_a_non_finite_position():
    fig = glp.figure()
    with pytest.raises(ValueError, match="x"):
        fig.text(float("nan"), 0.5, "x")


def test_a_figure_with_only_text_writes_no_empty_graph():
    fig = glp.figure()
    fig.text(0.1, 0.1, "only")
    gle = fig._generate_gle()
    assert "begin graph" not in gle
    assert 'write "only"' in gle


# --------------------------------------------------------------------------- #
# Figure.legend
# --------------------------------------------------------------------------- #


def test_figure_legend_lists_every_axes_and_turns_auto_keys_off():
    fig, _axes = _pair()
    assert fig.legend(loc="upper center", ncol=2) is fig
    gle = fig._generate_gle()
    assert gle.count("    key off") == 2
    block = gle[gle.index("begin key") :]
    assert block.startswith(
        "begin key\n    justify tc\n"
        "    absolute pagewidth()*0.5 pageheight()*1-0.21164\n"
        '    text "rise"'
    )
    assert block.index('"rise"') < block.index("separator") < block.index('"fall"')


def test_an_axes_legend_asked_for_is_still_drawn():
    fig, axes = _pair()
    axes[1].legend()
    fig.legend()
    gle = fig._generate_gle()
    assert gle.count("    key off") == 1
    assert "    key pos tr" in gle


def test_figure_legend_anchor_is_in_figure_fractions():
    fig, _axes = _pair()
    fig.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    assert fig._legend["anchor"] == [1.0, 0.5]
    assert "absolute pagewidth()*1+0.21164 pageheight()*0.5" in fig._generate_gle()


def test_a_none_spacing_keyword_is_the_default_and_does_not_warn():
    fig = glp.figure()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig.legend(borderpad=None, handlelength=None)
    assert fig._legend["spacing"] == {}


def test_best_is_not_a_figure_legend_location():
    fig = glp.figure()
    with pytest.raises(ValueError, match="best"):
        fig.legend(loc="best")


def test_figure_legend_warns_on_handles_and_unsupported_keywords():
    fig = glp.figure()
    with pytest.warns(UserWarning, match="handles"):
        fig.legend(["a"])
    with pytest.warns(UserWarning, match=r"legend\(title=...\)"):
        fig.legend(title="t")


def test_figure_legend_without_labels_warns_and_draws_nothing():
    fig = glp.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1])
    fig.legend()
    with pytest.warns(UserWarning, match="no labelled series"):
        gle = fig._generate_gle()
    assert "begin key" not in gle


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


def test_figure_level_state_round_trips_through_to_dict():
    fig, _axes = _pair()
    fig.suptitle("t")
    fig.text(0.1, 0.2, "x", rotation=10)
    fig.legend(loc="lower left", fontsize=9, handlelength=1.5)
    restored = Figure.from_dict(fig.to_dict())
    assert restored._suptitle == fig._suptitle
    assert restored.texts == fig.texts
    assert restored._legend == fig._legend
    assert restored._generate_gle() == fig._generate_gle()


def test_a_figure_without_them_keeps_its_snapshot_keys():
    fig, _axes = _pair()
    block = fig.to_dict()["figure"]
    assert not {"suptitle", "texts", "legend"} & set(block)


def test_close_clears_figure_level_state():
    fig, _axes = _pair()
    fig.suptitle("t")
    fig.text(0.1, 0.2, "x")
    fig.legend()
    fig.close()
    assert (fig._suptitle, fig.texts, fig._legend) == (None, [], None)
