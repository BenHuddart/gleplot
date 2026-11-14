"""Unit tests for text annotation support."""

import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


class TestTextAnnotations(unittest.TestCase):
    """Test in-plot text annotation APIs and GLE output."""

    def setUp(self):
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)

    def tearDown(self):
        glp.close()

    def test_axes_text_storage(self):
        self.ax.text(1.0, 2.0, "Peak A", color="red", fontsize=11, ha="center")

        self.assertEqual(len(self.ax.texts), 1)
        entry = self.ax.texts[0]
        self.assertEqual(entry["x"], 1.0)
        self.assertEqual(entry["y"], 2.0)
        self.assertEqual(entry["text"], "Peak A")
        self.assertEqual(entry["color"], "RED")
        self.assertEqual(entry["ha"], "center")
        self.assertEqual(entry["fontsize"], 11.0)

    def test_text_generates_gle_commands(self):
        self.ax.plot([0, 1, 2], [0.2, 0.5, 0.3], color="blue")
        self.ax.text(1.25, 0.45, "Comp 1", color="black", ha="left")

        gle = self.fig._generate_gle()

        self.assertIn("amove xg(1.25) yg(0.45)", gle)
        self.assertIn('write "Comp 1"', gle)
        # 'BLACK'/'left' are GLE's own defaults (and the sticky state the
        # writer starts in), so a text using them needs no 'set color'/'set
        # just' restated -- the writer skips redundant lines that would not
        # change anything (see GLEWriter.add_text sticky-state tracking).
        self.assertNotIn("set color BLACK", gle)
        self.assertNotIn("set just left", gle)
        self.assertLess(gle.find("end graph"), gle.find("amove xg(1.25) yg(0.45)"))

    def test_text_with_non_default_just_emits_set_just(self):
        # A halign that differs from GLE's sticky default ('left') must still
        # emit an explicit 'set just' so the rendered alignment is correct.
        self.ax.plot([0, 1, 2], [0.2, 0.5, 0.3], color="blue")
        self.ax.text(1.25, 0.45, "Comp 1", ha="center")

        gle = self.fig._generate_gle()

        self.assertIn("set just center", gle)
        self.assertIn('write "Comp 1"', gle)

    def test_module_level_text(self):
        glp.figure()
        glp.text(0.5, 0.25, "A")

        ax = glp.gca()
        self.assertEqual(len(ax.texts), 1)

    def test_figure_level_text(self):
        self.fig.text(0.2, 0.8, "Figure API")
        self.assertEqual(len(self.ax.texts), 1)
        self.assertEqual(self.ax.texts[0]["text"], "Figure API")

    def test_text_escapes_quotes_for_gle(self):
        self.ax.text(1.0, 1.0, 'He said "hello"')
        gle = self.fig._generate_gle()
        self.assertIn('write "He said \\"hello\\""', gle)

    def test_text_accepts_bbox_facecolor(self):
        self.ax.text(0.1, 0.2, "boxed", bbox={"facecolor": "yellow"})
        self.assertEqual(self.ax.texts[0]["box_color"], "YELLOW")

    def test_text_bbox_fill_is_an_alias_for_facecolor(self):
        self.ax.text(0.1, 0.2, "boxed", bbox={"fill": "yellow"})
        self.assertEqual(self.ax.texts[0]["box_color"], "YELLOW")

    def test_default_alignment_is_vertical_center_without_a_set_just(self):
        self.ax.plot([0, 1], [0, 1])
        self.ax.text(0.5, 0.5, "note", ha="left", va="center")
        gle = self.fig._generate_gle()
        self.assertNotIn("set just", gle)
        self.assertNotIn("begin rotate", gle)
        self.assertNotIn("begin box", gle)
        self.assertNotIn("rotation", self.ax.texts[0])

    def test_vertical_alignment_uses_two_letter_just(self):
        self.ax.plot([0, 1], [0, 1])
        self.ax.text(0.2, 0.8, "top", ha="center", va="top")
        self.ax.text(0.2, 0.2, "bottom", ha="right", va="bottom")
        # Back to the centred default: the previous ``bc`` is still in effect,
        # so the writer has to restate ``left``.
        self.ax.text(0.5, 0.5, "mid", ha="left", va="center")
        gle = self.fig._generate_gle()
        self.assertIn("set just tc", gle)
        self.assertIn("set just br", gle)
        self.assertIn("set just left", gle)
        self.assertLess(gle.index("set just tc"), gle.index("set just br"))
        self.assertLess(gle.index("set just br"), gle.index("set just left"))

    def test_rotation_and_bbox_emit_blocks_around_the_write(self):
        self.ax.plot([0, 1, 2], [0, 1, 0])
        self.ax.text(
            1,
            1,
            "peak",
            va="bottom",
            ha="center",
            rotation=45,
            bbox={"facecolor": "white"},
        )
        gle = self.fig._generate_gle()
        self.assertIn("set just bc", gle)
        self.assertIn("begin rotate 45", gle)
        self.assertIn("begin box fill WHITE add 0.05 nobox", gle)
        self.assertIn('write "peak"', gle)
        self.assertLess(gle.index("amove xg(1) yg(1)"), gle.index("begin rotate 45"))
        self.assertLess(gle.index("begin rotate 45"), gle.index("begin box fill WHITE"))
        self.assertLess(gle.index("begin box fill WHITE"), gle.index('write "peak"'))
        self.assertLess(gle.index('write "peak"'), gle.index("end box"))
        self.assertLess(gle.index("end box"), gle.index("end rotate"))
        self.assertEqual(self.ax.texts[0]["rotation"], 45.0)
        self.assertEqual(self.ax.texts[0]["va"], "bottom")

    def test_zero_rotation_is_not_stored_or_emitted(self):
        self.ax.text(0, 0, "flat", rotation=0)
        gle = self.fig._generate_gle()
        self.assertNotIn("rotation", self.ax.texts[0])
        self.assertNotIn("begin rotate", gle)

    def test_negative_rotation_emits_a_signed_angle(self):
        self.ax.plot([0, 1], [0, 1])
        self.ax.text(0.5, 0.5, "tilt", rotation=-30)
        gle = self.fig._generate_gle()
        self.assertIn("begin rotate -30", gle)
        self.assertIn("end rotate", gle)

    def test_rgb_bbox_round_trips_through_the_parser(self):
        import os
        import tempfile

        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.plot([0, 1], [0, 1])
        self.ax.text(
            0.4,
            0.6,
            "mark",
            ha="left",
            va="top",
            rotation=-15,
            color=(0.2, 0.4, 0.6),
            bbox={"facecolor": (1, 1, 0)},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.gle")
            self.fig.savefig_gle(path)
            got = parse_gle_figure(path).figure.axes_list[0].texts[0]
        self.assertEqual(got["text"], "mark")
        self.assertEqual(got["ha"], "left")
        self.assertEqual(got["va"], "top")
        self.assertEqual(got["rotation"], -15.0)
        self.assertEqual(got["color"], "rgb255(51,102,153)")
        self.assertEqual(got["box_color"], "rgb255(255,255,0)")

    def test_unknown_va_on_a_restored_text_keeps_ha(self):
        """A dict that bypasses ``Axes.text`` still keeps a valid ``ha``.

        ``Figure.from_dict`` restores the annotation as stored. An unknown
        ``va`` used to make the writer emit no ``set just`` at all, so GLE
        drew a right-aligned label on the left.
        """
        from gleplot.series import TextAnnotation

        self.ax.plot([0, 1], [0, 1])
        self.ax.texts.append(
            TextAnnotation(x=0.5, y=0.5, text="peak", ha="right", va="baseline")
        )
        self.ax.texts.append(
            TextAnnotation(x=0.2, y=0.8, text="high", ha="nope", va="top")
        )
        gle = self.fig._generate_gle()
        self.assertIn("set just right", gle)
        self.assertIn("set just tl", gle)
        self.assertLess(gle.index("set just right"), gle.index("set just tl"))

    def test_unsupported_text_arguments_warn(self):
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", va="baseline")
        self.assertEqual(self.ax.texts[-1]["va"], "center")
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", ha="justified")
        self.assertEqual(self.ax.texts[-1]["ha"], "left")
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", bbox={"facecolor": "white", "edgecolor": "black"})
        self.assertEqual(self.ax.texts[-1]["box_color"], "WHITE")
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", bbox="white")
        self.assertIsNone(self.ax.texts[-1]["box_color"])
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", bbox={})
        self.assertIsNone(self.ax.texts[-1]["box_color"])
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", rotation="sideways")
        self.assertNotIn("rotation", self.ax.texts[-1])
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", rotation=float("nan"))
        self.assertNotIn("rotation", self.ax.texts[-1])
        with self.assertWarns(UserWarning):
            self.ax.text(0, 0, "x", transform="axes")
        self.assertEqual(self.ax.texts[-1]["text"], "x")


class TestColorStateDoesNotLeakAcrossPanels(unittest.TestCase):
    """Regression test for the 2026-07-29 library gap found by the
    Gd3Ru4Al12 analysis repo's ``analysis/musr/prl_lf_jomega.py``: a
    coloured text ending one subplot panel must not colour the axes/ticks
    GLE draws for the NEXT panel.

    Root cause: graph-data-coordinate text is queued by ``add_text`` and
    flushed by ``GLEWriter.end_graph`` right AFTER 'end graph' -- i.e. at
    the PAGE level, where 'set color' is sticky interpreter state shared by
    every graph block in the script (not scoped to the panel that requested
    it). Left unguarded, the ambient colour a coloured label leaves behind
    is whatever colour the NEXT 'begin graph' block's axes/ticks render in.
    The fix wraps that flush in gsave/grestore (the same idiom already used
    for the broken-axis seam decoration -- see
    ``test_broken_axes.test_seam_decoration_is_wrapped_so_state_does_not_leak``
    in this test suite) so the colour reverts to ambient before the next
    panel's 'begin graph'.
    """

    def setUp(self):
        glp.close()

    def tearDown(self):
        glp.close()

    def _two_panel_figure(self):
        fig, axes = glp.subplots(2, 1, sharex=True, figsize=(3.4, 4.0))
        axes[0].plot([0, 1, 2], [0, 1, 2], color="blue")
        # The panel-ending coloured element: a green text label, exactly the
        # PRL-figure symptom (a phase label like "PM").
        axes[0].text(1, 1, "PM", color="green", ha="center")
        axes[1].plot([0, 1, 2], [0, 2, 1], color="blue")
        return fig

    def test_coloured_text_flush_is_wrapped_in_gsave_grestore(self):
        gle = self._two_panel_figure()._generate_gle()

        self.assertEqual(gle.count("gsave"), gle.count("grestore"))
        self.assertGreaterEqual(gle.count("gsave"), 1)

        first_end_graph = gle.index("end graph")
        second_begin_graph = gle.index("begin graph", first_end_graph)
        between_panels = gle[first_end_graph:second_begin_graph]

        self.assertIn("gsave", between_panels)
        self.assertIn("set color GREEN", between_panels)
        self.assertIn("grestore", between_panels)
        # Order matters: gsave, then the colour change, then grestore.
        self.assertLess(
            between_panels.index("gsave"), between_panels.index("set color GREEN")
        )
        self.assertLess(
            between_panels.index("set color GREEN"), between_panels.index("grestore")
        )

    def test_second_panel_axes_are_not_preceded_by_a_lingering_colour(self):
        """The direct assertion: nothing sets a colour between where the
        first panel's text state is restored and where the second panel's
        'begin graph' (and hence its axes/ticks) starts."""
        gle = self._two_panel_figure()._generate_gle()

        last_grestore = gle.rindex(
            "grestore", 0, gle.index("begin graph", gle.index("end graph"))
        )
        second_begin_graph = gle.index("begin graph", gle.index("end graph"))
        after_restore = gle[last_grestore:second_begin_graph]

        self.assertNotIn("set color", after_restore)


if __name__ == "__main__":
    unittest.main()
