import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import moxfield as mx  # noqa: E402


class ParseLine(unittest.TestCase):
    def t(self, line):
        return mx.parse_line(line, "mainboard")

    def test_full_bulk_syntax(self):
        c = self.t("1 Sol Ring (CMM) 410 *F* *A* #ramp #!staple")
        self.assertEqual((c.qty, c.name, c.set, c.cn, c.foil, c.alter), (1, "Sol Ring", "cmm", "410", True, True))
        self.assertEqual(c.tags, ["ramp"])
        self.assertEqual(c.gtags, ["staple"])

    def test_suffix_order_free(self):
        c = self.t("2x Sol Ring #ramp (CMM) *F* 410")
        self.assertEqual((c.qty, c.set, c.cn, c.foil, c.tags), (2, "cmm", "410", True, ["ramp"]))

    def test_the_list_collector_number(self):
        c = self.t("1 Command Beacon (PLST) C15-56")
        self.assertEqual((c.name, c.set, c.cn), ("Command Beacon", "plst", "C15-56"))

    def test_name_with_parens_kept(self):
        c = self.t("1 Who // What // When // Where // Why")
        self.assertEqual(c.name, "Who // What // When // Where // Why")
        c = self.t("1 Erase (Not the Urza's Legacy One)")
        self.assertEqual(c.name, "Erase (Not the Urza's Legacy One)")
        self.assertIsNone(c.set)

    def test_set_without_number(self):
        c = self.t("1 Lightning Bolt (STA)")
        self.assertEqual((c.name, c.set, c.cn), ("Lightning Bolt", "sta", None))

    def test_garbage(self):
        self.assertIsNone(self.t("About"))
        self.assertIsNone(self.t("Deck"))


class ParseDeck(unittest.TestCase):
    TEXT = """// Moxfield: https://moxfield.com/decks/abc
// Name: Test

// Commander
1 Olivia, Opulent Outlaw #cmd

// Mainboard
1 Sol Ring (CMM) 410
Sideboard
1 Swords to Plowshares
maybe:
1 Edgar Markov
"""

    def test_sections_and_meta(self):
        boards, meta = mx.parse_deck(self.TEXT)
        self.assertEqual(meta["name"], "Test")
        self.assertEqual(meta["moxfield"], "https://moxfield.com/decks/abc")
        self.assertEqual([c.name for c in boards["commanders"]], ["Olivia, Opulent Outlaw"])
        self.assertEqual([c.name for c in boards["mainboard"]], ["Sol Ring"])
        self.assertEqual([c.name for c in boards["sideboard"]], ["Swords to Plowshares"])
        self.assertEqual([c.name for c in boards["maybeboard"]], ["Edgar Markov"])
        self.assertNotIn("_warning", meta)

    def test_no_header_warns(self):
        boards, meta = mx.parse_deck("1 Sol Ring\n1 Swamp\n")
        self.assertIn("_warning", meta)
        self.assertEqual(len(boards["mainboard"]), 2)

    def test_portuguese_aliases(self):
        """Older deck files use Portuguese metadata keys and section headers."""
        text = ("// Nome: Velho\n// Formato: commander\n// Visibilidade: public\n\n"
                "// Comandante\n1 Olivia, Opulent Outlaw\n\n// Mainboard\n1 Sol Ring\n"
                "// Reserva\n1 Swords to Plowshares\n// Considerando\n1 Edgar Markov\n")
        boards, meta = mx.parse_deck(text)
        self.assertEqual((meta["name"], meta["format"], meta["visibility"]),
                         ("Velho", "commander", "public"))
        self.assertNotIn("nome", meta)
        self.assertEqual([c.name for c in boards["commanders"]], ["Olivia, Opulent Outlaw"])
        self.assertEqual([c.name for c in boards["sideboard"]], ["Swords to Plowshares"])
        self.assertEqual([c.name for c in boards["maybeboard"]], ["Edgar Markov"])
        rendered = mx.render_deck(boards, meta)
        self.assertIn("// Name: Velho", rendered)
        self.assertIn("// Format: commander", rendered)

    def test_roundtrip(self):
        boards, meta = mx.parse_deck(self.TEXT)
        text = mx.render_deck(boards, meta)
        boards2, meta2 = mx.parse_deck(text)
        self.assertEqual(mx.diff_boards(boards, boards2), [])
        self.assertEqual(meta2["name"], "Test")


class FromMoxfield(unittest.TestCase):
    DATA = {
        "publicUrl": "https://moxfield.com/decks/x", "name": "D", "format": "commander",
        "visibility": "public", "bracket": 3,
        "authorTags": {"Sol Ring": ["ramp"]},
        "boards": {
            "commanders": {"count": 1, "cards": {"a": {"quantity": 1, "isFoil": True, "finish": "foil",
                           "card": {"name": "Olivia, Opulent Outlaw", "set": "otj", "cn": "229"}}}},
            "mainboard": {"count": 2, "cards": {
                "b": {"quantity": 1, "isFoil": False, "card": {"name": "Sol Ring", "set": "cmm", "cn": "410"}},
                "c": {"quantity": 1, "isFoil": False, "card": {"name": "Swamp", "set": "otj", "cn": "275"}}}},
            "sideboard": {"count": 0, "cards": {}},
            "maybeboard": {"count": 0, "cards": {}},
            "attractions": {"count": 0, "cards": {}},
        },
    }

    def test_boards_tags_meta(self):
        boards, meta = mx.deck_from_moxfield(self.DATA)
        self.assertEqual(meta["bracket"], "3")
        cmd = boards["commanders"][0]
        self.assertTrue(cmd.foil)
        sol = next(c for c in boards["mainboard"] if c.name == "Sol Ring")
        self.assertEqual(sol.tags, ["ramp"])
        self.assertEqual(sol.render(), "1 Sol Ring (CMM) 410 #ramp")

    def test_public_id(self):
        for ref in ("j-0aJlxuOUm9FnKRvJcfZw",
                    "https://moxfield.com/decks/j-0aJlxuOUm9FnKRvJcfZw",
                    "https://www.moxfield.com/decks/j-0aJlxuOUm9FnKRvJcfZw/primer?x=1"):
            self.assertEqual(mx.public_id(ref), "j-0aJlxuOUm9FnKRvJcfZw")
        with self.assertRaises(SystemExit):
            mx.public_id("https://archidekt.com/decks/123")


class Diff(unittest.TestCase):
    def test_symbols(self):
        local, _ = mx.parse_deck("// Commander\n1 A\n// Mainboard\n1 B #x\n2 C\n")
        remote, _ = mx.parse_deck("// Commander\n1 A\n// Mainboard\n1 B\n1 C\n1 D\n")
        rows = mx.diff_boards(local, remote)
        self.assertEqual([(b, s) for b, s, _ in rows],
                         [("mainboard", "~"), ("mainboard", "~"), ("mainboard", "-")])
        self.assertIn("tags [] -> ['x']", rows[0][2])
        self.assertIn("qty 1 -> 2", rows[1][2])

    def test_printing_ignored(self):
        local, _ = mx.parse_deck("1 Sol Ring (CMM) 410 *F*\n")
        remote, _ = mx.parse_deck("1 Sol Ring (C21) 263\n")
        self.assertEqual(mx.diff_boards(local, remote), [])


def card(name, type_line="Creature", ci=(), text="", legal="legal", gc=False):
    return {"name": name, "type_line": type_line, "color_identity": list(ci),
            "oracle_text": text, "legalities": {"commander": legal}, "game_changer": gc}


class FakeScry:
    def __init__(self, db):
        self.db = db

    def resolve(self, names):
        return {n: self.db.get(n) for n in names}


class Validate(unittest.TestCase):
    def deck(self, cmds, main):
        boards = {b: [] for b in mx.BOARDS}
        boards["commanders"] = [mx.Card(1, n, "commanders") for n in cmds]
        boards["mainboard"] = [mx.Card(q, n, "mainboard") for q, n in main]
        return boards

    def run_validate(self, boards, db):
        out = io.StringIO()
        ok = mx.validate(boards, "commander", FakeScry(db), out=out)
        return ok, out.getvalue()

    def test_happy_path(self):
        db = {"Olivia": card("Olivia", "Legendary Creature — Vampire", "BRW"),
              "Swamp": card("Swamp", "Basic Land — Swamp"),
              "Sol Ring": card("Sol Ring", "Artifact", gc=False)}
        boards = self.deck(["Olivia"], [(98, "Swamp"), (1, "Sol Ring")])
        ok, out = self.run_validate(boards, db)
        self.assertTrue(ok, out)
        self.assertEqual(out.strip(), "ok")

    def test_errors(self):
        db = {"Olivia": card("Olivia", "Legendary Creature — Vampire", "BRW"),
              "Edgar": card("Edgar", "Legendary Creature — Vampire", "BRW"),
              "Counterspell": card("Counterspell", "Instant", "U"),
              "Sol Ring": card("Sol Ring", "Artifact"),
              "Mana Crypt": card("Mana Crypt", "Artifact", legal="banned", gc=True),
              "Swamp": card("Swamp", "Basic Land — Swamp")}
        boards = self.deck(["Olivia", "Edgar"],
                           [(1, "Counterspell"), (2, "Sol Ring"), (1, "Mana Crypt"), (94, "Swamp"), (1, "Typo")])
        ok, out = self.run_validate(boards, db)
        self.assertFalse(ok)
        for frag in ("without Partner or Background", "outside color identity BRW: Counterspell",
                     "duplicate (2x) not allowed: Sol Ring", "banned in commander: Mana Crypt",
                     "not found on Scryfall", "deck has 101 cards"):
            self.assertIn(frag, out)

    def test_partner_and_background_ok(self):
        db = {"A": card("A", "Legendary Creature", "W", text="Partner"),
              "B": card("B", "Legendary Creature", "R", text="Partner"),
              "Swamp": card("Swamp", "Basic Land — Swamp")}
        boards = self.deck(["A", "B"], [(98, "Swamp")])
        ok, out = self.run_validate(boards, db)
        self.assertNotIn("without Partner", out)
        db = {"C": card("C", "Legendary Creature", "W", text="Choose a Background"),
              "Bg": card("Bg", "Legendary Enchantment — Background", "R"),
              "Plains": card("Plains", "Basic Land — Plains")}
        boards = self.deck(["C", "Bg"], [(98, "Plains")])
        ok, out = self.run_validate(boards, db)
        self.assertNotIn("without Partner", out)

    def test_offline(self):
        boards = self.deck([], [(1, "Sol Ring")])
        out = io.StringIO()
        ok = mx.validate(boards, "commander", None, out=out)
        self.assertFalse(ok)
        self.assertIn("no commander", out.getvalue())


class ScryfallResolve(unittest.TestCase):
    def test_front_face_fallback(self):
        s = mx.Scryfall(delay=0)
        calls = []

        def fake_post(ids):
            calls.append([i["name"] for i in ids])
            names = [i["name"] for i in ids]
            data = []
            if "Delver of Secrets" in names:
                data.append({"name": "Delver of Secrets // Insectile Aberration"})
            if "Sol Ring" in names:
                data.append({"name": "Sol Ring"})
            return {"data": data, "not_found": []}

        s._post = fake_post
        s._named_fuzzy = lambda n: None
        r = s.resolve(["Sol Ring", "Delver of Secrets // Insectile Aberration"])
        self.assertEqual(r["Sol Ring"]["name"], "Sol Ring")
        self.assertEqual(r["Delver of Secrets // Insectile Aberration"]["name"],
                         "Delver of Secrets // Insectile Aberration")
        self.assertEqual(calls[1], ["Delver of Secrets"])


class ReadCardList(unittest.TestCase):
    def write(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_deck_boards_only_with_printings_and_tags_stripped(self):
        path = self.write("// Moxfield: https://moxfield.com/decks/x\n// Nome: T\n\n"
                          "// Commander\n1 Saruman, the White Hand (LTC) 8 #cmd\n\n"
                          "// Mainboard\n1 Sol Ring (CMM) 410 *F* #ramp\n"
                          "1 Delver of Secrets // Insectile Aberration\n8 Island\n\n"
                          "// Maybeboard\n1 Rhystic Study\n")
        self.assertEqual(mx.read_card_list(path), [
            (1, "Saruman, the White Hand"), (1, "Sol Ring"),
            (1, "Delver of Secrets // Insectile Aberration"), (8, "Island")])

    def test_all_boards_on_request(self):
        path = self.write("// Mainboard\n1 Sol Ring\n// Maybeboard\n1 Rhystic Study\n")
        self.assertEqual([n for _, n in mx.read_card_list(path, mx.BOARDS)],
                         ["Sol Ring", "Rhystic Study"])

    def test_bare_names_count_one_and_repeats_merge(self):
        path = self.write("Sol Ring\nBlood Artist\n\n2 Swamp\nsol ring\n")
        self.assertEqual(mx.read_card_list(path), [(2, "Sol Ring"), (1, "Blood Artist"),
                                                   (2, "Swamp")])



class PauperCommander(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"MTG_CUSTOM_CARDS": os.path.join(self.tmp.name, "c.json")})
        env.start()
        self.addCleanup(env.stop)
        mx.scryfall._custom_cache.clear()
        self.addCleanup(mx.scryfall._custom_cache.clear)

    def pdh(self, name, type_line="Creature", ci=(), legal="legal"):
        c = card(name, type_line, ci)
        c["legalities"] = {"commander": "legal", "paupercommander": legal}
        return c

    def run_validate(self, cmds, main, db, pdh_ok=()):
        scry = FakeScry(db)
        scry.pdh_commander = lambda name: name in pdh_ok
        boards = {b: [] for b in mx.BOARDS}
        boards["commanders"] = [mx.Card(1, n, "commanders") for n in cmds]
        boards["mainboard"] = [mx.Card(q, n, "mainboard") for q, n in main]
        out = io.StringIO()
        return mx.validate(boards, "paupercommander", scry, out=out), out.getvalue()

    def test_uncommon_commander_and_commons_pass(self):
        db = {"Tithe Drinker": self.pdh("Tithe Drinker", ci="WB", legal="not_legal"),
              "Swamp": self.pdh("Swamp", "Basic Land — Swamp")}
        ok, out = self.run_validate(["Tithe Drinker"], [(99, "Swamp")], db, {"Tithe Drinker"})
        self.assertTrue(ok, out)

    def test_structure_identity_and_legality_are_checked(self):
        db = {"Sol Ring": self.pdh("Sol Ring", "Artifact", legal="not_legal"),
              "Counterspell": self.pdh("Counterspell", "Instant", "U"),
              "Rare Guy": self.pdh("Rare Guy", "Legendary Creature", "B", legal="not_legal")}
        ok, out = self.run_validate(["Rare Guy"], [(1, "Sol Ring"), (1, "Counterspell")], db)
        self.assertFalse(ok)
        for frag in ("cannot lead a Pauper Commander deck", "deck has 3 cards",
                     "not_legal in paupercommander: Sol Ring",
                     "outside color identity B: Counterspell"):
            self.assertIn(frag, out)

    def test_custom_commander_is_trusted_with_a_warning(self):
        gio = mx.scryfall.custom_card({"name": "Giovanni", "mana_cost": "{1}{W}{B}",
                                       "type_line": "Legendary Creature — Human"})
        db = {"Giovanni": gio, "Swamp": self.pdh("Swamp", "Basic Land — Swamp"),
              "Counterspell": self.pdh("Counterspell", "Instant", "U")}
        ok, out = self.run_validate(["Giovanni"], [(98, "Swamp"), (1, "Counterspell")], db)
        self.assertFalse(ok)
        self.assertIn("outside color identity BW: Counterspell", out)
        self.assertIn("custom cards, legality and commander eligibility not checked: Giovanni", out)
        self.assertNotIn("cannot lead", out)

    def test_resolve_uses_custom_file_before_the_api(self):
        with open(os.environ["MTG_CUSTOM_CARDS"], "w", encoding="utf-8") as fh:
            json.dump([{"name": "Giovanni", "type_line": "Legendary Creature"}], fh)
        scry = mx.Scryfall(delay=0)
        with mock.patch.object(scry, "_post", return_value={"data": []}) as post, \
                mock.patch.object(scry, "_named_fuzzy", return_value=None):
            got = scry.resolve(["Giovanni", "Nope"])
        self.assertTrue(got["Giovanni"]["custom"])
        self.assertIsNone(got["Nope"])
        self.assertEqual(post.call_args[0][0], [{"name": "Nope"}])

if __name__ == "__main__":
    unittest.main()
