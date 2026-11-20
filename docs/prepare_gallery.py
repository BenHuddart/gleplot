#!/usr/bin/env python3
"""Convert the example PNGs into the documentation gallery's WebP images.

The gallery shows every example in ``EXAMPLES`` in
``examples/run_and_compile.py``. Run that script first; this one takes the
PNG it wrote for each ``.gle`` output in ``examples/outputs/``, scales it down
to the gallery's display width, and writes it as lossless WebP to
``docs/source/_static/gallery/``.

Without ``--strict``, missing images are reported and the process exits 0 so
a local ``make html`` still builds. The publish workflow passes ``--strict``
and fails if any gallery image is absent.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = DOCS_DIR.parent / "examples"
OUTPUTS_DIR = EXAMPLES_DIR / "outputs"
GALLERY_DIR = DOCS_DIR / "source" / "_static" / "gallery"
# The width, in CSS pixels, at which the gallery shows each image.
GALLERY_WIDTH = 600


def registered_examples() -> list:
    """Return ``EXAMPLES`` from ``examples/run_and_compile.py``."""
    if str(EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLES_DIR))
    import run_and_compile

    return run_and_compile.EXAMPLES


def gallery_images() -> list[str]:
    """Return each example output's path without extension, under the outputs folder."""
    return [
        basename for _, _, basenames in registered_examples() for basename in basenames
    ]


def convert_png(source: Path, target: Path) -> None:
    """Write ``source`` to ``target`` as lossless WebP, no wider than displayed."""
    try:
        from PIL import Image
    except ImportError:
        print("prepare_gallery: Pillow required; pip install Pillow", file=sys.stderr)
        sys.exit(1)

    with Image.open(source) as img:
        if img.width > GALLERY_WIDTH:
            height = max(1, round(img.height * GALLERY_WIDTH / img.width))
            img = img.resize((GALLERY_WIDTH, height), Image.Resampling.LANCZOS)
        img.save(target, "WEBP", lossless=True, method=6)


def main(argv: list[str] | None = None) -> int:
    strict = "--strict" in (argv if argv is not None else sys.argv[1:])

    images = gallery_images()
    missing = []
    # Clear images left by renamed or removed examples, which would be published.
    shutil.rmtree(GALLERY_DIR, ignore_errors=True)
    for basename in images:
        source = OUTPUTS_DIR / f"{basename}.png"
        if not source.is_file():
            missing.append(f"{basename}.png")
            continue
        target = GALLERY_DIR / f"{basename}.webp"
        target.parent.mkdir(parents=True, exist_ok=True)
        convert_png(source, target)

    if missing:
        stream = sys.stderr if strict else sys.stdout
        print(f"Gallery images not present in {OUTPUTS_DIR}:", file=stream)
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
