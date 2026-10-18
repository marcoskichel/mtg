"""Tests for edhrec.py with simulated HTTP. Run: python3 -m unittest discover -s tests"""

import io
import json
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import edhrec  # noqa: E402

NOT_FOUND_BODY = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                  b"<Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>")
CF_BODY = b"<!DOCTYPE html><html><head><title>Just a moment...</title></head></html>"


def http_error(code, body=b"", headers=None):
    return urllib.error.HTTPError("https://x", code, "err", headers or {}, io.BytesIO(body))


class FakeResp:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class SlugTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(edhrec.slug("Sol Ring"), "sol-ring")

    def test_apostrophe_and_comma_dropped(self):
        self.assertEqual(edhrec.slug("Kraum, Ludevic's Opus"), "kraum-ludevics-opus")

    def test_accents_and_ligatures(self):
        self.assertEqual(edhrec.slug("Lim-Dûl the Necromancer"), "lim-dul-the-necromancer")
        self.assertEqual(edhrec.slug("Jötun Grunt"), "jotun-grunt")
        self.assertEqual(edhrec.slug("Æther Vial"), "aether-vial")

    def test_transform_uses_front_face(self):
        self.assertEqual(edhrec.slug("Delver of Secrets // Insectile Aberration", "transform"),
                         "delver-of-secrets")

    def test_adventure_uses_front_face(self):
        self.assertEqual(edhrec.slug("Brazen Borrower // Petty Theft", "adventure"),
                         "brazen-borrower")

    def test_unknown_layout_with_slashes_uses_front_face(self):
        self.assertEqual(edhrec.slug("Delver of Secrets // Insectile Aberration"),
                         "delver-of-secrets")

    def test_split_and_aftermath_keep_both_halves(self):
        self.assertEqual(edhrec.slug("Fire // Ice", "split"), "fire-ice")
        self.assertEqual(edhrec.slug("Commit // Memory", "aftermath"), "commit-memory")

    def test_dots_and_modifier_colon_are_deleted(self):
        self.assertEqual(edhrec.slug("V.A.T.S."), "vats")
        self.assertEqual(edhrec.slug("Nick Fury, Agent of S.H.I.E.L.D."),
                         "nick-fury-agent-of-shield")
        self.assertEqual(edhrec.slug("Ratonhnhaké꞉ton"), "ratonhnhaketon")
        self.assertEqual(edhrec.slug("Dr. Madison Li"), "dr-madison-li")

    def test_pair_is_alphabetical(self):
        self.assertEqual(edhrec.pair_slug("Tymna the Weaver", "Kraum, Ludevic's Opus"),
                         "kraum-ludevics-opus-tymna-the-weaver")


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p1 = mock.patch.object(edhrec, "CACHE_DIR", Path(self.tmp.name))
        p2 = mock.patch.object(edhrec.time, "sleep")
        p1.start(); p2.start()
        self.addCleanup(p1.stop); self.addCleanup(p2.stop)
        edhrec.DELAY[0] = 0

    def test_ok_is_cached(self):
        with mock.patch.object(edhrec.urllib.request, "urlopen",
                               return_value=FakeResp({"a": 1})) as uo:
            page, _ = edhrec.fetch("cards/sol-ring")
            page2, _ = edhrec.fetch("cards/sol-ring")
        self.assertEqual(page, {"a": 1})
        self.assertEqual(page2, {"a": 1})
        self.assertEqual(uo.call_count, 1)

    def test_expired_cache_refetches(self):
        with mock.patch.object(edhrec.urllib.request, "urlopen",
                               return_value=FakeResp({"a": 1})) as uo:
            edhrec.fetch("cards/sol-ring")
            edhrec.fetch("cards/sol-ring", ttl_hours=0)
        self.assertEqual(uo.call_count, 2)

    def test_access_denied_is_not_found_and_cached(self):
        with mock.patch.object(edhrec.urllib.request, "urlopen",
                               side_effect=http_error(403, NOT_FOUND_BODY)) as uo:
            page, _ = edhrec.fetch("cards/nope")
            page2, _ = edhrec.fetch("cards/nope")
        self.assertIsNone(page)
        self.assertIsNone(page2)
        self.assertEqual(uo.call_count, 1)

    def test_cloudflare_403_is_blocked_after_retries_and_not_cached(self):
        with mock.patch.object(edhrec.urllib.request, "urlopen",
                               side_effect=http_error(403, CF_BODY)) as uo:
            with self.assertRaises(edhrec.Blocked):
                edhrec.fetch("cards/sol-ring")
        self.assertEqual(uo.call_count, 5)
        self.assertFalse(any(Path(self.tmp.name).rglob("*.json")))

    def test_redirect_is_followed_once_and_cached_under_requested_path(self):
        seq = [FakeResp({"redirect": "/commanders/b-a"}), FakeResp({"real": True})]
        with mock.patch.object(edhrec.urllib.request, "urlopen", side_effect=seq) as uo:
            page, _ = edhrec.fetch("commanders/a-b")
            again, _ = edhrec.fetch("commanders/a-b")
        self.assertEqual(page, {"real": True})
        self.assertEqual(again, {"real": True})
        self.assertEqual(uo.call_count, 2)
        self.assertTrue(uo.call_args_list[1][0][0].full_url.endswith("/pages/commanders/b-a.json"))

    def test_retry_after_is_clamped(self):
        seq = [http_error(429, b"", {"Retry-After": "-1"}),
               http_error(429, b"", {"Retry-After": "3600"}), FakeResp({"ok": True})]
        with mock.patch.object(edhrec.urllib.request, "urlopen", side_effect=seq):
            edhrec.fetch("cards/sol-ring")
        edhrec.time.sleep.assert_any_call(0.0)
        edhrec.time.sleep.assert_any_call(60.0)

    def test_429_retries_then_succeeds(self):
        seq = [http_error(429, b"", {"Retry-After": "10"}), FakeResp({"ok": True})]
        with mock.patch.object(edhrec.urllib.request, "urlopen", side_effect=seq):
            page, _ = edhrec.fetch("cards/sol-ring")
        self.assertEqual(page, {"ok": True})
        edhrec.time.sleep.assert_any_call(10.0)


CARD_PAGE = {"container": {"json_dict": {
    "card": {"name": "Blood Artist", "num_decks": 595488, "potential_decks": 5217553,
             "salt": 0.6854},
    "cardlists": [
        {"header": "Top Commanders", "cardviews": [
            {"name": "Avacyn, Angel of Horror", "num_decks": 133},
            {"name": "Niv-Mizzet, Ghost Counsel", "num_decks": 45}]}]}},
    "panels": {"taglinks": [{"slug": "aristocrats", "value": "Aristocrats", "count": 900}]}}

CMDR_PAGE = {"bracket_counts": {"5": 4120, "4": 255, "3": 140},
             "tag_counts": [{"slug": "combo", "value": "Combo", "count": 657}],
             "container": {"json_dict": {"card": {
                 "name": "Kraum, Ludevic's Opus // Tymna the Weaver",
                 "num_decks": 12088, "rank": 192, "salt": 1.2}}}}

THEME_PAGE = {"container": {"json_dict": {"cardlists": [
    {"header": "New Commanders", "cardviews": [{"name": "Fresh Guy", "num_decks": 3}]},
    {"header": "Top Commanders", "cardviews": [
        {"name": "Niv-Mizzet, Ghost Counsel", "num_decks": 45},
        {"name": "Edgar, Ancient Bloodlord", "num_decks": 12}]}]}}}


class ExtractTest(unittest.TestCase):
    def test_card_stats_play_rate(self):
        s = edhrec.card_stats(CARD_PAGE)
        self.assertEqual(s["decks"], 595488)
        self.assertAlmostEqual(s["play_rate"], 0.1141, places=3)
        self.assertEqual(s["top_commanders"][0], "Avacyn, Angel of Horror")

    def test_card_stats_missing_potential(self):
        page = json.loads(json.dumps(CARD_PAGE))
        del page["container"]["json_dict"]["card"]["potential_decks"]
        self.assertIsNone(edhrec.card_stats(page)["play_rate"])

    def test_commander_stats(self):
        s = edhrec.commander_stats(CMDR_PAGE)
        self.assertEqual(s["bracket_counts"]["5"], 4120)
        self.assertEqual(s["themes"], [{"name": "Combo", "count": 657}])
        self.assertEqual(s["rank"], 192)

    def test_list_names_by_header(self):
        self.assertEqual(edhrec.list_names(THEME_PAGE, "Top Commanders"),
                         [("Niv-Mizzet, Ghost Counsel", 45), ("Edgar, Ancient Bloodlord", 12)])
        self.assertEqual(len(edhrec.list_names(THEME_PAGE)), 3)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(edhrec, "CACHE_DIR", Path(self.tmp.name)),
                  mock.patch.object(edhrec.time, "sleep")):
            p.start(); self.addCleanup(p.stop)
        edhrec.DELAY[0] = 0

    def run_cli(self, argv, found, pages):
        def fake_resolve(names, report):
            wanted = {edhrec.scryfall.fold(edhrec.scryfall.front_face(n)): edhrec.scryfall.front_face(n) for n in names}
            for k, n in wanted.items():
                if k not in found:
                    report.missing[n] = ""
            return {k: v for k, v in found.items() if k in wanted}, wanted

        def fake_fetch(path, ttl_hours=24):
            if path in pages:
                if isinstance(pages[path], Exception):
                    raise pages[path]
                return pages[path], 0.0
            return None, 0.0

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(edhrec.scryfall, "resolve_names", side_effect=fake_resolve), \
             mock.patch.object(edhrec, "fetch", side_effect=fake_fetch), \
             mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = edhrec.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_card_prints_play_rate(self):
        found = {"blood artist": {"name": "Blood Artist", "layout": "normal"}}
        code, out, _ = self.run_cli(["card", "Blood Artist"], found,
                                    {"cards/blood-artist": CARD_PAGE})
        self.assertEqual(code, 0)
        self.assertIn("play rate 11.4% (595,488 / 5,217,553)", out)

    def test_card_not_on_edhrec_is_reported_not_fatal(self):
        found = {"new card": {"name": "New Card", "layout": "normal"}}
        code, out, err = self.run_cli(["card", "New Card"], found, {})
        self.assertEqual(code, 0)
        self.assertIn("no EDHREC page", out)

    def test_blocked_exits_1_and_says_blocked(self):
        found = {"sol ring": {"name": "Sol Ring", "layout": "normal"}}
        code, out, err = self.run_cli(["card", "Sol Ring"], found,
                                      {"cards/sol-ring": edhrec.Blocked("x")})
        self.assertEqual(code, 1)
        self.assertIn("EDHREC BLOCKED", err)
        self.assertNotIn("no EDHREC page", out)

    def test_unresolved_name_exits_1(self):
        code, out, err = self.run_cli(["card", "Nonsense"], {}, {})
        self.assertEqual(code, 1)
        self.assertIn("NOT FOUND", err)

    def test_dfc_uses_front_face_slug(self):
        found = {"delver of secrets": {"name": "Delver of Secrets // Insectile Aberration",
                                       "layout": "transform"}}
        page = {"container": {"json_dict": {"card": {"name": "Delver of Secrets",
                                                     "num_decks": 4402}}}}
        code, out, _ = self.run_cli(["card", "Delver of Secrets // Insectile Aberration"],
                                    found, {"cards/delver-of-secrets": page})
        self.assertEqual(code, 0)
        self.assertIn("4,402 decks", out)

    def test_commander_pair_uses_pair_slug(self):
        found = {"kraum, ludevic's opus": {"name": "Kraum, Ludevic's Opus", "layout": "normal"},
                 "tymna the weaver": {"name": "Tymna the Weaver", "layout": "normal"}}
        code, out, _ = self.run_cli(["commander", "Tymna the Weaver", "Kraum, Ludevic's Opus"],
                                    found, {"commanders/kraum-ludevics-opus-tymna-the-weaver":
                                            CMDR_PAGE})
        self.assertEqual(code, 0)
        self.assertIn("bracket 5: 4,120", out)

    def test_theme_with_colors(self):
        code, out, _ = self.run_cli(["theme", "aristocrats", "--colors", "wb"], {},
                                    {"tags/aristocrats/orzhov": THEME_PAGE})
        self.assertEqual(code, 0)
        self.assertIn("Niv-Mizzet, Ghost Counsel", out)
        self.assertNotIn("Fresh Guy", out)


class JsonEnvelopeTest(CliTest):
    """Every subcommand's --json uses {path, fetched, data}; data is null when missing."""

    def test_card_json(self):
        found = {"blood artist": {"name": "Blood Artist", "layout": "normal"},
                 "new card": {"name": "New Card", "layout": "normal"}}
        code, out, _ = self.run_cli(["card", "Blood Artist", "New Card", "--json"], found,
                                    {"cards/blood-artist": CARD_PAGE})
        rows = json.loads(out)
        self.assertEqual(set(rows[0]), {"name", "path", "fetched", "data"})
        self.assertEqual(rows[0]["data"]["decks"], 595488)
        self.assertNotIn("themes", rows[0]["data"])
        self.assertIsNone(rows[1]["data"])

    def test_commander_json_and_missing(self):
        found = {"edgar markov": {"name": "Edgar Markov", "layout": "normal"}}
        code, out, _ = self.run_cli(["commander", "Edgar Markov", "--json"], found,
                                    {"commanders/edgar-markov": CMDR_PAGE})
        obj = json.loads(out)
        self.assertEqual(obj["path"], "commanders/edgar-markov")
        self.assertEqual(obj["data"]["themes"], [{"name": "Combo", "count": 657}])
        code, out, _ = self.run_cli(["commander", "Edgar Markov", "--json"], found, {})
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out)["data"])

    def test_theme_and_partners_json(self):
        code, out, _ = self.run_cli(["theme", "aristocrats", "--json"], {},
                                    {"tags/aristocrats": THEME_PAGE})
        obj = json.loads(out)
        self.assertEqual(obj["data"][0], {"name": "Niv-Mizzet, Ghost Counsel", "decks": 45})
        found = {"tymna the weaver": {"name": "Tymna the Weaver", "layout": "normal"}}
        code, out, _ = self.run_cli(["partners", "Tymna the Weaver", "--json"], found, {})
        self.assertIsNone(json.loads(out)["data"])


CMDR_CARDS_PAGE = {"container": {"json_dict": {"cardlists": [
    {"header": "Top Cards", "tag": "topcards", "cardviews": [
        {"name": "Captivating Vampire", "num_decks": 42797, "potential_decks": 51928,
         "synergy": 0.7165},
        {"name": "Sol Ring", "num_decks": 50000, "potential_decks": 51928, "synergy": 0.02}]},
    {"header": "Creatures", "tag": "creatures", "cardviews": [
        {"name": "Captivating Vampire", "num_decks": 42797, "potential_decks": 51928,
         "synergy": 0.7165},
        {"name": "Bloodghast", "num_decks": 9000, "potential_decks": 0, "synergy": 0.1}]}]}}}

AVG_PAGE = {"creature": 33, "land": 36,
            "deck": {"commander": ["Edgar Markov"],
                     "cards": {"Artifact": [["Sol Ring", 1], ["Arcane Signet", 1]],
                               "Land": [["Swamp", 8], ["Command Tower", 1]]}}}


class CommanderCardsTest(unittest.TestCase):
    def test_dedupes_and_computes_inclusion(self):
        rows = edhrec.commander_cards(CMDR_CARDS_PAGE)
        names = [r["name"] for r in rows]
        self.assertEqual(names, ["Captivating Vampire", "Sol Ring", "Bloodghast"])
        self.assertAlmostEqual(rows[0]["inclusion"], 42797 / 51928)
        self.assertEqual(rows[0]["lists"], ["Top Cards", "Creatures"])
        self.assertIsNone(rows[2]["inclusion"])

    def test_average_deck(self):
        avg = edhrec.average_deck(AVG_PAGE)
        self.assertEqual(avg["commanders"], ["Edgar Markov"])
        self.assertIn((8, "Swamp"), avg["cards"])
        self.assertEqual(avg["lands"], 9)
        self.assertEqual(len(avg["cards"]), 4)

    def test_average_deck_missing(self):
        self.assertIsNone(edhrec.average_deck(None))
        self.assertIsNone(edhrec.average_deck({"header": "x"}))


if __name__ == "__main__":
    unittest.main()
