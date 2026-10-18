#!/usr/bin/env python3
"""Bookkeeping for building a Commander deck in picker rounds.

The build lives in files next to each other in decks/:
  <name>.txt         the deck: Commander + Mainboard are locked in, Maybeboard is
                     the candidate pool (Moxfield Bulk Edit syntax)
  <name>.build.json  targets per role, bracket, budget, pool data, rejected
                     cards, rounds done
  <name>.profile.md  score-card's profile (strategy the agent writes)

Subcommands:
  init    targets from the template, nudged by the commander's EDHREC average deck
  pool    candidates from EDHREC + the average deck + --extra searches -> Maybeboard
  round   shortlist for one round (a role, no-brainers, theme, lands) -> suggestions JSON
  apply   a card-picker answer: picked cards in, the rest of the offer rejected
  status  filled vs target per role, lands, game changers, open slots, budget

Scripts gather and count; the agent reads card text and grades with score-card.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _skill in ("moxfield-deck", "scryfall-cards", "card-finder", "edhrec"):
    sys.path.insert(0, str(ROOT / _skill / "scripts"))
import edhrec  # noqa: E402
import finder  # noqa: E402
import moxfield  # noqa: E402
import scryfall  # noqa: E402

LIGAPRECO = ROOT / "ligamagic-preco" / "scripts" / "ligapreco.py"

# Defaults for a 100-card deck. Each role counts cards carrying any of its tags;
# a card can fill more than one role. Everything else is theme.
TEMPLATE = {"lands": 36, "ramp": 10, "draw": 10, "removal": 8, "sweeper": 3, "protection": 3}
ROLE_TAGS = {"ramp": ("ramp",), "draw": ("draw", "card-advantage"), "removal": ("removal",),
             "sweeper": ("sweeper",), "protection": ("protection",)}
UTILITY_TAGS = {t for tags in ROLE_TAGS.values() for t in tags}
# How far the average deck may move a role target, and the land range.
MAX_SHIFT = 3
LANDS_RANGE = (33, 40)
NO_BRAINER_INCLUSION = 0.5
ROUNDS = ("no-brainers",) + tuple(ROLE_TAGS) + ("theme", "lands")
WUBRG = "WUBRG"


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #

def card_key(name):
    return moxfield.fold(scryfall.front_face(name))


def build_path(deck):
    p = Path(deck)
    return p.with_name(p.stem + ".build.json")


def load_state(deck):
    p = build_path(deck)
    return json.loads(p.read_text()) if p.exists() else None


def save_state(deck, state):
    p = build_path(deck)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(p)


def read_deck(path):
    return moxfield.parse_deck(Path(path).read_text())


def write_deck(path, boards, meta):
    Path(path).write_text(moxfield.render_deck(boards, meta))


def gc_limit(bracket):
    """Game changers allowed: none at 1-2, three at 3, no limit at 4-5."""
    return 0 if bracket <= 2 else 3 if bracket == 3 else None


def adjust_targets(avg_counts, avg_lands):
    """(targets, sources): the template, each role moved toward the average deck
    by at most MAX_SHIFT, lands taken from the average deck within LANDS_RANGE."""
    targets, sources = dict(TEMPLATE), {k: "template" for k in TEMPLATE}
    for role in ROLE_TAGS:
        if avg_counts and role in avg_counts:
            t = TEMPLATE[role]
            targets[role] = max(t - MAX_SHIFT, min(t + MAX_SHIFT, avg_counts[role]))
            sources[role] = "average deck"
    if avg_lands:
        targets["lands"] = max(LANDS_RANGE[0], min(LANDS_RANGE[1], avg_lands))
        sources["lands"] = "average deck"
    return targets, sources


def roles_to_groups(tags):
    return [r for r, rt in ROLE_TAGS.items() if any(t in tags for t in rt)]


def count_roles(entries):
    """entries: [(qty, tags)] -> {role: count}."""
    out = Counter()
    for qty, tags in entries:
        for r in roles_to_groups(tags):
            out[r] += qty
    return {r: out[r] for r in ROLE_TAGS}


def is_land(card):
    return "Land" in (card.get("type_line") or "").split("//")[0].split("—")[0]


def is_basic(card):
    return (card.get("type_line") or "").startswith("Basic Land")


def identity_of(cards):
    colors = set()
    for c in cards:
        colors |= set(c.get("color_identity") or [])
    return "".join(x for x in WUBRG if x in colors)


def fits_identity(card, identity):
    return set(card.get("color_identity") or []) <= set(identity)


def deck_cards(boards, boards_to=moxfield.DECK_BOARDS):
    return [c for b in boards_to for c in boards.get(b) or []]


# --------------------------------------------------------------------------- #
# data (patched in tests)
# --------------------------------------------------------------------------- #

def resolve(names):
    """({card_key: scryfall card}, [unresolved names])."""
    report = scryfall.Report()
    found, wanted = scryfall.resolve_names(names, report)
    report.emit()
    out = {card_key(wanted[k]): found[k] for k in wanted if k in found}
    return out, list(report.missing)


_tag_index = []


def roles_of(cards):
    """{card name: oracle tags from finder.ROLES}, offline from the tag file."""
    if not _tag_index:
        _tag_index.append(finder.TagIndex(finder.load_tags()))
    return finder.card_roles(_tag_index[0], list(cards))


def prices(names):
    """{name: lowest BRL price or None} through ligamagic-preco."""
    if not names:
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("".join(f"1 {n}\n" for n in names))
        path = f.name
    try:
        run = subprocess.run([sys.executable, str(LIGAPRECO), "--json", "-d", path],
                             capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    if not run.stdout.strip():
        print(f"warning: ligamagic-preco gave no output: {run.stderr.strip()[-300:]}",
              file=sys.stderr)
        return {n: None for n in names}
    data = json.loads(run.stdout)
    out = {n: None for n in names}
    for row in data.get("cartas") or []:
        if row.get("status") == "precificado":
            out[row.get("pedido")] = row.get("unitario")
    return out


def _commander_path(commanders):
    if len(commanders) == 2:
        return edhrec.pair_slug(*commanders)
    return edhrec.slug(commanders[0])


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def _need_state(deck):
    state = load_state(deck)
    if state is None:
        print(f"no build for {deck}: run build.py init {deck} first", file=sys.stderr)
    return state


def cmd_init(args):
    boards, meta = read_deck(args.deck)
    commanders = [c.name for c in boards["commanders"]]
    if not commanders:
        print(f"{args.deck} has no // Commander section: add the commander first",
              file=sys.stderr)
        return 2
    bracket = args.bracket or str(meta.get("bracket", "")).strip()
    if not bracket or not str(bracket).isdigit():
        print("no bracket: pass --bracket N (1-5) or add '// Bracket: N' to the deck",
              file=sys.stderr)
        return 2
    bracket = int(bracket)
    if build_path(args.deck).exists() and not args.force:
        print(f"{build_path(args.deck)} exists; pass --force to start the targets over",
              file=sys.stderr)
        return 1
    if str(meta.get("bracket", "")).strip() != str(bracket):
        meta["bracket"] = bracket
        write_deck(args.deck, boards, meta)

    cmd_cards, missing = resolve(commanders)
    identity = identity_of(cmd_cards.values())
    slug = _commander_path(commanders)
    page, _ = edhrec.fetch("average-decks/" + slug)
    avg = edhrec.average_deck(page)
    avg_counts = avg_lands = None
    if avg:
        found, _ = resolve([n for _, n in avg["cards"]])
        tags = roles_of(found.values())
        qty = {card_key(n): q for q, n in avg["cards"]}
        avg_counts = count_roles((qty.get(card_key(c["name"]), 1), tags.get(c["name"], []))
                                 for c in found.values())
        avg_lands = avg["lands"]
    targets, sources = adjust_targets(avg_counts, avg_lands)
    state = {"commanders": commanders, "identity": identity, "bracket": bracket,
             "targets": targets, "target_sources": sources,
             "budget": {"total": args.budget, "card": args.budget_card},
             "pool": {}, "rejected": [], "rounds": []}
    save_state(args.deck, state)
    print(f"targets for {' + '.join(commanders)} (bracket {bracket}, identity "
          f"{identity or 'colorless'}):")
    for k, v in targets.items():
        avg_note = ""
        if sources[k] == "average deck":
            avg_note = f" (average deck: {avg_lands if k == 'lands' else avg_counts[k]})"
        print(f"  {k:<11}{v:>3}  {sources[k]}{avg_note}")
    print(f"  {'theme':<11}  the rest; adjust targets in {build_path(args.deck)}")
    if not avg:
        print(f"note: EDHREC has no average deck for {slug}; template only", file=sys.stderr)
    return 1 if missing else 0


def cmd_pool(args):
    state = _need_state(args.deck)
    if state is None:
        return 2
    boards, meta = read_deck(args.deck)
    taken = {card_key(c.name) for c in deck_cards(boards, moxfield.BOARDS)}
    rejected = {card_key(n) for n in state["rejected"]}

    found_rows = {}
    slug = _commander_path(state["commanders"])
    page, _ = edhrec.fetch("commanders/" + slug)
    for row in edhrec.commander_cards(page) if page else []:
        found_rows.setdefault(row["name"], {"inclusion": row["inclusion"],
                                            "synergy": row["synergy"], "sources": ["edhrec"]})
    avg = edhrec.average_deck(edhrec.fetch("average-decks/" + slug)[0])
    for _, name in avg["cards"] if avg else []:
        found_rows.setdefault(name, {"inclusion": None, "synergy": None, "sources": []})
        if "average" not in found_rows[name]["sources"]:
            found_rows[name]["sources"].append("average")
    if args.extra:
        for _, name in moxfield.read_card_list(args.extra, moxfield.BOARDS):
            found_rows.setdefault(name, {"inclusion": None, "synergy": None, "sources": []})
            if "search" not in found_rows[name]["sources"]:
                found_rows[name]["sources"].append("search")

    names = [n for n in found_rows if card_key(n) not in taken | rejected]
    cards, missing = resolve(names)
    dropped = {"off-identity": [], "not legal": [], "game changer": [], "over budget": [],
               "basic land": []}
    keep = []
    limit = gc_limit(state["bracket"])
    for n in names:
        c = cards.get(card_key(n))
        if not c:
            continue
        if is_basic(c):
            dropped["basic land"].append(n)
        elif not fits_identity(c, state["identity"]):
            dropped["off-identity"].append(n)
        elif (c.get("legalities") or {}).get("commander") != "legal":
            dropped["not legal"].append(n)
        elif c.get("game_changer") and limit == 0:
            dropped["game changer"].append(n)
        else:
            keep.append((n, c))
    if state["budget"].get("card") and keep:
        cost = prices([c["name"] for _, c in keep])
        cap = state["budget"]["card"]
        over = [(n, c) for n, c in keep if (cost.get(c["name"]) or 0) > cap]
        dropped["over budget"] = [f"{c['name']} (R$ {cost[c['name']]:.2f})" for _, c in over]
        keep = [x for x in keep if x not in over]
    tags = roles_of([c for _, c in keep])
    for n, c in keep:
        row = found_rows[n]
        state["pool"][c["name"]] = {
            "inclusion": row["inclusion"], "synergy": row["synergy"],
            "sources": row["sources"], "roles": tags.get(c["name"], []),
            "land": is_land(c), "gc": bool(c.get("game_changer")), "cmc": c.get("cmc")}
        boards["maybeboard"].append(moxfield.Card(1, c["name"], "maybeboard"))
    boards["maybeboard"] = moxfield.merge(boards["maybeboard"])
    for card in boards["maybeboard"]:
        card.qty = 1
    write_deck(args.deck, boards, meta)
    save_state(args.deck, state)
    print(f"pool: {len(keep)} added, {len(boards['maybeboard'])} in Maybeboard")
    for why, items in dropped.items():
        if items and why != "basic land":
            print(f"  dropped {len(items)} {why}: {', '.join(items)}")
    if missing:
        print(f"  unresolved: {', '.join(missing)}")
    return 1 if missing else 0


def _fmt_pct(x):
    return f"{x:.0%}" if isinstance(x, (int, float)) else None


def _need(state, boards, cards, tags):
    """{role: (have, target)}, lands (have, target), open slots."""
    entries, lands = [], 0
    for c in deck_cards(boards):
        card = cards.get(card_key(c.name))
        if not card:
            continue
        entries.append((c.qty, tags.get(card["name"], [])))
        if is_land(card):
            lands += c.qty
    have = count_roles(entries)
    size = sum(c.qty for c in deck_cards(boards))
    roles = {r: {"have": have[r], "target": state["targets"][r]} for r in ROLE_TAGS}
    return roles, {"have": lands, "target": state["targets"]["lands"]}, 100 - size


def cmd_round(args):
    state = _need_state(args.deck)
    if state is None:
        return 2
    if args.role not in ROUNDS:
        print(f"unknown round {args.role}; one of: {', '.join(ROUNDS)}", file=sys.stderr)
        return 2
    boards, _ = read_deck(args.deck)
    in_maybe = {card_key(c.name) for c in boards["maybeboard"]}
    rejected = {card_key(n) for n in state["rejected"]}
    pool = {n: d for n, d in state["pool"].items()
            if card_key(n) in in_maybe and card_key(n) not in rejected}

    def keep(d):
        if args.role == "no-brainers":
            return (d["inclusion"] or 0) >= NO_BRAINER_INCLUSION
        if args.role == "lands":
            return d["land"]
        if args.role == "theme":
            return not d["land"] and not (set(d["roles"]) & UTILITY_TAGS)
        return bool(set(d["roles"]) & set(ROLE_TAGS[args.role]))

    rows = sorted(((n, d) for n, d in pool.items() if keep(d)),
                  key=lambda x: (-(x[1]["inclusion"] or -1), -(x[1]["synergy"] or 0), x[0]))
    rows = rows[:args.limit]
    commander = " + ".join(state["commanders"])
    out = []
    for n, d in rows:
        bits = []
        if d["inclusion"] is not None:
            bits.append(f"in {_fmt_pct(d['inclusion'])} of {commander} decks")
        if d["synergy"]:
            bits.append(f"synergy {d['synergy']:+.0%}")
        if d["roles"]:
            bits.append("roles: " + ", ".join(d["roles"]))
        if d["gc"]:
            bits.append("GAME CHANGER")
        bits.append("source: " + ", ".join(d["sources"]))
        out.append({"name": n, "reason": "; ".join(bits)})
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    state["last_round"] = args.role
    save_state(args.deck, state)

    deck_names = [c.name for c in deck_cards(boards)]
    cards, _ = resolve(deck_names) if deck_names else ({}, [])
    roles, lands, open_slots = _need(state, boards, cards, roles_of(cards.values()))
    if args.role in ROLE_TAGS:
        r = roles[args.role]
        need = f"need {max(r['target'] - r['have'], 0)} ({r['have']}/{r['target']})"
    elif args.role == "lands":
        need = f"need {max(lands['target'] - lands['have'], 0)} ({lands['have']}/{lands['target']})"
    else:
        need = f"need: open slots {open_slots}"
    print(f"{args.role}: {len(out)} of {len(pool)} pool cards -> {args.out}; {need}")
    return 0


def cmd_apply(args):
    state = _need_state(args.deck)
    if state is None:
        return 2
    answer = json.loads(Path(args.answer).read_text())
    if answer.get("status") != "picked":
        print(f"answer is {answer.get('status')!r}: nothing applied", file=sys.stderr)
        return 1
    offered = [o["name"] for o in json.loads(Path(args.offered).read_text())]
    picked = {card_key(p["name"]): p for p in answer.get("picked") or []}
    boards, meta = read_deck(args.deck)
    src, dst = ("mainboard", "maybeboard") if args.cut else ("maybeboard", "mainboard")
    moved = []
    for card in list(boards[src]):
        p = picked.get(card_key(card.name))
        if not p:
            continue
        boards[src].remove(card)
        if args.cut:
            boards[dst].append(moxfield.Card(1, card.name, dst))
        else:
            boards[dst].append(moxfield.Card(card.qty, p["name"], dst, p.get("set"),
                                             p.get("collector_number"), tags=card.tags))
        moved.append(p["name"])
    rejected_now = []
    if not args.cut:
        for name in offered:
            if card_key(name) in picked:
                continue
            boards["maybeboard"] = [c for c in boards["maybeboard"]
                                    if card_key(c.name) != card_key(name)]
            if name not in state["rejected"]:
                state["rejected"].append(name)
                rejected_now.append(name)
    write_deck(args.deck, boards, meta)
    role = "cut" if args.cut else args.role or state.get("last_round") or "?"
    state["rounds"].append({"role": role,
                            "offered": len(offered), "picked": moved, "cut": args.cut,
                            "note": answer.get("note")})
    save_state(args.deck, state)
    missing = [p["name"] for k, p in picked.items()
               if p["name"] not in moved and card_key(p["name"]) not in
               {card_key(m) for m in moved}]
    verb = "cut" if args.cut else "added"
    print(f"{verb} {len(moved)}: {', '.join(moved) or '-'}")
    if rejected_now:
        print(f"rejected {len(rejected_now)}: {', '.join(rejected_now)}")
    if missing:
        print(f"not found in {src}: {', '.join(missing)}", file=sys.stderr)
    _stamp_profile(args.deck)
    return 1 if missing else 0


def _stamp_profile(deck):
    """Keep score-card's profile fresh: the build changes the list on purpose."""
    profile = Path(deck).with_name(Path(deck).stem + ".profile.md")
    if profile.exists():
        sys.path.insert(0, str(ROOT / "score-card" / "scripts"))
        import deckprofile
        buf = __import__("io").StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            deckprofile.main(["stamp", str(profile)])
        finally:
            sys.stdout = old


def cmd_status(args):
    state = _need_state(args.deck)
    if state is None:
        return 2
    boards, _ = read_deck(args.deck)
    names = [c.name for c in deck_cards(boards)]
    cards, missing = resolve(names) if names else ({}, [])
    roles, lands, open_slots = _need(state, boards, cards, roles_of(cards.values()))
    gcs = sorted(c["name"] for c in cards.values() if c.get("game_changer"))
    rejected = {card_key(n) for n in state["rejected"]}
    pool_size = sum(1 for c in boards["maybeboard"] if card_key(c.name) not in rejected)
    out = {"deck_size": sum(c.qty for c in deck_cards(boards)), "open_slots": open_slots,
           "roles": roles, "lands": lands, "targets": state["targets"],
           "game_changers": {"have": gcs, "limit": gc_limit(state["bracket"])},
           "pool_size": pool_size, "rounds": [r["role"] for r in state["rounds"]]}
    if state["budget"].get("total"):
        cost = prices(names)
        out["budget"] = {"cap": float(state["budget"]["total"]),
                         "spent": round(sum(v for v in cost.values() if v), 2),
                         "unpriced": sorted(n for n, v in cost.items() if v is None)}
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"deck {out['deck_size']}/100, open slots {open_slots}, pool {pool_size}")
        print(f"  lands      {lands['have']:>3}/{lands['target']}")
        for r, v in roles.items():
            print(f"  {r:<11}{v['have']:>3}/{v['target']}")
        lim = out["game_changers"]["limit"]
        print(f"  game changers {len(gcs)}/{'-' if lim is None else lim}: "
              f"{', '.join(gcs) or '-'}")
        if "budget" in out:
            b = out["budget"]
            print(f"  budget R$ {b['spent']:.2f} / {b['cap']:.2f}"
                  + (f" (unpriced: {', '.join(b['unpriced'])})" if b["unpriced"] else ""))
        print(f"  rounds done: {', '.join(out['rounds']) or '-'}")
    over = gc_limit(state["bracket"]) is not None and len(gcs) > gc_limit(state["bracket"])
    if over:
        print(f"OVER BRACKET: {len(gcs)} game changers, bracket {state['bracket']} allows "
              f"{gc_limit(state['bracket'])}", file=sys.stderr)
    return 1 if missing or over else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a Commander deck in picker rounds.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="targets per role for a new build")
    p.add_argument("deck")
    p.add_argument("--bracket", type=int, choices=range(1, 6))
    p.add_argument("--budget", type=float, metavar="BRL", help="cap for the whole deck")
    p.add_argument("--budget-card", type=float, metavar="BRL", help="cap per card")
    p.add_argument("--force", action="store_true", help="overwrite an existing build")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("pool", help="candidates into the Maybeboard")
    p.add_argument("deck")
    p.add_argument("--extra", metavar="FILE", help="more names (card-finder results), any list")
    p.set_defaults(fn=cmd_pool)

    p = sub.add_parser("round", help="shortlist for one round as card-picker suggestions")
    p.add_argument("deck")
    p.add_argument("role", help=", ".join(ROUNDS))
    p.add_argument("--out", required=True, metavar="FILE")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_round)

    p = sub.add_parser("apply", help="apply a card-picker answer")
    p.add_argument("deck")
    p.add_argument("--answer", required=True, metavar="FILE", help="picker stdout JSON")
    p.add_argument("--offered", required=True, metavar="FILE", help="the suggestions file shown")
    p.add_argument("--role", help="round name, for the record")
    p.add_argument("--cut", action="store_true", help="picked cards leave the Mainboard")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("status", help="filled vs target")
    p.add_argument("deck")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except FileNotFoundError as exc:
        print(f"file not found: {exc.filename}", file=sys.stderr)
        return 1
    except edhrec.Blocked as exc:
        print(f"EDHREC BLOCKED: {exc}. Run again later.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
