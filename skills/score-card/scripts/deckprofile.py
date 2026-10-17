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
import os
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "moxfield-deck" / "scripts"))
import moxfield  # noqa: E402
sys.path.insert(0, str(ROOT / "scryfall-cards" / "scripts"))
sys.path.insert(0, str(ROOT / "card-finder" / "scripts"))
import finder  # noqa: E402
import scryfall  # noqa: E402

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
    if header.get("bracket") not in (None, "", "?") and str(meta.get("bracket", "")).strip() \
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


def card_key(name):
    """Lookup key for a deck line: Scryfall resolves 'A // B' by its front face."""
    return moxfield.fold(scryfall.front_face(name))


def load_cards(boards):
    """(cards keyed by card_key, roles by card name, missing names)."""
    names = [c.name for b in moxfield.DECK_BOARDS for c in boards.get(b) or []]
    report = scryfall.Report()
    found, wanted = scryfall.resolve_names(names, report)
    report.emit()
    cards = {card_key(wanted[k]): found[k] for k in wanted if k in found}
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
            card = cards.get(card_key(c.name))
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
        card = cards.get(card_key(c.name))
        colors |= set((card or {}).get("color_identity") or [])
    # Command Tower and Arcane Signet list all five colors in produced_mana;
    # only the commander's identity (plus colorless) can actually be made.
    if colors:
        sources = Counter({k: v for k, v in sources.items() if k in colors or k == "C"})
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


def _deck_of(profile, header):
    """Deck path from a profile header; relative paths are relative to the profile."""
    ref = header.get("profile-of")
    return Path(profile).parent / ref if ref else None


def _deck_header(deck_path, profile, boards, meta, f):
    return {
        "profile-of": os.path.relpath(Path(deck_path).resolve(), Path(profile).resolve().parent),
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
        deck_path = _deck_of(profile, header)
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
    if not out.name.endswith(".profile.md"):
        print(f"{out}: a profile file must be named <name>.profile.md", file=sys.stderr)
        return 2
    if out.exists():
        print(f"{out} exists; edit it, or run stamp after reviewing", file=sys.stderr)
        return 1
    if args.deck:
        boards, meta = _read_deck(args.deck)
        declared = str(meta.get("bracket", "")).strip()
        if args.bracket and declared and declared != str(args.bracket):
            print(f"{args.deck} says Bracket: {declared}; --bracket {args.bracket} would make "
                  "the profile stale at once. Change the deck file's Bracket line instead.",
                  file=sys.stderr)
            return 2
        cards, roles, missing = load_cards(boards)
        f = facts(boards, cards, roles)
        header = _deck_header(args.deck, out, boards, meta, f)
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
    deck_path = _deck_of(profile, header)
    header["reviewed"] = time.strftime("%Y-%m-%d")
    if deck_path:
        boards, meta = _read_deck(deck_path)
        lines = deck_lines(boards)
        header["deck-hash"] = fingerprint(lines)
        header["commanders"] = " + ".join(commander_names(boards))
        cmd_boards = {"commanders": boards.get("commanders") or []}
        cards, roles, _ = load_cards(cmd_boards)
        colors = facts(cmd_boards, cards, roles)["colors"]
        if colors:
            header["colors"] = colors
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
