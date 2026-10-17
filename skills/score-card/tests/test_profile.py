"""Tests for deckprofile.py. Run: python3 -m unittest discover -s tests"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deckprofile as prof  # noqa: E402

DECK = """// Moxfield: https://moxfield.com/decks/x
// Nome: Test
// Bracket: 3

// Commander
1 Saruman, the White Hand (LTC) 8 #cmd

// Mainboard
1 Sol Ring (CMM) 410 *F* #ramp
1 Arcane Signet (ELD) 331
1 Lightning Bolt
1 Counterspell
1 Brainstorm
1 Ponder
1 Preordain
8 Island

// Maybeboard
1 Rhystic Study
"""


def boards_of(text):
    return prof.moxfield.parse_deck(text)


def swap(text, old, new):
    return text.replace(old, new, 1)


class FingerprintTest(unittest.TestCase):
    def test_ignores_printing_tags_order_and_maybeboard(self):
        a = boards_of(DECK)[0]
        b_text = DECK.replace("(CMM) 410 *F* #ramp", "").replace("(ELD) 331", "(CMR) 1 #rock")
        b_text = b_text.replace("1 Lightning Bolt\n1 Counterspell\n",
                                "1 Counterspell\n1 lightning bolt\n")
        b_text = b_text.replace("1 Rhystic Study", "1 Mystic Remora")
        b = boards_of(b_text)[0]
        self.assertEqual(prof.fingerprint(prof.deck_lines(a)),
                         prof.fingerprint(prof.deck_lines(b)))

    def test_quantity_changes_hash(self):
        a = boards_of(DECK)[0]
        b = boards_of(DECK.replace("8 Island", "9 Island"))[0]
        self.assertNotEqual(prof.fingerprint(prof.deck_lines(a)),
                            prof.fingerprint(prof.deck_lines(b)))

    def test_hash_is_8_hex(self):
        h = prof.fingerprint(prof.deck_lines(boards_of(DECK)[0]))
        self.assertRegex(h, r"^[0-9a-f]{8}$")

    def test_commander_names_by_name_only(self):
        self.assertEqual(prof.commander_names(boards_of(DECK)[0]), ["Saruman, the White Hand"])


class PathsTest(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(prof.profile_path("decks/markov-gang.txt"),
                         Path("decks/markov-gang.profile.md"))
        self.assertEqual(prof.lock_path(Path("decks/markov-gang.profile.md")),
                         Path("decks/markov-gang.profile.lock"))


class ProfileFileTest(unittest.TestCase):
    def test_read_and_write_header_keeps_body(self):
        text = ("// profile-of: decks/x.txt\n// bracket: 3\n// deck-hash: aaaaaaaa\n\n"
                "## Plan\nGo wide. // not a header\n")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.profile.md"
            p.write_text(text)
            header, body = prof.read_profile(p)
            self.assertEqual(header["bracket"], "3")
            self.assertIn("Go wide. // not a header", body)
            header["deck-hash"] = "bbbbbbbb"
            prof.write_header(p, header)
            new = p.read_text()
            self.assertIn("// deck-hash: bbbbbbbb", new)
            self.assertTrue(new.endswith("## Plan\nGo wide. // not a header\n"))


class FreshnessTest(unittest.TestCase):
    def setUp(self):
        self.boards, self.meta = boards_of(DECK)
        self.lines = prof.deck_lines(self.boards)
        self.header = {"commanders": "Saruman, the White Hand", "bracket": "3",
                       "deck-hash": prof.fingerprint(self.lines)}

    def check(self, text, header=None, lock=None):
        boards, meta = boards_of(text)
        return prof.freshness(header or self.header, self.lines if lock is None else lock,
                              boards, meta)

    def test_fresh(self):
        self.assertEqual(self.check(DECK)[0], "fresh")

    def test_retag_and_reprint_stay_fresh(self):
        text = DECK.replace("(LTC) 8 #cmd", "(PLST) 99 #boss").replace("#ramp", "#rock")
        self.assertEqual(self.check(text)[0], "fresh")

    def test_small_swap_is_drift_with_names(self):
        status, _, added, removed = self.check(swap(DECK, "1 Ponder", "1 Opt"))
        self.assertEqual(status, "drift")
        self.assertEqual(added, ["opt"])
        self.assertEqual(removed, ["ponder"])

    def test_exactly_five_changes_is_drift(self):
        text = DECK.replace("8 Island", "3 Island")
        self.assertEqual(self.check(text)[0], "drift")

    def test_six_changes_is_stale(self):
        text = DECK.replace("8 Island", "2 Island")
        self.assertEqual(self.check(text)[0], "stale")

    def test_commander_change_is_stale(self):
        text = DECK.replace("Saruman, the White Hand (LTC) 8", "Edgar Markov")
        status, reason, _, _ = self.check(text)
        self.assertEqual(status, "stale")
        self.assertIn("commander", reason)

    def test_bracket_change_is_stale(self):
        status, reason, _, _ = self.check(DECK.replace("// Bracket: 3", "// Bracket: 4"))
        self.assertEqual(status, "stale")
        self.assertIn("bracket", reason)

    def test_hash_mismatch_without_lock_is_stale(self):
        text = swap(DECK, "1 Ponder", "1 Opt")
        boards, meta = boards_of(text)
        status, reason, _, _ = prof.freshness(self.header, None, boards, meta)
        self.assertEqual(status, "stale")
        self.assertIn("lock", reason)

    def test_strategy_only_profile_is_fresh(self):
        self.assertEqual(prof.freshness({"bracket": "3"}, None, None, {})[0], "fresh")


if __name__ == "__main__":
    unittest.main()
