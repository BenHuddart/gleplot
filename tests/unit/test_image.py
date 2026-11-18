"""``Axes.image``: the stored image, the emitted script, and what it rejects."""

from __future__ import annotations

import warnings
from pathlib import Path, PurePosixPath
from unittest import mock

import pytest

import gleplot as glp
from gleplot.series import PlacedImage


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _graph_lines(text: str):
    return [ln.strip() for ln in text.splitlines()]


def _setting(text: str, keyword: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith(keyword)]
    return lines[0] if lines else None


def test_a_png_is_drawn_by_the_bitmap_sub_in_its_own_layer():
    fig, ax = glp.subplots()
    entry = ax.image("micrograph.png", extent=(0, 10, 0, 5))
    assert isinstance(entry, PlacedImage)
    assert ax.images == [entry]
    lines = _graph_lines(_script(fig))
    i = lines.index('draw gleplot_bitmap "micrograph.png" 0 10 0 5')
    assert lines[i - 1] == "begin layer 150"
    assert lines[i + 1] == "end layer"


@pytest.mark.parametrize(
    "name,sub",
    [
        ("a.jpg", "gleplot_bitmap"),
        ("a.JPEG", "gleplot_bitmap"),
        ("a.gif", "gleplot_bitmap"),
        ("a.tif", "gleplot_bitmap"),
        ("a.tiff", "gleplot_bitmap"),
        ("a.eps", "gleplot_postscript"),
    ],
)
def test_the_extension_picks_the_sub(name, sub):
    fig, ax = glp.subplots()
    ax.image(name, extent=(0, 1, 0, 1))
    assert f'draw {sub} "{name}" 0 1 0 1' in _graph_lines(_script(fig))


def test_a_path_object_is_stored_as_its_string():
    fig, ax = glp.subplots()
    ax.image(PurePosixPath("figs/photo.png"), extent=(0, 1, 0, 1))
    assert ax.images[0]["file"] == "figs/photo.png"


def test_the_subs_are_defined_once_and_only_when_an_image_is_drawn():
    fig, ax = glp.subplots()
    ax.plot([0, 1], [0, 1])
    assert "sub gleplot_bitmap" not in _script(fig)

    ax.image("a.png", extent=(0, 1, 0, 1))
    ax.image("b.eps", extent=(0, 1, 0, 1))
    text = _script(fig)
    assert text.count("sub gleplot_bitmap ") == 1
    assert text.count("sub gleplot_postscript ") == 1
    assert text.index("sub gleplot_bitmap") < text.index("begin graph")


def test_a_hidden_image_draws_nothing():
    fig, ax = glp.subplots()
    ax.plot([0, 1], [0, 1])
    ax.image("a.png", extent=(0, 1, 0, 1))["visible"] = False
    text = _script(fig)
    assert "gleplot_bitmap" not in text
    assert "begin layer" not in text


def test_the_extent_sets_the_limits_of_an_axes_with_nothing_else():
    fig, ax = glp.subplots()
    ax.image("a.png", extent=(-2, 3, 0.5, 4))
    text = _script(fig)
    assert _setting(text, "xaxis") == "xaxis min -2 max 3"
    assert _setting(text, "yaxis") == "yaxis min 0.5 max 4"


def test_the_extent_widens_the_data_limits():
    fig, ax = glp.subplots()
    ax.plot([0, 4], [1, 2])
    ax.image("a.png", extent=(1, 6, -1, 1.5))
    text = _script(fig)
    assert _setting(text, "xaxis") == "xaxis min 0 max 6"
    assert _setting(text, "yaxis") == "yaxis min -1 max 2"


def test_explicit_limits_win_over_the_extent():
    fig, ax = glp.subplots()
    ax.image("a.png", extent=(0, 10, 0, 5))
    ax.set_xlim(2, 4)
    assert _setting(_script(fig), "xaxis") == "xaxis min 2 max 4"


@pytest.mark.parametrize("name", ["scan.bmp", "scan", "scan.pdf", "scan.svg"])
def test_a_file_type_gle_cannot_place_is_rejected(name):
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match=r"\.png, \.jpg"):
        ax.image(name, extent=(0, 1, 0, 1))


def test_a_double_quote_in_the_path_is_rejected():
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="double quote"):
        ax.image('say "cheese".png', extent=(0, 1, 0, 1))


def test_a_non_path_is_a_type_error():
    _fig, ax = glp.subplots()
    with pytest.raises(TypeError, match="file path"):
        ax.image(42, extent=(0, 1, 0, 1))


@pytest.mark.parametrize(
    "extent,message",
    [
        ((0, 1, 0), r"\(left, right, bottom, top\)"),
        ((1, 0, 0, 1), "xmin < xmax"),
        ((0, 1, 1, 1), "xmin < xmax"),
        ((0, float("nan"), 0, 1), "finite"),
    ],
)
def test_a_bad_extent_is_rejected(extent, message):
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match=message):
        ax.image("a.png", extent=extent)
    assert ax.images == []


def _compile_mocked(fig, path, **kwargs):
    fig.compiler = mock.Mock()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.savefig(str(path), **kwargs)
    return [str(w.message) for w in caught if "EPS" in str(w.message)]


def test_an_eps_image_warns_when_saved_as_svg(tmp_path):
    fig, ax = glp.subplots()
    ax.image("logo.eps", extent=(0, 1, 0, 1))
    assert _compile_mocked(fig, tmp_path / "out.svg") == [
        "image(...) EPS files are not drawn in SVG output; convert the image "
        "to PNG, or save as PDF, EPS or PNG without transparency."
    ]


def test_an_eps_image_warns_when_the_figure_needs_cairo(tmp_path):
    fig, ax = glp.subplots()
    ax.image("logo.eps", extent=(0, 1, 0, 1))
    ax.fill_between([0, 1], [0, 0], [1, 1], alpha=0.5)
    (message,) = _compile_mocked(fig, tmp_path / "out.pdf")
    assert "Cairo device" in message


def test_an_eps_image_does_not_warn_through_postscript(tmp_path):
    fig, ax = glp.subplots()
    ax.image("logo.eps", extent=(0, 1, 0, 1))
    assert _compile_mocked(fig, tmp_path / "out.pdf") == []


def test_a_png_image_does_not_warn_as_svg(tmp_path):
    fig, ax = glp.subplots()
    ax.image("photo.png", extent=(0, 1, 0, 1))
    assert _compile_mocked(fig, tmp_path / "out.svg") == []


def test_absolutize_file_references_rewrites_a_relative_image_path(tmp_path):
    fig, ax = glp.subplots()
    ax.image("figs/photo.png", extent=(0, 1, 0, 1))
    absolute = (tmp_path / "logo.png").as_posix()
    ax.image(absolute, extent=(0, 1, 0, 1))
    fig.absolutize_file_references(tmp_path)
    assert ax.images[0]["file"] == (tmp_path / "figs/photo.png").resolve().as_posix()
    assert ax.images[1]["file"] == absolute
    assert Path(ax.images[0]["file"]).is_absolute()
