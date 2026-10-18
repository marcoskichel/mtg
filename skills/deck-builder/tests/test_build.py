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
    sc("Path to Exile", "W", "Instant", cmc=1),
    sc("Snow-Covered Swamp", "B", "Basic Snow Land — Swamp", cmc=0),
    sc("Tymna the Weaver", "WB", "Legendary Creature — Human Cleric", cmc=3),
    sc("Kraum, Ludevic's Opus", "UR", "Legendary Creature — Zombie Horror", cmc=5),
]}
ALIASES = {"edgar markovv": "Edgar Markov"}
ROLES = {"Sol Ring": ["ramp", "mana-rock"], "Arcane Signet": ["ramp", "mana-rock"],
         "Swords to Plowshares": ["removal"], "Night's Whisper": ["draw", "card-advantage"],
         "Cyclonic Rift": ["removal"], "Rhystic Study": ["draw", "card-advantage"],
         "Path to Exile": ["removal", "ramp"]}

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
        key = build.card_key(ALIASES.get(build.card_key(n), n))
        for c in CARDS.values():
            if build.card_key(c["name"]) == key:
                out[build.card_key(n)] = c
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
        self.assertRegex(out, r"not legal: .*Mana Crypt")
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

    def test_no_brainers_round_keeps_the_rest_in_the_pool(self):
        self.run_cli(["round", str(self.deck), "no-brainers", "--out", str(self.offered)],
                     PAGES)
        code, out, _ = self.apply({"status": "picked", "picked": [
            {"name": "Command Tower", "set": "cmm", "collector_number": "1"}]})
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["rejected"], [])
        maybe = {c.name for c in self.boards()["maybeboard"]}
        self.assertIn("Captivating Vampire", maybe)
        self.assertEqual(self.state()["rounds"][-1]["role"], "no-brainers")

    def test_pick_not_in_offer_changes_nothing(self):
        before = self.deck.read_text()
        code, _, err = self.apply({"status": "picked", "picked": [
            {"name": "Swords to Plowshares", "set": "a25", "collector_number": "35"}]})
        self.assertEqual(code, 1)
        self.assertIn("Swords to Plowshares", err)
        self.assertEqual(self.deck.read_text(), before)
        self.assertEqual(self.state()["rejected"], [])

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


class ReviewFixesTest(Base):
    """Findings from the team review, each pinned by a test."""

    def init_pool(self, pages=PAGES, extra=None):
        self.run_cli(["init", str(self.deck)], pages)
        args = ["pool", str(self.deck)]
        if extra:
            f = self.dir / "extra.txt"
            f.write_text(extra)
            args += ["--extra", str(f)]
        return self.run_cli(args, pages)

    def test_budget_counts_quantity(self):
        self.deck.write_text(DECK + "10 Swamp\n")
        self.run_cli(["init", str(self.deck), "--budget", "200"], PAGES)
        code, out, _ = self.run_cli(["status", str(self.deck), "--json"], PAGES,
                                    prices={"Edgar Markov": 80.0, "Sol Ring": 8.0,
                                            "Swamp": 1.0})
        self.assertEqual(json.loads(out)["budget"]["spent"], 98.0)

    def test_cut_takes_one_copy_and_keeps_printing_and_tags(self):
        self.deck.write_text(DECK.replace("1 Sol Ring (CMM) 410", "1 Sol Ring (CMM) 410 #ramp")
                             + "6 Swamp (J25) 89\n")
        self.init_pool()
        offer = self.dir / "cut.json"
        offer.write_text(json.dumps([{"name": "Swamp", "reason": "x"},
                                     {"name": "Sol Ring", "reason": "x"}]))
        ans = self.dir / "ans.json"
        ans.write_text(json.dumps({"status": "picked", "picked": [
            {"name": "Swamp", "set": "j25", "collector_number": "89"},
            {"name": "Sol Ring", "set": "cmm", "collector_number": "410"}]}))
        code, _, _ = self.run_cli(["apply", str(self.deck), "--answer", str(ans),
                                   "--offered", str(offer), "--cut"], PAGES)
        self.assertEqual(code, 0)
        b = self.boards()
        main = {c.name: c for c in b["mainboard"]}
        self.assertEqual(main["Swamp"].qty, 5)
        maybe = {c.name: c for c in b["maybeboard"]}
        self.assertEqual((maybe["Sol Ring"].set, maybe["Sol Ring"].cn, maybe["Sol Ring"].tags),
                         ("cmm", "410", ["ramp"]))

    def test_apply_reads_role_from_the_offer_file(self):
        self.init_pool()
        nb, rr = self.dir / "nb.json", self.dir / "ramp.json"
        self.run_cli(["round", str(self.deck), "no-brainers", "--out", str(nb)], PAGES)
        self.run_cli(["round", str(self.deck), "ramp", "--out", str(rr)], PAGES)
        ans = self.dir / "ans.json"
        ans.write_text(json.dumps({"status": "picked", "picked": [
            {"name": "Command Tower", "set": "cmm", "collector_number": "1"}]}))
        code, _, _ = self.run_cli(["apply", str(self.deck), "--answer", str(ans),
                                   "--offered", str(nb)], PAGES)
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["rejected"], [])
        self.assertEqual(self.state()["rounds"][-1]["role"], "no-brainers")

    def test_apply_unknown_offer_needs_role(self):
        self.init_pool()
        offer = self.dir / "hand.json"
        offer.write_text(json.dumps([{"name": "Bloodghast", "reason": "x"}]))
        ans = self.dir / "ans.json"
        ans.write_text(json.dumps({"status": "picked", "picked": [
            {"name": "Bloodghast", "set": "m10", "collector_number": "1"}]}))
        code, _, err = self.run_cli(["apply", str(self.deck), "--answer", str(ans),
                                     "--offered", str(offer)], PAGES)
        self.assertEqual(code, 2)
        self.assertIn("--role", err)

    def test_maybeboard_cards_join_the_pool(self):
        self.deck.write_text(DECK + "\n// Maybeboard\n1 Night's Whisper\n")
        self.init_pool()
        self.assertIn("Night's Whisper", self.state()["pool"])

    def test_init_force_keeps_pool_and_rounds_work(self):
        self.init_pool()
        st = self.state()
        st["rejected"] = ["Bloodghast"]
        build.save_state(self.deck, st)
        self.run_cli(["init", str(self.deck), "--force"], PAGES)
        self.run_cli(["pool", str(self.deck)], PAGES)
        out = self.dir / "t.json"
        self.run_cli(["round", str(self.deck), "theme", "--out", str(out)], PAGES)
        self.assertEqual([d["name"] for d in json.loads(out.read_text())],
                         ["Captivating Vampire"])
        self.assertEqual(self.state()["rejected"], ["Bloodghast"])

    def test_commander_name_comes_from_scryfall(self):
        self.deck.write_text(DECK.replace("1 Edgar Markov", "1 Edgar Markovv"))
        code, _, _ = self.run_cli(["init", str(self.deck)], PAGES)
        self.assertEqual(code, 0)
        st = self.state()
        self.assertEqual(st["commanders"], ["Edgar Markov"])
        self.assertEqual(st["target_sources"]["lands"], "average deck")
        self.assertEqual([c.name for c in self.boards()["commanders"]], ["Edgar Markov"])

    def test_pool_without_commander_page_fails(self):
        self.run_cli(["init", str(self.deck)], PAGES)
        code, _, err = self.run_cli(["pool", str(self.deck)], {})
        self.assertEqual(code, 1)
        self.assertIn("EDHREC", err)

    def test_one_row_per_card_across_spellings(self):
        self.init_pool(extra="captivating vampire\n")
        row = self.state()["pool"]["Captivating Vampire"]
        self.assertAlmostEqual(row["inclusion"], 0.8)
        self.assertEqual(sorted(row["sources"]), ["edhrec", "search"])

    def test_snow_basics_are_basics(self):
        self.init_pool(extra="Snow-Covered Swamp\n")
        self.assertNotIn("Snow-Covered Swamp", {c.name for c in self.boards()["maybeboard"]})

    def test_multi_role_card_survives_one_role_round(self):
        self.init_pool(extra="Path to Exile\n")
        out = self.dir / "ramp.json"
        self.run_cli(["round", str(self.deck), "ramp", "--out", str(out)], PAGES)
        offered = [d["name"] for d in json.loads(out.read_text())]
        self.assertIn("Path to Exile", offered)
        ans = self.dir / "ans.json"
        ans.write_text(json.dumps({"status": "picked", "picked": [
            {"name": "Arcane Signet", "set": "cmm", "collector_number": "1"}]}))
        self.run_cli(["apply", str(self.deck), "--answer", str(ans), "--offered", str(out)],
                     PAGES)
        self.assertNotIn("Path to Exile", self.state()["rejected"])
        out2 = self.dir / "removal.json"
        self.run_cli(["round", str(self.deck), "removal", "--out", str(out2)], PAGES)
        self.assertIn("Path to Exile", [d["name"] for d in json.loads(out2.read_text())])

    def test_apply_leaves_the_profile_alone(self):
        self.init_pool()
        profile = self.dir / "gang.profile.md"
        profile.write_text("// profile-of: gang.txt\n// deck-hash: aaaaaaaa\n\n## Plan\nx\n")
        out = self.dir / "t.json"
        self.run_cli(["round", str(self.deck), "theme", "--out", str(out)], PAGES)
        ans = self.dir / "ans.json"
        ans.write_text(json.dumps({"status": "picked", "picked": [
            {"name": "Bloodghast", "set": "m10", "collector_number": "1"}]}))
        self.run_cli(["apply", str(self.deck), "--answer", str(ans), "--offered", str(out)],
                     PAGES)
        self.assertIn("aaaaaaaa", profile.read_text())

    def test_init_counts_roles_in_average_deck(self):
        self.run_cli(["init", str(self.deck)], PAGES)
        st = self.state()
        self.assertEqual(st["targets"]["ramp"], build.TEMPLATE["ramp"] - 3)
        self.assertEqual(st["targets"]["removal"], build.TEMPLATE["removal"] - 3)
        self.assertEqual(st["target_sources"]["ramp"], "average deck")

    def test_status_over_bracket(self):
        self.deck.write_text(DECK + "1 Bolas's Citadel\n1 Rhystic Study\n1 Cyclonic Rift\n"
                             "1 Mana Crypt\n")
        CARDS["Mana Crypt"]["game_changer"] = True
        self.addCleanup(CARDS["Mana Crypt"].__setitem__, "game_changer", False)
        self.run_cli(["init", str(self.deck)], PAGES)
        code, _, err = self.run_cli(["status", str(self.deck)], PAGES)
        self.assertEqual(code, 1)
        self.assertIn("OVER BRACKET", err)

    def test_pair_commander_uses_pair_page(self):
        self.deck.write_text(DECK.replace("1 Edgar Markov",
                                          "1 Tymna the Weaver\n1 Kraum, Ludevic's Opus"))
        pages = {"average-decks/kraum-ludevics-opus-tymna-the-weaver": AVG}
        self.run_cli(["init", str(self.deck)], pages)
        st = self.state()
        self.assertEqual(st["target_sources"]["lands"], "average deck")
        self.assertEqual(st["identity"], "WUBR")

    def test_pool_reports_unresolved(self):
        cmdr = json.loads(json.dumps(CMDR))
        cmdr["container"]["json_dict"]["cardlists"][0]["cardviews"].append(
            {"name": "Nonexistent Card", "num_decks": 1, "potential_decks": 100})
        pages = dict(PAGES, **{"commanders/edgar-markov": cmdr})
        code, out, _ = self.init_pool(pages)
        self.assertEqual(code, 1)
        self.assertIn("Nonexistent Card", out)


class PricesTest(unittest.TestCase):
    def test_parses_ligapreco_json(self):
        payload = {"cartas": [
            {"pedido": "Sol Ring", "status": "precificado", "unitario": 8.25},
            {"pedido": "Rare Thing", "status": "sem estoque", "unitario": 0}]}
        run = mock.Mock(stdout=json.dumps(payload), stderr="")
        with mock.patch.object(build.subprocess, "run", return_value=run):
            self.assertEqual(build.prices(["Sol Ring", "Rare Thing"]),
                             {"Sol Ring": 8.25, "Rare Thing": None})

    def test_no_output_means_unpriced(self):
        run = mock.Mock(stdout="", stderr="boom")
        with mock.patch.object(build.subprocess, "run", return_value=run), \
             mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(build.prices(["Sol Ring"]), {"Sol Ring": None})


def custom(name, ci):
    c = sc(name, ci, "Legendary Creature — Human Advisor", cmc=3)
    c["custom"], c["legalities"] = True, {}
    return c


def pdh(name, ci, legal, type_line="Creature"):
    c = sc(name, ci, type_line)
    c["legalities"] = {"commander": "legal", "paupercommander": legal}
    return c


PDH_CARDS = {c["name"]: c for c in [
    custom("Giovanni, Suporte Lateral", "WB"),
    pdh("Tithe Drinker", "WB", "legal"),
    pdh("Vindicate", "WB", "not_legal", "Sorcery"),
]}

PDH_DECK = """// Name: Gio
// Format: paupercommander
// Bracket: 2

// Commander
1 Giovanni, Suporte Lateral
"""


class CustomPauperTest(Base):
    def setUp(self):
        super().setUp()
        self.deck.write_text(PDH_DECK)
        p = mock.patch.dict(CARDS, PDH_CARDS)
        p.start()
        self.addCleanup(p.stop)

    def test_init_skips_edhrec_for_a_custom_commander(self):
        with mock.patch.object(build.edhrec, "fetch") as fetch:
            code, out, err = self.run_cli(["init", str(self.deck)], PAGES)
            self.assertFalse(fetch.called)
        self.assertEqual(code, 0, err)
        st = self.state()
        self.assertEqual((st["format"], st["custom_commander"], st["identity"]),
                         ("paupercommander", True, "WB"))
        self.assertEqual(st["targets"], build.TEMPLATE)
        self.assertIn("custom commander", err)

    def test_pool_filters_by_the_deck_format(self):
        self.run_cli(["init", str(self.deck)])
        extra = self.dir / "extra.txt"
        extra.write_text("Tithe Drinker\nVindicate\n")
        code, out, err = self.run_cli(["pool", str(self.deck), "--extra", str(extra)])
        self.assertEqual(code, 0, err)
        self.assertEqual([c.name for c in self.boards()["maybeboard"]], ["Tithe Drinker"])
        self.assertRegex(out, r"not legal: Vindicate")
        self.assertNotIn("EDHREC has no commander page", err)


class FormatAndShortlistTest(CustomPauperTest):
    def test_pool_reads_the_format_from_the_deck_file(self):
        self.run_cli(["init", str(self.deck)])
        st = self.state()
        del st["format"]  # a build.json written before formats existed
        build.save_state(self.deck, st)
        self.deck.write_text(self.deck.read_text().replace("paupercommander", "Commander"))
        extra = self.dir / "extra.txt"
        extra.write_text("Tithe Drinker\nVindicate\n")
        self.run_cli(["pool", str(self.deck), "--extra", str(extra)])
        self.assertEqual(sorted(c.name for c in self.boards()["maybeboard"]),
                         ["Tithe Drinker", "Vindicate"])
        self.assertEqual(self.state()["format"], "commander")

    def test_moxfield_format_name_is_understood(self):
        self.deck.write_text(PDH_DECK.replace("paupercommander", "pauperEdh"))
        self.run_cli(["init", str(self.deck)])
        self.assertEqual(self.state()["format"], "paupercommander")

    def test_unranked_shortlist_is_not_cut(self):
        self.run_cli(["init", str(self.deck)])
        st = self.state()
        st["pool"] = {f"Card {i:02}": {"inclusion": None, "synergy": None, "sources": ["search"],
                                       "roles": [], "land": False, "gc": False, "cmc": 2}
                      for i in range(30)}
        build.save_state(self.deck, st)
        self.deck.write_text(self.deck.read_text() + "\n// Maybeboard\n"
                             + "".join(f"1 Card {i:02}\n" for i in range(30)))
        out = self.dir / "theme.json"
        code, text, _ = self.run_cli(["round", str(self.deck), "theme", "--out", str(out)])
        self.assertEqual(len(json.loads(out.read_text())), 30)
        code, text, _ = self.run_cli(["round", str(self.deck), "theme", "--out", str(out),
                                      "--limit", "5"])
        self.assertIn("first 5 of 30", text)


if __name__ == "__main__":
    unittest.main()
