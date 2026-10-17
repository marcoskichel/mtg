import io
import json
import os
import sys
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
// Nome: Teste

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
        self.assertEqual(meta["nome"], "Teste")
        self.assertEqual(meta["moxfield"], "https://moxfield.com/decks/abc")
        self.assertEqual([c.name for c in boards["commanders"]], ["Olivia, Opulent Outlaw"])
        self.assertEqual([c.name for c in boards["mainboard"]], ["Sol Ring"])
        self.assertEqual([c.name for c in boards["sideboard"]], ["Swords to Plowshares"])
        self.assertEqual([c.name for c in boards["maybeboard"]], ["Edgar Markov"])
        self.assertNotIn("_aviso", meta)

    def test_no_header_warns(self):
        boards, meta = mx.parse_deck("1 Sol Ring\n1 Swamp\n")
        self.assertIn("_aviso", meta)
        self.assertEqual(len(boards["mainboard"]), 2)

    def test_roundtrip(self):
        boards, meta = mx.parse_deck(self.TEXT)
        text = mx.render_deck(boards, meta)
        boards2, meta2 = mx.parse_deck(text)
        self.assertEqual(mx.diff_boards(boards, boards2), [])
        self.assertEqual(meta2["nome"], "Teste")


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
        for frag in ("sem Partner", "fora da identidade de cor BRW: Counterspell",
                     "repetida (2x) sem permissao: Sol Ring", "banned em commander: Mana Crypt",
                     "nao encontrado na Scryfall", "deck tem 101 cartas"):
            self.assertIn(frag, out)

    def test_partner_and_background_ok(self):
        db = {"A": card("A", "Legendary Creature", "W", text="Partner"),
              "B": card("B", "Legendary Creature", "R", text="Partner"),
              "Swamp": card("Swamp", "Basic Land — Swamp")}
        boards = self.deck(["A", "B"], [(98, "Swamp")])
        ok, out = self.run_validate(boards, db)
        self.assertNotIn("sem Partner", out)
        db = {"C": card("C", "Legendary Creature", "W", text="Choose a Background"),
              "Bg": card("Bg", "Legendary Enchantment — Background", "R"),
              "Plains": card("Plains", "Basic Land — Plains")}
        boards = self.deck(["C", "Bg"], [(98, "Plains")])
        ok, out = self.run_validate(boards, db)
        self.assertNotIn("sem Partner", out)

    def test_offline(self):
        boards = self.deck([], [(1, "Sol Ring")])
        out = io.StringIO()
        ok = mx.validate(boards, "commander", None, out=out)
        self.assertFalse(ok)
        self.assertIn("sem comandante", out.getvalue())


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


if __name__ == "__main__":
    unittest.main()
