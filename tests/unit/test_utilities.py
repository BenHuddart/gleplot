"""Unit tests for utility functions."""

import warnings

from gleplot.colors import rgb_to_gle
from gleplot.markers import get_gle_marker


class TestColorMapping:
    """Test color conversion utilities."""

    def test_single_letter_colors(self):
        """Test single-letter color codes."""
        assert rgb_to_gle("b") == "BLUE"
        assert rgb_to_gle("r") == "RED"
        assert rgb_to_gle("g") == "GREEN"
        assert rgb_to_gle("k") == "BLACK"

    def test_named_colors(self):
        """Test named colors."""
        assert rgb_to_gle("red") == "RED"
        assert rgb_to_gle("blue") == "BLUE"
        assert rgb_to_gle("green") == "GREEN"

    def test_rgb_tuple(self):
        """RGB tuples convert to exact rgb255() expressions, never snapped."""
        # Pure blue
        color = rgb_to_gle((0.0, 0.0, 1.0))
        assert color == "rgb255(0,0,255)"

        # Pure red
        color = rgb_to_gle((1.0, 0.0, 0.0))
        assert color == "rgb255(255,0,0)"


class TestMarkerMapping:
    """Test marker conversion utilities."""

    def test_basic_markers(self):
        """Test basic matplotlib markers."""
        assert get_gle_marker("o") == "FCIRCLE"
        assert get_gle_marker("s") == "FSQUARE"
        assert get_gle_marker("^") == "FTRIANGLE"
        assert get_gle_marker("+") == "PLUS"

    def test_invalid_marker(self):
        """Test invalid marker returns default -- and now says so.

        The fallback value is unchanged, but it is no longer silent: an
        unrecognized symbol warns (see tests/unit/test_outline_markers.py) so
        a typo cannot quietly become a differently-shaped marker.
        """
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = get_gle_marker("INVALID")
        assert result == "FCIRCLE"  # Default
        assert any(issubclass(w.category, UserWarning) for w in caught)

    def test_case_significant_markers(self):
        """Case-significant matplotlib codes must map to distinct GLE markers.

        Regression: get_gle_marker() previously lowercased its input before the
        dict lookup, so 'D' (diamond) collapsed to a missing 'd' key and fell
        back to the default FCIRCLE, and 'P'/'H' were similarly mismapped.
        """
        assert get_gle_marker("D") == "FDIAMOND"  # Diamond, not default
        assert get_gle_marker("P") == "PLUS"  # Filled plus
        assert get_gle_marker("H") == "HEART"  # Distinct from 'h'
        # Lowercase counterparts remain their own mappings.
        assert get_gle_marker("h") == "DIAMOND"

    def test_common_lowercase_markers(self):
        """Common lowercase codes are unchanged by the case fix."""
        assert get_gle_marker("o") == "FCIRCLE"
        assert get_gle_marker("s") == "FSQUARE"
