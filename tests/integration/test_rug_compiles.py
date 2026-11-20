"""A rug compiles, and ``rugs.gle`` draws its ticks into the frame.

The script text is asserted in ``tests/unit/test_rug.py``. Skipped when the
binary is missing.
"""

from __future__ import annotations

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


def test_rug_ticks_point_into_the_frame(tmp_path):
    fig, ax = glp.subplots(figsize=(2, 1.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.rug([2, 5, 8], color="red", length=0.5)
    ax.rug([5], axis="y", position="right", color="blue")
    out = tmp_path / "rug.png"
    fig.savefig(str(out), dpi=300)
    width, rows = _png_rows(out)

    def pixels(match):
        return [
            (x, y)
            for y, row in enumerate(rows)
            for x in range(width)
            if match(row[3 * x], row[3 * x + 1], row[3 * x + 2])
        ]

    red = pixels(lambda r, g, b: r > 200 and g < 80 and b < 80)
    blue = pixels(lambda r, g, b: b > 200 and r < 80 and g < 80)
    assert red and blue
    # The bottom frame line is the lowest row that is dark across most of
    # the page; the red ticks stand on it, inside the frame.
    frame = max(
        y
        for y, row in enumerate(rows)
        if sum(max(row[3 * x : 3 * x + 3]) < 100 for x in range(width)) > width / 2
    )
    assert max(y for _x, y in red) <= frame
    assert frame - min(y for _x, y in red) > 30
    # The blue tick stands left of the right frame edge.
    assert max(x for x, _y in blue) < width - 1
