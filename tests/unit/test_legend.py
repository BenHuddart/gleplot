"""Legend visibility semantics.

``Axes.legend_on`` is tri-state:

* ``None`` (default) — auto: a legend is shown iff any series has a label.
* ``True`` — always show (what ``Axes.legend()`` sets).
* ``False`` — never show; the writer must emit ``key off`` because GLE
  draws an implicit key from per-dataset ``key "label"`` tokens.

Regression tests for the GUI legend toggle having no effect.
"""

import gleplot as glp


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

import pytest

from gleplot.parser.units import fontsize_pt_to_cm
from gleplot.writer import GLEWriter


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


def test_ncol_above_one_warns():
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="single column"):
        ax.legend(ncol=2)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"framealpha": 0.5},
        {"edgecolor": "black"},
        {"shadow": True},
        {"bbox_to_anchor": (1.0, 1.0)},
        {"markerscale": 2.0},
        {"title": "Models"},
        {"borderpad": 0.2},
    ],
)
def test_unsupported_kwargs_warn(kwargs):
    """Silent parameter swallowing was the bug; every survivor must speak."""
    fig, ax = _labeled_figure()
    with pytest.warns(UserWarning, match="not supported"):
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
