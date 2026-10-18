"""Tests for build.py with Scryfall, EDHREC and the tag file simulated.

Run: python3 -m unittest discover -s tests
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build  # noqa: E402


def sc(name, ci, type_line="Creature", legal=True, gc=False, cmc=2):
    return {"name": name, "oracle_id": "o-" + name.lower().replace(" ", "-"),
            "color_identity": list(ci), "type_line": type_line, "cmc": cmc,
            "legalities": {"commander": "legal" if legal else "banned"},
            "game_changer": gc, "layout": "normal"}


CARDS = {c["name"]: c for c in [
    sc("Edgar Markov", "WBR", "Legendary Creature — Vampire Knight", cmc=6),
    sc("Sol Ring", "", "Artifact", cmc=1),
    sc("Arcane Signet", "", "Artifact", cmc=2),
    sc("Captivating Vampire", "B"),
    sc("Bloodghast", "B"),
    sc("Swords to Plowshares", "W", "Instant", cmc=1),
    sc("Llanowar Elves", "G"),
    sc("Mana Crypt", "", "Artifact", legal=False, cmc=0),
    sc("Rhystic Study", "U", "Enchantment", gc=True),
    sc("Cyclonic Rift", "U", "Instant", gc=True),
    sc("Bolas's Citadel", "B", "Legendary Artifact", gc=True, cmc=6),
    sc("Command Tower", "", "Land", cmc=0),
    sc("Swamp", "B", "Basic Land — Swamp", cmc=0),
    sc("Night's Whisper", "B", "Sorcery", cmc=2),
    sc("Delver of Secrets // Insectile Aberration", "U"),
]}
ROLES = {"Sol Ring": ["ramp", "mana-rock"], "Arcane Signet": ["ramp", "mana-rock"],
         "Swords to Plowshares": ["removal"], "Night's Whisper": ["draw", "card-advantage"],
         "Cyclonic Rift": ["removal"], "Rhystic Study": ["draw", "card-advantage"]}

DECK = """// Name: Test Gang
// Format: commander
// Bracket: 3

// Commander
1 Edgar Markov

// Mainboard
1 Sol Ring (CMM) 410
"""


def fake_resolve(names):
    out = {}
    for n in names:
        key = build.card_key(n)
        for c in CARDS.values():
            if build.card_key(c["name"]) == key:
                out[key] = c
    return out, [n for n in names if build.card_key(n) not in out]


def fake_roles(cards):
    return {c["name"]: ROLES.get(c["name"], []) for c in cards}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.deck = self.dir / "gang.txt"
        self.deck.write_text(DECK)
        for target, fn in (("resolve", fake_resolve), ("roles_of", fake_roles)):
            p = mock.patch.object(build, target, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def run_cli(self, argv, fetch=None, prices=None):
        pages = fetch or {}

        def fake_fetch(path, ttl_hours=24):
            return pages.get(path), 0.0

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(build.edhrec, "fetch", side_effect=fake_fetch), \
             mock.patch.object(build, "prices", side_effect=lambda names: prices or {}), \
             mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = build.main(argv)
        return code, out.getvalue(), err.getvalue()

    def state(self):
        return json.loads(build.build_path(self.deck).read_text())

    def boards(self):
        return build.moxfield.parse_deck(self.deck.read_text())[0]


AVG = {"deck": {"commander": ["Edgar Markov"], "cards": {
    "Artifact": [["Sol Ring", 1], ["Arcane Signet", 1]],
    "Instant": [["Swords to Plowshares", 1]],
    "Land": [["Swamp", 30], ["Command Tower", 1]]}}}
CMDR = {"container": {"json_dict": {"cardlists": [
    {"header": "Top Cards", "cardviews": [
        {"name": "Captivating Vampire", "num_decks": 80, "potential_decks": 100, "synergy": 0.7},
        {"name": "Sol Ring", "num_decks": 95, "potential_decks": 100, "synergy": 0.0},
        {"name": "Bloodghast", "num_decks": 20, "potential_decks": 100, "synergy": 0.3}]},
    {"header": "Instants", "cardviews": [
        {"name": "Swords to Plowshares", "num_decks": 60, "potential_decks": 100,
         "synergy": 0.1},
        {"name": "Cyclonic Rift", "num_decks": 5, "potential_decks": 100, "synergy": 0.0}]},
    {"header": "Lands", "cardviews": [
        {"name": "Command Tower", "num_decks": 90, "potential_decks": 100, "synergy": 0.0}]}]}}}
PAGES = {"average-decks/edgar-markov": AVG, "commanders/edgar-markov": CMDR}


class TargetsTest(unittest.TestCase):
    def test_template_without_average(self):
        targets, sources = build.adjust_targets(None, None)
        self.assertEqual(targets, build.TEMPLATE)
        self.assertEqual(set(sources.values()), {"template"})

    def test_average_moves_targets_within_three(self):
        targets, sources = build.adjust_targets({"ramp": 20, "draw": 9, "removal": 0}, 31)
        self.assertEqual(targets["ramp"], build.TEMPLATE["ramp"] + 3)
        self.assertEqual(targets["draw"], 9)
        self.assertEqual(targets["removal"], build.TEMPLATE["removal"] - 3)
        self.assertEqual(targets["lands"], 33)
        self.assertEqual(sources["draw"], "average deck")

    def test_gc_limit(self):
        self.assertEqual(build.gc_limit(2), 0)
        self.assertEqual(build.gc_limit(3), 3)
        self.assertIsNone(build.gc_limit(4))


class InitTest(Base):
    def test_init_writes_targets_from_average_deck(self):
        code, out, _ = self.run_cli(["init", str(self.deck)], PAGES)
        self.assertEqual(code, 0)
        st = self.state()
        self.assertEqual(st["commanders"], ["Edgar Markov"])
        self.assertEqual(st["bracket"], 3)
        self.assertEqual(st["targets"]["lands"], 33)
        self.assertEqual(st["identity"], "WBR")
        self.assertIn("lands", out)

    def test_init_needs_commander(self):
        self.deck.write_text("// Mainboard\n1 Sol Ring\n")
        code, _, err = self.run_cli(["init", str(self.deck)], PAGES)
        self.assertEqual(code, 2)
        self.assertIn("commander", err)

    def test_init_needs_bracket(self):
        self.deck.write_text(DECK.replace("// Bracket: 3\n", ""))
        code, _, err = self.run_cli(["init", str(self.deck)], PAGES)
        self.assertEqual(code, 2)
        self.assertIn("--bracket", err)
        code, _, _ = self.run_cli(["init", str(self.deck), "--bracket", "4"], PAGES)
        self.assertEqual(code, 0)
        self.assertIn("// Bracket: 4", self.deck.read_text())

    def test_init_refuses_to_overwrite(self):
        self.run_cli(["init", str(self.deck)], PAGES)
        code, _, err = self.run_cli(["init", str(self.deck)], PAGES)
        self.assertEqual(code, 1)
        self.assertIn("--force", err)

    def test_init_without_average_deck_uses_template(self):
        code, out, err = self.run_cli(["init", str(self.deck)], {})
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["targets"], build.TEMPLATE)
        self.assertIn("template", out)


class PoolTest(Base):
    def setUp(self):
        super().setUp()
        self.run_cli(["init", str(self.deck)], PAGES)

    def test_pool_fills_maybeboard_and_filters(self):
        extra = self.dir / "extra.txt"
        extra.write_text("Llanowar Elves\nMana Crypt\nNight's Whisper\nBolas's Citadel\n")
        code, out, _ = self.run_cli(["pool", str(self.deck), "--extra", str(extra)], PAGES)
        self.assertEqual(code, 0)
        maybe = sorted(c.name for c in self.boards()["maybeboard"])
        self.assertEqual(maybe, ["Arcane Signet", "Bloodghast", "Bolas's Citadel",
                                 "Captivating Vampire", "Command Tower", "Night's Whisper",
                                 "Swords to Plowshares"])
        self.assertIn("off-identity", out)
        self.assertIn("Llanowar Elves", out)
        self.assertIn("Mana Crypt", out)
        pool = self.state()["pool"]
        self.assertAlmostEqual(pool["Captivating Vampire"]["inclusion"], 0.8)
        self.assertEqual(pool["Night's Whisper"]["sources"], ["search"])
        self.assertTrue(pool["Bolas's Citadel"]["gc"])
        self.assertEqual(pool["Arcane Signet"]["roles"], ["ramp", "mana-rock"])

    def test_pool_skips_basics_deck_cards_and_rejected(self):
        st = self.state()
        st["rejected"] = ["Bloodghast"]
        build.save_state(self.deck, st)
        self.run_cli(["pool", str(self.deck)], PAGES)
        maybe = {c.name for c in self.boards()["maybeboard"]}
        self.assertNotIn("Swamp", maybe)
        self.assertNotIn("Sol Ring", maybe)
        self.assertNotIn("Bloodghast", maybe)

    def test_pool_drops_game_changers_at_bracket_2(self):
        st = self.state()
        st["bracket"] = 2
        build.save_state(self.deck, st)
        extra = self.dir / "extra.txt"
        extra.write_text("Bolas's Citadel\n")
        code, out, _ = self.run_cli(["pool", str(self.deck), "--extra", str(extra)], PAGES)
        self.assertNotIn("Bolas's Citadel", {c.name for c in self.boards()["maybeboard"]})
        self.assertIn("game changer", out)

    def test_pool_budget_per_card(self):
        st = self.state()
        st["budget"]["card"] = 10.0
        build.save_state(self.deck, st)
        code, out, _ = self.run_cli(["pool", str(self.deck)], PAGES,
                                    prices={"Captivating Vampire": 25.0, "Bloodghast": 4.0})
        maybe = {c.name for c in self.boards()["maybeboard"]}
        self.assertNotIn("Captivating Vampire", maybe)
        self.assertIn("Bloodghast", maybe)
        self.assertIn("over budget", out)

    def test_pool_twice_does_not_duplicate(self):
        self.run_cli(["pool", str(self.deck)], PAGES)
        self.run_cli(["pool", str(self.deck)], PAGES)
        names = [c.name for c in self.boards()["maybeboard"]]
        self.assertEqual(len(names), len(set(names)))

    def test_pool_needs_init(self):
        build.build_path(self.deck).unlink()
        code, _, err = self.run_cli(["pool", str(self.deck)], PAGES)
        self.assertEqual(code, 2)
        self.assertIn("init", err)


class RoundTest(Base):
    def setUp(self):
        super().setUp()
        self.run_cli(["init", str(self.deck)], PAGES)
        self.run_cli(["pool", str(self.deck)], PAGES)
        self.out = self.dir / "round.json"

    def round(self, role, *extra):
        code, out, err = self.run_cli(["round", str(self.deck), role, "--out", str(self.out),
                                       *extra], PAGES)
        data = json.loads(self.out.read_text()) if self.out.exists() else None
        return code, out, data

    def test_role_round_filters_by_role_and_sorts_by_inclusion(self):
        code, out, data = self.round("removal")
        self.assertEqual(code, 0)
        self.assertEqual([d["name"] for d in data], ["Swords to Plowshares"])
        self.assertIn("60%", data[0]["reason"])
        self.assertIn("need", out)

    def test_no_brainers_take_high_inclusion_any_role(self):
        code, _, data = self.round("no-brainers")
        self.assertEqual([d["name"] for d in data],
                         ["Command Tower", "Captivating Vampire", "Swords to Plowshares"])

    def test_theme_excludes_utility_roles_and_lands(self):
        code, _, data = self.round("theme")
        self.assertEqual([d["name"] for d in data], ["Captivating Vampire", "Bloodghast"])

    def test_lands_round(self):
        code, _, data = self.round("lands")
        self.assertEqual([d["name"] for d in data], ["Command Tower"])

    def test_limit(self):
        code, _, data = self.round("theme", "--limit", "1")
        self.assertEqual(len(data), 1)

    def test_unknown_role(self):
        code, _, _ = self.round("vibes")
        self.assertEqual(code, 2)


class ApplyTest(Base):
    def setUp(self):
        super().setUp()
        self.run_cli(["init", str(self.deck)], PAGES)
        self.run_cli(["pool", str(self.deck)], PAGES)
        self.offered = self.dir / "round.json"
        self.run_cli(["round", str(self.deck), "theme", "--out", str(self.offered)], PAGES)
        self.answer = self.dir / "answer.json"

    def apply(self, answer, *extra):
        self.answer.write_text(json.dumps(answer))
        return self.run_cli(["apply", str(self.deck), "--answer", str(self.answer),
                             "--offered", str(self.offered), *extra], PAGES)

    def test_picked_move_to_mainboard_rest_rejected(self):
        code, out, _ = self.apply({"status": "picked", "picked": [
            {"name": "Captivating Vampire", "set": "m11", "collector_number": "88"}]})
        self.assertEqual(code, 0)
        b = self.boards()
        main = {c.name: c for c in b["mainboard"]}
        self.assertIn("Captivating Vampire", main)
        self.assertEqual((main["Captivating Vampire"].set, main["Captivating Vampire"].cn),
                         ("m11", "88"))
        maybe = {c.name for c in b["maybeboard"]}
        self.assertNotIn("Captivating Vampire", maybe)
        self.assertNotIn("Bloodghast", maybe)
        st = self.state()
        self.assertIn("Bloodghast", st["rejected"])
        self.assertEqual(st["rounds"][-1]["role"], "theme")
        self.assertEqual(st["rounds"][-1]["picked"], ["Captivating Vampire"])

    def test_cancelled_changes_nothing(self):
        before = self.deck.read_text()
        code, _, err = self.apply({"status": "cancelled"})
        self.assertEqual(code, 1)
        self.assertEqual(self.deck.read_text(), before)
        self.assertEqual(self.state()["rejected"], [])

    def test_dfc_full_name_matches_front_face_line(self):
        b = self.boards()
        b["maybeboard"].append(build.moxfield.Card(1, "Delver of Secrets", "maybeboard"))
        build.write_deck(self.deck, b, build.moxfield.parse_deck(self.deck.read_text())[1])
        self.offered.write_text(json.dumps([{"name": "Delver of Secrets", "reason": "x"}]))
        code, _, _ = self.apply({"status": "picked", "picked": [
            {"name": "Delver of Secrets // Insectile Aberration", "set": "isd",
             "collector_number": "51"}]})
        self.assertEqual(code, 0)
        self.assertIn("Delver of Secrets // Insectile Aberration",
                      {c.name for c in self.boards()["mainboard"]})

    def test_cut_moves_mainboard_card_to_maybeboard(self):
        self.offered.write_text(json.dumps([{"name": "Sol Ring", "reason": "x"}]))
        code, _, _ = self.apply({"status": "picked", "picked": [
            {"name": "Sol Ring", "set": "cmm", "collector_number": "410"}]}, "--cut")
        self.assertEqual(code, 0)
        b = self.boards()
        self.assertNotIn("Sol Ring", {c.name for c in b["mainboard"]})
        self.assertIn("Sol Ring", {c.name for c in b["maybeboard"]})
        self.assertNotIn("Sol Ring", self.state()["rejected"])


class StatusTest(Base):
    def test_status_counts(self):
        self.run_cli(["init", str(self.deck)], PAGES)
        self.run_cli(["pool", str(self.deck)], PAGES)
        code, out, _ = self.run_cli(["status", str(self.deck), "--json"], PAGES)
        self.assertEqual(code, 0)
        s = json.loads(out)
        self.assertEqual(s["deck_size"], 2)
        self.assertEqual(s["roles"]["ramp"], {"have": 1, "target": s["targets"]["ramp"]})
        self.assertEqual(s["lands"]["have"], 0)
        self.assertEqual(s["open_slots"], 98)
        self.assertEqual(s["game_changers"], {"have": [], "limit": 3})
        self.assertGreater(s["pool_size"], 0)

    def test_status_budget_total(self):
        self.run_cli(["init", str(self.deck), "--budget", "100"], PAGES)
        code, out, _ = self.run_cli(["status", str(self.deck), "--json"], PAGES,
                                    prices={"Edgar Markov": 80.0, "Sol Ring": 8.0})
        s = json.loads(out)
        self.assertEqual(s["budget"], {"cap": 100.0, "spent": 88.0, "unpriced": []})


if __name__ == "__main__":
    unittest.main()
