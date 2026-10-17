"""Tests for deckprofile.py. Run: python3 -m unittest discover -s tests"""

import io
import json
import os
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

    def test_unknown_bracket_placeholder_is_not_a_change(self):
        header = dict(self.header, bracket="?")
        self.assertEqual(self.check(DECK, header=header)[0], "fresh")

    def test_strategy_only_profile_is_fresh(self):
        self.assertEqual(prof.freshness({"bracket": "3"}, None, None, {})[0], "fresh")


def sc(name, cmc, type_line, ci, produced=None, gc=False, oid=None):
    return {"name": name, "cmc": cmc, "type_line": type_line, "color_identity": ci,
            "produced_mana": produced or [], "game_changer": gc,
            "oracle_id": oid or name.lower()}


CARDS = {
    "saruman, the white hand": sc("Saruman, the White Hand", 4, "Legendary Creature — Avatar",
                                  ["U", "B", "R"]),
    "sol ring": sc("Sol Ring", 1, "Artifact", [], ["C"], gc=True),
    "arcane signet": sc("Arcane Signet", 2, "Artifact", [], ["W", "U", "B", "R", "G"]),
    "lightning bolt": sc("Lightning Bolt", 1, "Instant", ["R"]),
    "counterspell": sc("Counterspell", 2, "Instant", ["U"]),
    "brainstorm": sc("Brainstorm", 1, "Instant", ["U"]),
    "ponder": sc("Ponder", 1, "Sorcery", ["U"]),
    "preordain": sc("Preordain", 1, "Sorcery", ["U"]),
    "island": sc("Island", 0, "Basic Land — Island", [], ["U"]),
}
ROLES = {"Sol Ring": ["ramp", "mana-rock"], "Arcane Signet": ["ramp", "mana-rock"],
         "Lightning Bolt": ["removal"], "Counterspell": ["counterspell"],
         "Brainstorm": ["draw"], "Ponder": [], "Preordain": [], "Island": [],
         "Saruman, the White Hand": []}


class FactsTest(unittest.TestCase):
    def setUp(self):
        self.f = prof.facts(boards_of(DECK)[0], CARDS, ROLES)

    def test_size_excludes_maybeboard(self):
        self.assertEqual(self.f["deck_size"], 16)

    def test_curve_counts_nonlands_with_quantity(self):
        self.assertEqual(self.f["curve"], {1: 5, 2: 2, 4: 1})
        self.assertAlmostEqual(self.f["avg_mv"], 13 / 8)

    def test_sources_count_lands_and_rocks(self):
        self.assertEqual(self.f["sources"]["U"], 9)
        self.assertEqual(self.f["sources"]["C"], 1)

    def test_role_counts_and_game_changers(self):
        self.assertEqual(self.f["role_counts"]["ramp"], 2)
        self.assertEqual(self.f["role_counts"]["removal"], 1)
        self.assertEqual(self.f["game_changers"], ["Sol Ring"])

    def test_mdfc_spell_land_counts_as_spell(self):
        cards = dict(CARDS)
        cards["ponder"] = sc("Ponder", 1, "Sorcery // Land", ["U"])
        f = prof.facts(boards_of(DECK)[0], cards, ROLES)
        self.assertEqual(f["curve"][1], 5)

    def test_sources_ignore_colors_outside_identity(self):
        cards = dict(CARDS)
        cards["island"] = sc("Command Tower", 0, "Land", [], ["W", "U", "B", "R", "G"])
        f = prof.facts(boards_of(DECK)[0], cards, ROLES)
        self.assertNotIn("W", f["sources"])
        self.assertNotIn("G", f["sources"])
        self.assertEqual(f["sources"]["U"], 9)

    def test_colors_from_commander(self):
        self.assertEqual(self.f["colors"], "ubr")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.deck = self.dir / "test.txt"
        self.deck.write_text(DECK)

    def run_cli(self, argv):
        def fake_load(boards):
            return CARDS, ROLES, []
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(prof, "load_cards", side_effect=fake_load), \
             mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = prof.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_show_without_profile_says_no_profile(self):
        code, out, err = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 1)
        self.assertIn("NO PROFILE", err)
        self.assertIn("deck size: 16", out)

    def test_new_from_deck_then_fresh(self):
        code, _, _ = self.run_cli(["new", "--deck", str(self.deck)])
        self.assertEqual(code, 0)
        p = self.dir / "test.profile.md"
        header, body = prof.read_profile(p)
        self.assertEqual(header["commanders"], "Saruman, the White Hand")
        self.assertEqual(header["bracket"], "3")
        self.assertEqual(header["colors"], "ubr")
        self.assertIn("## Plan", body)
        self.assertTrue((self.dir / "test.profile.lock").exists())
        code, out, _ = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 0)
        self.assertIn("status: fresh", out)

    def test_new_refuses_to_overwrite(self):
        self.run_cli(["new", "--deck", str(self.deck)])
        code, _, err = self.run_cli(["new", "--deck", str(self.deck)])
        self.assertEqual(code, 1)
        self.assertIn("exists", err)

    def test_stale_after_big_change_then_stamp_fixes(self):
        self.run_cli(["new", "--deck", str(self.deck)])
        self.deck.write_text(DECK.replace("8 Island", "1 Island"))
        code, out, err = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 1)
        self.assertIn("PROFILE STALE", err)
        p = self.dir / "test.profile.md"
        p.write_text(p.read_text().replace("## Plan\n", "## Plan\nReviewed plan.\n"))
        code, _, _ = self.run_cli(["stamp", str(p)])
        self.assertEqual(code, 0)
        self.assertIn("Reviewed plan.", p.read_text())
        code, out, _ = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 0)
        self.assertIn("status: fresh", out)

    def test_drift_lists_cards_exit_0(self):
        self.run_cli(["new", "--deck", str(self.deck)])
        self.deck.write_text(DECK.replace("1 Ponder", "1 Opt"))
        code, out, err = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 0)
        self.assertIn("drift", out)
        self.assertIn("+ opt", out)
        self.assertIn("- ponder", out)

    def test_new_rejects_bracket_that_contradicts_deck(self):
        code, _, err = self.run_cli(["new", "--deck", str(self.deck), "--bracket", "4"])
        self.assertEqual(code, 2)
        self.assertIn("Bracket: 3", err)
        self.assertFalse((self.dir / "test.profile.md").exists())

    def test_new_bracket_used_when_deck_has_none(self):
        self.deck.write_text(DECK.replace("// Bracket: 3\n", ""))
        code, _, _ = self.run_cli(["new", "--deck", str(self.deck), "--bracket", "4"])
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli(["show", str(self.deck)])
        self.assertEqual(code, 0)
        self.assertIn("bracket: 4", out)
        self.run_cli(["stamp", str(self.dir / "test.profile.md")])
        header, _ = prof.read_profile(self.dir / "test.profile.md")
        self.assertEqual(header["bracket"], "4")

    def test_profile_works_from_another_directory(self):
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.run_cli(["new", "--deck", "test.txt"])
        profile = self.dir / "test.profile.md"
        self.assertEqual(prof.read_profile(profile)[0]["profile-of"], "test.txt")
        os.chdir("/")
        code, out, err = self.run_cli(["show", str(profile)])
        self.assertEqual(code, 0, err)
        self.assertIn("status: fresh", out)
        code, _, err = self.run_cli(["stamp", str(profile)])
        self.assertEqual(code, 0, err)

    def test_new_strategy_only(self):
        out_path = self.dir / "aristo.profile.md"
        code, _, _ = self.run_cli(["new", "--strategy", "aristocrats, drain on death",
                                   "--colors", "wb", "--bracket", "3", "-o", str(out_path)])
        self.assertEqual(code, 0)
        header, body = prof.read_profile(out_path)
        self.assertNotIn("deck-hash", header)
        self.assertIn("aristocrats, drain on death", body)
        code, out, _ = self.run_cli(["show", str(out_path)])
        self.assertEqual(code, 0)
        self.assertIn("status: fresh", out)

    def test_new_commander_requires_bracket(self):
        with self.assertRaises(SystemExit):
            self.run_cli(["new", "--commander", "Edgar Markov", "-o",
                          str(self.dir / "e.profile.md")])

    def test_deck_without_commander_warns(self):
        self.deck.write_text(DECK.replace("// Commander\n1 Saruman, the White Hand (LTC) 8 #cmd\n",
                                          ""))
        code, out, err = self.run_cli(["show", str(self.deck)])
        self.assertIn("no commander", err)


class LoadCardsTest(unittest.TestCase):
    """Real scryfall.resolve_names, only HTTP and the tag file mocked."""

    def test_dfc_in_deck_counts_in_facts(self):
        text = ("// Commander\n1 Saruman, the White Hand\n\n"
                "// Mainboard\n1 Delver of Secrets // Insectile Aberration\n")
        delver = {"object": "card", "name": "Delver of Secrets // Insectile Aberration",
                  "layout": "transform", "cmc": 1.0, "oracle_id": "o-delver",
                  "type_line": "Creature — Human Wizard // Creature — Human Insect",
                  "color_identity": ["U"], "produced_mana": []}
        saruman = {"object": "card", "name": "Saruman, the White Hand", "layout": "normal",
                   "cmc": 4.0, "oracle_id": "o-sar", "type_line": "Legendary Creature",
                   "color_identity": ["U", "B", "R"]}

        def fake_http(method, url, body=None, retries=3):
            return {"object": "list", "data": [delver, saruman]}

        boards, _ = boards_of(text)
        with mock.patch.object(prof.scryfall, "_http", side_effect=fake_http), \
             mock.patch.object(prof.finder, "load_tags", return_value=[]), \
             mock.patch.object(sys, "stderr", io.StringIO()):
            cards, roles, missing = prof.load_cards(boards)
        f = prof.facts(boards, cards, roles)
        self.assertEqual(missing, [])
        self.assertEqual(f["curve"], {1: 1, 4: 1})


if __name__ == "__main__":
    unittest.main()
