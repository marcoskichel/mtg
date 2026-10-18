"""Tests for ligapreco.py with the network simulated. Run: python3 -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ligapreco  # noqa: E402


def counts(text):
    return {k: sum(e.qty for e in v) for k, v in ligapreco.parse_text(text).items() if v}


class ParseSections(unittest.TestCase):
    def test_moxfield_file_headers(self):
        text = ("// Name: Gio\n// Format: paupercommander\n\n"
                "// Commander\n1 Tithe Drinker\n\n"
                "// Mainboard\n1 Sol Ring\n10 Plains\n\n"
                "// Maybeboard\n1 Murder\n")
        self.assertEqual(counts(text), {"commander": 1, "main": 11, "maybe": 1})

    def test_plain_headers_and_colon(self):
        self.assertEqual(counts("Commander:\n1 X\nDeck\n3 Y\nSideboard\n1 Z\n"),
                         {"commander": 1, "main": 3, "side": 1})

    def test_comments_are_not_cards(self):
        self.assertEqual(counts("// just a note\n# another\n1 X\n"), {"main": 1})

    def test_blank_lines_split_sections_without_headers(self):
        self.assertEqual(counts("4 Bolt\n2 Path\n\n1 Duress\n"), {"main": 6, "side": 1})


if __name__ == "__main__":
    unittest.main()
