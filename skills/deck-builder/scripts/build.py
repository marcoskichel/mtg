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
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_state(deck, state):
    p = build_path(deck)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def read_deck(path):
    return moxfield.parse_deck(Path(path).read_text(encoding="utf-8"))


def write_deck(path, boards, meta):
    Path(path).write_text(moxfield.render_deck(boards, meta), encoding="utf-8")


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
    """Basic supertype on the front face: Swamp, Wastes, Snow-Covered Swamp."""
    return "Basic" in (card.get("type_line") or "").split("//")[0].split("—")[0].split()


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
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("".join(f"1 {n}\n" for n in names))
        path = f.name
    try:
        run = subprocess.run([sys.executable, str(LIGAPRECO), "--json", "-d", path],
                             capture_output=True, text=True, encoding="utf-8")
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
    old_state = load_state(args.deck)
    if old_state and not args.force:
        print(f"{build_path(args.deck)} exists; pass --force to redo the targets "
              "(the pool, rejected cards and rounds are kept)", file=sys.stderr)
        return 1
    if str(meta.get("bracket", "")).strip() != str(bracket):
        meta["bracket"] = bracket
        write_deck(args.deck, boards, meta)

    cmd_cards, missing = resolve(commanders)
    if missing:
        print(f"commander not found on Scryfall: {', '.join(missing)}", file=sys.stderr)
        return 2
    # EDHREC pages are named after the canonical card, not what the file says.
    commanders = [cmd_cards[card_key(n)]["name"] for n in commanders]
    renamed = False
    for c in boards["commanders"]:
        canonical = cmd_cards[card_key(c.name)]["name"]
        if c.name != canonical:
            c.name, renamed = canonical, True
    if renamed:
        write_deck(args.deck, boards, meta)
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
             "pool": {}, "rejected": [], "rounds": [], "offers": {}}
    for kept in ("pool", "rejected", "rounds", "offers"):
        if old_state and kept in old_state:
            state[kept] = old_state[kept]
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
    return 0


def cmd_pool(args):
    state = _need_state(args.deck)
    if state is None:
        return 2
    boards, meta = read_deck(args.deck)
    # Maybeboard cards are candidates too (a pulled list, a hand edit, a cut):
    # they get pool data like the rest, without a second line in the file.
    taken = {card_key(c.name) for c in deck_cards(boards, ("commanders", "companions",
                                                           "mainboard", "sideboard"))}
    in_maybe = {card_key(c.name) for c in boards["maybeboard"]}
    rejected = {card_key(n) for n in state["rejected"]}

    rows = {}   # card_key -> row; one row per card however each source spells it

    def add(name, source, inclusion=None, synergy=None):
        row = rows.setdefault(card_key(name), {"name": name, "inclusion": None,
                                               "synergy": None, "sources": []})
        if row["inclusion"] is None and inclusion is not None:
            row["inclusion"] = inclusion
        if row["synergy"] is None and synergy is not None:
            row["synergy"] = synergy
        if source not in row["sources"]:
            row["sources"].append(source)

    slug = _commander_path(state["commanders"])
    page, _ = edhrec.fetch("commanders/" + slug)
    no_page = page is None
    for row in edhrec.commander_cards(page) if page else []:
        add(row["name"], "edhrec", row["inclusion"], row["synergy"])
    avg = edhrec.average_deck(edhrec.fetch("average-decks/" + slug)[0])
    for _, name in avg["cards"] if avg else []:
        add(name, "average")
    if args.extra:
        for _, name in moxfield.read_card_list(args.extra, moxfield.BOARDS):
            add(name, "search")
    for c in boards["maybeboard"]:
        add(c.name, "maybeboard")

    names = [r["name"] for k, r in rows.items() if k not in taken | rejected]
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
    added = 0
    for n, c in keep:
        row = rows[card_key(n)]
        state["pool"][c["name"]] = {
            "inclusion": row["inclusion"], "synergy": row["synergy"],
            "sources": row["sources"], "roles": tags.get(c["name"], []),
            "land": is_land(c), "gc": bool(c.get("game_changer")), "cmc": c.get("cmc")}
        if card_key(n) not in in_maybe and card_key(c["name"]) not in in_maybe:
            boards["maybeboard"].append(moxfield.Card(1, c["name"], "maybeboard"))
            in_maybe.add(card_key(c["name"]))
            added += 1
    write_deck(args.deck, boards, meta)
    save_state(args.deck, state)
    print(f"pool: {added} added, {len(boards['maybeboard'])} in Maybeboard")
    for why, items in dropped.items():
        if items and why != "basic land":
            print(f"  dropped {len(items)} {why}: {', '.join(items)}")
    if missing:
        print(f"  unresolved: {', '.join(missing)}")
    if no_page:
        print(f"EDHREC has no commander page for {slug}: the pool holds only the "
              "average deck, --extra and Maybeboard cards", file=sys.stderr)
    return 1 if missing or no_page else 0


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
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state.setdefault("offers", {})[str(Path(args.out).resolve())] = args.role
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
    answer = json.loads(Path(args.answer).read_text(encoding="utf-8"))
    if answer.get("status") != "picked":
        print(f"answer is {answer.get('status')!r}: nothing applied", file=sys.stderr)
        return 1
    # The round comes from the file round wrote, so applying an older offer
    # after building a newer one still uses the right rules.
    role = "cut" if args.cut else args.role or (state.get("offers") or {}).get(
        str(Path(args.offered).resolve()))
    if not role:
        print(f"{args.offered} wasn't written by round: pass --role <round>",
              file=sys.stderr)
        return 2
    offered = [o["name"] for o in json.loads(Path(args.offered).read_text(encoding="utf-8"))]
    picked = {card_key(p["name"]): p for p in answer.get("picked") or []}
    boards, meta = read_deck(args.deck)
    src, dst = ("mainboard", "maybeboard") if args.cut else ("maybeboard", "mainboard")
    # The picker only returns cards it was shown: a pick outside the offer, or
    # one no longer in the board, means a stale --offered file. Change nothing.
    offered_keys = {card_key(n) for n in offered}
    in_src = {card_key(c.name) for c in boards[src]}
    stray = [p["name"] for k, p in picked.items() if k not in offered_keys or k not in in_src]
    if stray:
        print(f"picked but not in {args.offered} and the {src.capitalize()}: "
              f"{', '.join(stray)}. Nothing applied; rerun round and the picker.",
              file=sys.stderr)
        return 1
    moved = []
    for card in list(boards[src]):
        p = picked.get(card_key(card.name))
        if not p:
            continue
        if args.cut:
            # One copy per pick: cutting a Swamp from 14 leaves 13.
            card.qty -= 1
            if card.qty <= 0:
                boards[src].remove(card)
            boards[dst].append(moxfield.Card(1, card.name, dst, card.set, card.cn, card.foil,
                                             card.alter, card.tags, card.gtags))
        else:
            boards[src].remove(card)
            boards[dst].append(moxfield.Card(card.qty, p["name"], dst,
                                             p.get("set") or card.set,
                                             p.get("collector_number") or card.cn,
                                             card.foil, card.alter, card.tags, card.gtags))
        moved.append(p["name"])
    boards[dst] = moxfield.merge(boards[dst])
    rejected_now = _reject_rest(state, boards, role, offered, picked)
    write_deck(args.deck, boards, meta)
    state["rounds"].append({"role": role, "offered": len(offered), "picked": moved,
                            "cut": args.cut, "note": answer.get("note")})
    save_state(args.deck, state)
    verb = "cut" if args.cut else "added"
    print(f"{verb} {len(moved)}: {', '.join(moved) or '-'}")
    if rejected_now:
        print(f"rejected {len(rejected_now)}: {', '.join(rejected_now)}")
    return 0


def _reject_rest(state, boards, role, offered, picked):
    """Offered but not picked leaves the pool, unless another round still wants it.

    No-brainers declined stay for their role round; a card with several roles
    (Path to Exile: removal and ramp) stays until each of its role rounds ran.
    """
    if role in ("cut", "no-brainers"):
        return []
    done = {r["role"] for r in state["rounds"]} | {role}
    out = []
    for name in offered:
        if card_key(name) in picked:
            continue
        row = state["pool"].get(name) or {}
        pending = set(roles_to_groups(row.get("roles") or [])) - done
        if row.get("land") and "lands" not in done:
            pending.add("lands")
        if pending:
            continue
        boards["maybeboard"] = [c for c in boards["maybeboard"]
                                if card_key(c.name) != card_key(name)]
        if name not in state["rejected"]:
            state["rejected"].append(name)
            out.append(name)
    return out


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
        qty = Counter()
        for c in deck_cards(boards):
            qty[c.name] += c.qty
        cost = prices(list(qty))
        out["budget"] = {"cap": float(state["budget"]["total"]),
                         "spent": round(sum((cost.get(n) or 0) * q for n, q in qty.items()), 2),
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
    # Card names are Unicode; Windows would otherwise use its legacy code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
