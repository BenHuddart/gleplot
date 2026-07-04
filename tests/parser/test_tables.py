"""Tests for gleplot.parser.tables: colors, markers, line styles, key
positions (Track A2).
"""

import pytest

from gleplot.parser import tables
from gleplot.markers import MATPLOTLIB_TO_GLE_MARKERS


class TestColors:
    def test_color_count(self):
        # 151 GLE 4.3.10 default colors: SVG named colors + GRAY1..GRAY90.
        assert len(tables.COLORS) == 151

    def test_known_colors(self):
        assert tables.COLORS["BLACK"] == (0, 0, 0)
        assert tables.COLORS["WHITE"] == (255, 255, 255)
        assert tables.COLORS["RED"] == (255, 0, 0)
        assert tables.COLORS["GREEN"] == (0, 128, 0)
        assert tables.COLORS["BLUE"] == (0, 0, 255)

    def test_gray_ramp_present(self):
        for name in ("GRAY1", "GRAY5", "GRAY10", "GRAY20", "GRAY30", "GRAY40",
                     "GRAY50", "GRAY60", "GRAY70", "GRAY80", "GRAY90"):
            assert name in tables.COLORS

    def test_all_values_are_valid_rgb_triples(self):
        for name, rgb in tables.COLORS.items():
            assert len(rgb) == 3
            for component in rgb:
                assert 0 <= component <= 255
                assert isinstance(component, int)

    def test_keys_are_uppercase(self):
        for name in tables.COLORS:
            assert name == name.upper()

    def test_gle_color_rgb_case_insensitive(self):
        assert tables.gle_color_rgb("blue") == (0, 0, 255)
        assert tables.gle_color_rgb("Blue") == (0, 0, 255)
        assert tables.gle_color_rgb("BLUE") == (0, 0, 255)
        assert tables.gle_color_rgb("  blue  ") == (0, 0, 255)

    def test_gle_color_rgb_unknown_returns_none(self):
        assert tables.gle_color_rgb("notacolor") is None

    def test_nearest_gle_color_exact_match(self):
        assert tables.nearest_gle_color(0, 0, 255) == "BLUE"
        assert tables.nearest_gle_color(255, 0, 0) == "RED"
        assert tables.nearest_gle_color(0, 0, 0) == "BLACK"

    def test_nearest_gle_color_euclidean_fallback(self):
        # Close to BLUE but not exact.
        result = tables.nearest_gle_color(2, 2, 250)
        assert result == "BLUE"

    def test_nearest_gle_color_returns_known_name(self):
        result = tables.nearest_gle_color(123, 45, 67)
        assert result in tables.COLORS


class TestMarkers:
    def test_marker_count(self):
        # GLE 4.3.10 stdmark[] table (src/gle/pass.cpp ~2371-2418).
        assert len(tables.MARKERS) == 48

    def test_known_markers_present(self):
        for name in ("CIRCLE", "FCIRCLE", "SQUARE", "FSQUARE", "TRIANGLE",
                     "FTRIANGLE", "DIAMOND", "FDIAMOND", "PLUS", "CROSS",
                     "STARR", "FSTARR", "DOT", "PCROSS"):
            assert name in tables.MARKERS

    def test_gle_marker_to_matplotlib_is_inverse_of_writer_map(self):
        # Every value in the built inverse map must map back correctly
        # through the writer's forward map.
        for gle_name, mpl_code in tables.GLE_MARKER_TO_MATPLOTLIB.items():
            assert MATPLOTLIB_TO_GLE_MARKERS[mpl_code] == gle_name

    def test_gle_marker_to_matplotlib_covers_every_gle_target(self):
        # Every GLE name that appears as a *value* in the writer's forward
        # map must have exactly one inverse entry.
        expected_targets = set(MATPLOTLIB_TO_GLE_MARKERS.values())
        assert set(tables.GLE_MARKER_TO_MATPLOTLIB.keys()) == expected_targets

    def test_canonical_choices_for_ambiguous_targets(self):
        # Documented canonical choices where multiple mpl codes collide on
        # one GLE name (first-seen-in-dict-order wins).
        assert tables.GLE_MARKER_TO_MATPLOTLIB["TRIANGLE"] == "<"
        assert tables.GLE_MARKER_TO_MATPLOTLIB["PLUS"] == "+"
        assert tables.GLE_MARKER_TO_MATPLOTLIB["PCROSS"] == "x"
        assert tables.GLE_MARKER_TO_MATPLOTLIB["DOT"] == "."

    def test_gle_marker_to_matplotlib_values_are_valid_gle_markers(self):
        # Sanity: every GLE name used as a key must itself be a real marker
        # gleplot's writer could emit (subset of the full stdmark table).
        for gle_name in tables.GLE_MARKER_TO_MATPLOTLIB:
            assert gle_name in tables.MARKERS


class TestLineStyles:
    def test_forward_map(self):
        assert tables.LSTYLE_TO_MATPLOTLIB == {1: "-", 2: "--", 3: ":", 4: "-."}

    def test_reverse_is_exact_inverse(self):
        for style_int, mpl in tables.LSTYLE_TO_MATPLOTLIB.items():
            assert tables.MATPLOTLIB_TO_LSTYLE[mpl] == style_int

    def test_matches_gle_style_config_defaults(self):
        from gleplot.config import GLEStyleConfig
        cfg = GLEStyleConfig()
        assert tables.MATPLOTLIB_TO_LSTYLE["--"] == cfg.line_style_dashed
        assert tables.MATPLOTLIB_TO_LSTYLE[":"] == cfg.line_style_dotted
        assert tables.MATPLOTLIB_TO_LSTYLE["-."] == cfg.line_style_dashdot
        assert tables.MATPLOTLIB_TO_LSTYLE["-"] == cfg.line_style_solid


class TestKeyPositions:
    def test_long_to_short_matches_writer_pos_map(self):
        assert tables.KEY_POSITIONS_LONG_TO_SHORT == {
            "top right": "tr",
            "top left": "tl",
            "bottom right": "br",
            "bottom left": "bl",
            "center": "cc",
        }

    def test_short_to_long_is_inverse_for_writer_positions(self):
        for long, short in tables.KEY_POSITIONS_LONG_TO_SHORT.items():
            assert tables.KEY_POSITIONS_SHORT_TO_LONG[short] == long

    def test_short_to_long_covers_all_gle_corner_and_center_positions(self):
        for short in ("tr", "tl", "br", "bl", "cc", "tc", "bc", "lc", "rc"):
            assert short in tables.KEY_POSITIONS_SHORT_TO_LONG

    def test_matches_axes_legend_loc_map_targets(self):
        # Axes.legend's loc_map produces these long-form strings; every one
        # must be representable in the long->short table.
        loc_map_targets = {
            "top right", "top left", "bottom left", "bottom right", "center",
        }
        assert loc_map_targets <= set(tables.KEY_POSITIONS_LONG_TO_SHORT.keys())


class TestGreyAliases:
    """MA-review fix: British GREY spellings resolve to GRAY entries."""

    def test_grey_aliases(self):
        from gleplot.parser.tables import gle_color_rgb
        assert gle_color_rgb("grey") == gle_color_rgb("gray")
        assert gle_color_rgb("DARKGREY") == gle_color_rgb("DARKGRAY")
        assert gle_color_rgb("lightslategrey") == gle_color_rgb("lightslategray")
        assert gle_color_rgb("grey") is not None
