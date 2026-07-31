"""Matplotlib-compatible ``zorder`` controls GLE ``dN`` emission order."""

from __future__ import annotations

import re

import pytest

import gleplot as glp


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig, tmp_path):
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    return gle_path.read_text(encoding="utf-8")


def _dataset_commands(script: str) -> list[str]:
    return [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]


def _command_index(cmd: str) -> int:
    m = re.match(r"d(\d+)", cmd.split()[0])
    assert m, cmd
    return int(m.group(1))


def test_default_draw_order_keeps_lines_below_errorbars(tmp_path):
    """Call order alone must not reorder layers when ``zorder`` is omitted."""
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2], [1, 2], yerr=0.1, fmt="o", label="data")
    ax.plot([1, 2], [1, 2], linestyle="--", label="fit")

    cmds = _dataset_commands(_script(fig, tmp_path))
    assert len(cmds) == 2
    line_cmd, err_cmd = cmds
    assert "line" in line_cmd or "lstyle" in line_cmd
    assert "err" in err_cmd
    assert _command_index(line_cmd) < _command_index(err_cmd)


def test_zorder_puts_fit_line_on_top(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2], [1, 2], yerr=0.1, fmt="o", zorder=1, label="data")
    ax.plot([1, 2], [1, 2], linestyle="--", zorder=2, label="fit")

    cmds = _dataset_commands(_script(fig, tmp_path))
    assert len(cmds) == 2
    err_cmd, line_cmd = cmds
    assert "err" in err_cmd
    assert _command_index(line_cmd) > _command_index(err_cmd)


def test_equal_zorder_preserves_call_order(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([1], [1], color="RED", zorder=2, label="first")
    ax.plot([2], [2], color="BLUE", zorder=2, label="second")

    cmds = _dataset_commands(_script(fig, tmp_path))
    assert len(cmds) == 2
    assert "RED" in cmds[0]
    assert "BLUE" in cmds[1]


def test_zorder_round_trips_through_to_dict(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.errorbar([1], [1], yerr=0.1, fmt="o", zorder=1)
    ax.plot([1], [1], zorder=3)

    restored = glp.Figure.from_dict(fig.to_dict())
    rax = restored.axes_list[0]
    assert rax.errorbars[0]["zorder"] == 1.0
    assert rax.lines[0]["zorder"] == 3.0
    assert _script(fig, tmp_path) == _script(restored, tmp_path)


def test_broken_axes_forwards_zorder(tmp_path):
    fig = glp.figure()
    bax = fig.add_broken_xaxes([(0.0, 1.0), (2.0, 3.0)], width_ratios=[1, 1])
    bax.errorbar([0.5, 2.5], [1, 1], yerr=0.1, fmt="o", zorder=1)
    bax.plot([0.5, 2.5], [1, 1], linestyle="--", zorder=2)

    script = _script(fig, tmp_path)
    graph_blocks = script.split("end graph")
    drawable_blocks = [b for b in graph_blocks if re.search(r"\bd\d+\s", b)]
    assert len(drawable_blocks) == 2
    for block in drawable_blocks:
        cmds = [ln.strip() for ln in block.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]
        assert len(cmds) == 2
        assert "err" in cmds[0]
        assert _command_index(cmds[1]) > _command_index(cmds[0])
