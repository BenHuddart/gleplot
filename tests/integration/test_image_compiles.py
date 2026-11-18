"""Placed images compile, and GLE reads them from the script's folder.

The script text is asserted in ``tests/unit/test_image.py``. This checks that
GLE accepts the ``gleplot_bitmap`` and ``gleplot_postscript`` draw calls,
embeds both files in its PostScript output, finds a relative file next to the
script whatever the working directory, and fails loudly on a missing file.
Skipped when the binary is missing.
"""

from __future__ import annotations

import struct
import zlib

import pytest

import gleplot as glp
from gleplot.compiler import GLECompileError

pytestmark = pytest.mark.gle

#: A minimal EPS: a blue 20 x 10 pt rectangle.
_EPS = (
    "%!PS-Adobe-3.0 EPSF-3.0\n"
    "%%BoundingBox: 0 0 20 10\n"
    "0 0 1 setrgbcolor 0 0 20 10 rectfill\n"
    "%%EOF\n"
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _write_png(path, width=4, height=2):
    """A solid green 8-bit RGB PNG."""

    def chunk(kind, body):
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + b"\x00\xff\x00" * width for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def test_a_png_and_an_eps_are_embedded_from_the_scripts_folder(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    (out_dir / "art").mkdir(parents=True)
    _write_png(out_dir / "art" / "photo.png")
    (out_dir / "art" / "logo.eps").write_text(_EPS)
    # A relative path is read from the folder the script is saved in, not
    # from the working directory.
    monkeypatch.chdir(tmp_path)

    fig, ax = glp.subplots()
    ax.plot([0, 10], [0, 5], color="red")
    ax.image("art/photo.png", extent=(1, 9, 1, 4))
    ax.image("art/logo.eps", extent=(0.5, 2.5, 0.5, 1.5))
    out = fig.savefig(str(out_dir / "fig.eps"))

    eps = out.read_text(encoding="latin-1")
    assert "%% BEGIN image: art/photo.png" in eps
    assert "%%BeginDocument: art/logo.eps" in eps
    assert fig.savefig(str(out_dir / "fig.png")).stat().st_size > 0


def test_a_missing_image_file_fails_the_compile(tmp_path):
    fig, ax = glp.subplots()
    ax.image("nowhere.png", extent=(0, 1, 0, 1))
    with pytest.raises(GLECompileError):
        fig.savefig(str(tmp_path / "fig.pdf"))
