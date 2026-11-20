"""Reading figure-level text and the figure legend back from GLE."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from tests.parser import _golden_battery as golden


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _recognize(fig, tmp_path):
    path = tmp_path / "figure.gle"
    fig.savefig_gle(str(path))
    return parse_gle_figure(path)


def test_suptitle_and_texts_come_back(tmp_path):
    fig = golden.figure_text_and_suptitle()
    recognized = _recognize(fig, tmp_path)
    got = recognized.figure
    assert got._suptitle is not None
    assert got._suptitle["text"] == "Sample A"
    assert got._suptitle["color"] == "BLUE"
    assert [t["text"] for t in got.texts] == [t["text"] for t in fig.texts]
    assert got.texts[1]["rotation"] == 15.0
    assert got.texts[1]["box_color"] == "WHITE"
    assert got.passthrough_trailer == ["amove 1 1"]
    assert recognized.warnings == []


def test_a_suptitle_off_its_default_place_comes_back_as_a_text(tmp_path):
    got = _recognize(golden.figure_text_only(), tmp_path).figure
    assert got._suptitle is None
    assert [t["text"] for t in got.texts] == ["left title", "centre"]
    assert got.axes_list == []


def test_a_figure_text_where_the_suptitle_goes_comes_back_as_it(tmp_path):
    fig = glp.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1])
    fig.text(0.5, 0.98, "top", ha="center", va="top", fontsize=14)
    got = _recognize(fig, tmp_path).figure
    assert got._suptitle is not None and got.texts == []


def test_figure_legend_comes_back_with_its_axes_keys(tmp_path):
    fig = golden.figure_legend()
    got = _recognize(fig, tmp_path).figure
    assert got._legend == fig._legend
    # The auto key 'key off' is the default again; the asked-for key stays.
    assert [ax.legend_on for ax in got.axes_list] == [None, True]
    assert got.passthrough_trailer == []


def test_legends_listing_histogram_and_function_curves_come_back(tmp_path):
    """#236: the axes and figure ``begin key`` blocks are read, not kept raw."""
    fig = golden.legend_curves()
    recognized = _recognize(fig, tmp_path)
    got = recognized.figure
    assert got._legend == fig._legend
    assert got.axes_list[0].legend_labelcolor == "BLUE"
    assert got.passthrough_trailer == []
    assert not recognized.warnings


def test_figure_legend_options_come_back(tmp_path):
    fig = golden.figure_legend_options()
    got = _recognize(fig, tmp_path).figure
    assert got._legend["loc"] == "left center"
    assert got._legend["anchor"] == [0.8, 0.6]
    assert got._legend["ncol"] == 2
    assert got._legend["facecolor"] == "LIGHTYELLOW"
    assert got._legend["fontsize"] == pytest.approx(10.0, abs=1e-4)
    assert got._legend["spacing"] == pytest.approx(fig._legend["spacing"], abs=1e-4)


def _labelled_graph(tmp_path) -> str:
    """A one-axes script with one labelled line and its auto key off."""
    fig = glp.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1], label="a")
    fig.legend()
    path = tmp_path / "figure.gle"
    fig.savefig_gle(str(path))
    text = path.read_text()
    return text[: text.index("begin key")]


@pytest.mark.parametrize(
    "block",
    [
        # An entry that is not a series of the graph.
        "begin key\n    justify tr\n    absolute pagewidth()*1-0.21164 "
        'pageheight()*1-0.21164\n    text "zz"\nend key',
        # A distance from the edge the writer would not choose.
        "begin key\n    justify tr\n    absolute pagewidth()*1-0.5 "
        'pageheight()*1-0.21164\n    text "a"\nend key',
        # No swatch, which the writer would add (#412).
        "begin key\n    justify tr\n    absolute pagewidth()*1-0.21164 "
        'pageheight()*1-0.21164\n    text "a"\nend key',
        # A swatch edited by hand (#412).
        "begin key\n    justify tr\n    absolute pagewidth()*1-0.21164 "
        'pageheight()*1-0.21164\n    text "a" color MAGENTA lwidth 0.05292 '
        "lstyle 1\nend key",
    ],
)
def test_a_key_block_the_writer_would_not_write_stays_raw(block, tmp_path):
    path = tmp_path / "hand.gle"
    path.write_text(_labelled_graph(tmp_path) + block + "\n")
    got = parse_gle_figure(path).figure
    assert got._legend is None
    assert got.passthrough_trailer == block.split("\n")
    out = tmp_path / "again.gle"
    got.savefig_gle(str(out))
    assert out.read_text().endswith(block)


def test_a_hand_written_figure_key_is_recovered(tmp_path):
    block = (
        "begin key\n    justify tr\n"
        "    absolute pagewidth()*1-0.21164 pageheight()*1-0.21164\n"
        '    text "a" color blue lwidth 0.05292 lstyle 1\nend key'
    )
    path = tmp_path / "hand.gle"
    path.write_text(_labelled_graph(tmp_path) + block + "\n")
    got = parse_gle_figure(path).figure
    assert got._legend is not None and got._legend["loc"] == "top right"
    assert got.axes_list[0].legend_on is None
