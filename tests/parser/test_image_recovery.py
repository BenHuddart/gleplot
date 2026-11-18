"""Reading placed images back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from gleplot.writer import IMAGE_SUBS


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _parse(tmp_path, body: str):
    path = tmp_path / "image.gle"
    path.write_text(
        "size 10 10\n\n"
        + "\n\n".join(IMAGE_SUBS.values())
        + "\n\nbegin graph\n"
        + "    xaxis min 0 max 10\n"
        + "    yaxis min 0 max 5\n"
        + body
        + "end graph\n"
    )
    return parse_gle_figure(path)


def _block(call: str, layer: int = 150) -> str:
    return f"    begin layer {layer}\n        {call}\n    end layer\n"


def test_image_blocks_come_back_as_placed_images(tmp_path):
    recognized = _parse(
        tmp_path,
        _block('draw gleplot_bitmap "my scans/a.png" 0 10 -1 5')
        + _block('draw gleplot_postscript "logo.eps" 1 2.5 3 4'),
    )
    ax = recognized.figure.axes_list[0]
    assert [dict(image) for image in ax.images] == [
        {"type": "image", "file": "my scans/a.png", "extent": [0.0, 10.0, -1.0, 5.0]},
        {"type": "image", "file": "logo.eps", "extent": [1.0, 2.5, 3.0, 4.0]},
    ]
    assert ax.passthrough == []
    assert recognized.warnings == []


@pytest.mark.parametrize(
    "block",
    [
        # The layer was edited to change the stacking.
        _block('draw gleplot_bitmap "a.png" 0 1 0 1', layer=600),
        # The call does not fit the file type.
        _block('draw gleplot_postscript "a.png" 0 1 0 1'),
        # A reversed extent.
        _block('draw gleplot_bitmap "a.png" 1 0 0 1'),
        # An argument missing.
        _block('draw gleplot_bitmap "a.png" 0 1 0'),
    ],
    ids=["layer", "type", "reversed", "arity"],
)
def test_an_edited_image_block_stays_raw_with_a_note(tmp_path, block):
    recognized = _parse(tmp_path, block)
    ax = recognized.figure.axes_list[0]
    assert ax.images == []
    assert [line.strip() for line in ax.passthrough] == [
        line.strip() for line in block.splitlines()
    ]
    (warning,) = recognized.warnings
    assert warning.startswith("structure: 'draw gleplot_")
    assert "read back as an image" in warning


def test_a_hand_written_bitmap_draw_stays_raw_and_silent(tmp_path):
    block = _block('draw mypicture "a.png" 0 1 0 1')
    recognized = _parse(tmp_path, block)
    ax = recognized.figure.axes_list[0]
    assert ax.images == []
    assert len(ax.passthrough) == 3
    assert recognized.warnings == []
