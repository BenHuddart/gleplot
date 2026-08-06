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
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.parser.units import fontsize_cm_to_pt


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


def test_negative_offset_component_round_trips_through_parser(tmp_path):
    """A negative offset component must not be dropped by the recognizer.

    GLE's tokenizer has no signed-literal NUMBER: 'offset 1.5 -0.5' lexes as
    NUMBER('1.5') OP('-') NUMBER('0.5'), which the (fixed) recognizer must
    still read as the literal pair (1.5, -0.5), not bail to raw passthrough.
    """
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot(np.linspace(0, 1, 5), np.linspace(0, 1, 5), label="a")
    ax.legend(loc="lower left", fontsize=9.0, offset=(1.5, -0.5))
    path = tmp_path / "fig.gle"
    fig.savefig(str(path))
    first = path.read_text()

    fig2 = glp.open_gle(str(path))
    ax2 = fig2.axes_list[0]
    assert ax2.legend_offset == pytest.approx((1.5, -0.5))
    assert ax2.legend_pos == "bottom left"
    assert ax2.legend_fontsize == pytest.approx(9.0, abs=1e-3)
    path2 = tmp_path / "fig2.gle"
    fig2.savefig(str(path2))
    assert _key_line(path2.read_text()) == _key_line(first)


def test_reviewer_reproducer_string_is_fully_recognized(tmp_path):
    """The exact Phase-5 gate reproducer: every 'key' option is modelled.

    Before the fix, this line -- byte-for-byte what GLEWriter.add_legend
    emits for a legend with an offset and a fontsize -- fell through
    ``_scan_key_options`` (the negative offset component broke the literal-
    number scan), so the WHOLE line was kept as raw passthrough: legend_pos
    stayed at its 'top right' default ('bl' silently ignored), legend_offset
    and legend_fontsize stayed None, and only frameon (already True by
    default) looked "recognized". Zero warnings pointed at the loss.
    """
    src = (
        "size 10 10\n"
        "begin graph\n"
        "   data data_a.dat d1=c1,c2\n"
        '   d1 line color blue key "s"\n'
        "   key pos bl offset 1.5 -0.5 hei 0.31746\n"
        "end graph\n"
    )
    data_file = tmp_path / "data_a.dat"
    data_file.write_text("0 0\n1 1\n")
    gle_file = tmp_path / "k.gle"
    gle_file.write_text(src)

    rec = parse_gle_figure(gle_file)
    ax = rec.figure.axes_list[0]

    assert ax.legend_pos == "bottom left"
    assert ax.legend_offset == pytest.approx((1.5, -0.5))
    assert ax.legend_fontsize == pytest.approx(fontsize_cm_to_pt(0.31746))
    assert ax.legend_frameon is True
    assert not any("unsupported options" in w for w in rec.warnings)

    out = tmp_path / "k2.gle"
    rec.figure.savefig_gle(str(out))
    assert "key pos bl offset 1.5 -0.5 hei 0.31746" in out.read_text()
