"""Tests for ligapreco.py with the network simulated. Run: python3 -m unittest discover -s tests"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class CustomCards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "custom.json"
        path.write_text(json.dumps([{"name": "Giovanni, Suporte Lateral",
                                     "type_line": "Legendary Creature"}]), encoding="utf-8")
        env = mock.patch.dict(os.environ, {ligapreco.scryfall.CUSTOM_ENV: str(path)})
        env.start()
        self.addCleanup(env.stop)
        ligapreco.scryfall._custom_cache.clear()
        self.addCleanup(ligapreco.scryfall._custom_cache.clear)

    def test_custom_card_is_left_out_without_asking_the_liga(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ligapreco.NameResolver, "_lookup") as lookup, \
                mock.patch.object(ligapreco.PriceClient, "get") as get, \
                mock.patch.object(ligapreco.NameResolver, "save"), \
                mock.patch.object(ligapreco.PriceClient, "save"), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = ligapreco.main(["--json", "--no-cache", "giovanni, suporte lateral"])
        self.assertEqual(code, 0)
        self.assertFalse(lookup.called or get.called)
        data = json.loads(out.getvalue())
        self.assertEqual((data["total"], data["completo"]), (0, True))
        self.assertEqual(data["cartas"][0]["status"], "carta custom")
        self.assertEqual(data["cartas"][0]["liga"], "Giovanni, Suporte Lateral")


if __name__ == "__main__":
    unittest.main()
