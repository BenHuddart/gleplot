"""Unit tests for text annotation support."""

import sys
import unittest
import warnings
from pathlib import Path

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


class TestAnnotate(unittest.TestCase):
    """``Axes.annotate``: a text plus a ``join`` arrow from its named box."""

    def setUp(self):
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([0, 1, 2], [0, 1, 0])

    def tearDown(self):
        glp.close()

    def test_issue_example_emits_named_box_and_join(self):
        entry = self.ax.annotate(
            "peak", xy=(2, 3), xytext=(2.4, 3.5), arrowprops={"arrowstyle": "->"}
        )
        self.assertIs(entry, self.ax.texts[-1])
        self.assertEqual((entry["x"], entry["y"]), (2.4, 3.5))
        self.assertEqual(entry["xy"], [2.0, 3.0])
        self.assertEqual(entry["arrow"], "->")
        self.assertEqual(entry["arrowstyle"], "simple")
        self.assertEqual(entry["arrow_color"], "BLACK")
        self.assertNotIn("arrow_linewidth", entry)
        gle = self.fig._generate_gle()
        block = (
            "amove xg(2.4) yg(3.5)\n"
            "begin box add 0.05 nobox name ann1\n"
            'write "peak"\n'
            "end box\n"
            "amove xg(2) yg(3)\n"
            "save ann1_xy\n"
            "gsave\n"
            "set color BLACK\n"
            "set arrowstyle simple\n"
            "join ann1 -> ann1_xy\n"
            "grestore\n"
        )
        self.assertIn(block, gle)

    def test_arrowstyle_mapping(self):
        cases = {
            "-": ("-", None),
            "->": ("->", "simple"),
            "<-": ("<-", "simple"),
            "<->": ("<->", "simple"),
            "-|>": ("->", "filled"),
            "<|-": ("<-", "filled"),
            "<|-|>": ("<->", "filled"),
        }
        for style, (sep, tip) in cases.items():
            entry = self.ax.annotate(
                "a", xy=(0, 0), xytext=(1, 1), arrowprops={"arrowstyle": style}
            )
            self.assertEqual(entry["arrow"], sep, style)
            self.assertEqual(entry.get("arrowstyle"), tip, style)
        gle = self.fig._generate_gle()
        # '-' has no head, so no arrowstyle line precedes its join.
        self.assertIn("set color BLACK\njoin ann1 - ann1_xy", gle)
        # Names are unique per script.
        self.assertIn("join ann7 <-> ann7_xy", gle)

    def test_legacy_arrowprops_is_a_filled_arrow(self):
        with self.assertWarns(UserWarning) as cm:
            entry = self.ax.annotate(
                "a",
                xy=(0, 0),
                xytext=(1, 1),
                arrowprops={"facecolor": "red", "shrink": 0.05},
            )
        self.assertIn("shrink", str(cm.warning))
        self.assertEqual((entry["arrow"], entry["arrowstyle"]), ("->", "filled"))
        self.assertEqual(entry["arrow_color"], "RED")

    def test_arrow_colour_precedence_and_linewidth(self):
        entry = self.ax.annotate(
            "a",
            xy=(0, 0),
            xytext=(1, 1),
            color="green",
            arrowprops={"arrowstyle": "->", "ec": "blue", "fc": "red", "lw": 2},
        )
        self.assertEqual(entry["color"], "GREEN")
        self.assertEqual(entry["arrow_color"], "BLUE")
        self.assertEqual(entry["arrow_linewidth"], 2.0)
        gle = self.fig._generate_gle()
        self.assertIn("set color BLUE\nset lwidth 0.07056\nset arrowstyle simple", gle)
        # The arrow colour is inside gsave: the text colour state is GREEN.
        self.assertLess(gle.index("set color GREEN"), gle.index("begin box"))

    def test_no_arrow_without_xytext_or_arrowprops(self):
        a = self.ax.annotate("a", xy=(1, 2), arrowprops={"arrowstyle": "->"})
        b = self.ax.annotate("b", xy=(1, 2), xytext=(0, 0))
        for entry in (a, b):
            self.assertNotIn("arrow", entry)
        self.assertEqual((a["x"], a["y"]), (1.0, 2.0))
        self.assertEqual((b["x"], b["y"]), (0.0, 0.0))
        gle = self.fig._generate_gle()
        self.assertNotIn("join", gle)
        self.assertNotIn("name ann", gle)

    def test_unsupported_arguments_warn(self):
        for kwargs in (
            {"textcoords": "offset points"},
            {"xycoords": "axes fraction"},
            {"annotation_clip": False},
            {"arrowprops": {"arrowstyle": "fancy"}},
            {"arrowprops": {"arrowstyle": "->,head_width=0.4"}},
            {"arrowprops": {"arrowstyle": "->", "connectionstyle": "arc3,rad=0.3"}},
            {"arrowprops": "->"},
            {"fontweight": "bold"},
        ):
            with self.assertWarns(UserWarning, msg=str(kwargs)):
                self.ax.annotate("a", xy=(0, 0), xytext=(1, 1), **kwargs)
        self.assertEqual(self.ax.texts[3]["arrowstyle"], "filled")
        self.assertNotIn("arrow", self.ax.texts[6])
        # A straight connection does not warn.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.ax.annotate(
                "a",
                xy=(0, 0),
                xytext=(1, 1),
                arrowprops={"arrowstyle": "->", "connectionstyle": "arc3, rad=0"},
            )

    def test_text_keywords_reach_the_text(self):
        entry = self.ax.annotate(
            "a",
            xy=(0, 0),
            xytext=(1, 1),
            ha="right",
            va="top",
            fontsize=12,
            rotation=30,
            bbox={"facecolor": "white"},
            arrowprops={"arrowstyle": "->"},
        )
        self.assertEqual((entry["ha"], entry["va"]), ("right", "top"))
        self.assertEqual(entry["rotation"], 30.0)
        self.assertEqual(entry["box_color"], "WHITE")
        gle = self.fig._generate_gle()
        self.assertIn(
            "begin rotate 30\n"
            "begin box fill WHITE add 0.05 nobox name ann1\n"
            'write "a"\n'
            "end box\n"
            "end rotate\n"
            "amove xg(0) yg(0)",
            gle,
        )

    def test_straight_connectionstyle_spellings_do_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for style in ("arc3", "arc3,rad=0.", "arc3, rad=0.00"):
                self.ax.annotate(
                    "a",
                    xy=(0, 0),
                    xytext=(1, 1),
                    arrowprops={"arrowstyle": "->", "connectionstyle": style},
                )
        with self.assertWarns(UserWarning):
            self.ax.annotate(
                "a",
                xy=(0, 0),
                xytext=(1, 1),
                arrowprops={"connectionstyle": "angle3,angleA=0,angleB=90"},
            )

    def test_restored_arrow_values_outside_the_gle_set_are_normalized(self):
        from gleplot.series import TextAnnotation

        self.ax.texts.append(
            TextAnnotation(
                x=1, y=1, text="a", xy=[0, 0], arrow="=>", arrowstyle="empty"
            )
        )
        gle = self.fig._generate_gle()
        self.assertIn("set arrowstyle filled\njoin ann1 -> ann1_xy", gle)

    def test_module_level_annotate_and_dict_round_trip(self):
        glp.annotate("m", xy=(0, 0), xytext=(1, 1), arrowprops={"arrowstyle": "-|>"})
        restored = glp.Figure.from_dict(self.fig.to_dict())
        self.assertEqual(restored.to_dict(), self.fig.to_dict())
        self.assertEqual(restored._generate_gle(), self.fig._generate_gle())
        self.assertIn("join ann1 -> ann1_xy", restored._generate_gle())


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
