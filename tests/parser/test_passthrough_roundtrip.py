"""THE key test: byte-exact passthrough of real gleplot output.

Two batteries:

1. *Generated* -- every gleplot feature is exercised via the public API (a
   builder set mirroring ``tests/integration/test_project_io.py``), the figure
   is saved to a temporary ``.gle`` file, that file is read back, parsed with
   :func:`parse_gle_source`, and re-emitted. The re-emitted bytes must equal
   the file bytes exactly.

2. *Hand-written nasty cases* -- odd spacing, comments everywhere, semicolons,
   opaque ``begin``/``end`` blocks, and an unbalanced block. Each must
   re-emit byte-identically.
"""

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure
from gleplot.parser import emit, parse_gle_source


# --------------------------------------------------------------------------- #
# Figure builders (mirror the integration battery)
# --------------------------------------------------------------------------- #

def _single_line():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color="blue", label="quad")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("single line")
    return fig


def _multi_series_styles():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 20)
    ax.plot(x, np.sin(x), color="red", linestyle="--", linewidth=2, label="sin")
    ax.plot(x, np.cos(x), color="green", linestyle=":", label="cos")
    ax.plot(x, np.sin(x) * 0.5, color="blue", marker="o", linestyle="none",
            markersize=8, label="half")
    ax.legend(loc="upper left")
    return fig


def _scatter():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3, 4], [4, 3, 2, 1], color="purple", s=40, marker="s",
               label="pts")
    ax.legend()
    return fig


def _bar():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color="orange")
    ax.set_title("bar")
    return fig


def _errorbar_symmetric():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.5, color="red", marker="o",
                capsize=4, label="sym")
    ax.legend()
    return fig


def _errorbar_asymmetric():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6],
                yerr=([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]),
                color="blue", marker="s", capsize=3)
    return fig


def _errorbar_xerr():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.3, xerr=0.2, capsize=5,
                color="green", marker="^")
    return fig


def _fill_between():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), x ** 0.5, color="lightblue", alpha=0.4)
    ax.plot(x, x ** 0.5, color="blue")
    return fig


def _text_annotations():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.text(1.5, 2.0, "peak", color="red", fontsize=14, ha="center")
    ax.text(2.5, 1.0, "boxed", bbox={"facecolor": "yellow"})
    return fig


def _log_scales():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    x = np.array([1, 10, 100, 1000], dtype=float)
    ax.plot(x, x ** 2, color="blue")
    ax.set_xscale("log")
    ax.set_yscale("log")
    return fig


def _limits():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16])
    ax.set_xlim(0, 5)
    ax.set_ylim(-1, 20)
    return fig


def _legend_positions():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="a")
    ax.legend(loc="lower right")
    return fig


def _secondary_yaxis():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color="blue", label="left", yaxis="y")
    ax.plot([1, 2, 3], [100, 200, 300], color="red", label="right", yaxis="y2")
    ax.set_ylabel("left y")
    ax.set_ylabel("right y", axis="y2")
    ax.set_ylim(0, 400, axis="y2")
    ax.set_yscale("log", axis="y2")
    ax.legend()
    return fig


def _subplots_sharex():
    fig, axes = glp.subplots(3, 1, sharex=True, data_prefix="fig")
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f"s{i}")
        ax.set_ylabel(f"y{i}")
    axes[-1].set_xlabel("shared x")
    return fig


def _subplots_sharey_adjust():
    fig, axes = glp.subplots(1, 3, sharey=True, data_prefix="fig")
    for i, ax in enumerate(axes):
        ax.bar([1, 2, 3], [i + 1, i + 2, i + 3], color="teal")
        ax.set_title(f"c{i}")
    fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.15, wspace=0.3)
    return fig


def _subplots_grid():
    fig, axes = glp.subplots(2, 2, data_prefix="fig")
    axes[0].plot([1, 2, 3], [1, 2, 3])
    axes[1].scatter([1, 2, 3], [3, 2, 1], marker="o")
    axes[2].bar([1, 2, 3], [2, 4, 6], color="red")
    axes[3].errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, capsize=3)
    fig.subplots_adjust(hspace=0.4, wspace=0.4)
    return fig


def _file_series():
    fig = glp.figure(data_prefix="fig")
    ax = fig.add_subplot(111)
    ax.line_from_file("external.dat", 1, 2, color="blue", linestyle="--",
                      label="line-file")
    ax.errorbar_from_file("external.dat", 1, 2, yerr_col=3, color="red",
                          marker="o", capsize=4, label="eb-file")
    ax.legend()
    return fig


def _data_prefix_multi():
    fig = glp.figure(data_prefix="myrun")
    ax = fig.add_subplot(111)
    for i in range(4):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f"l{i}")
    ax.legend()
    return fig


def _passthrough_buckets():
    """Track B2: Figure.passthrough_header/trailer, Axes.passthrough, and
    Figure.metadata_extra all populated. The metadata block and passthrough
    lines are plain GLE-comment/statement text, so they must round-trip
    through the structural parser exactly like everything else here."""
    fig = glp.figure(data_prefix="fig")
    fig.passthrough_header = ["! recovered header comment", "set some_directive 1"]
    fig.passthrough_trailer = ["! recovered trailer comment"]
    fig.metadata_extra = {"future_key": "future_value"}
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color="blue", label="quad")
    ax.passthrough = ["! recovered axes-local comment", "amove 1 1"]
    return fig


BUILDERS = [
    _single_line,
    _multi_series_styles,
    _scatter,
    _bar,
    _errorbar_symmetric,
    _errorbar_asymmetric,
    _errorbar_xerr,
    _fill_between,
    _text_annotations,
    _log_scales,
    _limits,
    _legend_positions,
    _secondary_yaxis,
    _subplots_sharex,
    _subplots_sharey_adjust,
    _subplots_grid,
    _file_series,
    _data_prefix_multi,
    _passthrough_buckets,
]

BUILDER_IDS = [b.__name__.lstrip("_") for b in BUILDERS]


# --------------------------------------------------------------------------- #
# Battery 1: generated figures -> savefig_gle -> parse -> emit, byte-identical
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("builder", BUILDERS, ids=BUILDER_IDS)
def test_generated_gle_roundtrips_byte_identical(builder, tmp_path):
    fig = builder()
    out = tmp_path / "plot.gle"
    fig.savefig_gle(str(out))

    original_bytes = out.read_bytes()
    text = original_bytes.decode("utf-8")

    doc = parse_gle_source(text)
    reemitted = emit(doc)

    assert reemitted == text, (
        f"round-trip mismatch for {builder.__name__}"
    )
    assert reemitted.encode("utf-8") == original_bytes
    # Well-formed gleplot output must parse without structural warnings.
    assert doc.warnings == [], [str(w) for w in doc.warnings]


@pytest.mark.parametrize("builder", BUILDERS, ids=BUILDER_IDS)
def test_generated_gle_has_expected_structure(builder, tmp_path):
    """Sanity: every generated figure yields at least one graph block."""
    fig = builder()
    out = tmp_path / "plot.gle"
    fig.savefig_gle(str(out))
    doc = parse_gle_source(out.read_text(encoding="utf-8"))
    assert len(doc.graphs) >= 1


# --------------------------------------------------------------------------- #
# Battery 2: hand-written nasty strings
# --------------------------------------------------------------------------- #

NASTY_CASES = {
    "odd_spacing": (
        "size   20    15\n"
        "\t\tset hei 0.5\n"
        "begin graph\n"
        "        d1   line    color   BLUE\n"
        "end graph\n"
    ),
    "comments_everywhere": (
        "! top comment\n"
        "size 20 15   ! inline after command\n"
        "! another\n"
        "begin graph ! comment on begin\n"
        '    title "hi" ! titled\n'
        "    ! comment-only inside graph\n"
        "end graph ! and the end\n"
    ),
    "semicolons_and_strings": (
        'write "a ; b ; c"; amove 1 1; set hei 0.5\n'
        'draw "d ! not a comment ; nope"\n'
    ),
    "opaque_blocks": (
        "size 20 15\n"
        "begin object myobj\n"
        "   this ; is opaque\n"
        '   "with quotes" and ! bangs\n'
        "   begin graph\n"          # even a nested-looking graph stays opaque
        "   end graph\n"
        "end object\n"
        "amove 5 5\n"
        "begin text\n"
        "  lorem ipsum\n"
        "end text\n"
    ),
    "unbalanced_block": (
        "size 20 15\n"
        "begin graph\n"
        "   d1 line\n"
        "! oops, forgot to close the graph\n"
    ),
    "no_trailing_newline_crlf": (
        "size 20 15\r\n"
        "begin graph\r\n"
        "end graph"
    ),
}


@pytest.mark.parametrize("name", list(NASTY_CASES), ids=list(NASTY_CASES))
def test_nasty_cases_roundtrip_byte_identical(name):
    src = NASTY_CASES[name]
    doc = parse_gle_source(src)
    assert emit(doc) == src


def test_unbalanced_case_records_warning():
    doc = parse_gle_source(NASTY_CASES["unbalanced_block"])
    assert any("not closed" in w.message for w in doc.warnings)


def test_opaque_case_keeps_nested_graph_opaque():
    doc = parse_gle_source(NASTY_CASES["opaque_blocks"])
    from gleplot.parser.syntax import OpaqueBlock
    obj = next(n for n in doc.nodes
               if isinstance(n, OpaqueBlock) and n.block_type == "object")
    # The inner 'begin graph'/'end graph' were kept as raw inner lines, not
    # parsed into a GraphBlock.
    assert len(doc.graphs) == 0
    assert any("begin graph" in ln.text for ln in obj.inner_lines)
