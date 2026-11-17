#!/usr/bin/env python3
"""Copy the example PNGs into the documentation gallery and resize them.

The gallery shows every example in ``EXAMPLES`` in
``examples/run_and_compile.py``. Run that script first; this one copies the
PNG it wrote for each ``.gle`` output from ``examples/outputs/`` to
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
MAX_WIDTH = 800


def registered_examples() -> list:
    """Return ``EXAMPLES`` from ``examples/run_and_compile.py``."""
    if str(EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLES_DIR))
    import run_and_compile

    return run_and_compile.EXAMPLES


def gallery_images() -> list[str]:
    """Return each example output's PNG path, relative to the gallery folder."""
    return [
        f"{basename}.png"
        for _, _, basenames in registered_examples()
        for basename in basenames
    ]


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

    images = gallery_images()
    missing = []
    for name in images:
        source = OUTPUTS_DIR / name
        if not source.is_file():
            missing.append(name)
            continue
        target = GALLERY_DIR / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        resize_png(target)

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
