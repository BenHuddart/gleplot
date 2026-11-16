#!/usr/bin/env python3
"""Resize gallery PNGs for the documentation site.

Without ``--strict``, missing images are reported and the process exits 0 so
a local ``make html`` still builds. The publish workflow passes ``--strict``
and fails if any image named in ``gallery.rst`` is absent.
"""

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


def main(argv: list[str] | None = None) -> int:
    strict = "--strict" in (argv if argv is not None else sys.argv[1:])
    if not GALLERY_RST.is_file():
        print(f"Missing {GALLERY_RST}", file=sys.stderr)
        return 1

    images = referenced_images()
    missing = []
    for image_path in images:
        if not image_path.is_file():
            missing.append(image_path.name)
            continue
        if image_path.suffix.lower() == ".png":
            resize_png(image_path)

    if missing:
        stream = sys.stderr if strict else sys.stdout
        print("Gallery images not present:", file=stream)
        for name in sorted(missing):
            print(f"  {name}", file=stream)
        if strict:
            print(
                "Publish requires every gallery image. Generate them with "
                "examples/run_and_compile.py before this check.",
                file=sys.stderr,
            )
            return 1
        print(
            "Continuing without them. A local HTML build still succeeds; "
            "the publish workflow passes --strict and fails if any are missing."
        )
        return 0

    print(f"Gallery OK: {len(images)} image(s) in {GALLERY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
