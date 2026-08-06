"""Every axes-styling clause gleplot emits is one the real GLE binary accepts.

The writer/recognizer batteries round-trip their GLE as *text*; only a real
compile proves the spellings taken from the manual (``xaxis format``, ``xaxis
angle``, ``xaxis grid``, ``xticks``/``xsubticks`` style, ``title``/``xtitle``
``hei``/``color``/``dist``, ``y2labels on``) are the ones GLE 4.3.10 parses.
Skipped when GLE is not installed.

``y2labels on`` earns its own case: GLE draws no y2 tick labels without it
unless a plotted series actually uses the y2 axis (GLE auto-enables labels
for an axis carrying a dataset -- see ``GLEWriter.add_axes``). A y2 axis
that is merely *configured* (limits/log/title) with nothing plotted on it,
or additionally styled, would otherwise compile happily and render
nothing -- the failure mode a text-only test cannot see.
"""

from __future__ import annotations

import re
import subprocess

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler, find_gle


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _assert_compiles(fig, tmp_path, name):
    """Compile to PDF. ``savefig`` raises if GLE rejects the script."""
    out = fig.savefig(str(tmp_path / f"{name}.pdf"))
    assert out.exists() and out.stat().st_size > 0
    return out


def _base():
    fig = glp.figure(data_prefix="stylec")
    ax = fig.add_subplot(111)
    x = np.linspace(1.0, 10.0, 20)
    ax.plot(x, x**2, label="quad")
    return fig, ax


@pytest.mark.parametrize(
    "fmt",
    [
        "fix 1",
        "sci 2 10",
        "eng 2",
        "round 3",
        "percent 0",
        "pi",
        "sci 2 10 min 1e2 fix 0",
    ],
)
def test_tick_label_formats_compile(tmp_path, fmt):
    fig, ax = _base()
    ax.set_tick_format(fmt)
    _assert_compiles(fig, tmp_path, "fmt")


@pytest.mark.parametrize("which", ["major", "both"])
def test_grids_compile(tmp_path, which):
    fig, ax = _base()
    ax.grid(True, which=which, linestyle=":", linewidth=0.4, color="gray40")
    _assert_compiles(fig, tmp_path, "grid")


def test_titles_labels_and_angles_compile(tmp_path):
    fig, ax = _base()
    ax.set_title("Styled")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.title_size, ax.title_color, ax.title_dist = 14, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10, "BLUE", 0.35
    ax.ylabel_size, ax.ylabel_color = 9, "GREEN"
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7, "ORANGE", 45
    _assert_compiles(fig, tmp_path, "titles")


def test_everything_at_once_compiles(tmp_path):
    fig, ax = _base()
    ax.set_title("Styled")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_ylabel("Y2", axis="y2")
    ax.set_ylim(0, 1000, axis="y2")
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2 10", axis="y2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10, "BLUE", 0.35
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7, "ORANGE", 45
    ax.y2ticklabel_size = 6
    ax.legend()
    _assert_compiles(fig, tmp_path, "all")


_INK_RE = re.compile(r"INKBOX ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+)")


def _ink_right_edge_cm_text(text, tmp_path, name):
    """Page-cm x of the rightmost ink in ``text``, a full ``.gle`` script.

    Same ``begin name`` + ``print ptx/pty`` probe ``test_ink_on_page.py``
    uses: it sees ink wherever GLE actually put it, including outside the
    page, which a raster or PDF bounding box would clip. Takes raw script
    text (rather than a :class:`~gleplot.figure.Figure`) so a caller can
    compile two byte-identical-except-for-one-line variants -- e.g. with and
    without a single ``y2labels on`` line -- without gleplot's own
    auto-margin sizing (which reserves extra space once a y2 axis is
    configured) confounding the comparison with a frame-geometry change.
    """
    (tmp_path / f"{name}.gle").write_text(text, encoding="utf-8")
    lines = text.split("\n")
    cut = next(i for i, line in enumerate(lines) if line.startswith("size ")) + 1
    probe = "\n".join(
        lines[:cut]
        + ["begin name inkbox"]
        + lines[cut:]
        + [
            "end name",
            'print "INKBOX" ptx(inkbox.bl) pty(inkbox.bl) '
            "ptx(inkbox.tr) pty(inkbox.tr)",
            "",
        ]
    )
    (tmp_path / f"{name}_probe.gle").write_text(probe, encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", f"{name}_probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    found = _INK_RE.search(proc.stdout + proc.stderr)
    assert found is not None, f"no ink box:\n{proc.stdout}\n{proc.stderr}"
    return float(found.group(3))


def _ink_right_edge_cm(fig, tmp_path, name):
    """Page-cm x of the rightmost ink in the compiled figure."""
    fig.savefig_gle(str(tmp_path / f"{name}.gle"))
    text = (tmp_path / f"{name}.gle").read_text(encoding="utf-8")
    return _ink_right_edge_cm_text(text, tmp_path, name)


def _configured_y2_script(tmp_path):
    """A figure with explicit y2 limits, no styling, and nothing plotted on
    y2 -- the case that used to compile with mirrored tick marks and no
    numbers (see ``GLEWriter.add_axes``'s note on the fix). Returns its
    generated ``.gle`` text, with sidecars written alongside so it compiles.
    """
    fig = glp.figure(data_prefix="y2u")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_ylim(1000.0, 3000.0, axis="y2")
    fig.savefig_gle(str(tmp_path / "with_labels.gle"))
    return (tmp_path / "with_labels.gle").read_text(encoding="utf-8")


def test_a_configured_y2_axis_labels_the_right_axis_even_unstyled(tmp_path):
    """Without ``y2labels on`` GLE draws no y2 numbers at all -- a y2 axis
    that is configured (explicit limits here) but carries no styling and no
    plotted series would compile happily and render nothing. The proof is
    ink: the ``y2labels on`` line the writer now emits for this case must
    push the rightmost ink further right than the byte-identical script with
    only that one line removed, because numbers now sit outside the frame.

    Comparing against gleplot's own "no y2 at all" build would confound the
    result with ``Figure._auto_margins_cm``'s y2 margin reservation (which
    keys off the same explicit-limits signal and so changes the frame's
    geometry, not just its ink) -- surgically removing just the
    ``y2labels on`` line holds geometry fixed and isolates the one line's
    effect, matching this file's ``format``-is-applied test below.

    (When a series is actually plotted *on* y2, GLE auto-enables its labels
    on its own -- see ``GLEWriter.add_axes``'s note on
    ``do_each_dataset_settings`` -- so this specifically exercises the
    axis-configured-but-dataless case, which is what used to render blank.)
    """
    with_labels = _configured_y2_script(tmp_path)
    assert "\n    y2labels on\n" in with_labels
    without_labels = with_labels.replace("\n    y2labels on\n", "\n", 1)

    labelled = _ink_right_edge_cm_text(with_labels, tmp_path, "labelled")
    blank = _ink_right_edge_cm_text(without_labels, tmp_path, "blank")
    assert labelled > blank + 0.1, (blank, labelled)


def test_a_y2_format_is_actually_applied(tmp_path):
    """A y2 tick-label format must still take effect, not just switch numbers
    on: with y2 limits alone (unstyled) the axis already shows default
    numbers (the test above), so the proof that ``format`` itself is
    honoured needs a format that is unambiguously wider than the default
    rendering -- zero-padded to 8 digits (``1000`` -> ``00001000``) -- and
    the ink must move further right still, holding the rest of the script
    (and so the frame geometry) identical.
    """

    def build(with_format):
        fig = glp.figure(data_prefix=f"y2f{int(with_format)}")
        ax = fig.add_subplot(111)
        ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
        ax.set_ylim(1000.0, 3000.0, axis="y2")
        if with_format:
            ax.set_tick_format("fix 0 prefix 8", axis="y2")
        return fig

    plain = _ink_right_edge_cm(build(False), tmp_path, "plain")
    labelled = _ink_right_edge_cm(build(True), tmp_path, "labelled")
    assert labelled > plain + 0.1, (plain, labelled)
