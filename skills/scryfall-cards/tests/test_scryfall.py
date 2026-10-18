"""Tests for scryfall.py with simulated HTTP. Run: python3 -m unittest discover -s tests"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scryfall  # noqa: E402


def card(name, **kw):
    base = {
        "object": "card", "name": name, "layout": "normal", "lang": "en",
        "mana_cost": "{R}", "cmc": 1.0, "type_line": "Instant",
        "oracle_text": f"{name} deals 3 damage to any target.",
        "colors": ["R"], "color_identity": ["R"], "keywords": [],
        "legalities": {"commander": "legal", "modern": "legal", "standard": "not_legal"},
        "set": "m11", "set_name": "Magic 2011", "collector_number": "149",
        "rarity": "common", "released_at": "2010-07-16",
        "prices": {"usd": "1.00", "usd_foil": "5.00", "eur": "0.90", "tix": "0.01"},
        "finishes": ["nonfoil", "foil"], "promo": False, "digital": False,
        "image_uris": {"normal": f"https://img/{name}.jpg"},
        "rulings_uri": f"https://api.scryfall.com/cards/{name}/rulings",
        "prints_search_uri": f"https://api.scryfall.com/cards/search?q=oracleid:{name}&unique=prints",
        "scryfall_uri": f"https://scryfall.com/{name}",
    }
    base.update(kw)
    return base


DELVER = card(
    "Delver of Secrets // Insectile Aberration", layout="transform",
    mana_cost=None, oracle_text=None, type_line="Creature — Human Wizard // Creature — Human Insect",
    card_faces=[
        {"name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature — Human Wizard",
         "oracle_text": "At the beginning of your upkeep, look at the top card.",
         "power": "1", "toughness": "1", "image_uris": {"normal": "https://img/front.jpg"}},
        {"name": "Insectile Aberration", "mana_cost": "", "type_line": "Creature — Human Insect",
         "oracle_text": "Flying", "power": "3", "toughness": "2",
         "image_uris": {"normal": "https://img/back.jpg"}},
    ],
    image_uris=None,
)


class FakeHTTP:
    """Routes calls by (method, URL fragment). Keeps the call history."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, body=None):
        self.calls.append((method, url, body))
        for key, resp in self.routes:
            if key in url:
                return resp(body) if callable(resp) else resp
        raise AssertionError(f"route not simulated: {method} {url}")


def run(argv, routes):
    fake = FakeHTTP(routes)
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(scryfall, "_http", fake), \
            mock.patch.object(scryfall.time, "sleep"), \
            redirect_stdout(out), redirect_stderr(err):
        code = scryfall.main(argv)
    return code, out.getvalue(), err.getvalue(), fake.calls


def collection(found, not_found=()):
    def handler(body):
        return {"object": "list", "data": found,
                "not_found": [{"name": n} for n in not_found]}
    return handler


class ParseDeck(unittest.TestCase):
    def test_sections_and_formats(self):
        text = "Commander\n1 Edgar Markov\n\nDeck\n2x Lightning Bolt (M11) 149\nSB: 1 Fire // Ice\n"
        secs = scryfall.parse_input(text)
        self.assertEqual([e.name for e in secs["commander"]], ["Edgar Markov"])
        self.assertEqual([(e.qty, e.name) for e in secs["main"]], [(2, "Lightning Bolt")])
        self.assertEqual([e.name for e in secs["side"]], ["Fire // Ice"])

    def test_front_face(self):
        self.assertEqual(scryfall.front_face("Delver of Secrets // Insectile Aberration"),
                         "Delver of Secrets")
        self.assertEqual(scryfall.front_face("Fire // Ice"), "Fire")


class CardCmd(unittest.TestCase):
    def test_dfc_prints_both_faces(self):
        code, out, err, calls = run(
            ["card", "Delver of Secrets"],
            [("/cards/collection", collection([DELVER]))])
        self.assertEqual(code, 0)
        self.assertIn("Delver of Secrets", out)
        self.assertIn("Insectile Aberration", out)
        self.assertIn("Flying", out)
        self.assertIn("1/1", out)
        self.assertIn("3/2", out)
        # face text comes from the face, not the top level (which is null)
        self.assertNotIn("None", out)

    def test_dfc_full_name_sent_as_front_face(self):
        code, out, err, calls = run(
            ["card", "Delver of Secrets // Insectile Aberration"],
            [("/cards/collection", collection([DELVER]))])
        self.assertEqual(code, 0)
        body = json.loads(calls[0][2])
        self.assertEqual(body["identifiers"], [{"name": "Delver of Secrets"}])

    def test_fallback_pt_exact_before_fuzzy(self):
        """Not found in collection -> exact lang:pt search -> fuzzy, in that order."""
        code, out, err, calls = run(
            ["card", "Raio"],
            [("/cards/collection", collection([], ["Raio"])),
             ("/cards/search", {"object": "list", "data": [card("Lightning Bolt", lang="pt", printed_name="Raio")],
                                "has_more": False, "total_cards": 1})])
        self.assertEqual(code, 0)
        self.assertIn("Lightning Bolt", out)
        self.assertIn("Raio", err)         # rename report
        kinds = [c[1].split("?")[0].rsplit("/", 1)[-1] for c in calls]
        self.assertEqual(kinds, ["collection", "search"])
        self.assertIn('q=%21%22Raio%22+lang%3Apt', calls[1][1])   # exact, not substring

    def test_fuzzy_accepts_typo(self):
        code, out, err, calls = run(
            ["card", "Lightnig Bolt"],
            [("/cards/collection", collection([], ["Lightnig Bolt"])),
             ("/cards/search", {"object": "error", "code": "not_found", "status": 404}),
             ("/cards/named?fuzzy=", card("Lightning Bolt"))])
        self.assertEqual(code, 0)
        self.assertIn("Lightning Bolt", out)
        self.assertIn("fuzzy", err)

    def test_fuzzy_rejects_unrelated_card(self):
        """Scryfall returns 'Samurai of the Pale Curtain' for 'Raio'. Do not accept."""
        code, out, err, calls = run(
            ["card", "Raio"],
            [("/cards/collection", collection([], ["Raio"])),
             ("/cards/search", {"object": "error", "code": "not_found", "status": 404}),
             ("/cards/named?fuzzy=", card("Samurai of the Pale Curtain"))])
        self.assertEqual(code, 1)
        self.assertNotIn("Samurai", out)
        self.assertIn("NOT FOUND", err)
        self.assertIn("rejected", err)

    def test_unresolved_exit_1_with_suggestions(self):
        code, out, err, calls = run(
            ["card", "Lightnig Bol"],
            [("/cards/collection", collection([], ["Lightnig Bol"])),
             ("/cards/search", {"object": "error", "code": "not_found", "status": 404}),
             ("/cards/named?fuzzy=", {"object": "error", "code": "not_found", "status": 404,
                                      "details": "No cards found matching “Lightnig Bol”"})])
        self.assertEqual(code, 1)
        self.assertIn("NOT FOUND", err)
        self.assertIn("Lightnig Bol", err)

    def test_formats_and_rulings(self):
        bolt = card("Lightning Bolt")
        code, out, err, calls = run(
            ["card", "Lightning Bolt", "--formats", "modern,standard", "--rulings"],
            [("/cards/collection", collection([bolt])),
             ("/rulings", {"object": "list", "data": [
                 {"published_at": "2020-01-01", "comment": "Bolt the bird."}]})])
        self.assertEqual(code, 0)
        self.assertIn("modern", out)
        self.assertIn("standard", out)
        self.assertIn("Bolt the bird.", out)
        self.assertIn("2020-01-01", out)

    def test_deck_from_stdin_batches_75(self):
        names = [f"Card {i}" for i in range(80)]
        text = "\n".join(f"1 {n}" for n in names)
        found = [card(n) for n in names]
        with mock.patch.object(sys, "stdin", io.StringIO(text)):
            code, out, err, calls = run(
                ["card", "-d", "-", "--json"],
                [("/cards/collection", collection(found))])
        self.assertEqual(code, 0)
        posts = [c for c in calls if "/cards/collection" in c[1]]
        self.assertEqual(len(posts), 2)
        self.assertEqual(len(json.loads(posts[0][2])["identifiers"]), 75)
        data = json.loads(out)
        self.assertEqual(len(data["cards"]), 80)
        self.assertEqual(data["cards"][0]["name"], "Card 0")

    def test_json_trimmed(self):
        code, out, err, calls = run(
            ["card", "Lightning Bolt", "--json"],
            [("/cards/collection", collection([card("Lightning Bolt", multiverse_ids=[1], foo="bar")]))])
        data = json.loads(out)
        c = data["cards"][0]
        self.assertIn("oracle_text", c)
        self.assertIn("legalities", c)
        self.assertNotIn("foo", c)
        self.assertNotIn("multiverse_ids", c)


class Search(unittest.TestCase):
    def test_warnings_go_to_stderr_and_exit_1(self):
        code, out, err, calls = run(
            ["search", "c:r badkey:zz"],
            [("/cards/search", {"object": "list", "total_cards": 7079, "has_more": False,
                                "warnings": ["Invalid expression “badkey:zz” was ignored."],
                                "data": [card("Aardwolf's Advantage")]})])
        self.assertEqual(code, 1)
        self.assertIn("SCRYFALL WARNING", err)
        self.assertIn("badkey:zz", err)
        self.assertIn("Aardwolf's Advantage", out)

    def test_no_match_404(self):
        code, out, err, calls = run(
            ["search", "name:zzzzqqq"],
            [("/cards/search", {"object": "error", "code": "not_found", "status": 404,
                                "details": "Your query didn’t match any cards."})])
        self.assertEqual(code, 1)
        self.assertIn("no cards", err.lower())

    def test_limit_stops_pagination(self):
        page1 = {"object": "list", "total_cards": 350, "has_more": True,
                 "next_page": "https://api.scryfall.com/cards/search?page=2&q=x",
                 "data": [card(f"A{i}") for i in range(175)]}
        code, out, err, calls = run(
            ["search", "x", "--limit", "20"],
            [("/cards/search", page1)])
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in calls if "/cards/search" in c[1]]), 1)
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("A")), 20)
        self.assertIn("350", err)   # total reported

    def test_all_follows_next_page(self):
        page1 = {"object": "list", "total_cards": 180, "has_more": True,
                 "next_page": "https://api.scryfall.com/cards/search?page=2&q=x",
                 "data": [card(f"A{i}") for i in range(175)]}
        page2 = {"object": "list", "total_cards": 180, "has_more": False,
                 "data": [card(f"B{i}") for i in range(5)]}
        code, out, err, calls = run(
            ["search", "x", "--all"],
            [("page=2", page2), ("/cards/search", page1)])
        self.assertEqual(code, 0)
        self.assertEqual(len([c for c in calls if "/cards/search" in c[1]]), 2)
        self.assertIn("B4", out)

    def test_query_and_order_in_url(self):
        code, out, err, calls = run(
            ["search", "c:r t:creature", "--order", "cmc", "--unique", "prints"],
            [("/cards/search", {"object": "list", "total_cards": 1, "has_more": False,
                                "data": [card("X")]})])
        url = calls[0][1]
        self.assertIn("q=c%3Ar+t%3Acreature", url)
        self.assertIn("order=cmc", url)
        self.assertIn("unique=prints", url)


class Printings(unittest.TestCase):
    def test_filters_and_image(self):
        prints = {"object": "list", "total_cards": 3, "has_more": False, "data": [
            card("Lightning Bolt", set="m11", digital=False, promo=False),
            card("Lightning Bolt", set="pm11", digital=False, promo=True),
            card("Lightning Bolt", set="prm", digital=True, promo=False),
        ]}
        code, out, err, calls = run(
            ["printings", "lightning bolt", "--no-digital", "--no-promo", "--image"],
            [("/cards/named?fuzzy=", card("Lightning Bolt")),
             ("unique=prints", prints)])
        self.assertEqual(code, 0)
        self.assertIn("m11", out)
        self.assertNotIn("pm11", out)
        self.assertNotIn("prm", out)
        self.assertIn("https://img/Lightning Bolt.jpg", out)

    def test_dfc_images_per_face(self):
        prints = {"object": "list", "total_cards": 1, "has_more": False, "data": [DELVER]}
        code, out, err, calls = run(
            ["printings", "delver", "--image"],
            [("/cards/named?fuzzy=", DELVER), ("unique=prints", prints)])
        self.assertIn("https://img/front.jpg", out)
        self.assertIn("https://img/back.jpg", out)

    def test_ambiguous_name(self):
        code, out, err, calls = run(
            ["printings", "bolt"],
            [("/cards/named?fuzzy=", {"object": "error", "code": "not_found", "type": "ambiguous",
                                      "details": "Too many cards match ambiguous name “bolt”."})])
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", err.lower())


class Rulings(unittest.TestCase):
    def test_lists_rulings(self):
        code, out, err, calls = run(
            ["rulings", "Brash Taunter"],
            [("/cards/named?fuzzy=", card("Brash Taunter")),
             ("/rulings", {"object": "list", "data": [
                 {"published_at": "2020-06-23", "comment": "Damage greater than toughness."}]})])
        self.assertEqual(code, 0)
        self.assertIn("2020-06-23", out)
        self.assertIn("Damage greater", out)

    def test_no_rulings(self):
        code, out, err, calls = run(
            ["rulings", "Sol Ring"],
            [("/cards/named?fuzzy=", card("Sol Ring")),
             ("/rulings", {"object": "list", "data": []})])
        self.assertEqual(code, 0)
        self.assertIn("no rulings", out.lower())


class Retry(unittest.TestCase):
    def test_429_honors_retry_after(self):
        import urllib.error
        attempts = []

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen2(req, timeout=0):
            attempts.append(req.full_url)
            if len(attempts) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {"Retry-After": "3"}, io.BytesIO(b"{}"))
            return Resp(json.dumps({"object": "card", "name": "X"}).encode())

        with mock.patch.object(scryfall.urllib.request, "urlopen", fake_urlopen2), \
                mock.patch.object(scryfall.time, "sleep") as sleep, \
                redirect_stderr(io.StringIO()):
            data = scryfall._http("GET", "https://api.scryfall.com/cards/named?exact=X")
        self.assertEqual(data["name"], "X")
        self.assertEqual(len(attempts), 2)
        self.assertIn(mock.call(3.0), sleep.call_args_list)

    def test_user_agent_set(self):
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req, timeout=0):
            seen.update(req.headers)
            return Resp(b'{"object":"card"}')

        with mock.patch.object(scryfall.urllib.request, "urlopen", fake_urlopen):
            scryfall._http("GET", "https://api.scryfall.com/cards/named?exact=X")
        self.assertTrue(any(k.lower() == "user-agent" for k in seen))
        self.assertTrue(any(k.lower() == "accept" for k in seen))


GIOVANNI = {
    "name": "Giovanni, Suporte Lateral", "mana_cost": "{1}{W}{B}",
    "type_line": "Legendary Creature — Human Advisor", "power": "1", "toughness": "3",
    "oracle_text": "{1}{W/B}, {T}: Choose one —\n• Another target creature gains vigilance.",
    "image": "giovanni.png",
}


class CustomCards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "custom.json"
        env = mock.patch.dict(os.environ, {scryfall.CUSTOM_ENV: str(self.file)})
        env.start()
        self.addCleanup(env.stop)
        scryfall._custom_cache.clear()
        self.addCleanup(scryfall._custom_cache.clear)

    def write(self, data):
        self.file.write_text(json.dumps(data), encoding="utf-8")

    def test_fields_are_derived(self):
        c = scryfall.custom_card(dict(GIOVANNI), Path("/x"))
        self.assertEqual(c["cmc"], 3.0)
        self.assertEqual(c["colors"], ["W", "B"])
        self.assertEqual(c["color_identity"], ["W", "B"])
        self.assertTrue(c["custom"])
        self.assertRegex(c["id"], r"^[0-9a-f-]{36}$")
        self.assertEqual(c["id"], scryfall.custom_card(dict(GIOVANNI))["id"])
        self.assertTrue(c["image_uris"]["normal"].startswith("file:"))
        self.assertTrue(c["image_uris"]["normal"].endswith("giovanni.png"))

    def test_identity_counts_symbols_in_rules_text(self):
        c = scryfall.custom_card({"name": "X", "type_line": "Artifact", "mana_cost": "{2}",
                                  "oracle_text": "{T}: Add {G}."})
        self.assertEqual(c["colors"], [])
        self.assertEqual(c["color_identity"], ["G"])

    def test_resolve_finds_custom_without_the_api(self):
        self.write({"cards": [GIOVANNI]})
        bolt = card("Lightning Bolt")
        fake = FakeHTTP([("/cards/collection", collection([bolt]))])
        calls = fake.calls
        report = scryfall.Report()
        with mock.patch.object(scryfall, "_http", fake), mock.patch.object(scryfall.time, "sleep"):
            found, _ = scryfall.resolve_names(["giovanni, suporte lateral", "Lightning Bolt"],
                                              report)
        self.assertTrue(found["giovanni, suporte lateral"]["custom"])
        self.assertEqual(found["lightning bolt"]["name"], "Lightning Bolt")
        body = json.loads(calls[0][2])
        self.assertEqual([i["name"] for i in body["identifiers"]], ["Lightning Bolt"])
        self.assertEqual(report.custom, ["Giovanni, Suporte Lateral"])
        self.assertFalse(report.missing)

    def test_list_file_and_no_file(self):
        self.write([GIOVANNI])
        self.assertIn("giovanni, suporte lateral", scryfall.load_custom_cards())
        scryfall._custom_cache.clear()
        self.file.unlink()
        self.assertEqual(scryfall.load_custom_cards(), {})

    def test_bad_file_stops_with_the_path(self):
        self.write([{"name": "No type"}])
        with self.assertRaises(SystemExit) as ctx:
            scryfall.load_custom_cards()
        self.assertIn(str(self.file), str(ctx.exception))

    def test_card_output_marks_custom(self):
        c = scryfall.custom_card(dict(GIOVANNI))
        self.assertIn("[custom card]", scryfall.format_card(c, []))


class CustomIdentity(unittest.TestCase):
    def test_reminder_text_does_not_count(self):
        c = scryfall.custom_card({"name": "X", "type_line": "Creature", "mana_cost": "{W}",
                                  "oracle_text": "Extort (you may pay {W/B}.)"})
        self.assertEqual(c["color_identity"], ["W"])

    def test_given_colors_count(self):
        c = scryfall.custom_card({"name": "X", "type_line": "Creature", "colors": ["G"]})
        self.assertEqual(c["color_identity"], ["G"])

    def test_missing_names_point_at_the_custom_file(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {scryfall.CUSTOM_ENV: tmp + "/none.json"}):
            report = scryfall.Report()
            report.missing["Giovanni"] = ""
            err = io.StringIO()
            report.emit(err)
        self.assertIn("no custom cards file at", err.getvalue())


if __name__ == "__main__":
    unittest.main()
