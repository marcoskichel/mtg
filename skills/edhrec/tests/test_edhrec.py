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

    def test_429_retries_then_succeeds(self):
        seq = [http_error(429, b"", {"Retry-After": "10"}), FakeResp({"ok": True})]
        with mock.patch.object(edhrec.urllib.request, "urlopen", side_effect=seq):
            page, _ = edhrec.fetch("cards/sol-ring")
        self.assertEqual(page, {"ok": True})
        edhrec.time.sleep.assert_any_call(10.0)


if __name__ == "__main__":
    unittest.main()
