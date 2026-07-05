#!/usr/bin/env python3
"""Build application icons for the gleplot release bundles.

Reads the square source logo at ``src/gleplot/gui/assets/gleplot.png`` and
writes a macOS ``.icns`` (and, optionally, a Windows ``.ico``) suitable for
PyInstaller / Inno Setup. Requires Pillow.

Examples
--------
    python packaging/macos_icon.py --icns build/icons/gleplot.icns
    python packaging/macos_icon.py --ico  build/icons/gleplot.ico
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "gleplot" / "gui" / "assets" / "gleplot.png"
DEFAULT_ICONSET = PROJECT_ROOT / "build" / "icons" / "gleplot.iconset"
MACOS_ICON_TILE_SCALE = 0.82

# (points, scale) renditions used both for the .iconset and the .icns sizes.
ICONSET_RENDITIONS = (
    (16, 1),
    (16, 2),
    (32, 1),
    (32, 2),
    (128, 1),
    (128, 2),
    (256, 1),
    (256, 2),
    (512, 1),
    (512, 2),
)

# Windows .ico embedded sizes.
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    alpha_bbox = image.getchannel("A").getbbox()
    if alpha_bbox is None:
        return (0, 0, image.width, image.height)
    return alpha_bbox


def make_macos_icon_image(
    source_path: Path,
    *,
    size: int = 1024,
    corner_radius_fraction: float = 0.223,
    tile_scale: float = MACOS_ICON_TILE_SCALE,
) -> Image.Image:
    """Return a rounded-square macOS-styled icon from the source logo."""

    if size <= 0:
        raise ValueError("icon size must be positive")
    if not 0 < corner_radius_fraction < 0.5:
        raise ValueError("corner radius fraction must be between 0 and 0.5")
    if not 0 < tile_scale <= 1:
        raise ValueError("tile scale must be between 0 and 1")

    source = Image.open(source_path).convert("RGBA")
    source = source.crop(_alpha_bbox(source))
    flattened_source = Image.new("RGBA", source.size, (255, 255, 255, 255))
    flattened_source.alpha_composite(source)
    tile_size = max(1, round(size * tile_scale))
    tile_offset = (size - tile_size) // 2
    tile = flattened_source.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.alpha_composite(tile, (tile_offset, tile_offset))

    mask = Image.new("L", (size, size), 0)
    radius = round(tile_size * corner_radius_fraction)
    ImageDraw.Draw(mask).rounded_rectangle(
        (
            tile_offset,
            tile_offset,
            tile_offset + tile_size - 1,
            tile_offset + tile_size - 1,
        ),
        radius=radius,
        fill=255,
    )

    icon.putalpha(mask)
    return icon


def write_iconset(source_path: Path, iconset_dir: Path) -> list[Path]:
    """Write a complete `.iconset` directory and return the generated PNG paths."""

    iconset_dir.mkdir(parents=True, exist_ok=True)
    base_icon = make_macos_icon_image(source_path)
    generated: list[Path] = []

    for points, scale in ICONSET_RENDITIONS:
        pixels = points * scale
        suffix = "@2x" if scale == 2 else ""
        path = iconset_dir / f"icon_{points}x{points}{suffix}.png"
        base_icon.resize((pixels, pixels), Image.Resampling.LANCZOS).save(path)
        generated.append(path)

    return generated


def write_icns(source_path: Path, icns_path: Path) -> None:
    """Write an `.icns` file from the rounded-square source image."""

    icns_path.parent.mkdir(parents=True, exist_ok=True)
    icon = make_macos_icon_image(source_path)
    icon.save(
        icns_path,
        sizes=tuple(
            sorted({(points * scale, points * scale) for points, scale in ICONSET_RENDITIONS})
        ),
    )


def write_ico(source_path: Path, ico_path: Path) -> None:
    """Write a Windows `.ico` (square, no rounded corners) from the source logo."""

    ico_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        icon = image.convert("RGBA")
        icon.save(ico_path, format="ICO", sizes=ICO_SIZES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="source PNG logo")
    parser.add_argument(
        "--iconset",
        type=Path,
        default=DEFAULT_ICONSET,
        help="output .iconset directory (written whenever --icns is requested)",
    )
    parser.add_argument("--icns", type=Path, help="output .icns path (macOS)")
    parser.add_argument("--ico", type=Path, help="output .ico path (Windows)")
    args = parser.parse_args(argv)

    if args.icns is None and args.ico is None:
        parser.error("at least one of --icns or --ico must be given")

    if args.icns is not None:
        write_iconset(args.source, args.iconset)
        write_icns(args.source, args.icns)
    if args.ico is not None:
        write_ico(args.source, args.ico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
