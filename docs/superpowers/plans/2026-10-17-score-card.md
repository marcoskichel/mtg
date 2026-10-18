# score-card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the agent grade any Magic card for Commander, standalone or against a deck profile, from fetched data instead of memory.

**Architecture:** Three pieces, each owned by the skill whose data it reads. A new `edhrec` skill reads EDHREC's JSON pages (play rate, salt, bracket split, themes, pairings). `card-finder` gains a `roles` subcommand that computes ramp/draw/removal/... offline from the Oracle Tags bulk file it already caches. A new `score-card` skill holds `deckprofile.py` (deck facts, fingerprint, staleness) plus the rubric the agent grades with. Scripts gather facts; the agent grades.

**Tech Stack:** Python 3 standard library only. `unittest` with mocked HTTP. Sibling skills imported via `sys.path.insert`, as `card-finder/scripts/finder.py` already does.

**Spec:** `docs/superpowers/specs/2026-10-17-score-card-design.md`

All paths below are relative to the worktree root `/home/kichelm/mtg/.claude/worktrees/feat-score-card-ec6d092a`. Run every command from there.

## Global Constraints

- Standard library only; no `pip install`.
- stdout is the answer; stderr is what changed or failed. Exit 1 whenever the answer is incomplete.
- EDHREC: `https://json.edhrec.com/pages/<path>.json`, browser User-Agent, cache under `~/.cache/mtg-skills/edhrec/`, default TTL 24h, 0.5 s between uncached calls.
- EDHREC not-found = HTTP 403 whose body contains `<Code>AccessDenied</Code>`. Any other 403, and any 429, = blocked → retry ×4 honoring `Retry-After`, then `EDHREC BLOCKED`. Never report blocked as not found.
- Play rate = `num_decks / potential_decks`, printed with both raw numbers; missing `potential_decks` → `n/a`.
- Role list (exact, in order): `ramp, mana-rock, cost-reducer, draw, card-advantage, removal, sweeper, counterspell, protection, tutor, sacrifice-outlet, recursion`.
- Profile fingerprint: SHA-256, first 8 hex chars, over sorted `"<qty> <folded name>"` lines from Commander + Companion + Mainboard only.
- Drift threshold: ≤5 cards changed (added + removed, counting quantity) = `drift`, exit 0; >5, or commanders changed, or bracket changed = `STALE`, exit 1.
- Profile file: `decks/<name>.profile.md`; lock file: `decks/<name>.profile.lock`.
- Verdicts: `STAPLE`, `STRONG`, `PLAYABLE`, `NICHE`, `WEAK`. Grades: `low`, `med`, `high`.
- Commit messages: Conventional Commits, lowercase.
- Deck files are read with `moxfield.parse_deck` (handles `// Commander` headers, `(SET) 123`, `*F*`, `#tags`). Never with `scryfall.parse_input`: it skips `//` lines, so it loses section headers, and it keeps `#tag` in the card name.

## Review Focus

1. A real deck file from `decks/` (with `// Commander` header, `(SET) 123`, `#tags`, Portuguese metadata keys) passed to `edhrec.py card -d` or `finder.py roles -d` → every card name resolves cleanly; no `#ramp` glued to a name. Test in Task 2 and Task 3.
2. EDHREC answers 403 with a Cloudflare HTML page (not the S3 AccessDenied XML) → treated as blocked and retried, never cached as not-found. Test in Task 1.
3. A not-found EDHREC page is cached, so a second run over the same pool doesn't re-hit EDHREC for it; a blocked one is not cached. Test in Task 1.
4. Profile for a deck whose Commander line carries printing and tags (`1 Saruman, the White Hand (LTC) 8 #cmd`) → commander compared by name only; re-tagging or reprinting never makes the profile stale. Test in Task 4.
5. Deck with a double-faced card written `Delver of Secrets // Insectile Aberration` → roles resolve through the front face; EDHREC slug uses the front face. Test in Task 1 (slug) and Task 3 (roles).

---

## File Structure

```
skills/edhrec/
  SKILL.md                       when/how to read EDHREC, traps
  scripts/edhrec.py              slug, fetch+cache, page extractors, CLI
  tests/test_edhrec.py
skills/card-finder/
  scripts/finder.py              + ROLES, card_roles(), cmd_roles, "roles" subparser
  tests/test_finder.py           + roles tests
  SKILL.md                       + "Roles of a card or deck" section
skills/score-card/
  SKILL.md                       scoring flow: single card, pool, freshness
  references/rubric.md           factors, bracket weights, verdicts, flags, examples
  scripts/deckprofile.py             profile file I/O, fingerprint, freshness, facts, CLI
  tests/test_profile.py
AGENTS.md                        list the new skills
```

---

### Task 1: edhrec core — slug, fetch, cache

**Files:**
- Create: `skills/edhrec/scripts/edhrec.py`
- Test: `skills/edhrec/tests/test_edhrec.py`

**Interfaces:**
- Produces:
  - `slug(name: str, layout: str | None = None) -> str`
  - `pair_slug(a: str, b: str) -> str`
  - `class Blocked(RuntimeError)`
  - `fetch(path: str, ttl_hours: float = 24) -> tuple[dict | None, float]` — `(page, fetched_epoch)`; `page is None` means not found. Raises `Blocked`.
  - module globals `CACHE_DIR: Path`, `DELAY: list[float]` (`[0.5]`), `BASE = "https://json.edhrec.com/pages/"`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/edhrec/tests -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'edhrec'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Commander data from EDHREC's JSON pages.

EDHREC has no public API. json.edhrec.com/pages/<path>.json is what the site
itself loads; it answers a browser User-Agent. A missing page is HTTP 403 with
S3's AccessDenied XML, not 404; any other 403 or a 429 is Cloudflare blocking
us, and must never be reported as "no such card".
"""

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://json.edhrec.com/pages/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
CACHE_DIR = Path.home() / ".cache" / "mtg-skills" / "edhrec"
DELAY = [0.5]
RETRIES = 4
NOT_FOUND_MARK = b"<Code>AccessDenied</Code>"
# Layouts whose EDHREC page names both halves; every other "A // B" uses A.
BOTH_HALVES = {"split", "aftermath"}

_last_call = [0.0]


class Blocked(RuntimeError):
    """EDHREC refused the request (Cloudflare 403 or 429) after retries."""


def slug(name, layout=None):
    name = html.unescape(name or "")
    if "//" in name:
        halves = [h.strip() for h in name.split("//")]
        name = " ".join(halves) if layout in BOTH_HALVES else halves[0]
    name = name.replace("Æ", "Ae").replace("æ", "ae")
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = re.sub(r"['’,]", "", name.lower())
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def pair_slug(a, b):
    return "-".join(sorted([slug(a), slug(b)]))


def _cache_file(path):
    return CACHE_DIR / (path.strip("/") + ".json")


def _read_cache(path, ttl_hours):
    f = _cache_file(path)
    if not f.exists():
        return None
    try:
        entry = json.loads(f.read_text())
    except ValueError:
        return None
    if time.time() - entry.get("fetched", 0) > ttl_hours * 3600:
        return None
    return entry


def _write_cache(path, page):
    f = _cache_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    entry = {"fetched": time.time(), "page": page}
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry))
    tmp.replace(f)
    return entry


def fetch(path, ttl_hours=24):
    """(page, fetched_epoch). page None = EDHREC has no such page. Raises Blocked."""
    cached = _read_cache(path, ttl_hours)
    if cached is not None:
        return cached["page"], cached["fetched"]
    req = urllib.request.Request(BASE + path.strip("/") + ".json",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    wait = 2.0
    for attempt in range(RETRIES + 1):
        gap = DELAY[0] - (time.monotonic() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        _last_call[0] = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.loads(resp.read().decode("utf-8", "replace"))
            entry = _write_cache(path, page)
            return entry["page"], entry["fetched"]
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            if exc.code == 403 and NOT_FOUND_MARK in body:
                entry = _write_cache(path, None)
                return None, entry["fetched"]
            if exc.code not in (403, 429):
                raise
            if attempt == RETRIES:
                raise Blocked(f"EDHREC refused {path} (HTTP {exc.code}) after {RETRIES} retries")
            ra = exc.headers.get("Retry-After") if exc.headers else None
            try:
                pause = float(ra) if ra else wait
            except ValueError:
                pause = wait
            print(f"warning: HTTP {exc.code} from EDHREC; waiting {pause:.0f}s", file=sys.stderr)
            time.sleep(pause)
            wait *= 2
    raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/edhrec/tests -v`
Expected: 13 tests, OK

- [ ] **Step 5: Commit**

```bash
git add skills/edhrec/scripts/edhrec.py skills/edhrec/tests/test_edhrec.py
git commit -m "feat(edhrec): add page fetch with cache and blocked/not-found split"
```

---

### Task 2: edhrec extractors, CLI and SKILL.md

**Files:**
- Modify: `skills/edhrec/scripts/edhrec.py` (append below `fetch`)
- Modify: `skills/edhrec/tests/test_edhrec.py` (append test classes)
- Create: `skills/edhrec/SKILL.md`

**Interfaces:**
- Consumes: `slug`, `pair_slug`, `fetch`, `Blocked` (Task 1); `scryfall.resolve_names(names, report) -> (found: {folded_key: card}, wanted: {folded_key: name})`, `scryfall.Report`, `scryfall.fold`, `scryfall.front_face` from `skills/scryfall-cards/scripts/scryfall.py`; `moxfield.parse_deck(text) -> ({board: [Card]}, meta)` from `skills/moxfield-deck/scripts/moxfield.py`.
- Produces:
  - `card_stats(page: dict) -> dict` with keys `name, decks, potential, play_rate (float|None), salt, top_commanders (list[str]), themes (list[str])`
  - `commander_stats(page: dict) -> dict` with keys `name, decks, rank, salt, bracket_counts (dict[str,int]), themes (list[tuple[str,int]])`
  - `list_names(page: dict, header: str | None = None) -> list[tuple[str, int]]` — `(name, num_decks)` from `cardlists`
  - `deck_names(path: str) -> list[str]` — names from a deck file or loose list
  - `main(argv=None) -> int`

- [ ] **Step 1: Write the failing tests** (append to `test_edhrec.py`, before `if __name__`)

```python
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
        self.assertEqual(s["themes"], ["Aristocrats"])

    def test_card_stats_missing_potential(self):
        page = json.loads(json.dumps(CARD_PAGE))
        del page["container"]["json_dict"]["card"]["potential_decks"]
        self.assertIsNone(edhrec.card_stats(page)["play_rate"])

    def test_commander_stats(self):
        s = edhrec.commander_stats(CMDR_PAGE)
        self.assertEqual(s["bracket_counts"]["5"], 4120)
        self.assertEqual(s["themes"], [("Combo", 657)])
        self.assertEqual(s["rank"], 192)

    def test_list_names_by_header(self):
        self.assertEqual(edhrec.list_names(THEME_PAGE, "Top Commanders"),
                         [("Niv-Mizzet, Ghost Counsel", 45), ("Edgar, Ancient Bloodlord", 12)])
        self.assertEqual(len(edhrec.list_names(THEME_PAGE)), 3)


class DeckNamesTest(unittest.TestCase):
    def test_moxfield_file_with_headers_printings_tags(self):
        text = ("// Moxfield: https://moxfield.com/decks/x\n// Nome: Test\n// Bracket: 3\n\n"
                "// Commander\n1 Saruman, the White Hand (LTC) 8 #cmd\n\n"
                "// Mainboard\n1 Sol Ring (CMM) 410 *F* #ramp\n"
                "1 Ash Barrens (PLST) CM2-235\n"
                "1 Delver of Secrets // Insectile Aberration\n")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
        self.addCleanup(Path(f.name).unlink)
        self.assertEqual(edhrec.deck_names(f.name),
                         ["Saruman, the White Hand", "Sol Ring", "Ash Barrens",
                          "Delver of Secrets // Insectile Aberration"])

    def test_bare_names_without_quantity(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("Sol Ring\nBlood Artist\n\n2 Swamp\n")
        self.addCleanup(Path(f.name).unlink)
        self.assertEqual(edhrec.deck_names(f.name), ["Sol Ring", "Blood Artist", "Swamp"])


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
            wanted = {edhrec.scryfall.fold(edhrec.scryfall.front_face(n)): n for n in names}
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/edhrec/tests -v`
Expected: new tests ERROR with `AttributeError: module 'edhrec' has no attribute 'card_stats'` (and `scryfall`, `deck_names`, `main`)

- [ ] **Step 3: Write the implementation**

Add below the existing imports in `edhrec.py`:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scryfall-cards" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "moxfield-deck" / "scripts"))
import moxfield  # noqa: E402
import scryfall  # noqa: E402
```

Append below `fetch`:

```python
# Color identity letters -> the guild/shard/wedge name EDHREC uses in tag paths.
COLOR_NAMES = {
    "w": "mono-white", "u": "mono-blue", "b": "mono-black", "r": "mono-red", "g": "mono-green",
    "c": "colorless",
    "wu": "azorius", "ub": "dimir", "br": "rakdos", "rg": "gruul", "gw": "selesnya",
    "wb": "orzhov", "ur": "izzet", "bg": "golgari", "rw": "boros", "gu": "simic",
    "wub": "esper", "ubr": "grixis", "brg": "jund", "rgw": "naya", "gwu": "bant",
    "wbg": "abzan", "urw": "jeskai", "bgu": "sultai", "rwb": "mardu", "gur": "temur",
    "wubr": "yore-tiller", "ubrg": "glint-eye", "brgw": "dune-brood", "rgwu": "ink-treader",
    "gwub": "witch-maw", "wubrg": "five-color",
}
WUBRG = "wubrg"


def color_name(letters):
    """'bw' / 'wb' / 'esper' -> EDHREC's name; order of letters doesn't matter."""
    key = letters.lower()
    if key in COLOR_NAMES.values():
        return key
    letters = "".join(sorted(set(key), key=WUBRG.index)) if set(key) <= set(WUBRG) else key
    for k, v in COLOR_NAMES.items():
        if sorted(k, key=lambda c: WUBRG.index(c) if c in WUBRG else 9) == list(letters):
            return v
    raise ValueError(f"unknown colors: {letters}")


def _json_dict(page):
    return (page or {}).get("container", {}).get("json_dict", {})


def list_names(page, header=None):
    out = []
    for cl in _json_dict(page).get("cardlists") or []:
        if header and cl.get("header") != header:
            continue
        out += [(v.get("name"), v.get("num_decks") or 0) for v in cl.get("cardviews") or []]
    return out


def card_stats(page):
    c = _json_dict(page).get("card") or {}
    decks, potential = c.get("num_decks"), c.get("potential_decks")
    themes = [t.get("value") for t in (page.get("panels") or {}).get("taglinks") or []]
    return {
        "name": c.get("name"), "decks": decks, "potential": potential,
        "play_rate": decks / potential if decks is not None and potential else None,
        "salt": c.get("salt"),
        "top_commanders": [n for n, _ in list_names(page, "Top Commanders")][:5],
        "themes": themes[:8],
    }


def commander_stats(page):
    c = _json_dict(page).get("card") or {}
    tags = page.get("tag_counts") or (page.get("panels") or {}).get("taglinks") or []
    return {
        "name": c.get("name"), "decks": c.get("num_decks"), "rank": c.get("rank"),
        "salt": c.get("salt"), "bracket_counts": page.get("bracket_counts") or {},
        "themes": [(t.get("value"), t.get("count")) for t in tags][:10],
    }


def deck_names(path):
    """Names from a deck file (Moxfield syntax, headers, tags) or a loose list.

    Lines without a quantity count as 1. Uses moxfield.parse_deck, never
    scryfall.parse_input: that one skips `//` headers and keeps `#tags` in names.
    """
    text = Path(path).read_text() if path != "-" else sys.stdin.read()
    fixed = []
    for ln in text.splitlines():
        s = ln.strip()
        if s and not s.startswith("//") and not moxfield.LINE_RE.match(s) \
                and s.rstrip(":").lower() not in moxfield.SECTION_HEADERS:
            s = "1 " + s
        fixed.append(s)
    boards, _ = moxfield.parse_deck("\n".join(fixed))
    names = []
    for b in moxfield.BOARDS:
        for c in boards[b]:
            if c.name not in names:
                names.append(c.name)
    return names


def _fmt_int(n):
    return f"{n:,}" if isinstance(n, int) else "?"


def _age(epoch):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch)) if epoch else "?"


def _resolve(names):
    report = scryfall.Report()
    found, wanted = scryfall.resolve_names(names, report)
    report.emit()
    cards = [found[k] for k in wanted if k in found]
    return cards, bool(report.missing)


def _report_blocked(blocked):
    for path, msg in blocked:
        print(f"EDHREC BLOCKED: {path} — {msg}. Run again later; this is not "
              f"'card not on EDHREC'.", file=sys.stderr)


def cmd_card(args):
    names = deck_names(args.deck) if args.deck else args.names
    cards, missing = _resolve(names)
    rows, blocked = [], []
    for card in cards:
        path = "cards/" + slug(card["name"], card.get("layout"))
        try:
            page, fetched = fetch(path, args.ttl)
        except Blocked as exc:
            blocked.append((path, str(exc)))
            continue
        stats = card_stats(page) if page else None
        rows.append({"name": card["name"], "edhrec": stats, "fetched": fetched, "path": path})
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        for r in rows:
            s = r["edhrec"]
            if not s:
                print(f"{r['name']}: no EDHREC page ({r['path']})")
                continue
            rate = (f"play rate {s['play_rate']:.1%} ({_fmt_int(s['decks'])} / "
                    f"{_fmt_int(s['potential'])})" if s["play_rate"] is not None
                    else f"play rate n/a ({_fmt_int(s['decks'])} decks)")
            salt = f"salt {s['salt']:.2f}" if s["salt"] is not None else "salt n/a"
            print(f"{r['name']}: {rate}, {salt}")
            if s["top_commanders"]:
                print(f"  top commanders: {', '.join(s['top_commanders'])}")
            if s["themes"]:
                print(f"  themes: {', '.join(s['themes'])}")
            print(f"  fetched {_age(r['fetched'])}")
    _report_blocked(blocked)
    return 1 if missing or blocked else 0


def cmd_commander(args):
    cards, missing = _resolve(args.names)
    if missing or not cards:
        return 1
    names = [c["name"] for c in cards]
    path = "commanders/" + (pair_slug(*names) if len(names) == 2
                            else slug(names[0], cards[0].get("layout")))
    try:
        page, fetched = fetch(path, args.ttl)
    except Blocked as exc:
        _report_blocked([(path, str(exc))])
        return 1
    if not page:
        print(f"{' + '.join(names)}: no EDHREC page ({path})")
        return 0
    s = commander_stats(page)
    if args.json:
        print(json.dumps(s, indent=2, ensure_ascii=False))
        return 0
    salt = f"salt {s['salt']:.2f}" if s["salt"] is not None else "salt n/a"
    print(f"{s['name']}: {_fmt_int(s['decks'])} decks, rank {s['rank']}, {salt}")
    total = sum(s["bracket_counts"].values()) or 0
    for b in sorted(s["bracket_counts"], reverse=True):
        n = s["bracket_counts"][b]
        print(f"  bracket {b}: {_fmt_int(n)}" + (f" ({n / total:.0%})" if total else ""))
    if s["themes"]:
        print("  themes: " + ", ".join(f"{v} ({_fmt_int(c)})" for v, c in s["themes"]))
    print(f"  fetched {_age(fetched)}")
    return 0


def cmd_theme(args):
    path = "tags/" + slug(args.theme)
    if args.colors:
        try:
            path += "/" + color_name(args.colors)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    try:
        page, fetched = fetch(path, args.ttl)
    except Blocked as exc:
        _report_blocked([(path, str(exc))])
        return 1
    if not page:
        print(f"no EDHREC theme page {path} — check the theme name on edhrec.com/tags",
              file=sys.stderr)
        return 1
    rows = list_names(page, "Top Commanders")[:args.limit]
    if args.json:
        print(json.dumps([{"name": n, "decks": d} for n, d in rows], indent=2,
                         ensure_ascii=False))
        return 0
    for n, d in rows:
        print(f"{_fmt_int(d):>8}  {n}")
    print(f"  fetched {_age(fetched)}", file=sys.stderr)
    return 0


def cmd_partners(args):
    cards, missing = _resolve([args.name])
    if missing or not cards:
        return 1
    path = "partners/" + slug(cards[0]["name"], cards[0].get("layout"))
    try:
        page, fetched = fetch(path, args.ttl)
    except Blocked as exc:
        _report_blocked([(path, str(exc))])
        return 1
    if not page:
        print(f"{cards[0]['name']}: no pairings page on EDHREC ({path})")
        return 0
    rows = list_names(page)[:args.limit]
    if args.json:
        print(json.dumps([{"name": n, "decks": d} for n, d in rows], indent=2,
                         ensure_ascii=False))
        return 0
    for n, d in rows:
        print(f"{_fmt_int(d):>8}  {n}")
    print(f"  fetched {_age(fetched)}", file=sys.stderr)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Commander data from EDHREC.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON on stdout")
    common.add_argument("--ttl", type=float, default=24, metavar="HOURS",
                        help="cache age limit in hours (default 24; 0 = fetch now)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("card", parents=[common], help="play rate, salt, top commanders, themes")
    p.add_argument("names", nargs="*")
    p.add_argument("-d", "--deck", metavar="FILE", help="deck file or list ('-' = stdin)")
    p.set_defaults(fn=cmd_card)

    p = sub.add_parser("commander", parents=[common],
                       help="decks, rank, salt, bracket split, themes (two names = pair)")
    p.add_argument("names", nargs="+")
    p.set_defaults(fn=cmd_commander)

    p = sub.add_parser("theme", parents=[common], help="top commanders for a theme")
    p.add_argument("theme")
    p.add_argument("--colors", help="color letters or name: wb, esper, mono-black")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_theme)

    p = sub.add_parser("partners", parents=[common], help="legal pairings with deck counts")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_partners)

    args = ap.parse_args(argv)
    if args.cmd == "card" and not args.names and not args.deck:
        ap.error("card: give names or -d FILE")
    if args.cmd == "commander" and len(args.names) > 2:
        ap.error("commander: one name, or two for a pair")
    try:
        return args.fn(args)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"NETWORK FAILURE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

Note: `scryfall.Report.emit()` prints `NOT FOUND on Scryfall (N):` for misses; the tests assert on `NOT FOUND`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/edhrec/tests -v`
Expected: all tests OK

- [ ] **Step 5: Write `skills/edhrec/SKILL.md`**

~~~markdown
---
name: edhrec
description: Use when you need Commander popularity or context data for a card or commander — play rate (how many decks that could play a card actually do), salt, which commanders use a card, a commander's deck count, bracket split and themes, top commanders for a theme in some colors, or legal partner pairings — e.g. "how popular is Blood Artist", "what brackets is Edgar played at", "best aristocrats commanders in Orzhov", "who pairs with Tymna". Also the data source for score-card and commander-finder.
---

# EDHREC data

EDHREC has no public API. `json.edhrec.com/pages/<path>.json` is what the site
loads. It counts decks people uploaded: it measures **popularity, not power**.
A card in many decks is well supported, not necessarily strong; precon cards
are inflated because every precon list counts.

```bash
E=skills/edhrec/scripts/edhrec.py
python3 $E card "Blood Artist" "Sol Ring"
python3 $E card -d decks/markov-gang.txt
python3 $E commander "Edgar Markov"
python3 $E commander "Kraum, Ludevic's Opus" "Tymna the Weaver"   # a pair
python3 $E theme aristocrats --colors wb
python3 $E partners "Tymna the Weaver"
```

`--json` on every subcommand; `--ttl 0` fetches fresh (default cache 24h,
`~/.cache/mtg-skills/edhrec/`). Every output says when the data was fetched.

## What the numbers mean

- **play rate** = decks with the card ÷ decks that could play it (right colors).
  Sol Ring 83%, Blood Artist 11%. High = useful in many strategies.
- **salt**: how much players dislike facing the card (0–4).
- **bracket split** (commanders): how many of its decks sit in each bracket 1–5.
  Shows where people actually play it.
- **themes**: EDHREC's tags with deck counts.

## Read stderr

- `EDHREC BLOCKED` (exit 1): Cloudflare refused us after retries. The card may
  well have a page. Run again later with fewer cards; never tell the user the
  card has no EDHREC data.
- `no EDHREC page` on stdout: the page really doesn't exist (new card, never
  played, or a name EDHREC spells differently). Not fatal.
- `NOT FOUND` / `Names adjusted`: name resolution through Scryfall, same as
  `scryfall-cards`.

## Names

Names go through Scryfall first, then become EDHREC slugs: lowercase, no
accents, no apostrophes or commas, `Æ` → `ae`. Double-faced and adventure cards
use the front face; split and aftermath cards use both halves (`fire-ice`).
Pairs join both slugs alphabetically.

## Theme names

`theme` takes EDHREC's tag slug (`aristocrats`, `plus-1-plus-1-counters`,
`lifegain`). A wrong slug answers "no EDHREC theme page" — look up the slug in
a commander's `themes` line or on edhrec.com/tags. `--colors` takes letters in
any order (`bw`, `wb`) or a name (`orzhov`, `esper`).

Pace: 0.5 s between uncached calls. Don't loop over hundreds of commanders
with `--ttl 0`.
~~~

- [ ] **Step 6: Live smoke check**

Run:
```bash
python3 skills/edhrec/scripts/edhrec.py card "Blood Artist" "Sol Ring" "Delver of Secrets // Insectile Aberration" "Fire // Ice"
python3 skills/edhrec/scripts/edhrec.py commander "Tymna the Weaver" "Kraum, Ludevic's Opus"
python3 skills/edhrec/scripts/edhrec.py theme aristocrats --colors bw --limit 5
python3 skills/edhrec/scripts/edhrec.py partners "Tymna the Weaver" --limit 5
python3 skills/edhrec/scripts/edhrec.py card -d decks/saruman.txt > /dev/null; echo "exit $?"
```
Expected: Blood Artist ≈11% play rate; Sol Ring ≈83%; Delver and Fire // Ice have pages; the pair shows bracket 5 as largest; theme lists Orzhov commanders; partners lists Kraum and Thrasios first; deck run exits 0.

- [ ] **Step 7: Commit**

```bash
git add skills/edhrec
git commit -m "feat(edhrec): add card, commander, theme and partners subcommands"
```

---

### Task 3: card-finder `roles`

**Files:**
- Modify: `skills/card-finder/scripts/finder.py` (constants after `LINK_RE`; functions before `main`; subparser inside `main`)
- Modify: `skills/card-finder/tests/test_finder.py` (append)
- Modify: `skills/card-finder/SKILL.md` (append section)

**Interfaces:**
- Consumes: `TagIndex`, `load_tags`, `scryfall.resolve_names`, `scryfall.Report` (existing); `edhrec.deck_names(path) -> list[str]` (Task 2) — imported via `sys.path` from `skills/edhrec/scripts`.
- Produces:
  - `ROLES: tuple[str, ...]` — exactly the Global Constraints list
  - `card_roles(idx: TagIndex, cards: list[dict]) -> dict[str, list[str]]` — card name → roles in `ROLES` order
  - `missing_roles(idx: TagIndex) -> list[str]` — role slugs not found in the index
  - CLI `finder.py roles NAME... | -d FILE [--json]`

- [ ] **Step 1: Write the failing tests** (append to `test_finder.py`, before `if __name__`)

```python
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
```

Add `import tempfile` to the imports at the top of `test_finder.py` if absent.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/card-finder/tests -v`
Expected: new tests ERROR — `AttributeError: module 'finder' has no attribute 'ROLES'`; `roles` is an invalid choice.

- [ ] **Step 3: Write the implementation**

After `import scryfall  # noqa: E402` in `finder.py`:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "edhrec" / "scripts"))
import edhrec  # noqa: E402  (deck_names: Moxfield-syntax deck files and loose lists)
```

After `LINK_RE`:

```python
# What a card does for a deck, as score-card counts it. Slugs are oracle tags;
# each counts its descendants (removal covers removal-creature, ...).
ROLES = ("ramp", "mana-rock", "cost-reducer", "draw", "card-advantage", "removal",
         "sweeper", "counterspell", "protection", "tutor", "sacrifice-outlet",
         "recursion")
```

Before `def main`:

```python
def missing_roles(idx):
    return [r for r in ROLES if idx.resolve(r) is None]


def card_roles(idx, cards):
    """Card name -> roles it carries, in ROLES order. Offline: bulk tag file only."""
    sets = {r: idx.cards(idx.resolve(r)) for r in ROLES if idx.resolve(r)}
    return {c["name"]: [r for r in ROLES if r in sets and c.get("oracle_id") in sets[r]]
            for c in cards}


def cmd_roles(args):
    names = edhrec.deck_names(args.deck) if args.deck else args.names
    idx = TagIndex(load_tags(args.refresh))
    gone = missing_roles(idx)
    if gone:
        print(f"warning: role tags missing from Scryfall's tag file: {', '.join(gone)}",
              file=sys.stderr)
    report = scryfall.Report()
    found, wanted = scryfall.resolve_names(names, report)
    report.emit()
    cards = [found[k] for k in wanted if k in found]
    roles = card_roles(idx, cards)
    counts = {r: sum(1 for v in roles.values() if r in v) for r in ROLES}
    if args.json:
        print(json.dumps({"cards": roles, "counts": counts}, indent=2, ensure_ascii=False))
    else:
        for name, rs in roles.items():
            print(f"{name}: {', '.join(rs) if rs else '(no roles tagged)'}")
        if args.deck:
            print("\ncounts:")
            for r in ROLES:
                print(f"  {r}: {counts[r]}")
    return 1 if report.missing or gone else 0
```

Inside `main`, after the `find` subparser block:

```python
    p = sub.add_parser("roles", parents=[common],
                       help="ramp/draw/removal/... a card or deck carries (offline tag file)")
    p.add_argument("names", nargs="*")
    p.add_argument("-d", "--deck", metavar="FILE", help="deck file or list ('-' = stdin)")
    p.set_defaults(fn=cmd_roles)
```

And after `args = ap.parse_args(argv)`:

```python
    if args.cmd == "roles" and not args.names and not args.deck:
        ap.error("roles: give names or -d FILE")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/card-finder/tests -v`
Expected: all tests OK (old and new)

- [ ] **Step 5: Append to `skills/card-finder/SKILL.md`** (before `## Read stderr`)

~~~markdown
## Roles of a card or deck

`roles` says which of a fixed set of functions each card carries, from the
cached tag file, with no searches:

```bash
python3 $F roles "Blood Artist" "Sol Ring"
python3 $F roles -d decks/markov-gang.txt        # + counts per role
```

Roles: `ramp, mana-rock, cost-reducer, draw, card-advantage, removal, sweeper,
counterspell, protection, tutor, sacrifice-outlet, recursion`. A parent counts
its children (`removal` includes `removal-creature`). `(no roles tagged)` means
nobody tagged it, not that the card does nothing — read its text. score-card
uses these counts to see what a deck lacks.
~~~

- [ ] **Step 6: Live smoke check**

Run:
```bash
python3 skills/card-finder/scripts/finder.py roles "Sol Ring" "Blood Artist" "Swords to Plowshares" "Wrath of God"
python3 skills/card-finder/scripts/finder.py roles -d decks/saruman.txt | tail -14; echo "exit ${PIPESTATUS[0]}"
```
Expected: Sol Ring → ramp, mana-rock; Swords → removal; Wrath → removal, sweeper (or sweeper only — whatever the tag tree says; note it); deck counts printed, exit 0, no role-missing warning.

- [ ] **Step 7: Commit**

```bash
git add skills/card-finder
git commit -m "feat(card-finder): add roles subcommand computed from the oracle tag file"
```

---

### Task 4: score-card profile core — file format, fingerprint, freshness

**Files:**
- Create: `skills/score-card/scripts/deckprofile.py`
- Test: `skills/score-card/tests/test_profile.py`

**Interfaces:**
- Consumes: `moxfield.parse_deck`, `moxfield.fold`, `moxfield.DECK_BOARDS`.
- Produces:
  - `DRIFT_MAX = 5`
  - `deck_lines(boards: dict) -> list[str]` — sorted `"<qty> <folded name>"` over `DECK_BOARDS`, quantities merged per name
  - `fingerprint(lines: list[str]) -> str` — 8 hex chars
  - `commander_names(boards) -> list[str]` — sorted display names of Commander board
  - `profile_path(deck_path: str) -> Path` — `decks/x.txt` → `decks/x.profile.md`
  - `lock_path(profile: Path) -> Path` — `.profile.md` → `.profile.lock`
  - `read_profile(path) -> tuple[dict, str]` — `(header, body)`; header keys lowercase, values stripped
  - `write_header(path, header: dict) -> None` — rewrites only the `// key: value` block, keeps body byte-for-byte
  - `freshness(header: dict, lock_lines: list[str] | None, boards: dict, meta: dict) -> tuple[str, str, list[str], list[str]]` — `(status, reason, added, removed)`; status ∈ `fresh`, `drift`, `stale`
  - `HEADER_KEYS = ("profile-of", "commanders", "colors", "bracket", "deck-hash", "cards-at-write", "reviewed")`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for deckprofile.py. Run: python3 -m unittest discover -s tests"""

import io
import json
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

    def test_strategy_only_profile_is_fresh(self):
        self.assertEqual(prof.freshness({"bracket": "3"}, None, None, {})[0], "fresh")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/score-card/tests -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'deckprofile'`. (The script is not called `profile.py`: Python's standard library has a `profile` module that would shadow it.)

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Deck profile for score-card: measured facts, fingerprint, staleness.

A profile is <deck>.profile.md: a `// key: value` header plus a strategy the
agent writes (plan, rewards, lacks, avoid). Facts (curve, sources, roles) are
recomputed every run and never stored. The header fingerprints the deck the
strategy was written for, so a changed deck can't be scored against an old
plan without anyone noticing.
"""

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "moxfield-deck" / "scripts"))
import moxfield  # noqa: E402

DRIFT_MAX = 5
HEADER_KEYS = ("profile-of", "commanders", "colors", "bracket", "deck-hash",
               "cards-at-write", "reviewed")


def deck_lines(boards):
    qty = Counter()
    for b in moxfield.DECK_BOARDS:
        for c in boards.get(b) or []:
            qty[moxfield.fold(c.name)] += c.qty
    return sorted(f"{n} {name}" for name, n in qty.items())


def fingerprint(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:8]


def commander_names(boards):
    return sorted(c.name for c in boards.get("commanders") or [])


def profile_path(deck_path):
    p = Path(deck_path)
    return p.with_name(p.stem + ".profile.md")


def lock_path(profile):
    p = Path(profile)
    return p.with_name(p.name[:-len(".profile.md")] + ".profile.lock")


def read_profile(path):
    header, body_lines, in_header = {}, [], True
    for ln in Path(path).read_text().splitlines(keepends=True):
        s = ln.strip()
        if in_header and s.startswith("//") and ":" in s:
            k, v = s[2:].split(":", 1)
            header[k.strip().lower()] = v.strip()
            continue
        in_header = False
        body_lines.append(ln)
    return header, "".join(body_lines)


def write_header(path, header):
    _, body = read_profile(path)
    keys = [k for k in HEADER_KEYS if k in header] + [k for k in header if k not in HEADER_KEYS]
    head = "".join(f"// {k}: {header[k]}\n" for k in keys)
    Path(path).write_text(head + body)


def _multiset(lines):
    out = Counter()
    for ln in lines or []:
        n, name = ln.split(" ", 1)
        out[name] += int(n)
    return out


def freshness(header, lock_lines, boards, meta):
    """(status, reason, added, removed). Strategy-only profiles (no deck) are fresh."""
    if boards is None:
        return "fresh", "strategy-only profile", [], []
    reasons = []
    want_cmd = sorted(x.strip() for x in header.get("commanders", "").split("+") if x.strip())
    have_cmd = commander_names(boards)
    if want_cmd and [moxfield.fold(x) for x in want_cmd] != [moxfield.fold(x) for x in have_cmd]:
        reasons.append(f"commanders changed: {' + '.join(want_cmd)} -> "
                       f"{' + '.join(have_cmd) or 'none'}")
    if header.get("bracket") and str(meta.get("bracket", "")).strip() \
            and header["bracket"] != str(meta["bracket"]).strip():
        reasons.append(f"bracket changed: {header['bracket']} -> {meta['bracket']}")
    lines = deck_lines(boards)
    if fingerprint(lines) == header.get("deck-hash") and not reasons:
        return "fresh", "", [], []
    if lock_lines is None:
        reasons.append("deck changed and no .profile.lock to tell what changed")
        return "stale", "; ".join(reasons), [], []
    old, new = _multiset(lock_lines), _multiset(lines)
    added = sorted((new - old).elements())
    removed = sorted((old - new).elements())
    changed = len(added) + len(removed)
    if changed > DRIFT_MAX:
        reasons.append(f"{changed} cards changed (limit {DRIFT_MAX})")
    if reasons:
        return "stale", "; ".join(reasons), sorted(set(added)), sorted(set(removed))
    return "drift", f"{changed} cards changed", sorted(set(added)), sorted(set(removed))
```

Note: `added`/`removed` returned as distinct sorted names (`set`), so `8 Island → 3 Island` reports `removed == ["island"]` while `changed == 5` counts copies.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/score-card/tests -v`
Expected: all tests OK

- [ ] **Step 5: Commit**

```bash
git add skills/score-card/scripts/deckprofile.py skills/score-card/tests/test_profile.py
git commit -m "feat(score-card): add deck profile fingerprint and staleness check"
```

---

### Task 5: score-card profile CLI — facts, show, new, stamp

**Files:**
- Modify: `skills/score-card/scripts/deckprofile.py` (append)
- Modify: `skills/score-card/tests/test_profile.py` (append)

**Interfaces:**
- Consumes: Task 4 functions; `scryfall.resolve_names`, `scryfall.Report` (`skills/scryfall-cards/scripts`); `finder.TagIndex`, `finder.load_tags`, `finder.card_roles`, `finder.missing_roles`, `finder.ROLES` (`skills/card-finder/scripts`, Task 3).
- Produces:
  - `facts(boards: dict, cards: dict[str, dict], roles: dict[str, list[str]]) -> dict` — keys `commanders, colors, deck_size, curve (dict[int,int], 7 = 7+), avg_mv, sources (dict[str,int] over W U B R G C), role_counts (dict[str,int]), game_changers (list[str])`; `cards` keyed by `moxfield.fold(name)`
  - `format_facts(f: dict) -> str`
  - `STRATEGY_SKELETON: str`
  - `main(argv=None) -> int` with subcommands `show`, `new`, `stamp`

- [ ] **Step 1: Write the failing tests** (append before `if __name__`)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/score-card/tests -v`
Expected: new tests ERROR — `AttributeError: module 'deckprofile' has no attribute 'facts'`

- [ ] **Step 3: Write the implementation** (append to `deckprofile.py`; add imports at top)

Add after `import moxfield  # noqa: E402`:

```python
sys.path.insert(0, str(ROOT / "scryfall-cards" / "scripts"))
sys.path.insert(0, str(ROOT / "card-finder" / "scripts"))
import finder  # noqa: E402
import scryfall  # noqa: E402
```

Append:

```python
COLORS = ("W", "U", "B", "R", "G", "C")
STRATEGY_SKELETON = """
## Plan
<how the deck wins, in two or three sentences>

## Rewards
<what the deck wants more of: card types, events, resources>

## Lacks
<roles the deck is short on; check the role counts above>

## Avoid
<house rules and things that don't fit, e.g. infinite combos>
"""


def load_cards(boards):
    """(cards keyed by folded name, roles by card name, missing names)."""
    names = [c.name for b in moxfield.DECK_BOARDS for c in boards.get(b) or []]
    report = scryfall.Report()
    found, wanted = scryfall.resolve_names(names, report)
    report.emit()
    cards = {moxfield.fold(wanted[k]): found[k] for k in wanted if k in found}
    idx = finder.TagIndex(finder.load_tags())
    gone = finder.missing_roles(idx)
    if gone:
        print(f"warning: role tags missing: {', '.join(gone)}", file=sys.stderr)
    roles = finder.card_roles(idx, list(cards.values()))
    return cards, roles, list(report.missing)


def facts(boards, cards, roles):
    curve, sources, role_counts = Counter(), Counter(), Counter()
    size = mv_total = nonlands = 0
    gcs = []
    for b in moxfield.DECK_BOARDS:
        for c in boards.get(b) or []:
            size += c.qty
            card = cards.get(moxfield.fold(c.name))
            if not card:
                continue
            for color in card.get("produced_mana") or []:
                if color in COLORS:
                    sources[color] += c.qty
            if card.get("game_changer"):
                gcs.append(card["name"])
            for r in roles.get(card["name"], []):
                role_counts[r] += c.qty
            # Front face decides: a spell // land MDFC counts as a spell.
            front_type = (card.get("type_line") or "").split("//")[0].split("—")[0]
            if "Land" in front_type:
                continue
            mv = int(card.get("cmc") or 0)
            curve[min(mv, 7)] += c.qty
            mv_total += mv * c.qty
            nonlands += c.qty
    colors = set()
    for c in boards.get("commanders") or []:
        card = cards.get(moxfield.fold(c.name))
        colors |= set((card or {}).get("color_identity") or [])
    return {
        "commanders": commander_names(boards),
        "colors": "".join(x.lower() for x in "WUBRG" if x in colors),
        "deck_size": size,
        "curve": dict(sorted(curve.items())),
        "avg_mv": mv_total / nonlands if nonlands else 0.0,
        "sources": {k: sources[k] for k in COLORS if sources[k]},
        "role_counts": {r: role_counts[r] for r in finder.ROLES},
        "game_changers": sorted(gcs),
    }


def format_facts(f):
    curve = "  ".join(f"{'7+' if k == 7 else k}:{v}" for k, v in f["curve"].items())
    out = [
        f"commanders: {' + '.join(f['commanders']) or '(none)'}",
        f"colors: {f['colors'] or '(unknown)'}",
        f"deck size: {f['deck_size']}",
        f"curve (non-land): {curve}   avg mv {f['avg_mv']:.2f}",
        "sources: " + "  ".join(f"{k}:{v}" for k, v in f["sources"].items()),
        "roles: " + "  ".join(f"{r}:{n}" for r, n in f["role_counts"].items()),
        f"game changers ({len(f['game_changers'])}): {', '.join(f['game_changers']) or '-'}",
    ]
    return "\n".join(out)


def _read_deck(path):
    return moxfield.parse_deck(Path(path).read_text())


def _lock_lines(profile):
    lp = lock_path(profile)
    return lp.read_text().splitlines() if lp.exists() else None


def _deck_header(deck_path, boards, meta, f):
    return {
        "profile-of": str(deck_path),
        "commanders": " + ".join(commander_names(boards)),
        "colors": f["colors"],
        "bracket": str(meta.get("bracket", "")).strip() or "?",
        "deck-hash": fingerprint(deck_lines(boards)),
        "cards-at-write": str(f["deck_size"]),
        "reviewed": time.strftime("%Y-%m-%d"),
    }


def cmd_show(args):
    target = Path(args.path)
    if target.name.endswith(".profile.md"):
        profile = target
        header, body = read_profile(profile)
        deck_path = header.get("profile-of")
    else:
        deck_path, profile = target, profile_path(target)
        header, body = read_profile(profile) if profile.exists() else ({}, None)
    code = 0
    boards = meta = None
    if deck_path:
        boards, meta = _read_deck(deck_path)
        if not boards.get("commanders"):
            print("warning: deck has no commander; profile uses colors and strategy only",
                  file=sys.stderr)
        cards, roles, missing = load_cards(boards)
        f = facts(boards, cards, roles)
        print(format_facts(f) if not args.json else json.dumps(f, indent=2))
        code = 1 if missing else 0
    if body is None:
        print(f"NO PROFILE — run: deckprofile.py new --deck {deck_path}", file=sys.stderr)
        return 1
    status, reason, added, removed = freshness(header, _lock_lines(profile), boards, meta or {})
    print(f"\nprofile: {profile}")
    for k in HEADER_KEYS:
        if k in header:
            print(f"  {k}: {header[k]}")
    print(f"status: {status}" + (f" ({reason})" if reason else ""))
    for n in added:
        print(f"  + {n}")
    for n in removed:
        print(f"  - {n}")
    print(body.rstrip())
    if status == "stale":
        print(f"PROFILE STALE: {reason}. Review the strategy against the current deck, "
              f"then run: deckprofile.py stamp {profile}", file=sys.stderr)
        return 1
    if status == "drift":
        print(f"warning: profile drift ({reason}); check whether the changed cards shift "
              "the plan", file=sys.stderr)
    return code


def cmd_new(args):
    if args.deck:
        out = Path(args.output) if args.output else profile_path(args.deck)
    else:
        if not args.output:
            print("new without --deck needs -o PATH.profile.md", file=sys.stderr)
            return 2
        out = Path(args.output)
    if out.exists():
        print(f"{out} exists; edit it, or run stamp after reviewing", file=sys.stderr)
        return 1
    if args.deck:
        boards, meta = _read_deck(args.deck)
        cards, roles, missing = load_cards(boards)
        f = facts(boards, cards, roles)
        header = _deck_header(args.deck, boards, meta, f)
        if args.bracket:
            header["bracket"] = str(args.bracket)
        lock_path(out).write_text("\n".join(deck_lines(boards)) + "\n")
        intro = ""
    else:
        header = {"bracket": str(args.bracket), "reviewed": time.strftime("%Y-%m-%d")}
        if args.commander:
            header["commanders"] = " + ".join(args.commander)
        if args.colors:
            header["colors"] = args.colors.lower()
        intro = f"\nStrategy: {args.strategy}\n" if args.strategy else ""
        missing = []
    out.write_text("".join(f"// {k}: {v}\n" for k, v in header.items())
                   + intro + STRATEGY_SKELETON)
    print(f"wrote {out} — fill in the strategy sections, then run: deckprofile.py stamp {out}")
    return 1 if missing else 0


def cmd_stamp(args):
    profile = Path(args.profile)
    header, _ = read_profile(profile)
    deck_path = header.get("profile-of")
    header["reviewed"] = time.strftime("%Y-%m-%d")
    if deck_path:
        boards, meta = _read_deck(deck_path)
        lines = deck_lines(boards)
        header["deck-hash"] = fingerprint(lines)
        header["commanders"] = " + ".join(commander_names(boards))
        header["cards-at-write"] = str(sum(int(ln.split(" ", 1)[0]) for ln in lines))
        if str(meta.get("bracket", "")).strip():
            header["bracket"] = str(meta["bracket"]).strip()
        lock_path(profile).write_text("\n".join(lines) + "\n")
    write_header(profile, header)
    print(f"stamped {profile}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deck profile for score-card.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="facts + strategy + freshness")
    p.add_argument("path", help="deck file or .profile.md")
    p.add_argument("--json", action="store_true", help="facts as JSON")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("new", help="create a profile with an empty strategy")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--deck", help="deck file in decks/")
    src.add_argument("--commander", action="append", help="commander name (twice for a pair)")
    src.add_argument("--strategy", help="strategy in words, no deck yet")
    p.add_argument("--colors", help="color letters, e.g. wb (strategy profiles)")
    p.add_argument("--bracket", type=int, choices=range(1, 6))
    p.add_argument("-o", "--output", help="profile path (default: next to --deck)")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("stamp", help="mark the strategy as reviewed for the current deck")
    p.add_argument("profile")
    p.set_defaults(fn=cmd_stamp)

    args = ap.parse_args(argv)
    if args.cmd == "new" and not args.deck and args.bracket is None:
        ap.error("new: --bracket is required without --deck")
    try:
        return args.fn(args)
    except FileNotFoundError as exc:
        print(f"file not found: {exc.filename}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as exc:
        print(f"NETWORK FAILURE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/score-card/tests -v`
Expected: all tests OK

- [ ] **Step 5: Live smoke check**

Run:
```bash
P=skills/score-card/scripts/deckprofile.py
cp decks/saruman.txt /tmp/claude-1000/sc-saruman.txt
python3 $P show /tmp/claude-1000/sc-saruman.txt; echo "exit $?"
python3 $P new --deck /tmp/claude-1000/sc-saruman.txt && python3 $P show /tmp/claude-1000/sc-saruman.txt | tail -15
rm /tmp/claude-1000/sc-saruman*
```
Expected: first `show` prints deck size 100, a curve, sources, role counts, then `NO PROFILE`, exit 1. After `new`, `status: fresh`. (Run on a copy so no profile lands in `decks/`.)

- [ ] **Step 6: Commit**

```bash
git add skills/score-card/scripts/deckprofile.py skills/score-card/tests/test_profile.py
git commit -m "feat(score-card): add profile show, new and stamp with measured deck facts"
```

---

### Task 6: score-card rubric, SKILL.md, AGENTS.md, acceptance run

**Files:**
- Create: `skills/score-card/references/rubric.md`
- Create: `skills/score-card/SKILL.md`
- Modify: `AGENTS.md` (first paragraph skill list)

**Interfaces:**
- Consumes: CLIs from Tasks 2, 3, 5 exactly as named: `edhrec.py card`, `finder.py roles`, `scryfall.py card`, `deckprofile.py show|new|stamp`. The spec calls the script `profile.py`; it is `deckprofile.py` because the standard library already has a `profile` module.

- [ ] **Step 1: Write `skills/score-card/references/rubric.md`**

~~~markdown
# Scoring rubric

Grade every factor `low` / `med` / `high` with one line of reason. The reason
quotes or paraphrases the oracle text you just fetched, or names a number from
the data. A grade without a reason is not a grade.

## Factors

| Factor | Standalone: ask | In-deck: adjust |
|---|---|---|
| efficiency | Effect per mana compared with cards doing the same job | Less weight if the profile has cost reducers or a big-mana plan (avg mv ≥ 3.5, ramp ≥ 12); more on a low curve (avg mv ≤ 2.5) |
| speed | Impact the turn it lands: haste, ETB, flash, instant | More at brackets 4–5 and in aggro plans |
| card advantage | Draws or makes value repeatedly | More if role count `draw` + `card-advantage` < 8 |
| resilience | Survives spot removal and wipes; value when it dies | More if the plan depends on the board (tokens, voltron, aristocrats) |
| snowball | Gets worse for opponents every turn it stays | — |
| self-sufficiency | Works alone vs needs specific other cards | Less weight when the deck already has those pieces |
| interaction | Answers opponents' threats | More if `removal` < 8, `sweeper` < 2, or `protection` < 3 |
| usefulness | *Standalone only.* Strategies it fits; play rate from `edhrec.py card` | — |
| fit | *In-deck only.* Matches the profile's Plan and Rewards, the commander's text | — |
| fills gap | *In-deck only.* Covers a role in Lacks or a low role count; diminishing for the Nth copy of a role | — |

Role-count thresholds above are starting points for a 100-card deck; say when
you depart from them and why.

## Bracket emphasis

- **1–3**: fit, resilience, card advantage carry the verdict.
- **4**: speed, efficiency, interaction.
- **5**: speed, efficiency, combo potential; play rate matters less than
  cEDH results (`edhrec.py commander` bracket split, EDHTop16 in a later skill).

## Verdicts

| Verdict | Standalone | In-deck |
|---|---|---|
| `STAPLE` | Belongs in nearly any deck in its colors (play rate ≳ 30% and strong grades) | Auto-include |
| `STRONG` | Clearly good in its natural decks | Clearly worth a slot |
| `PLAYABLE` | Fine filler | Fine; first to cut for an upgrade |
| `NICHE` | Good only in specific strategies | Doesn't fit this deck's plan |
| `WEAK` | Outclassed | Outclassed or works against the plan |

## Flags

Print above the grades. A flag is never averaged away.

- `GAME CHANGER` — `game_changer` from Scryfall; bracket 3 allows up to 3.
- `INFINITE COMBO RISK` — your oracle read finds a two- or three-card infinite
  with commonly played cards. Name the partner cards.
- `OFF-IDENTITY` — outside the profile's colors.
- `BANNED` — `legalities.commander` is not `legal`.
- `PROFILE STALE` — no in-deck score; review the profile first.

## Data vs your read

Always print the `data:` line. When your read disagrees with it (STRONG at 2%
play rate, WEAK at 40%), add a `note:` with the reason: new card, precon
inflation, underplayed, popular for flavor. Don't move grades toward the data.

## Output

```
Blood Artist — in: Markov Gang (bracket 3)
  verdict: STRONG
  efficiency   high  2 mv, triggers on any creature death
  speed        med   no immediate impact
  resilience   low   1/1, dies to anything
  fit          high  deck makes vampire tokens; 4 sac outlets
  fills gap    med   deck already has 2 drain effects
  data: play rate 11.4% (595,488 / 5,217,553), salt 0.69, not a game changer
```

Standalone heading: `Blood Artist — standalone`. Use `usefulness` in place of
`fit` and `fills gap`.

## Worked examples (acceptance)

- Sol Ring standalone → `STAPLE`: efficiency high (1 mv, +2 mana), usefulness
  high (83% play rate, colorless). Flag `GAME CHANGER`.
- Blood Artist standalone → `NICHE`: strong only where creatures die en masse;
  11% play rate.
- Blood Artist in an aristocrats profile → `STRONG`: fit high, fills a drain role.
- A 7+ mv sorcery bomb → efficiency `high` in a cost-reducer / big-mana profile,
  `low` in a low-curve aggro profile. Same card, different deck.
~~~

- [ ] **Step 2: Write `skills/score-card/SKILL.md`**

~~~markdown
---
name: score-card
description: Use when someone asks how good a Magic card is, whether it belongs in a deck, which of several cards is better, or wants a candidate list ranked — "is Blood Artist good", "should I play X in my Edgar deck", "rate these cards", "score this pool for my aristocrats deck", "is this a staple". Grades per factor with reasons, standalone or against a deck profile built from a deck file, a commander, or a strategy.
---

# Scoring cards

A card has no fixed power. Standalone, it's raw power plus how many strategies
it fits. In a deck, the deck sets the weights: mana value matters less in a
deck full of cost reducers than in a low-curve aggro deck. Scripts gather
facts; you grade with `references/rubric.md`. Every grade cites text you
fetched in this session or a number from the data.

```bash
S=skills/scryfall-cards/scripts/scryfall.py
F=skills/card-finder/scripts/finder.py
E=skills/edhrec/scripts/edhrec.py
P=skills/score-card/scripts/deckprofile.py
```

## Pick the context

| User gave | Do |
|---|---|
| Only cards | Standalone |
| A deck file in `decks/` | `$P show decks/x.txt` |
| A Moxfield link | `moxfield-deck`: `pull <url> -o decks/x.txt`, then as above |
| A commander, no list | `$P new --commander "<name>" --bracket N -o decks/<slug>.profile.md` |
| A strategy, no commander | `$P new --strategy "<words>" --colors wb --bracket N -o decks/<slug>.profile.md` |

No bracket given and none in the deck file: ask. It changes the weights.

## The profile

`deckprofile.py show` prints measured facts (curve, average mana value, colored
sources, role counts, game changers) and the strategy from
`<deck>.profile.md`, then a status:

- `fresh` — score.
- `drift (+X −Y)` — score, but read the changed cards first; if one shifts the
  plan, update the strategy and `stamp`.
- `STALE` (exit 1) — do not score in-deck. Read the current deck, rewrite Plan /
  Rewards / Lacks / Avoid, run `$P stamp <profile>`, then `show` again.
- `NO PROFILE` (exit 1) — `$P new --deck <file>`, read the deck's cards
  (`$S card -d <file>`), write the strategy, `stamp`.

Writing the strategy: Plan is how the deck wins; Rewards is what it wants more
of; Lacks comes from the role counts and the plan; Avoid holds house rules
(e.g. no infinite combos for the Markov Gang deck). Keep it short; it is read
on every score.

## One card

1. Profile (in-deck only), as above.
2. `$S card "<name>"` — oracle text, type, cost, legality.
3. `$F roles "<name>"` — ramp, draw, removal...
4. `$E card "<name>"` — play rate, salt, top commanders, themes.
5. Grade each factor with the rubric, print the output block from
   `references/rubric.md`, flags first.

## A pool (dozens to hundreds of cards)

1. Batch: `$S card -d pool.txt`, `$F roles -d pool.txt`, `$E card -d pool.txt`.
2. Drop off-identity and banned cards, and cards with no role and nothing in
   their text that touches the profile's Plan or Rewards. List what you dropped
   and why, in one line each.
3. One line per survivor: `verdict  name — fit tag`.
4. Full rubric block only for cards near the cut line, borderline
   `PLAYABLE`/`STRONG`, or when asked.

## Traps

- **EDHREC counts popularity, not power.** Precon cards are inflated; new cards
  are deflated. When your read and the data disagree, say so in a `note:`.
- **`EDHREC BLOCKED` is not "no data".** Run again later; don't grade
  usefulness as low because the request failed.
- **`(no roles tagged)` is not "does nothing".** Tags lag new sets. Read the text.
- **Bracket 3 allows 3 game changers.** Adding a 4th pushes the deck to bracket 4;
  say so when scoring one into a deck already at 3.
- **Don't edit the deck.** Scoring recommends; changes go through `moxfield-deck`.
~~~

- [ ] **Step 3: Update `AGENTS.md`** — replace the first paragraph's skill list sentence with:

```markdown
Commander deck tooling. Each skill under `skills/` owns one job: `scryfall-cards` reads cards (text, search, printings, rulings), `card-finder` finds cards by what they do (Scryfall oracle tags, every result checked against its text) and lists a card's or deck's roles, `edhrec` reads Commander popularity data (play rate, salt, bracket split, themes, pairings), `score-card` grades a card standalone or against a deck profile, `ligamagic-preco` prices them in BRL, `moxfield-deck` keeps a local decklist as source of truth and syncs it to moxfield.com.
```

- [ ] **Step 4: Run every test suite**

Run:
```bash
for d in edhrec card-finder score-card scryfall-cards moxfield-deck; do
  python3 -m unittest discover -s skills/$d/tests 2>&1 | tail -1
done
```
Expected: five lines of `OK`.

- [ ] **Step 5: Acceptance run (by hand, following SKILL.md)**

Score, following the SKILL.md flow exactly, and keep the outputs for the PR body:

1. `Sol Ring` standalone → expect `STAPLE`, flag `GAME CHANGER`.
2. `Blood Artist` standalone → expect `NICHE`.
3. Create a strategy profile in the scratchpad:
   `python3 $P new --strategy "aristocrats: sacrifice creatures, drain on death" --colors wb --bracket 3 -o /tmp/claude-1000/aristo.profile.md`, fill in Plan/Rewards/Lacks, then score `Blood Artist` against it → expect `STRONG`.
4. Pick a 7+ mv sorcery (e.g. `Rise of the Eldrazi`-era bomb or any `t:sorcery mv>=7` from `$S search`), score it against two scratchpad strategy profiles: "big mana: cost reducers and ramp, cast huge spells" and "low-curve go-wide aggro" → expect efficiency `high` vs `low`.
5. A 30-card pool: `$S search "id<=wb otag:sacrifice-outlet f:commander" --limit 30`, write names to `/tmp/claude-1000/pool.txt` (one per line), run the pool flow against the aristocrats profile.

If any expectation fails, fix the rubric wording (not the expectation) and rerun; record what changed.

- [ ] **Step 6: Commit**

```bash
git add skills/score-card/SKILL.md skills/score-card/references/rubric.md AGENTS.md
git commit -m "feat(score-card): add rubric and scoring skill"
```
