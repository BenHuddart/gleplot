"""The legend ``offset`` extension: GLE's ``key ... offset dx dy``.

A gleplot extension (not a matplotlib kwarg): ``legend(offset=(dx, dy))``
displaces the key from its anchor by centimetres, positive dy moving DOWN,
following GLE's own convention.  It exists because precise key placement
relative to other in-panel elements (e.g. "just below the panel letter") is
not expressible through the nine anchors alone.
"""

import warnings

import numpy as np
import pytest

import gleplot as glp


def _gle_text(fig, tmp_path):
    path = tmp_path / "fig.gle"
    fig.savefig(str(path))
    return path.read_text()


def _key_line(text):
    lines = [l for l in text.splitlines() if l.strip().startswith("key ")]
    assert len(lines) == 1, lines
    return lines[0]


def test_offset_is_emitted_in_cm(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    ax.legend(loc="upper right", offset=(0.1, 0.45))
    line = _key_line(_gle_text(fig, tmp_path))
    assert "pos tr" in line
    assert "offset 0.1 0.45" in line


def test_offset_combines_with_fontsize_and_frameon(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    ax.legend(loc="upper right", fontsize=6.5, frameon=False, offset=(0.0, 0.4))
    line = _key_line(_gle_text(fig, tmp_path))
    assert "offset 0 0.4" in line
    assert "hei" in line
    assert "nobox" in line


def test_no_offset_is_byte_identical_to_before(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    ax.legend(loc="upper right")
    line = _key_line(_gle_text(fig, tmp_path))
    assert "offset" not in line


def test_offset_none_clears(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    ax.legend(offset=(0.1, 0.2))
    ax.legend(offset=None)
    line = _key_line(_gle_text(fig, tmp_path))
    assert "offset" not in line


def test_bad_offset_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    with pytest.raises(ValueError, match="offset"):
        ax.legend(offset="up a bit")


def test_offset_does_not_warn():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ax.legend(offset=(0.1, 0.2))


def test_offset_round_trips_through_parser(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot(np.linspace(0, 1, 5), np.linspace(0, 1, 5), label="a")
    ax.legend(loc="upper right", fontsize=7.0, frameon=False, offset=(0.15, 0.4))
    path = tmp_path / "fig.gle"
    fig.savefig(str(path))
    first = path.read_text()

    fig2 = glp.open_gle(str(path))
    ax2 = fig2.axes_list[0]
    assert ax2.legend_offset == pytest.approx((0.15, 0.4))
    path2 = tmp_path / "fig2.gle"
    fig2.savefig(str(path2))
    assert _key_line(path2.read_text()) == _key_line(first)


def test_offset_survives_to_dict_from_dict():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="a")
    ax.legend(offset=(0.2, 0.3))
    d = ax.to_dict()
    assert d["legend_offset"] == [0.2, 0.3] or d["legend_offset"] == (0.2, 0.3)
