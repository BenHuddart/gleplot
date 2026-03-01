"""Unit tests for utility functions."""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from gleplot.colors import rgb_to_gle
from gleplot.markers import get_gle_marker


class TestColorMapping(unittest.TestCase):
    """Test color conversion utilities."""
    
    def test_single_letter_colors(self):
        """Test single-letter color codes."""
        self.assertEqual(rgb_to_gle('b'), 'BLUE')
        self.assertEqual(rgb_to_gle('r'), 'RED')
        self.assertEqual(rgb_to_gle('g'), 'GREEN')
        self.assertEqual(rgb_to_gle('k'), 'BLACK')
    
    def test_named_colors(self):
        """Test named colors."""
        self.assertEqual(rgb_to_gle('red'), 'RED')
        self.assertEqual(rgb_to_gle('blue'), 'BLUE')
        self.assertEqual(rgb_to_gle('green'), 'GREEN')
    
    def test_rgb_tuple(self):
        """Test RGB tuple conversion."""
        # Pure blue
        color = rgb_to_gle((0.0, 0.0, 1.0))
        self.assertEqual(color, 'BLUE')
        
        # Pure red
        color = rgb_to_gle((1.0, 0.0, 0.0))
        self.assertEqual(color, 'RED')


class TestMarkerMapping(unittest.TestCase):
    """Test marker conversion utilities."""
    
    def test_basic_markers(self):
        """Test basic matplotlib markers."""
        self.assertEqual(get_gle_marker('o'), 'FCIRCLE')
        self.assertEqual(get_gle_marker('s'), 'FSQUARE')
        self.assertEqual(get_gle_marker('^'), 'FTRIANGLE')
        self.assertEqual(get_gle_marker('+'), 'PLUS')
    
    def test_invalid_marker(self):
        """Test invalid marker returns default."""
        result = get_gle_marker('INVALID')
        self.assertEqual(result, 'FCIRCLE')  # Default


if __name__ == '__main__':
    unittest.main()
