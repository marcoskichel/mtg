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
