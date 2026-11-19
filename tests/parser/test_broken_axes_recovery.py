"""Parser behaviour on a generated broken-axis script (x or y).

The recognizer has no notion of a :class:`~gleplot.brokenaxes.BrokenAxes` and
is not expected to reconstruct one. What it *must* do is degrade to
passthrough preservation: parse without raising, keep every plotted series,
keep the axis options it cannot model (``dticks``, ``yaxis off``) and
keep the seam decoration -- and warn about what it could not model, so the
loss is never silent. These tests pin that contract down.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.parser.recognizer import parse_gle_figure

T = np.linspace(0.0, 3.0, 20)
A = np.exp(-T)


@pytest.fixture
def broken_script(tmp_path):
    """A saved broken-axis ``.gle`` (with its sidecars) on disk.

    Written out rather than parsed from a string so the recognizer can read
    the ``.dat`` files back as real series instead of falling back to
    file-reference entries with a "data file not found" warning.
    """
    fig = glp.figure(figsize=(6.0, 4.0), data_prefix="rt")
    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)], width_ratios=[1, 3], divider="slash"
    )
    bax.set_ylim(0.0, 1.0)
    bax.errorbar(T, A, yerr=0.02, fmt="none", marker="o")
    bax.axhline(0.1, color="gray")
    bax.set_ylabel("Asymmetry (%)")
    bax.set_xlabel("t (us)")
    bax.set_xticks(dticks=[0.01, 1.0])
    return fig.savefig_gle(str(tmp_path / "broken.gle"))


def test_parses_without_raising(broken_script):
    recognized = parse_gle_figure(broken_script)
    assert len(recognized.figure.axes_list) == 2


def test_the_broken_axis_structure_is_not_recovered(broken_script):
    """Documented limitation, asserted so it cannot regress into a crash."""
    recognized = parse_gle_figure(broken_script)
    assert recognized.figure.broken_axes == []
    assert all(ax._break_owner is None for ax in recognized.figure.axes_list)


def test_every_plotted_series_survives(broken_script):
    recognized = parse_gle_figure(broken_script)
    for ax in recognized.figure.axes_list:
        assert len(ax.errorbars) == 1
        # The axhline comes back a guide, not the two-point line it
        # materialized into: the emission carries a provenance marker
        # (G18-lite). Before that it was recovered as a plain LineSeries --
        # same picture, but no longer editable as a guide and no longer
        # re-materialized against the range of the figure it reopened into.
        assert len(ax.reflines) == 1
        assert ax.reflines[0]["orient"] == "h"
        assert ax.reflines[0]["value"] == pytest.approx(0.1)
        assert len(ax.lines) == 0


def test_unmodellable_axis_options_are_preserved_and_warned_about(broken_script):
    recognized = parse_gle_figure(broken_script)
    passthrough = "\n".join(
        line for ax in recognized.figure.axes_list for line in ax.passthrough
    )
    assert "dticks 0.01" in passthrough
    assert "yaxis" in passthrough and "off" in passthrough

    joined = " ".join(recognized.warnings)
    assert "dticks" in joined
    assert "off" in joined


def test_seam_decoration_and_shared_title_survive_as_trailer_passthrough(
    broken_script,
):
    recognized = parse_gle_figure(broken_script)
    trailer = "\n".join(recognized.figure.passthrough_trailer)
    assert "xg(xgmax)" in trailer  # the double-slash break marks
    assert 't (us)"' in trailer  # the centred x title


def test_reemission_keeps_the_preserved_content(broken_script):
    recognized = parse_gle_figure(broken_script)
    reemitted = recognized.figure._generate_gle_with_files()[0]

    for fragment in ("dticks 0.01", "y2axis off", "xg(xgmax)", 't (us)"'):
        assert fragment in reemitted


# --------------------------------------------------------------------------- #
# Broken y-axis: the same contract
# --------------------------------------------------------------------------- #


@pytest.fixture
def broken_y_script(tmp_path):
    """A saved broken-y-axis ``.gle`` (with its sidecars) on disk."""
    fig = glp.figure(figsize=(4.0, 3.2), data_prefix="ry")
    bax = fig.add_broken_yaxes([(0.0, 1.0), (10.0, 12.0)], divider="slash")
    bax.bar([1, 2, 3], [0.4, 0.8, 11.0])
    bax.set_ylabel("Counts")
    bax.set_title("Outliers")
    bax.set_yticks(dticks=[0.2, 1.0])
    return fig.savefig_gle(str(tmp_path / "broken_y.gle"))


def test_broken_y_parses_into_independent_subplots(broken_y_script):
    recognized = parse_gle_figure(broken_y_script)
    assert recognized.figure.broken_axes == []
    assert [len(ax.bars) for ax in recognized.figure.axes_list] == [1, 1]


def test_broken_y_axis_options_are_preserved_and_warned_about(broken_y_script):
    recognized = parse_gle_figure(broken_y_script)
    passthrough = "\n".join(
        line for ax in recognized.figure.axes_list for line in ax.passthrough
    )
    assert "xaxis off" in passthrough and "x2axis on" in passthrough
    joined = " ".join(recognized.warnings)
    assert "xaxis" in joined and "off" in joined


def test_broken_y_seam_and_shared_titles_survive_re_emission(broken_y_script):
    recognized = parse_gle_figure(broken_y_script)
    trailer = "\n".join(recognized.figure.passthrough_trailer)
    assert "xg(xgmax)-0.2 yg(ygmax)" in trailer  # the break marks
    assert 'write "Counts"' in trailer and 'write "Outliers"' in trailer
    reemitted = recognized.figure._generate_gle_with_files()[0]
    for fragment in ("x2axis on", "begin rotate 90", 'write "Outliers"'):
        assert fragment in reemitted
