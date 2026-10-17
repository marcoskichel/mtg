"""Tests for finder.py with simulated tags and HTTP. Run: python3 -m unittest discover -s tests"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finder  # noqa: E402

scryfall = finder.scryfall


def tag(tid, slug, oracle_ids=(), parents=(), children=(), aliases=(), desc=None):
    return {"object": "tag", "id": tid, "slug": slug, "label": slug.replace("-", " "),
            "type": "oracle", "description": desc, "aliases": list(aliases),
            "parent_ids": list(parents), "child_ids": list(children),
            "taggings": [{"oracle_id": o, "weight": "median"} for o in oracle_ids]}


TAGS = [
    tag("r", "removal", children=["s", "sp"], desc="Get things off the table."),
    tag("s", "sweeper", ["o-wrath", "o-acid"], parents=["r"], children=["s1"],
        aliases=["wrath of god", "mass removal", "wipe", "boardwipe"],
        desc="Destroy all the things! See also [spot removal](spot-removal)."),
    tag("s1", "sweeper-one-sided", ["o-plague"], parents=["s"]),
    tag("sp", "spot-removal", ["o-bolt"], parents=["r"]),
    tag("d", "draw", ["o-div"], desc="Spells that draw cards."),
    tag("rd", "repeatable-draw", ["o-rhystic"]),
]


def card(name, oracle_id, text, **kw):
    base = {"object": "card", "name": name, "oracle_id": oracle_id, "layout": "normal",
            "mana_cost": "{2}{W}{W}", "cmc": 4.0, "type_line": "Sorcery",
            "oracle_text": text, "color_identity": ["W"],
            "legalities": {"commander": "legal"}, "set": "m10", "collector_number": "1"}
    base.update(kw)
    return base


WRATH = card("Wrath of God", "o-wrath", "Destroy all creatures. They can't be regenerated.")
PLAGUE = card("Plague Wind", "o-plague", "Destroy all creatures you don't control.")


class FakeHTTP:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, body=None, retries=3):
        self.calls.append((method, url))
        for key, resp in self.routes:
            if key in url:
                return resp
        raise AssertionError(f"route not simulated: {method} {url}")


def run(argv, routes=(), tags=TAGS):
    fake = FakeHTTP(list(routes))
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(finder, "load_tags", lambda refresh=False: tags), \
            mock.patch.object(scryfall, "_http", fake), \
            mock.patch.object(scryfall.time, "sleep"), \
            redirect_stdout(out), redirect_stderr(err):
        code = finder.main(argv)
    return code, out.getvalue(), err.getvalue(), fake.calls


def page(cards, total=None, warnings=None):
    d = {"object": "list", "data": cards, "has_more": False,
         "total_cards": len(cards) if total is None else total}
    if warnings:
        d["warnings"] = warnings
    return d


class Norm(unittest.TestCase):
    def test_scryfall_equivalences(self):
        self.assertEqual(finder.norm("board-wipe"), finder.norm("boardwipe"))
        self.assertEqual(finder.norm("Mass Removal"), finder.norm("mass_removal"))

    def test_query_tags(self):
        q = 'otag:sweeper -function:"mass removal" (oracletag:draw or c:u) o:"otag:no"'
        self.assertEqual(finder.query_tags(q)[:3],
                         [("sweeper", False), ("mass removal", True), ("draw", False)])

    def test_query_tags_ignores_other_keywords(self):
        self.assertEqual(finder.query_tags("art:dragon t:creature id<=wb"), [])


class Index(unittest.TestCase):
    def setUp(self):
        self.idx = finder.TagIndex(TAGS)

    def test_alias_resolves_to_slug(self):
        self.assertEqual(self.idx.resolve("board-wipe")["slug"], "sweeper")
        self.assertEqual(self.idx.resolve("Wrath of God")["slug"], "sweeper")
        self.assertIsNone(self.idx.resolve("card-draw"))

    def test_parent_counts_children(self):
        """removal has no direct taggings; otag:removal still matches its tree."""
        self.assertEqual(self.idx.cards(self.idx.resolve("removal")),
                         {"o-wrath", "o-acid", "o-plague", "o-bolt"})

    def test_search_ranks_exact_alias_first(self):
        ranked = self.idx.search("wipe")
        self.assertEqual(ranked[0][2]["slug"], "sweeper")

    def test_search_reaches_description(self):
        slugs = [t["slug"] for _, _, t in self.idx.search("off the table")]
        self.assertEqual(slugs, ["removal"])


class FindCmd(unittest.TestCase):
    def test_unknown_tag_stops_before_search(self):
        code, out, err, calls = run(["find", "otag:card-draw c:u"])
        self.assertEqual(code, 2)
        self.assertIn("UNKNOWN TAG: card-draw", err)
        self.assertIn("draw", err)          # suggestion
        self.assertEqual(calls, [])         # Scryfall never called

    def test_prints_oracle_text_and_matched_tag(self):
        code, out, err, calls = run(
            ["find", "otag:wipe id<=w"],
            [("/cards/search", page([WRATH, PLAGUE], total=40))])
        self.assertEqual(code, 0)
        self.assertIn("Destroy all creatures. They can't be regenerated.", out)
        self.assertIn("Destroy all creatures you don't control.", out)
        self.assertIn("tagged: sweeper-one-sided", out)
        self.assertIn("40 card(s) in total, 2 shown", err)
        self.assertIn("order=edhrec", calls[0][1])

    def test_negated_tag_validated_but_not_reported(self):
        code, out, err, calls = run(
            ["find", "otag:sweeper -otag:sweeper-one-sided"],
            [("/cards/search", page([WRATH]))])
        self.assertEqual(code, 0)
        self.assertIn("tagged: sweeper\n", out)

    def test_scryfall_warning_fails(self):
        code, out, err, calls = run(
            ["find", "otag:sweeper tipo:creature"],
            [("/cards/search", page([WRATH], warnings=["Unknown keyword “tipo”."]))])
        self.assertEqual(code, 1)
        self.assertIn("SCRYFALL WARNING", err)

    def test_no_results(self):
        code, out, err, calls = run(
            ["find", "otag:sweeper c:g mv=0"],
            [("/cards/search", {"object": "error", "code": "not_found", "status": 404,
                                "details": "Your query didn't match any cards."})])
        self.assertEqual(code, 1)
        self.assertIn("no cards for the query", err)

    def test_tag_load_failure_still_searches(self):
        def boom(refresh=False):
            raise OSError("offline")
        out, err = io.StringIO(), io.StringIO()
        fake = FakeHTTP([("/cards/search", page([WRATH]))])
        with mock.patch.object(finder, "load_tags", boom), \
                mock.patch.object(scryfall, "_http", fake), \
                mock.patch.object(scryfall.time, "sleep"), \
                redirect_stdout(out), redirect_stderr(err):
            code = finder.main(["find", "otag:sweeper"])
        self.assertEqual(code, 0)
        self.assertIn("NOT validated", err.getvalue())
        self.assertIn("Wrath of God", out.getvalue())

    def test_json(self):
        code, out, err, calls = run(
            ["find", "otag:sweeper", "--json"],
            [("/cards/search", page([PLAGUE]))])
        data = json.loads(out)
        self.assertEqual(data["cards"][0]["matched_tags"], ["sweeper-one-sided"])


class TagCmds(unittest.TestCase):
    def test_tags_lists_hierarchy(self):
        code, out, err, _ = run(["tags", "removal"])
        self.assertEqual(code, 0)
        self.assertIn("removal  (4 cards)", out)
        self.assertIn("children (2): sweeper, spot-removal", out)

    def test_tags_cleans_markdown_links(self):
        code, out, err, _ = run(["tags", "sweeper"])
        self.assertIn("See also spot removal.", out)

    def test_tag_alias_and_tree(self):
        code, out, err, _ = run(["tag", "board-wipe"])
        self.assertEqual(code, 0)
        self.assertIn("alias of sweeper", err)
        self.assertIn("└ sweeper-one-sided", out)

    def test_tag_unknown(self):
        code, out, err, _ = run(["tag", "nope-nope"])
        self.assertEqual(code, 1)
        self.assertIn("UNKNOWN TAG", err)


ROLE_TAGS = [
    tag("ramp", "ramp", children=["mr"]),
    tag("mr", "mana-rock", ["o-sol"], parents=["ramp"]),
    tag("cr", "cost-reducer"),
    tag("dr", "draw", ["o-div"]),
    tag("ca", "card-advantage"),
    tag("rm", "removal", children=["rc"]),
    tag("rc", "removal-creature", ["o-bolt"], parents=["rm"]),
    tag("sw", "sweeper", ["o-wrath"]),
    tag("cs", "counterspell"),
    tag("pr", "protection"),
    tag("tu", "tutor"),
    tag("so", "sacrifice-outlet", ["o-altar"]),
    tag("rec", "recursion"),
]


class RolesTest(unittest.TestCase):
    def setUp(self):
        self.idx = finder.TagIndex(ROLE_TAGS)

    def test_role_list_is_exact(self):
        self.assertEqual(finder.ROLES, (
            "ramp", "mana-rock", "cost-reducer", "draw", "card-advantage", "removal",
            "sweeper", "counterspell", "protection", "tutor", "sacrifice-outlet",
            "recursion"))

    def test_all_roles_present_in_fixture(self):
        self.assertEqual(finder.missing_roles(self.idx), [])

    def test_missing_role_reported(self):
        idx = finder.TagIndex([t for t in ROLE_TAGS if t["slug"] != "tutor"])
        self.assertEqual(finder.missing_roles(idx), ["tutor"])

    def test_parent_role_counts_descendants(self):
        cards = [card("Sol Ring", "o-sol", "{T}: Add {C}{C}."),
                 card("Lightning Bolt", "o-bolt", "Deal 3 damage to any target.")]
        roles = finder.card_roles(self.idx, cards)
        self.assertEqual(roles["Sol Ring"], ["ramp", "mana-rock"])
        self.assertEqual(roles["Lightning Bolt"], ["removal"])

    def test_untagged_card_gets_empty_list(self):
        roles = finder.card_roles(self.idx, [card("Grizzly Bears", "o-bears", "")])
        self.assertEqual(roles["Grizzly Bears"], [])


class RolesCliTest(unittest.TestCase):
    def run_cli(self, argv, found):
        def fake_resolve(names, report):
            wanted = {scryfall.fold(scryfall.front_face(n)): n for n in names}
            for k, n in wanted.items():
                if k not in found:
                    report.missing[n] = ""
            return {k: v for k, v in found.items() if k in wanted}, wanted

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(finder, "load_tags", return_value=ROLE_TAGS), \
             mock.patch.object(scryfall, "resolve_names", side_effect=fake_resolve), \
             redirect_stdout(out), redirect_stderr(err):
            code = finder.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_names(self):
        found = {"sol ring": card("Sol Ring", "o-sol", "")}
        code, out, _ = self.run_cli(["roles", "Sol Ring"], found)
        self.assertEqual(code, 0)
        self.assertIn("Sol Ring: ramp, mana-rock", out)

    def test_untagged_says_so(self):
        found = {"grizzly bears": card("Grizzly Bears", "o-bears", "")}
        code, out, _ = self.run_cli(["roles", "Grizzly Bears"], found)
        self.assertIn("Grizzly Bears: (no roles tagged)", out)

    def test_dfc_resolves_front_face(self):
        found = {"delver of secrets": card("Delver of Secrets // Insectile Aberration",
                                           "o-div", "")}
        code, out, _ = self.run_cli(["roles", "Delver of Secrets // Insectile Aberration"],
                                    found)
        self.assertEqual(code, 0)
        self.assertIn("Delver of Secrets // Insectile Aberration: draw", out)

    def test_deck_file_counts_and_tags_stripped(self):
        text = ("// Commander\n1 Saruman, the White Hand (LTC) 8 #cmd\n\n"
                "// Mainboard\n1 Sol Ring (CMM) 410 #ramp\n1 Lightning Bolt\n")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
        self.addCleanup(Path(f.name).unlink)
        found = {"sol ring": card("Sol Ring", "o-sol", ""),
                 "lightning bolt": card("Lightning Bolt", "o-bolt", ""),
                 "saruman, the white hand": card("Saruman, the White Hand", "o-sar", "")}
        code, out, _ = self.run_cli(["roles", "-d", f.name], found)
        self.assertEqual(code, 0)
        self.assertIn("ramp: 1", out)
        self.assertIn("removal: 1", out)
        self.assertNotIn("#ramp", out)

    def test_json(self):
        found = {"sol ring": card("Sol Ring", "o-sol", "")}
        code, out, _ = self.run_cli(["roles", "Sol Ring", "--json"], found)
        self.assertEqual(json.loads(out)["cards"]["Sol Ring"], ["ramp", "mana-rock"])


if __name__ == "__main__":
    unittest.main()
