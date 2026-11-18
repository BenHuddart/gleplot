"""A box plot compiles, with its tick labels, and its caps are drawn whole.

The script text is asserted in ``tests/unit/test_boxplot.py``. This checks
that GLE accepts the ``gleplot_box`` subs and their calls after ``end
graph``, and that the clip to the frame leaves a cap lying on the frame
whole. Skipped when the binary is missing.
"""

from __future__ import annotations

import re
import struct
import zlib

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_box_plot_with_fliers_means_and_tick_labels_compiles(tmp_path):
    fig, ax = glp.subplots()
    ax.boxplot(
        [[1, 2, 3, 4, 5, 6, 7, 8, 9, 100], [2, 3, 4]],
        tick_labels=["Frogs", "Hogs"],
        showmeans=True,
    )
    out = tmp_path / "box.eps"
    fig.savefig(str(out))
    eps = out.read_text(encoding="latin-1")
    # GLE writes text one glyph at a time: '(F) s'.
    glyphs = "".join(re.findall(r"^\((.)\) s$", eps, flags=re.MULTILINE))
    for word in ("Frogs", "Hogs"):
        assert word in glyphs


def _png_rows(path):
    """Decode an 8-bit RGB PNG, as GLE writes it, into rows of bytes."""
    data = path.read_bytes()
    pos, idat = 8, b""
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + size]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", body[:10])
            assert (depth, colour) == (8, 2)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + size
    raw = zlib.decompress(idat)
    stride = 3 * width
    rows, prev = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            a = line[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                near = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + near) & 255
        rows.append(bytes(line))
        prev = line
    return width, rows


def test_caps_on_the_frame_are_drawn_whole(tmp_path):
    # Autoscaled, the whisker ends are the y limits: both caps lie on the
    # frame, whose line is hidden so only box ink is dark there.
    fig, ax = glp.subplots(figsize=(2, 1.5))
    ax.boxplot([0, 2, 3, 4, 10], whis=(0, 100))
    ax.set_axis_line(color="white")
    out = tmp_path / "caps.png"
    fig.savefig(str(out), dpi=600)
    width, rows = _png_rows(out)

    def dark_runs(x, lo=0, hi=len(rows)):
        runs, start = [], None
        for y in range(lo, hi + 1):
            dark = y < hi and max(rows[y][3 * x : 3 * x + 3]) < 100
            if dark and start is None:
                start = y
            elif not dark and start is not None:
                runs.append((start, y - start))
                start = None
        return runs

    # The upper whisker is the longest vertical line. Its column runs from
    # the top cap down to the bottom one; below that is the tick label.
    whisker_x = max(
        range(width), key=lambda x: max([n for _y, n in dark_runs(x)] or [0])
    )
    lines = [(y, n) for y, n in dark_runs(whisker_x) if n > 20]
    lo, hi = lines[0][0] - 5, sum(lines[-1]) + 5
    # Columns right of the whisker that cross a cap: cap, box top edge, box
    # bottom edge, cap. Past the cap only the two box edges remain.
    cap_columns = []
    for x in range(whisker_x + 1, width):
        runs = [n for _y, n in dark_runs(x, lo, hi)]
        if len(runs) == 4:
            cap_columns.append(runs)
        elif cap_columns:
            break
    assert len(cap_columns) > 5
    # The caps are as thick as the box edges, not cut in half by the frame.
    for top_cap, top_edge, bottom_edge, bottom_cap in cap_columns:
        assert min(top_cap, bottom_cap) >= max(top_edge, bottom_edge) - 1
