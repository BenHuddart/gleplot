"""G18-lite, engine side: the provenance marker is invisible to GLE.

The dataset-form guide's marker (``! gleplot:guide ...``) is a comment, so it
has no rendering impact *by construction* -- GLE's lexer stops at ``!``. That
is exactly the kind of claim worth checking against the binary anyway: the
whole design rests on it, and "additive bytes only" is worth nothing if the
byte we added moves a pixel.

So: compile what gleplot emits, compile the same script with every marker line
deleted, and diff the two rasters. Any difference at all -- one antialiased
edge, one shifted tick -- fails.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import gleplot as glp
from gleplot.guides import GUIDE_MARKER_PREFIX

pytestmark = pytest.mark.gle

DPI = 150


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _marked_figure():
    """Every guide kind, materialized (limits resolve), styled and labelled."""
    fig = glp.figure(data_prefix="gm")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 4.0, 9.0], label="data")
    ax.axvline(1.5, color="red", linestyle="--", linewidth=2.0, label="threshold")
    ax.axhline(2.0, color="blue", linestyle=":", ymin=0.1, ymax=0.9)
    ax.axvspan(0.5, 1.0, color="orange", label="band")
    ax.axhspan(3.0, 5.0, color="lightgray", xmin=0.2, xmax=0.8)
    ax.legend()
    return fig


def _write(tmp_path: Path, stem: str, text: str, files) -> Path:
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    script = tmp_path / f"{stem}.gle"
    script.write_text(text, encoding="utf-8")
    return script


def _render(script: Path) -> Path:
    proc = subprocess.run(
        ["gle", "-d", "png", "-r", str(DPI), "-verbosity", "0", script.name],
        cwd=script.parent,
        capture_output=True,
        text=True,
    )
    png = script.with_suffix(".png")
    assert proc.returncode == 0 and png.exists(), proc.stdout + proc.stderr
    return png


def _strip_markers(text: str) -> str:
    """The same script as gleplot wrote before G18-lite: no marker comments."""
    return re.sub(
        r"^[ \t]*" + re.escape(GUIDE_MARKER_PREFIX) + r"[^\n]*\n",
        "",
        text,
        flags=re.MULTILINE,
    )


def test_a_marked_emission_renders_identically_to_the_unmarked_one(tmp_path):
    text, files = _marked_figure()._generate_gle_with_files()
    stripped = _strip_markers(text)
    assert stripped != text, "the fixture emitted no markers at all"

    marked = _render(_write(tmp_path, "marked", text, files))
    plain = _render(_write(tmp_path, "plain", stripped, files))

    from PIL import Image, ImageChops

    with Image.open(marked) as a, Image.open(plain) as b:
        left = a.convert("RGB")
        right = b.convert("RGB")
        assert left.size == right.size
        assert ImageChops.difference(left, right).getbbox() is None


def test_a_marked_emission_compiles_clean(tmp_path):
    """No warning either: GLE must not so much as notice the comment."""
    text, files = _marked_figure()._generate_gle_with_files()
    script = _write(tmp_path, "marked", text, files)
    proc = subprocess.run(
        ["gle", "-d", "png", "-r", str(DPI), script.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    combined = (proc.stdout + proc.stderr).lower()
    assert "error" not in combined
    assert "warning" not in combined
