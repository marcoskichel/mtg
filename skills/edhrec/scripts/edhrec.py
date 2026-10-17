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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scryfall-cards" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "moxfield-deck" / "scripts"))
import moxfield  # noqa: E402
import scryfall  # noqa: E402

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
    names = ([n for _, n in moxfield.read_card_list(args.deck, moxfield.BOARDS)]
             if args.deck else args.names)
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

    p = sub.add_parser("card", parents=[common], help="play rate, salt, top commanders")
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
