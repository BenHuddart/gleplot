"""Placed image example: a picture file under a line plot, in data coordinates."""

import struct
import sys
import zlib
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np

import gleplot as glp


def _write_png(path, rgb):
    """Write an (height, width, 3) uint8 array as an 8-bit RGB PNG."""

    def chunk(kind, body):
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    height, width, _ = rgb.shape
    rows = b"".join(b"\x00" + rgb[row].tobytes() for row in range(height))
    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def example_placed_image():
    """``image`` places a PNG over a rectangle given in data coordinates.

    The picture (here a made-up micrograph) is drawn under the grid and the
    data, and clipped to the axes; a line profile is plotted over it.
    """
    print("Creating example: Placed Image...")

    # A stand-in for a micrograph: soft blobs on a dark background.
    yy, xx = np.mgrid[0:120, 0:240]
    rng = np.random.default_rng(3)
    grey = np.zeros(xx.shape)
    for cx, cy, r in zip(rng.uniform(0, 240, 25), rng.uniform(0, 120, 25), [14] * 25):
        grey += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r**2))
    grey = (255 * grey / grey.max()).astype(np.uint8)
    _write_png("example_placed_image_micrograph.png", np.dstack([grey] * 3))

    x = np.linspace(0, 10, 50)
    fig = glp.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    # A relative path is read from the folder the .gle script is saved in.
    ax.image("example_placed_image_micrograph.png", extent=(0, 10, 0, 5))
    ax.plot(x, 2.5 + 1.5 * np.sin(x), color="orange", linewidth=2)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("Line profile over a micrograph")

    fig.savefig_gle("example_placed_image.gle")
    print("  Saved to example_placed_image.gle")


if __name__ == "__main__":
    example_placed_image()
