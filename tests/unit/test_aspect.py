"""``Axes.set_aspect``: the frame is shrunk about its centre at write time."""

import json
import re
import warnings

import pytest

import gleplot as glp
from gleplot import Figure, GLEGraphConfig


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _frames(fig):
    """``[(x, y, w, h)]`` of every graph frame in the emitted script."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        text = fig._generate_gle()
    amoves = re.findall(r"^amove (\S+) (\S+)$", text, re.MULTILINE)
    sizes = re.findall(r"^[ \t]+size (\S+) (\S+)$", text, re.MULTILINE)
    return [tuple(map(float, a + s)) for a, s in zip(amoves, sizes)]


def _square(aspect=None, **limits):
    fig, ax = glp.subplots(figsize=(6, 4))
    ax.plot([0, 2], [0, 1])
    ax.set_xlim(*limits.get("x", (0, 2)))
    ax.set_ylim(*limits.get("y", (0, 1)))
    if aspect is not None:
        ax.set_aspect(aspect)
    return fig, ax


def test_equal_gives_a_unit_the_same_length_on_both_axes():
    fig, ax = _square()
    x0, y0, w0, h0 = _frames(fig)[0]
    ax.set_aspect("equal")
    x, y, w, h = _frames(fig)[0]
    assert h / w == pytest.approx(1 / 2, rel=1e-4)
    assert max(w0 - w, h0 - h) > 0 and min(w0 - w, h0 - h) == pytest.approx(0)
    # Centred in the place the frame had.
    assert x + w / 2 == pytest.approx(x0 + w0 / 2, abs=1e-4)
    assert y + h / 2 == pytest.approx(y0 + h0 / 2, abs=1e-4)


def test_numeric_aspect_scales_the_y_unit():
    fig, _ax = _square(aspect=0.5, y=(0, 2))
    _x, _y, w, h = _frames(fig)[0]
    assert h / w == pytest.approx(0.5, rel=1e-4)


def test_log_axis_is_measured_in_decades():
    fig, ax = _square(x=(0, 2), y=(1, 100))
    ax.set_yscale("log")
    ax.set_aspect("equal")
    _x, _y, w, h = _frames(fig)[0]
    assert h / w == pytest.approx(1.0, rel=1e-4)


def test_auto_restores_the_full_frame():
    fig, ax = _square()
    plain = _frames(fig)
    ax.set_aspect(3)
    ax.set_aspect("auto")
    assert _frames(fig) == plain


def test_one_panel_of_a_grid():
    fig, (left, right) = glp.subplots(1, 2, figsize=(8, 4))
    left.plot([0, 1], [0, 1])
    right.plot([0, 1], [0, 1])
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    plain = _frames(fig)
    right.set_aspect("equal")
    frames = _frames(fig)
    assert frames[0] == plain[0]
    assert frames[1][2] == pytest.approx(frames[1][3], rel=1e-4)


def test_get_aspect():
    _fig, ax = glp.subplots()
    assert ax.get_aspect() == "auto"
    ax.set_aspect("equal")
    assert ax.get_aspect() == 1.0
    ax.set_aspect(2)
    assert ax.get_aspect() == 2.0
    polar = glp.figure().add_subplot(projection="polar")
    assert polar.get_aspect() == 1.0


@pytest.mark.parametrize("aspect", [0, -1, float("nan"), "square"])
def test_bad_aspect_raises(aspect):
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="finite positive"):
        ax.set_aspect(aspect)


@pytest.mark.parametrize("aspect", [None, [1, 2]])
def test_wrong_type_aspect_raises_type_error(aspect):
    _fig, ax = glp.subplots()
    with pytest.raises(TypeError, match="finite positive"):
        ax.set_aspect(aspect)


def test_a_bad_aspect_raises_before_any_warning():
    _fig, ax = glp.subplots()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ValueError):
            ax.set_aspect(-1, share=True)


def test_bad_anchor_raises():
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="anchor"):
        ax.set_aspect("equal", anchor="X")


def test_bad_adjustable_raises():
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="adjustable"):
        ax.set_aspect("equal", adjustable="figure")


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"adjustable": "datalim"}, "datalim"),
        ({"anchor": "SW"}, "anchor"),
        ({"anchor": (0.0, 0.5)}, "anchor"),
        ({"share": True}, "share"),
    ],
)
def test_unsupported_keywords_warn(kwargs, match):
    _fig, ax = glp.subplots()
    with pytest.warns(UserWarning, match=match):
        ax.set_aspect("equal", **kwargs)
    assert ax.get_aspect() == 1.0


def test_polar_set_aspect_raises():
    polar = glp.figure().add_subplot(projection="polar")
    with pytest.raises(NotImplementedError):
        polar.set_aspect("equal")


def test_no_range_warns_and_skips():
    fig, ax = glp.subplots()
    plain = _frames(fig)
    ax.set_aspect("equal")
    with pytest.warns(UserWarning, match="set_aspect"):
        fig._generate_gle()
    assert _frames(fig) == plain


def test_fullsize_warns():
    fig = glp.figure(graph=GLEGraphConfig(scale_mode="fullsize"))
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1])
    ax.set_aspect("equal")
    with pytest.warns(UserWarning, match="fullsize"):
        fig._generate_gle()


def test_aspect_round_trips_through_to_dict():
    fig, ax = _square(aspect=2)
    payload = fig.to_dict()
    restored = Figure.from_dict(json.loads(json.dumps(payload)))
    assert restored.axes_list[0].get_aspect() == 2.0
    assert restored.to_dict() == payload


def test_unset_aspect_leaves_to_dict_unchanged():
    _fig, ax = glp.subplots()
    assert "aspect" not in ax.to_dict()


def test_inset_aspect_shrinks_its_own_rect():
    fig, ax = _square()
    inset = fig.add_axes([0.5, 0.5, 0.4, 0.2])
    inset.plot([0, 1], [0, 1])
    inset.set_xlim(0, 1)
    inset.set_ylim(0, 1)
    inset.set_aspect("equal")
    _x, _y, w, h = _frames(fig)[1]
    assert w == pytest.approx(h, rel=1e-4)
