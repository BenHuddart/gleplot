"""Unit tests for text annotation support."""

import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

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
        self.ax.text(1.0, 2.0, 'Peak A', color='red', fontsize=11, ha='center')

        self.assertEqual(len(self.ax.texts), 1)
        entry = self.ax.texts[0]
        self.assertEqual(entry['x'], 1.0)
        self.assertEqual(entry['y'], 2.0)
        self.assertEqual(entry['text'], 'Peak A')
        self.assertEqual(entry['color'], 'RED')
        self.assertEqual(entry['ha'], 'center')
        self.assertEqual(entry['fontsize'], 11.0)

    def test_text_generates_gle_commands(self):
        self.ax.plot([0, 1, 2], [0.2, 0.5, 0.3], color='blue')
        self.ax.text(1.25, 0.45, 'Comp 1', color='black', ha='left')

        gle = self.fig._generate_gle()

        self.assertIn('amove xg(1.25) yg(0.45)', gle)
        self.assertIn('write "Comp 1"', gle)
        self.assertIn('set just left', gle)
        self.assertLess(gle.find('end graph'), gle.find('amove xg(1.25) yg(0.45)'))

    def test_module_level_text(self):
        glp.figure()
        glp.text(0.5, 0.25, 'A')

        ax = glp.gca()
        self.assertEqual(len(ax.texts), 1)

    def test_figure_level_text(self):
        self.fig.text(0.2, 0.8, 'Figure API')
        self.assertEqual(len(self.ax.texts), 1)
        self.assertEqual(self.ax.texts[0]['text'], 'Figure API')

    def test_text_escapes_quotes_for_gle(self):
        self.ax.text(1.0, 1.0, 'He said "hello"')
        gle = self.fig._generate_gle()
        self.assertIn('write "He said \\"hello\\""', gle)

    def test_text_accepts_bbox_facecolor(self):
        self.ax.text(0.1, 0.2, 'boxed', bbox={'facecolor': 'yellow'})
        self.assertEqual(self.ax.texts[0]['box_color'], 'YELLOW')


if __name__ == '__main__':
    unittest.main()
