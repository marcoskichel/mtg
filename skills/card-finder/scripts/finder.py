#!/usr/bin/env python3
"""Find Magic cards by what they do, through Scryfall oracle tags.

Three subcommands: tags (which oracle tag names a concept, from the Oracle Tags
bulk file), tag (one tag with its parents and children) and find (a Scryfall
search with every oracle tag validated first, printing the full oracle text
of each result so it can be checked against the request).

Reuses the HTTP, pacing and card formatting of skills/scryfall-cards.
"""

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scryfall-cards" / "scripts"))
import scryfall  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "edhrec" / "scripts"))
import edhrec  # noqa: E402  (deck_names: Moxfield-syntax deck files and loose lists)

CACHE_DIR = Path.home() / ".cache" / "mtg-skills"
TAGS_FILE = CACHE_DIR / "oracle-tags.jsonl.gz"
# Scryfall rebuilds the file daily; tags move slowly, a week is fresh enough.
MAX_AGE = 7 * 24 * 3600

# otag:sweeper, function:"mana rock", -oracletag:ramp. The operator is ':' or '='.
TAG_RE = re.compile(
    r'(?<![\w-])(?P<neg>-?)(?:otag|oracletag|function)[:=]'
    r'(?:"(?P<quoted>[^"]+)"|(?P<bare>[^\s()]+))', re.I)
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")

# What a card does for a deck, as score-card counts it. Slugs are oracle tags;
# each counts its descendants (removal covers removal-creature, ...).
ROLES = ("ramp", "mana-rock", "cost-reducer", "draw", "card-advantage", "removal",
         "sweeper", "counterspell", "protection", "tutor", "sacrifice-outlet",
         "recursion")


def norm(s):
    """Scryfall's tag key: case, hyphens, underscores and spaces don't matter.

    Measured: otag:board-wipe, otag:wrathofgod and otag:"mass removal" all hit
    the sweeper tag through its aliases.
    """
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# --------------------------------------------------------------------------- #
# tag data
# --------------------------------------------------------------------------- #

def _download_tags():
    listing = scryfall.api("/bulk-data")
    if scryfall.is_error(listing):
        raise RuntimeError(f"bulk-data listing failed: {listing.get('details')}")
    entry = next((b for b in listing.get("data") or [] if b.get("type") == "oracle_tags"), None)
    if not entry:
        raise RuntimeError("no oracle_tags entry in /bulk-data")
    uri = entry.get("jsonl_download_uri") or entry.get("download_uri")
    req = urllib.request.Request(uri, headers={"User-Agent": scryfall.UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TAGS_FILE.with_suffix(".tmp")
    tmp.write_bytes(raw)
    tmp.replace(TAGS_FILE)


def load_tags(refresh=False):
    """List of oracle tag objects, from the local cache or a fresh download.

    A failed download with a stale cache uses the stale cache and says so.
    """
    stale = TAGS_FILE.exists() and time.time() - TAGS_FILE.stat().st_mtime > MAX_AGE
    if refresh or not TAGS_FILE.exists() or stale:
        try:
            print("downloading Scryfall oracle tags (~6 MB)...", file=sys.stderr)
            _download_tags()
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            if not TAGS_FILE.exists():
                raise
            print(f"warning: tag download failed ({exc}); using the cached copy "
                  f"from {time.strftime('%Y-%m-%d', time.localtime(TAGS_FILE.stat().st_mtime))}",
                  file=sys.stderr)
    lines = gzip.decompress(TAGS_FILE.read_bytes()).splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]


class TagIndex:
    def __init__(self, tags):
        self.tags = [t for t in tags if t.get("type", "oracle") == "oracle"]
        self.by_id = {t["id"]: t for t in self.tags}
        self.by_key = {}
        for t in self.tags:
            self.by_key.setdefault(norm(t["slug"]), t)
        for t in self.tags:   # aliases never shadow a real slug
            for a in t.get("aliases") or []:
                self.by_key.setdefault(norm(a), t)
        self._cards = {}

    def resolve(self, name):
        return self.by_key.get(norm(name))

    def children(self, tag):
        return [self.by_id[i] for i in tag.get("child_ids") or [] if i in self.by_id]

    def parents(self, tag):
        return [self.by_id[i] for i in tag.get("parent_ids") or [] if i in self.by_id]

    def descendants(self, tag):
        seen, stack = {}, [tag]
        while stack:
            t = stack.pop()
            if t["id"] in seen:
                continue
            seen[t["id"]] = t
            stack.extend(self.children(t))
        return list(seen.values())

    def cards(self, tag):
        """oracle_ids tagged with the tag or any descendant (what otag: matches).

        The bulk file only holds direct taggings: `removal` has none of its own.
        """
        if tag["id"] not in self._cards:
            self._cards[tag["id"]] = {
                g["oracle_id"] for t in self.descendants(tag)
                for g in t.get("taggings") or [] if g.get("oracle_id")}
        return self._cards[tag["id"]]

    def search(self, phrase):
        """Tags ranked by how well slug, aliases, label and description match."""
        key = norm(phrase)
        words = [w for w in re.split(r"[^a-z0-9]+", phrase.lower()) if w]
        ranked = []
        for t in self.tags:
            names = [t["slug"], t.get("label") or ""] + list(t.get("aliases") or [])
            keys = [norm(n) for n in names]
            hay = " ".join(names).lower()
            desc = (t.get("description") or "").lower()
            if key in keys:
                score = 100
            elif key and any(key in k for k in keys):
                score = 70
            elif words and all(w in hay for w in words):
                score = 50
            elif words and all(w in hay or w in desc for w in words):
                score = 30
            else:
                continue
            ranked.append((score, len(self.cards(t)), t))
        ranked.sort(key=lambda r: (-r[0], -r[1], r[2]["slug"]))
        return ranked


def clean_desc(text):
    text = LINK_RE.sub(r"\1", text or "")
    return re.sub(r"\s+", " ", text).strip()


def tag_line(idx, tag):
    aliases = tag.get("aliases") or []
    return (f"{tag['slug']}  ({len(idx.cards(tag))} cards)"
            + (f"  aliases: {', '.join(aliases)}" if aliases else ""))


def query_tags(query):
    """[(written name, negated)] of every oracle tag term in a Scryfall query."""
    return [(m.group("quoted") or m.group("bare"), bool(m.group("neg")))
            for m in TAG_RE.finditer(query)]


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #

def cmd_tags(args):
    idx = TagIndex(load_tags(args.refresh))
    phrase = " ".join(args.terms)
    ranked = idx.search(phrase)
    if not ranked:
        print(f"no oracle tag matches '{phrase}'. Try a synonym, a shorter word, "
              "or search the oracle text with o:", file=sys.stderr)
        return 1
    shown = ranked[:args.limit]
    if args.json:
        json.dump([{"slug": t["slug"], "cards": n, "aliases": t.get("aliases") or [],
                    "description": clean_desc(t.get("description")),
                    "parents": [p["slug"] for p in idx.parents(t)],
                    "children": [c["slug"] for c in idx.children(t)]}
                   for _, n, t in shown], sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    for _, _, t in shown:
        print(tag_line(idx, t))
        rel = []
        if idx.parents(t):
            rel.append("parent: " + ", ".join(p["slug"] for p in idx.parents(t)))
        if idx.children(t):
            kids = [c["slug"] for c in idx.children(t)]
            rel.append(f"children ({len(kids)}): " + ", ".join(kids[:12])
                       + (", ..." if len(kids) > 12 else ""))
        if rel:
            print("  " + "   ".join(rel))
        if t.get("description"):
            print("  " + clean_desc(t["description"])[:220])
    print(f"{len(ranked)} tag(s) match, {len(shown)} shown", file=sys.stderr)
    return 0


def cmd_tag(args):
    idx = TagIndex(load_tags(args.refresh))
    tag = idx.resolve(args.name)
    if not tag:
        print(f"UNKNOWN TAG: {args.name}", file=sys.stderr)
        _suggest(idx, args.name)
        return 1
    if norm(tag["slug"]) != norm(args.name):
        print(f"'{args.name}' is an alias of {tag['slug']}", file=sys.stderr)
    print(tag_line(idx, tag))
    if tag.get("description"):
        print("  " + clean_desc(tag["description"]))
    for p in idx.parents(tag):
        print(f"  parent: {tag_line(idx, p)}")

    def walk(t, depth):
        for c in sorted(idx.children(t), key=lambda c: -len(idx.cards(c))):
            print("  " + "  " * depth + "└ " + tag_line(idx, c))
            if depth + 1 < args.depth:
                walk(c, depth + 1)
    walk(tag, 0)
    return 0


def _suggest(idx, name):
    near = [t["slug"] for _, _, t in idx.search(name)[:8]]
    if not near:
        import difflib
        near = difflib.get_close_matches(norm(name), list(idx.by_key), n=8, cutoff=0.6)
        near = [idx.by_key[k]["slug"] for k in near]
    if near:
        print("  did you mean: " + ", ".join(dict.fromkeys(near)), file=sys.stderr)
    print("  find tags with: finder.py tags <words>", file=sys.stderr)


def cmd_find(args):
    terms = query_tags(args.query)
    idx = None
    wanted = []   # tags whose subtree is reported per card
    if terms:
        try:
            idx = TagIndex(load_tags(args.refresh))
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            print(f"warning: could not load oracle tags ({exc}); tag names NOT "
                  "validated. A misspelled tag returns 'no cards', not an error.",
                  file=sys.stderr)
    if idx:
        unknown = []
        for name, neg in terms:
            tag = idx.resolve(name)
            if not tag:
                unknown.append(name)
            elif not neg:
                wanted.append(tag)
        if unknown:
            # Scryfall answers an unknown tag with 404 "no cards", same as a
            # real tag with no match. Stop before that misleads anyone.
            for name in unknown:
                print(f"UNKNOWN TAG: {name}", file=sys.stderr)
                _suggest(idx, name)
            return 2

    report = scryfall.Report()
    params = {"q": args.query, "unique": "cards"}
    if args.order:
        params["order"] = args.order
    if args.dir:
        params["dir"] = args.dir
    cards, total = [], 0
    resp = scryfall.api("/cards/search", **params)
    while True:
        if scryfall.is_error(resp):
            if resp.get("code") == "not_found":
                print(f"no cards for the query: {args.query}", file=sys.stderr)
                if resp.get("details"):
                    print(f"  {resp['details']}", file=sys.stderr)
                return 1
            print(f"Scryfall error: {resp.get('details')}", file=sys.stderr)
            return 1
        for w in resp.get("warnings") or []:
            if w not in report.warnings:
                report.warnings.append(w)
        total = resp.get("total_cards", 0)
        cards.extend(resp.get("data") or [])
        if not resp.get("has_more") or (not args.all and len(cards) >= args.limit):
            break
        resp = scryfall.api(resp["next_page"])
    if not args.all:
        cards = cards[:args.limit]

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if args.json:
        out = []
        for c in cards:
            d = scryfall.trim_card(c)
            d["matched_tags"] = matched_tags(idx, wanted, c)
            out.append(d)
        json.dump({"total": total, "shown": len(cards), "cards": out},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for c in cards:
            text = scryfall.format_card(c, formats).rstrip("\n")
            hits = matched_tags(idx, wanted, c)
            if hits:
                text += "\n  tagged: " + ", ".join(hits)
            print(text + "\n")
    print(f"{total} card(s) in total, {len(cards)} shown"
          + ("" if args.all or len(cards) >= total else
             ". Use --limit N or --all to see more"), file=sys.stderr)
    report.emit()
    return 1 if report.failed else 0


def matched_tags(idx, wanted, card):
    """The most specific tags under the queried ones that this card carries.

    Says why the card came back (sweeper-one-sided vs plain sweeper), which is
    a hint for reading its text, never a substitute for it.
    """
    if not idx or not wanted:
        return []
    oid = card.get("oracle_id")
    hits = []
    for tag in wanted:
        for t in idx.descendants(tag):
            if any(g.get("oracle_id") == oid for g in t.get("taggings") or []):
                hits.append(t["slug"])
    return list(dict.fromkeys(hits))


# --------------------------------------------------------------------------- #

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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Find Magic cards by function through Scryfall oracle tags.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="emit JSON on stdout instead of text")
    common.add_argument("--refresh", action="store_true",
                        help="download the oracle tag file even if the cache is fresh")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tags", parents=[common], help="oracle tags for a concept")
    p.add_argument("terms", nargs="+", help="words describing the function")
    p.add_argument("--limit", type=int, default=15, metavar="N")
    p.set_defaults(fn=cmd_tags)

    p = sub.add_parser("tag", parents=[common], help="one tag with parents and children")
    p.add_argument("name", help="slug or alias")
    p.add_argument("--depth", type=int, default=1, metavar="N",
                   help="levels of children to show (default 1)")
    p.set_defaults(fn=cmd_tag)

    p = sub.add_parser("find", parents=[common],
                       help="search, validating tags, printing full oracle text")
    p.add_argument("query", help="Scryfall syntax, e.g. 'otag:sweeper id<=wb f:commander'")
    p.add_argument("--order", default="edhrec", metavar="FIELD",
                   help="Scryfall order (default edhrec: most played first)")
    p.add_argument("--dir", choices=("asc", "desc"))
    p.add_argument("--limit", type=int, default=50, metavar="N",
                   help="maximum cards shown (default 50)")
    p.add_argument("--all", action="store_true", help="follow every page")
    p.add_argument("--formats", default="commander",
                   help="legalities to show, comma-separated (default: commander)")
    p.add_argument("--delay", type=float, default=scryfall.DEFAULT_DELAY, metavar="SEC",
                   help=f"pause between calls (default {scryfall.DEFAULT_DELAY})")
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("roles", parents=[common],
                       help="ramp/draw/removal/... a card or deck carries (offline tag file)")
    p.add_argument("names", nargs="*")
    p.add_argument("-d", "--deck", metavar="FILE", help="deck file or list ('-' = stdin)")
    p.set_defaults(fn=cmd_roles)

    args = ap.parse_args(argv)
    if args.cmd == "roles" and not args.names and not args.deck:
        ap.error("roles: give names or -d FILE")
    if getattr(args, "delay", None) is not None:
        scryfall.DELAY[0] = args.delay
    try:
        return args.fn(args)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"network or API failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
