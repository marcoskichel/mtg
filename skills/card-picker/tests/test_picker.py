"""Tests for picker.py: input parsing, card views, answers and the HTTP server.

No network: Scryfall is mocked and the server runs on a free local port.
Run: python3 -m unittest discover -s tests
"""

import argparse
import io
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import picker  # noqa: E402

BOLT_ID = "11111111-1111-1111-1111-111111111111"
DELVER_ID = "22222222-2222-2222-2222-222222222222"
FIRE_ID = "33333333-3333-3333-3333-333333333333"


def card(name, cid, **kw):
    base = {
        "object": "card", "id": cid, "name": name, "layout": "normal",
        "mana_cost": "{R}", "type_line": "Instant",
        "oracle_text": f"{name} deals 3 damage to any target.",
        "flavor_text": "Zap.", "set": "m11", "set_name": "Magic 2011",
        "collector_number": "149", "rarity": "common", "artist": "Someone",
        "image_uris": {"normal": f"https://cards.scryfall.io/normal/{cid}.jpg"},
    }
    base.update(kw)
    return base


BOLT = card("Lightning Bolt", BOLT_ID)
DELVER = card(
    "Delver of Secrets // Insectile Aberration", DELVER_ID, layout="transform",
    mana_cost=None, oracle_text=None, image_uris=None, flavor_text=None,
    type_line="Creature — Human Wizard // Creature — Human Insect",
    card_faces=[
        {"name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature — Human Wizard",
         "oracle_text": "At the beginning of your upkeep, look at the top card.",
         "power": "1", "toughness": "1",
         "image_uris": {"normal": "https://cards.scryfall.io/front.jpg"}},
        {"name": "Insectile Aberration", "mana_cost": "", "type_line": "Creature — Human Insect",
         "oracle_text": "Flying", "power": "3", "toughness": "2",
         "flavor_text": "Final entry.",
         "image_uris": {"normal": "https://cards.scryfall.io/back.jpg"}},
    ])
del DELVER["image_uris"]
FIRE = card(
    "Fire // Ice", FIRE_ID, layout="split", mana_cost="{1}{R} // {1}{U}", oracle_text=None,
    type_line="Instant // Instant", flavor_text=None,
    card_faces=[
        {"name": "Fire", "mana_cost": "{1}{R}", "type_line": "Instant",
         "oracle_text": "Fire deals 2 damage divided as you choose."},
        {"name": "Ice", "mana_cost": "{1}{U}", "type_line": "Instant",
         "oracle_text": "Tap target permanent.\nDraw a card."},
    ])


def request(mode="pick", lo=1, hi=1, prompt=None, optional=False):
    cards = [picker.card_view(c) for c in (BOLT, DELVER, FIRE)]
    return {"mode": mode, "min": lo, "max": hi, "prompt": prompt,
            "promptOptional": optional, "cards": cards}


class ParseCount(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(picker.parse_count("2"), (2, 2))
        self.assertEqual(picker.parse_count("1-3"), (1, 3))
        self.assertEqual(picker.parse_count(" 1 - 3 "), (1, 3))
        self.assertEqual(picker.parse_count("any"), (1, None))

    def test_rejects(self):
        for bad in ("0", "3-1", "two", "-1", ""):
            with self.subTest(bad=bad), self.assertRaises(argparse.ArgumentTypeError):
                picker.parse_count(bad)


class Inputs(unittest.TestCase):
    def test_suggestions_mix_strings_and_reasons(self):
        got = picker.parse_suggestions('["Sol Ring", {"name": "Bolt", "reason": "cheap"}]')
        self.assertEqual(got, [("Sol Ring", ""), ("Bolt", "cheap")])

    def test_suggestions_errors(self):
        for bad in ("{}", "not json", '[{"reason": "x"}]', "[3]"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                picker.parse_suggestions(bad)

    def test_collect_dedupes_across_sources_keeping_first(self):
        args = argparse.Namespace(deck=None, cards=["Fire // Ice", "lightning bolt"],
                                  suggestions="-")
        stdin = '[{"name": "Lightning Bolt", "reason": "dup"}, {"name": "Fire", "reason": "dup"}, "Opt"]'
        with mock.patch.object(sys, "stdin") as fake:
            fake.read.return_value = stdin
            got = picker.collect_entries(args)
        self.assertEqual(got, [("Fire // Ice", ""), ("lightning bolt", ""), ("Opt", "")])

    def test_collect_reads_deck_sections_in_order(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        deck = Path(tmp.name) / "deck.txt"
        deck.write_text("Commander\n1 Edgar Markov\n\nDeck\n1 Sol Ring\n4 Lightning Bolt\n")
        args = argparse.Namespace(deck=str(deck), cards=None, suggestions=None)
        self.assertEqual([n for n, _ in picker.collect_entries(args)],
                         ["Edgar Markov", "Sol Ring", "Lightning Bolt"])


class CardView(unittest.TestCase):
    def test_normal_card(self):
        v = picker.card_view(BOLT, "why not")
        self.assertEqual(v["set"], "M11")
        self.assertEqual(v["images"], 1)
        self.assertEqual(v["reason"], "why not")
        self.assertEqual(len(v["faces"]), 1)
        self.assertEqual(v["faces"][0]["flavor"], "Zap.")
        self.assertNotIn("image_uris", json.dumps(v))

    def test_transform_card_has_an_image_per_face(self):
        v = picker.card_view(DELVER)
        self.assertEqual(v["images"], 2)
        self.assertEqual([f["name"] for f in v["faces"]], ["Delver of Secrets", "Insectile Aberration"])
        self.assertEqual(v["faces"][1]["power"], "3")
        self.assertEqual(picker.card_images(DELVER),
                         ["https://cards.scryfall.io/front.jpg", "https://cards.scryfall.io/back.jpg"])

    def test_split_card_shares_one_image(self):
        v = picker.card_view(FIRE)
        self.assertEqual(v["images"], 1)
        self.assertEqual(len(v["faces"]), 2)

    def test_resolve_keeps_input_order_and_reports_misses(self):
        def fake_resolve(names, report):
            report.missing["Nope"] = "not found"
            return {"fire": FIRE, "lightning bolt": BOLT}, {}
        with mock.patch.object(picker.scryfall, "resolve_names", fake_resolve):
            views, images, report = picker.resolve_cards(
                [("Fire // Ice", "a"), ("Nope", ""), ("Lightning Bolt", "b")])
        self.assertEqual([v["name"] for v in views], ["Fire // Ice", "Lightning Bolt"])
        self.assertEqual([v["reason"] for v in views], ["a", "b"])
        self.assertEqual(set(images), {FIRE_ID, BOLT_ID})
        self.assertTrue(report.failed)


class BuildAnswer(unittest.TestCase):
    def test_pick_uses_names_from_the_request(self):
        out, code = picker.build_answer(request(lo=2, hi=2), {"status": "picked", "picked": [2, 0]})
        self.assertEqual(code, 0)
        self.assertEqual(out, {"status": "picked", "picked": [
            {"name": "Fire // Ice", "set": "m11", "collector_number": "149"},
            {"name": "Lightning Bolt", "set": "m11", "collector_number": "149"}]})

    def test_count_is_enforced(self):
        req = request(lo=1, hi=2)
        for picked in ([], [0, 1, 2]):
            with self.subTest(picked=picked), self.assertRaises(ValueError):
                picker.build_answer(req, {"status": "picked", "picked": picked})

    def test_bad_indices(self):
        for picked in ([5], [-1], [0, 0], ["0"], None, [[0]], [{}], [True]):
            with self.subTest(picked=picked), self.assertRaises(ValueError):
                picker.build_answer(request(hi=3), {"status": "picked", "picked": picked})

    def test_note_rules(self):
        out, _ = picker.build_answer(request(prompt="Why?", optional=True),
                                     {"status": "picked", "picked": [0], "note": "  "})
        self.assertNotIn("note", out)
        with self.assertRaises(ValueError):
            picker.build_answer(request(prompt="Why?"), {"status": "picked", "picked": [0]})
        out, _ = picker.build_answer(request(prompt="Why?"),
                                     {"status": "picked", "picked": [0], "note": " fast "})
        self.assertEqual(out["note"], "fast")
        out, _ = picker.build_answer(request(), {"status": "picked", "picked": [0], "note": "x"})
        self.assertNotIn("note", out)

    def test_chosen_printing(self):
        req = request(lo=1, hi=2)
        req["printings"] = {"0": [picker.print_view(card("Lightning Bolt", "p1", set="lea",
                                                           collector_number="161"))]}
        out, _ = picker.build_answer(req, {"status": "picked", "picked": [0, 1],
                                           "prints": {"0": "p1"}})
        self.assertEqual([(p["set"], p["collector_number"]) for p in out["picked"]],
                         [("lea", "161"), ("m11", "149")])
        for prints in ({"0": "nope"}, {"1": "p1"}, ["p1"]):
            with self.subTest(prints=prints), self.assertRaises(ValueError):
                picker.build_answer(req, {"status": "picked", "picked": [0, 1], "prints": prints})

    def test_cancel_and_show(self):
        self.assertEqual(picker.build_answer(request(), {"status": "cancelled"}),
                         ({"status": "cancelled"}, 130))
        self.assertEqual(picker.build_answer(request("show"), {"status": "closed", "focused": 1}),
                         ({"status": "closed", "focused": DELVER["name"]}, 0))
        self.assertEqual(picker.build_answer(request("show"), {"status": "closed", "focused": 9}),
                         ({"status": "closed", "focused": None}, 0))
        # Esc on a view closes it; it is not a refusal.
        self.assertEqual(picker.build_answer(request("show"), {"status": "cancelled", "focused": 0}),
                         ({"status": "closed", "focused": "Lightning Bolt"}, 0))

    def test_unknown_status(self):
        with self.assertRaises(ValueError):
            picker.build_answer(request(), {"status": "whatever"})


class BuildRequest(unittest.TestCase):
    def build(self, mode, n_cards, count=(1, 1), prompt=None, deck=None):
        args = argparse.Namespace(title=None, label=None, agent="Test", deck=deck,
                                  count=count, prompt=prompt, prompt_optional=False)
        return picker.build_request(args, mode, [{"name": str(i)} for i in range(n_cards)])

    def test_pick_labels(self):
        cases = [
            ((2, 2), 5, None, "Pick 2 cards", "Pick 2", (2, 2)),
            ((1, 3), 5, None, "Pick 1–3 cards", "Pick 1–3", (1, 3)),
            ((1, None), 5, None, "Pick any cards", "Pick any", (1, 5)),
            ((2, 5), 5, None, "Pick 2–5 cards", "Pick 2–5", (2, 5)),
            ((2, 10), 6, None, "Pick 2–6 cards", "Pick 2–6", (2, 6)),
            ((1, 1), 1, None, "Pick 1 card", "Pick 1", (1, 1)),
            ((1, 1), 4, "Why?", "Pick 1 card", "Pick 1 + note", (1, 1)),
        ]
        for count, n, prompt, ask, label, bounds in cases:
            with self.subTest(count=count, n=n):
                req = self.build("pick", n, count, prompt)
                self.assertEqual((req["ask"], req["label"], (req["min"], req["max"])),
                                 (ask, label, bounds))

    def test_show_defaults(self):
        req = self.build("show", 3, deck="decks/saruman.txt")
        self.assertEqual((req["ask"], req["label"], req["mode"]),
                         ("Take a look at saruman.txt", "View", "show"))
        self.assertEqual(self.build("show", 3, deck="-")["ask"], "Take a look")


class Server(unittest.TestCase):
    def setUp(self):
        quiet = mock.patch.object(picker.Handler, "log_message", lambda *a: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.server, self.hub = picker.make_server(0, "secret", "v1")
        self.port = self.server.server_address[1]
        self.state = {"port": self.port, "token": "secret"}
        t = threading.Thread(target=self.server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def raw(self, path, method="GET", headers=None, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     headers=headers or {}, data=body)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read()

    def register(self, **kw):
        req = request(**kw)
        req.update(ask="Pick", label="Pick 1", agent="Test",
                   images={BOLT_ID: ["https://cards.scryfall.io/b.jpg"]})
        status, body = picker.call(self.state, "POST", "/api/requests", req)
        self.assertEqual(status, 200)
        return body["id"]

    def test_api_needs_token(self):
        status, _ = self.raw("/api/requests")
        self.assertEqual(status, 401)
        status, _ = self.raw("/api/requests", headers={"X-Picker-Token": "wrong"})
        self.assertEqual(status, 401)

    def test_foreign_host_is_refused(self):
        status, _ = self.raw("/", headers={"Host": f"evil.example:{self.port}"})
        self.assertEqual(status, 403)

    def test_page_and_unknown_paths(self):
        status, body = self.raw("/")
        self.assertEqual(status, 200)
        self.assertIn(b"card-picker", body)
        self.assertEqual(self.raw("/favicon.ico")[0], 404)

    def test_full_round_trip(self):
        rid = self.register(lo=1, hi=2)
        status, listing = picker.call(self.state, "GET", "/api/requests")
        self.assertEqual([r["id"] for r in listing["requests"]], [rid])
        self.assertNotIn("cards", listing["requests"][0])
        status, full = picker.call(self.state, "GET", f"/api/requests/{rid}")
        self.assertEqual(len(full["cards"]), 3)
        self.assertNotIn("images", full)

        status, pending = picker.call(self.state, "GET", f"/api/requests/{rid}/wait?timeout=0")
        self.assertEqual(pending, {"pending": True})

        status, bad = picker.call(self.state, "POST", f"/api/requests/{rid}/answer",
                                  {"status": "picked", "picked": [0, 1, 2]})
        self.assertEqual(status, 400)

        status, ok = picker.call(self.state, "POST", f"/api/requests/{rid}/answer",
                                 {"status": "picked", "picked": [1]})
        self.assertEqual((status, ok["code"]), (200, 0))
        status, done = picker.call(self.state, "GET", f"/api/requests/{rid}/wait?timeout=1")
        self.assertEqual(done["answer"]["picked"][0]["name"], DELVER["name"])
        # Delivered once, then gone.
        status, _ = picker.call(self.state, "GET", f"/api/requests/{rid}/wait?timeout=0")
        self.assertEqual(status, 410)

    def test_answer_wakes_a_waiting_caller(self):
        rid = self.register()
        registered = self.hub.requests[rid]["seen"]
        got = {}
        t = threading.Thread(target=lambda: got.update(picker.call(
            self.state, "GET", f"/api/requests/{rid}/wait?timeout=5", timeout=10)[1]))
        t.start()
        # Answer only once the waiter is parked inside wait().
        picker.wait_until(lambda: self.hub.requests[rid]["seen"] > registered, 5, step=0.01)
        picker.call(self.state, "POST", f"/api/requests/{rid}/answer", {"status": "cancelled"})
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual(got, {"answer": {"status": "cancelled"}, "code": 130})

    def test_ping_proves_the_token_without_receiving_it(self):
        info = picker.ping(self.state)
        self.assertEqual((info["version"], info["pending"]), ("v1", 0))
        self.assertIsNone(picker.ping({"port": self.port, "token": "other"}))
        self.assertEqual(self.raw("/api/ping")[0], 400)

    def test_withdraw_returns_an_answer_that_landed_first(self):
        rid = self.register()
        picker.call(self.state, "POST", f"/api/requests/{rid}/answer", {"status": "picked", "picked": [0]})
        status, resp = picker.call(self.state, "DELETE", f"/api/requests/{rid}")
        self.assertEqual(resp["answer"]["picked"][0]["name"], "Lightning Bolt")
        status, resp = picker.call(self.state, "DELETE", f"/api/requests/{rid}")
        self.assertEqual(resp, {"ok": True})

    def test_delete_needs_token(self):
        rid = self.register()
        self.assertEqual(self.raw(f"/api/requests/{rid}", method="DELETE")[0], 403)
        self.assertIn(rid, self.hub.requests)

    def test_closing_server_refuses_new_requests(self):
        self.assertTrue(self.hub.close_if_idle())
        req = dict(request(), images={})
        status, _ = picker.call(self.state, "POST", "/api/requests", req)
        self.assertEqual(status, 503)

    def test_bad_bodies(self):
        rid = self.register()
        headers = {"X-Picker-Token": "secret", "Content-Type": "application/json"}
        status, _ = self.raw(f"/api/requests/{rid}/answer", "POST", headers, b"[1, 2]")
        self.assertEqual(status, 400)
        status, _ = self.raw(f"/api/requests/{rid}/wait?timeout=abc", headers=headers)
        self.assertEqual(status, 400)

    def test_symbol_route(self):
        self.hub.symbols = {"{W/U}": "https://svgs.scryfall.io/card-symbols/WU.svg"}
        with mock.patch.object(picker, "cached_fetch", return_value=b"<svg/>") as fetch:
            self.assertEqual(self.raw("/sym/W%2FU.svg"), (200, b"<svg/>"))
            self.assertEqual(self.raw("/sym/Z.svg")[0], 404)
            self.assertEqual(self.raw("/sym/ABCDEFGHIJKLM.svg")[0], 404)
        url, path = fetch.call_args[0]
        self.assertEqual(url, "https://svgs.scryfall.io/card-symbols/WU.svg")
        self.assertRegex(path.name, r"^[0-9a-f]{16}\.svg$")

    def test_printings_route(self):
        rid = self.register()
        uri = "https://api.scryfall.com/cards/search?q=oracleid%3Ax&unique=prints"
        self.hub.requests[rid]["cards"][0]["printsUri"] = uri
        pages = {
            uri: {"data": [card("Lightning Bolt", "p1", set="lea"),
                           card("Lightning Bolt", "p2", set="prm", games=["mtgo"])],
                  "has_more": True, "next_page": "https://api.scryfall.com/page2"},
            "https://api.scryfall.com/page2": {"data": [card("Lightning Bolt", "p3", set="2xm")]},
        }
        with mock.patch.object(picker.scryfall, "api", side_effect=pages.__getitem__) as api:
            status, body = picker.call(self.state, "GET", f"/api/requests/{rid}/cards/0/prints")
            again = picker.call(self.state, "GET", f"/api/requests/{rid}/cards/0/prints")[1]
        self.assertEqual(status, 200)
        self.assertEqual([p["set"] for p in body["printings"]], ["LEA", "2XM"])
        self.assertEqual(again, body)
        self.assertEqual(api.call_count, 2)
        self.assertEqual(self.hub.images["p1"], ["https://cards.scryfall.io/normal/p1.jpg"])
        self.assertEqual(picker.call(self.state, "GET", f"/api/requests/{rid}/cards/9/prints")[0], 410)
        self.assertEqual(picker.call(self.state, "GET", "/api/requests/nope/cards/0/prints")[0], 410)
        status, listing = picker.call(self.state, "GET", "/api/requests")
        self.assertNotIn("printings", listing["requests"][0])

    def test_printings_stay_on_scryfall(self):
        with mock.patch.object(picker.scryfall, "api") as api:
            self.assertEqual(picker.load_printings("https://evil.example/cards"), [])
        api.assert_not_called()

    def test_set_icon_route(self):
        self.hub.sets = {"dom": "https://svgs.scryfall.io/sets/dom.svg"}
        with mock.patch.object(picker, "cached_fetch", return_value=b"<svg/>") as fetch:
            self.assertEqual(self.raw("/set/dom.svg"), (200, b"<svg/>"))
            self.assertEqual(self.raw("/set/xyz.svg")[0], 404)
            self.assertEqual(self.raw("/set/..%2Fdom.svg")[0], 404)
        self.assertEqual(fetch.call_args[0][0], "https://svgs.scryfall.io/sets/dom.svg")

    def test_answer_after_caller_left(self):
        rid = self.register()
        picker.call(self.state, "DELETE", f"/api/requests/{rid}")
        status, _ = picker.call(self.state, "POST", f"/api/requests/{rid}/answer",
                                {"status": "picked", "picked": [0]})
        self.assertEqual(status, 410)

    def test_prune_drops_dead_callers(self):
        rid = self.register()
        self.hub.requests[rid]["seen"] -= picker.CLIENT_GONE + 1
        self.hub.prune()
        self.assertNotIn(rid, self.hub.requests)

    def test_shutdown_refused_while_busy(self):
        self.register()
        status, _ = picker.call(self.state, "POST", "/api/shutdown")
        self.assertEqual(status, 409)

    def test_image_routes_only_known_cards(self):
        self.register()
        self.assertEqual(self.raw(f"/img/{DELVER_ID}/0.jpg")[0], 404)
        self.assertEqual(self.raw(f"/img/{BOLT_ID}/1.jpg")[0], 404)
        self.assertEqual(self.raw("/img/../0.jpg")[0], 404)
        with mock.patch.object(picker, "cached_fetch", return_value=b"JPEG") as fetch:
            status, body = self.raw(f"/img/{BOLT_ID}/0.jpg")
        self.assertEqual((status, body), (200, b"JPEG"))
        self.assertEqual(fetch.call_args[0][0], "https://cards.scryfall.io/b.jpg")


class RunRequest(unittest.TestCase):
    """The exit-code contract agents rely on, against an in-process server."""

    def setUp(self):
        quiet = mock.patch.object(picker.Handler, "log_message", lambda *a: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.server, self.hub = picker.make_server(0, "secret", "v1")
        self.state = {"port": self.server.server_address[1], "token": "secret"}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        for target, value in (("ensure_server", self.state), ("webbrowser", mock.Mock())):
            patch = mock.patch.object(picker, target, return_value=value) if target == "ensure_server" \
                else mock.patch.object(picker, target, value)
            patch.start()
            self.addCleanup(patch.stop)

    def run_main(self, argv, cards=(BOLT, FIRE)):
        def fake_resolve(entries):
            return ([picker.card_view(c) for c in cards],
                    {c["id"]: picker.card_images(c) for c in cards}, picker.scryfall.Report())
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(picker, "resolve_cards", fake_resolve), \
                redirect_stdout(out), redirect_stderr(err):
            code = picker.main(argv)
        return code, out.getvalue(), err.getvalue()

    def answer_when_listed(self, body):
        def go():
            rid = picker.wait_until(lambda: next(iter(self.hub.requests), None), 5, step=0.02)
            self.hub.answer(rid, body)
        t = threading.Thread(target=go)
        t.start()
        self.addCleanup(t.join, 5)

    def test_no_cards(self):
        code, _, err = self.run_main(["pick", "--no-open"])
        self.assertEqual(code, picker.EXIT_INPUT)
        self.assertIn("no cards given", err)

    def test_count_above_found_cards(self):
        code, _, err = self.run_main(["pick", "--cards", "Bolt", "Fire", "--count", "3"])
        self.assertEqual(code, picker.EXIT_INPUT)
        self.assertIn("only 2 cards", err)

    def test_picked(self):
        self.answer_when_listed({"status": "picked", "picked": [1]})
        code, out, err = self.run_main(["pick", "--cards", "Bolt", "Fire", "--no-open"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["picked"][0]["name"], "Fire // Ice")
        self.assertIn("Waiting for the user", err)

    def test_cancelled(self):
        self.answer_when_listed({"status": "cancelled"})
        code, out, _ = self.run_main(["pick", "--cards", "Bolt", "--no-open"])
        self.assertEqual((code, json.loads(out)), (130, {"status": "cancelled"}))

    def test_timeout_withdraws_the_tab(self):
        code, out, _ = self.run_main(["pick", "--cards", "Bolt", "--timeout", "0.3", "--no-open"])
        self.assertEqual((code, json.loads(out)), (124, {"status": "timeout"}))
        self.assertEqual(self.hub.requests, {})

    def test_opens_browser_only_without_a_live_page(self):
        self.hub.browser_seen = time.monotonic()
        self.answer_when_listed({"status": "cancelled"})
        self.run_main(["pick", "--cards", "Bolt"])
        picker.webbrowser.open.assert_not_called()


class CachedFetch(unittest.TestCase):
    def test_refuses_other_hosts(self):
        for url in ("http://169.254.169.254/latest", "https://cards.scryfall.io.evil.com/x.jpg"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                picker.cached_fetch(url, Path("/nonexistent/x"))

    def test_cache_hit_needs_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.jpg"
            path.write_bytes(b"cached")
            with mock.patch.object(picker.urllib.request, "urlopen") as net:
                self.assertEqual(picker.cached_fetch("https://cards.scryfall.io/a.jpg", path), b"cached")
            net.assert_not_called()


if __name__ == "__main__":
    unittest.main()
