#!/usr/bin/env python3
"""Resize gallery PNGs for web and verify gallery.rst references."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
SOURCE_DIR = DOCS_DIR / "source"
GALLERY_RST = SOURCE_DIR / "gallery.rst"
GALLERY_DIR = SOURCE_DIR / "_static" / "gallery"
MAX_WIDTH = 800


def referenced_images() -> list[Path]:
    text = GALLERY_RST.read_text(encoding="utf-8")
    names = re.findall(r"\.\. image:: _static/gallery/([^\s]+)", text)
    return [GALLERY_DIR / name for name in names]


def resize_png(path: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        print("prepare_gallery: Pillow required; pip install Pillow", file=sys.stderr)
        sys.exit(1)

    with Image.open(path) as img:
        if img.width <= MAX_WIDTH:
            return
        ratio = MAX_WIDTH / float(img.width)
        height = max(1, int(img.height * ratio))
        resized = img.resize((MAX_WIDTH, height), Image.Resampling.LANCZOS)
        resized.save(path, optimize=True)


def main() -> int:
    if not GALLERY_RST.is_file():
        print(f"Missing {GALLERY_RST}", file=sys.stderr)
        return 1

    missing = []
    for image_path in referenced_images():
        if not image_path.is_file():
            missing.append(image_path.name)
            continue
        if image_path.suffix.lower() == ".png":
            resize_png(image_path)

    if missing:
        print("Gallery images missing (build aborted):", file=sys.stderr)
        for name in sorted(missing):
            print(f"  {name}", file=sys.stderr)
        return 1

    print(f"Gallery OK: {len(referenced_images())} image(s) in {GALLERY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())