#!/usr/bin/env python3
"""Magic card lookup through the Scryfall API.

Four subcommands: card (oracle text for one or many cards, including a whole
decklist), search (Scryfall search syntax), printings (every printing of a
card) and rulings.

Output is meant to be read by a model: compact text on stdout, a report of
unresolved names and warnings on stderr, --json when another script consumes it.
"""

import argparse
import difflib
import html
import json
import os
import re
import sys
import time
import unicodedata
import uuid
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://api.scryfall.com"
# Scryfall requires User-Agent and Accept; without them it answers 400.
UA = "mtg-skills/0.1"
# Scryfall asks for at most 10 req/s. 0.1s between calls respects that.
DEFAULT_DELAY = 0.1
COLLECTION_BATCH = 75
PAGE_SIZE = 175
# "Lightnig Bolt" x "Lightning Bolt" = 0.96; "Raio" x "Samurai of the Pale
# Curtain" = 0.26. 0.75 separates a typo from an API guess.
FUZZY_MIN_RATIO = 0.75
# Cards that exist only on the user's side (homebrew, MTG.Design): a JSON list
# of Scryfall-shaped cards, read before any API call. Path relative to the
# folder the agent runs in; the environment variable overrides it.
CUSTOM_ENV = "MTG_CUSTOM_CARDS"
CUSTOM_DEFAULT = Path("cards") / "custom.json"
MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")
REMINDER_RE = re.compile(r"\([^)]*\)")

SECTION_HEADERS = {
    "deck": "main", "main": "main", "maindeck": "main", "main deck": "main",
    "mainboard": "main", "principal": "main",
    "sideboard": "side", "side": "side", "sb": "side", "reserva": "side",
    "maybeboard": "maybe", "maybe": "maybe", "considerando": "maybe",
    "commander": "commander", "comandante": "commander",
    "companion": "companion", "companheiro": "companion",
}
SECTIONS = ("commander", "companion", "main", "side", "maybe")
SECTION_LABELS = {"commander": "Commander", "companion": "Companion",
                  "main": "Main deck", "side": "Sideboard", "maybe": "Maybeboard"}

LINE_RE = re.compile(r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<rest>\S.*?)\s*$")
SB_PREFIX_RE = re.compile(r"^\s*SB:\s*", re.I)
MWS_SET_RE = re.compile(r"^\[[^\]]*\]\s*")
ARENA_TAIL_RE = re.compile(r"\s*\([A-Za-z0-9]{2,6}\)\s+[0-9]+[a-z★]?\s*$")
FOIL_MARK_RE = re.compile(r"\s*\*[FEfe]\*\s*$")

# Fields worth keeping with --json: the raw Scryfall object has ~60.
CARD_FIELDS = (
    "name", "layout", "lang", "printed_name", "mana_cost", "cmc", "type_line",
    "oracle_text", "power", "toughness", "loyalty", "defense", "colors",
    "color_identity", "keywords", "legalities", "set", "set_name",
    "collector_number", "rarity", "released_at", "prices", "finishes", "promo",
    "digital", "image_uris", "scryfall_uri", "rulings_uri", "prints_search_uri", "custom",
)
FACE_FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "power",
               "toughness", "loyalty", "defense", "colors", "image_uris")


# --------------------------------------------------------------------------- #
# names
# --------------------------------------------------------------------------- #

def fold(s):
    """Comparison key: no accents, no case, collapsed whitespace."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def front_face(name):
    """'A // B' -> 'A'. /cards/collection only recognizes the front face."""
    return name.split("//")[0].strip() if "//" in name else name.strip()


def clean_card_name(raw):
    """Strip export noise from other tools, keeping the real name."""
    name = raw.strip()
    name = MWS_SET_RE.sub("", name)
    prev = None
    while prev != name:
        prev = name
        name = FOIL_MARK_RE.sub("", name)
        name = ARENA_TAIL_RE.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


# --------------------------------------------------------------------------- #
# decklist parsing (same rules as the ligamagic-preco skill, duplicated on
# purpose so the skill is self-contained)
# --------------------------------------------------------------------------- #

class Entry:
    __slots__ = ("qty", "raw", "name", "section", "card", "status", "note")

    def __init__(self, qty, raw, section="main"):
        self.qty = qty
        self.raw = raw
        self.name = clean_card_name(raw)
        self.section = section
        self.card = None
        self.status = "pending"
        self.note = ""


def parse_cockatrice(text):
    root = ET.fromstring(text)
    sections = {k: [] for k in SECTIONS}
    for zone in root.iter("zone"):
        key = {"main": "main", "side": "side"}.get(
            (zone.get("name") or "").lower(), "main")
        for card in zone.findall("card"):
            n = int(card.get("number") or 1)
            sections[key].append(Entry(n, card.get("name") or "", key))
    return sections


def parse_text(text):
    sections = {k: [] for k in SECTIONS}
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    has_header = any(ln.strip().rstrip(":").lower() in SECTION_HEADERS
                     for ln in lines)
    has_sb_prefix = any(SB_PREFIX_RE.match(ln) for ln in lines)

    current = "main"
    block = 0
    blank_run = 0
    blank_order = ["main", "side", "maybe"]

    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            blank_run += 1
            continue
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        key = stripped.rstrip(":").lower()
        if key in SECTION_HEADERS:
            current = SECTION_HEADERS[key]
            blank_run = 0
            continue
        if not LINE_RE.match(stripped) and not SB_PREFIX_RE.match(stripped):
            continue
        target = current
        body = stripped
        if SB_PREFIX_RE.match(body):
            body = SB_PREFIX_RE.sub("", body)
            target = "side"
        elif not has_header and not has_sb_prefix and blank_run:
            block = min(block + 1, len(blank_order) - 1)
            target = blank_order[block]
            current = target
        blank_run = 0
        m = LINE_RE.match(body)
        if not m:
            continue
        sections[target].append(Entry(int(m.group("qty")), m.group("rest"), target))
    return sections


def parse_input(text):
    if text.lstrip().startswith("<?xml") or "<cockatrice_deck" in text[:400]:
        try:
            return parse_cockatrice(text)
        except ET.ParseError:
            pass
    return parse_text(text)


# --------------------------------------------------------------------------- #
# network
# --------------------------------------------------------------------------- #

_last_call = [0.0]
DELAY = [DEFAULT_DELAY]
RETRY_STATUS = {429, 500, 502, 503, 504}


def _http(method, url, body=None, retries=3):
    """One API call, with pacing and backoff on 429/5xx.

    4xx errors that Scryfall explains (404 not_found, ambiguous) come back as
    the error JSON, not as an exception: the caller decides what to tell the user.
    """
    gap = DELAY[0] - (time.monotonic() - _last_call[0])
    if gap > 0:
        time.sleep(gap)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if body is not None:
        data = body.encode() if isinstance(body, str) else body
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    wait = 2.0
    for attempt in range(retries + 1):
        _last_call[0] = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
            if exc.code in RETRY_STATUS and attempt < retries:
                ra = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    pause = float(ra) if ra else wait
                except ValueError:
                    pause = wait
                print(f"warning: HTTP {exc.code} from Scryfall; waiting {pause:.0f}s",
                      file=sys.stderr)
                time.sleep(pause)
                wait *= 2
                continue
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            if isinstance(err, dict) and err.get("object") == "error":
                return err
            raise
    raise RuntimeError("unreachable")


def api(path, **params):
    url = path if path.startswith("http") else API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return _http("GET", url)


def is_error(obj):
    return isinstance(obj, dict) and obj.get("object") == "error"


# --------------------------------------------------------------------------- #
# name resolution
# --------------------------------------------------------------------------- #

def _index_cards(cards):
    """Keys under which a returned card can match the requested name."""
    idx = {}
    for c in cards:
        keys = {fold(c.get("name")), fold(front_face(c.get("name", "")))}
        for f in c.get("card_faces") or []:
            keys.add(fold(f.get("name")))
        if c.get("printed_name"):
            keys.add(fold(c["printed_name"]))
        for k in keys:
            idx.setdefault(k, c)
    return idx


# --------------------------------------------------------------------------- #
# custom cards
# --------------------------------------------------------------------------- #

def custom_cards_path():
    env = os.environ.get(CUSTOM_ENV)
    return Path(env) if env else CUSTOM_DEFAULT


def _symbol_colors(text):
    """WUBRG letters in the mana symbols of a cost or rules text ({W/B} -> W, B)."""
    found = set()
    for sym in MANA_SYMBOL_RE.findall(text or ""):
        found |= {c for c in sym.upper().split("/") if c in "WUBRG"}
    return [c for c in "WUBRG" if c in found]


def _mana_value(cost):
    total = 0
    for sym in MANA_SYMBOL_RE.findall(cost or ""):
        if sym.isdigit():
            total += int(sym)
        elif sym.upper() not in ("X", "Y", "Z"):
            # {2/W} counts 2, any other symbol (hybrid, phyrexian) counts 1
            total += int(sym.split("/")[0]) if sym.split("/")[0].isdigit() else 1
    return float(total)


def custom_card(raw, base=None):
    """A user's card -> a Scryfall-shaped card. Missing fields are derived:
    colors from the cost, identity from cost + text, mana value from the cost.
    'image' is a picture of the card: a local file, relative to base."""
    if not raw.get("name") or not raw.get("type_line"):
        raise ValueError("a custom card needs at least 'name' and 'type_line'")
    card = dict(raw)
    cost = card.get("mana_cost") or ""
    card.setdefault("object", "card")
    # Same name, same id: a UUID like Scryfall's, so other tools take it as one.
    card.setdefault("id", str(uuid.uuid5(uuid.NAMESPACE_URL, "custom-card:" + fold(card["name"]))))
    image = card.pop("image", None)
    if image and "image_uris" not in card:
        path = Path(image).expanduser()
        if not path.is_absolute() and base is not None:
            path = Path(base) / path
        card["image_uris"] = {"normal": path.resolve().as_uri()}
    card.setdefault("layout", "normal")
    card.setdefault("lang", "en")
    card.setdefault("mana_cost", cost)
    card.setdefault("cmc", _mana_value(cost))
    card.setdefault("oracle_text", "")
    card.setdefault("colors", _symbol_colors(cost))
    # Identity: cost, rules text without reminder text, and given colors (rule 903.4).
    text = REMINDER_RE.sub("", card.get("oracle_text") or "")
    card.setdefault("color_identity", [c for c in "WUBRG" if c in set(
        _symbol_colors(cost + " " + text)) | set(card["colors"])])
    card.setdefault("keywords", [])
    card.setdefault("legalities", {})
    card.setdefault("set", "custom")
    card.setdefault("set_name", "Custom card")
    card.setdefault("collector_number", "")
    card.setdefault("rarity", "special")
    card.setdefault("prices", {})
    card["custom"] = True
    return card


_custom_cache = {}


def load_custom_cards():
    """{fold(name): card} from the custom cards file; {} when there is none."""
    path = custom_cards_path()
    key = str(path.resolve())
    if key in _custom_cache:
        return _custom_cache[key]
    cards = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raws = data.get("cards") if isinstance(data, dict) else data
            for raw in raws or []:
                c = custom_card(raw, path.parent)
                for k in {fold(c["name"]), fold(front_face(c["name"])),
                          fold(c.get("printed_name") or "")} - {""}:
                    cards.setdefault(k, c)
        except (ValueError, AttributeError, TypeError) as exc:
            raise SystemExit(f"custom cards file {path}: {exc}")
    _custom_cache[key] = cards
    return cards


def is_custom(card):
    return bool(card and card.get("custom"))


def resolve_names(names, report):
    """Requested name -> card object, via /cards/collection + fallbacks.

    Custom cards (see load_custom_cards) win over Scryfall. Scryfall only
    matches the exact English name in the collection; 'A // B' has to go as
    'A'. Whatever is left tries an exact search on the printed Portuguese
    name, then fuzzy (typos).
    """
    wanted = {}
    for n in names:
        wanted.setdefault(fold(front_face(n)), front_face(n))
    found = {}
    custom = load_custom_cards()
    for k in wanted:
        if k in custom:
            found[k] = custom[k]
            report.custom.append(custom[k]["name"])
    keys = [k for k in wanted if k not in found]
    for i in range(0, len(keys), COLLECTION_BATCH):
        chunk = keys[i:i + COLLECTION_BATCH]
        body = json.dumps({"identifiers": [{"name": wanted[k]} for k in chunk]})
        resp = _http("POST", API + "/cards/collection", body)
        if is_error(resp):
            raise RuntimeError(f"/cards/collection: {resp.get('details')}")
        idx = _index_cards(resp.get("data") or [])
        for k in chunk:
            if k in idx:
                found[k] = idx[k]

    for k in keys:
        if k in found:
            continue
        query = wanted[k]
        # Printed Portuguese name, exact match ('!'): 'name:' is a
        # substring match and would return 67 cards for "Raio".
        pt = api("/cards/search", q=f'!"{query}" lang:pt', unique="cards")
        if not is_error(pt) and pt.get("data"):
            card = pt["data"][0]
            # The Portuguese printing has English oracle text and the canonical
            # name in 'name'; 'printed_name' is what the user wrote.
            found[k] = card
            report.renames[query] = (card["name"], "Portuguese name")
            continue
        card = api("/cards/named", fuzzy=query)
        if is_error(card):
            report.missing[query] = card.get("details") or ""
            continue
        # fuzzy with a short or Portuguese name returns anything ("Raio"
        # -> Samurai of the Pale Curtain). Accept only if it looks like the request.
        if looks_like(query, card):
            found[k] = card
            report.renames[query] = (card["name"], "fuzzy")
        else:
            report.missing[query] = (f"fuzzy suggested \"{card['name']}\", rejected "
                                     "because it does not look like the requested name")
    return found, wanted


def looks_like(query, card):
    """Fuzzy gate: substring or high similarity with one of the card names."""
    q = fold(query)
    names = [card.get("name", "")] + [f.get("name", "") for f in card.get("card_faces") or []]
    for n in names:
        n = fold(n)
        if q in n:
            return True
        if difflib.SequenceMatcher(None, q, n).ratio() >= FUZZY_MIN_RATIO:
            return True
    return False


class Report:
    def __init__(self):
        self.renames = {}
        self.missing = {}
        self.warnings = []
        self.custom = []

    def emit(self, out=None):
        out = out or sys.stderr
        if self.custom:
            print(f"Custom cards, not on Scryfall ({len(self.custom)}): "
                  f"{', '.join(self.custom)}  [from {custom_cards_path().resolve()}]", file=out)
        if self.warnings:
            for w in self.warnings:
                print(f"SCRYFALL WARNING: {w}", file=out)
            print("  ^ ignored expression = the search is BROADER than "
                  "requested. Fix the query before using the result.", file=out)
        if self.renames:
            print(f"Names adjusted ({len(self.renames)}):", file=out)
            for old, (new, why) in self.renames.items():
                print(f"  {old}  ->  {new}   [{why}]", file=out)
        if self.missing:
            print(f"NOT FOUND on Scryfall ({len(self.missing)}):", file=out)
            for name, hint in self.missing.items():
                print(f"  {name}" + (f"\n      {hint}" if hint else ""), file=out)
            path = custom_cards_path().resolve()
            if not path.is_file():
                print(f"  (no custom cards file at {path}: a card of your own goes there)",
                      file=out)

    @property
    def failed(self):
        return bool(self.missing or self.warnings)


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #

def faces_of(card):
    """Faces with their own text; a normal card is a single face."""
    if card.get("oracle_text") is None and card.get("card_faces"):
        return card["card_faces"]
    return [card]


def _pt(face):
    if face.get("power") is not None:
        return f"{face['power']}/{face['toughness']}"
    if face.get("loyalty") is not None:
        return f"loyalty {face['loyalty']}"
    if face.get("defense") is not None:
        return f"defense {face['defense']}"
    return ""


def format_card(card, formats, rulings=None):
    lines = []
    name = card.get("name", "?")
    ci = "".join(card.get("color_identity") or []) or "colorless"
    where = "custom card" if is_custom(card) else \
        f"{card.get('set', '').upper()} {card.get('collector_number', '')}"
    head = f"{name}  [{where}]  identity: {ci}"
    lines.append(head)
    lines.append("-" * min(len(head), 90))
    for face in faces_of(card):
        multi = face is not card
        if multi:
            lines.append(f"  == {face.get('name')}")
        ind = "    " if multi else "  "
        cost = face.get("mana_cost") or ""
        stats = _pt(face)
        lines.append(f"{ind}{cost}  {face.get('type_line', '')}"
                     + (f"  {stats}" if stats else ""))
        for ln in (face.get("oracle_text") or "").split("\n"):
            lines.append(f"{ind}{ln}")
    if formats and is_custom(card):
        lines.append("  legality: custom card, not checked")
    elif formats:
        leg = card.get("legalities") or {}
        parts = [f"{f}: {leg.get(f, '?').replace('_', ' ')}" for f in formats]
        lines.append("  legality: " + ", ".join(parts))
    if rulings is not None:
        if rulings:
            lines.append("  rulings:")
            for r in rulings:
                lines.append(f"    [{r.get('published_at')}] {r.get('comment')}")
        else:
            lines.append("  rulings: no rulings")
    lines.append("")
    return "\n".join(lines)


def trim_card(card, rulings=None):
    out = {k: card.get(k) for k in CARD_FIELDS if k in card}
    if card.get("card_faces"):
        out["card_faces"] = [{k: f.get(k) for k in FACE_FIELDS if k in f}
                             for f in card["card_faces"]]
    if rulings is not None:
        out["rulings"] = [{"published_at": r.get("published_at"),
                           "comment": r.get("comment")} for r in rulings]
    return out


def fetch_rulings(card):
    uri = card.get("rulings_uri")
    if not uri:
        return []
    resp = api(uri)
    return [] if is_error(resp) else resp.get("data") or []


def lookup_one(query):
    """One card by approximate name, for printings/rulings. (card, error)."""
    card = api("/cards/named", fuzzy=query)
    if is_error(card):
        if card.get("type") == "ambiguous":
            return None, f"ambiguous name: {card.get('details')}"
        return None, card.get("details") or "not found"
    return card, None


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #

def cmd_card(args):
    if args.deck:
        text = sys.stdin.read() if args.deck == "-" else \
            Path(args.deck).read_text(encoding="utf-8", errors="replace")
        sections = parse_input(text)
        if not any(sections.values()):
            print("no card recognized in the input", file=sys.stderr)
            return 2
    elif args.names:
        sections = {k: [] for k in SECTIONS}
        sections["main"] = [Entry(1, n) for n in args.names]
    else:
        print("pass card names or -d FILE (- for stdin)", file=sys.stderr)
        return 2

    entries = [e for s in SECTIONS for e in sections[s]]
    report = Report()
    found, _ = resolve_names([e.name for e in entries], report)
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]

    rulings = {}
    for e in entries:
        e.card = found.get(fold(front_face(e.name)))
        if e.card and args.rulings:
            key = e.card.get("rulings_uri")
            if key not in rulings:
                rulings[key] = fetch_rulings(e.card)

    if args.json:
        payload = {"cards": [], "not_found": list(report.missing)}
        for e in entries:
            if not e.card:
                continue
            item = trim_card(e.card, rulings.get(e.card.get("rulings_uri")) if args.rulings else None)
            item["requested"] = e.name
            item["qty"] = e.qty
            item["section"] = e.section
            payload["cards"].append(item)
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for sec in SECTIONS:
            if not sections[sec]:
                continue
            if args.deck:
                print(f"== {SECTION_LABELS[sec]} ==\n")
            for e in sections[sec]:
                if not e.card:
                    continue
                if args.deck and e.qty != 1:
                    print(f"{e.qty}x", end=" ")
                print(format_card(e.card, formats,
                                  rulings.get(e.card.get("rulings_uri")) if args.rulings else None))
    report.emit()
    return 1 if report.failed else 0


def cmd_search(args):
    report = Report()
    params = {"q": args.query, "unique": args.unique}
    if args.order:
        params["order"] = args.order
    if args.dir:
        params["dir"] = args.dir
    cards, total = [], 0
    resp = api("/cards/search", **params)
    while True:
        if is_error(resp):
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
        resp = api(resp["next_page"])
    if not args.all:
        cards = cards[:args.limit]

    if args.json:
        json.dump({"total": total, "shown": len(cards),
                   "cards": [trim_card(c) for c in cards]},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for c in cards:
            faces = faces_of(c)
            cost = " // ".join(f.get("mana_cost") or "" for f in faces).strip()
            stats = " // ".join(_pt(f) for f in faces if _pt(f))
            print(f"{c.get('name')}  |  {cost}  |  {c.get('type_line', '')}"
                  + (f"  {stats}" if stats else "")
                  + f"  |  {c.get('set', '').upper()}")
    print(f"{total} card(s) in total, {len(cards)} shown"
          + ("" if args.all or len(cards) >= total else
             f". Use --limit N or --all to see more"), file=sys.stderr)
    report.emit()
    return 1 if report.failed else 0


def cmd_printings(args):
    card, err = lookup_one(args.name)
    if err:
        print(err, file=sys.stderr)
        return 1
    prints = []
    resp = api(card["prints_search_uri"])
    while True:
        if is_error(resp):
            print(f"Scryfall error: {resp.get('details')}", file=sys.stderr)
            return 1
        prints.extend(resp.get("data") or [])
        if not resp.get("has_more"):
            break
        resp = api(resp["next_page"])
    if args.no_digital:
        prints = [p for p in prints if not p.get("digital")]
    if args.no_promo:
        prints = [p for p in prints if not p.get("promo")]

    if args.json:
        json.dump({"name": card["name"], "printings": [trim_card(p) for p in prints]},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    print(f"{card['name']} — {len(prints)} printing(s)")
    print(f"{'set':<6} {'set name':<34} {'no.':>7} {'date':<10} {'finishes':<16} "
          f"{'usd':>8} {'usd foil':>9} {'eur':>8}  flags")
    for p in prints:
        pr = p.get("prices") or {}
        flags = " ".join(f for f, on in (("promo", p.get("promo")),
                                         ("digital", p.get("digital")))
                         if on)
        print(f"{p.get('set', ''):<6} {(p.get('set_name') or '')[:34]:<34} "
              f"{p.get('collector_number', ''):>7} {p.get('released_at', ''):<10} "
              f"{','.join(p.get('finishes') or []):<16} "
              f"{pr.get('usd') or '-':>8} {pr.get('usd_foil') or '-':>9} "
              f"{pr.get('eur') or '-':>8}  {flags}")
        if args.image:
            for face in faces_of(p):
                uri = (face.get("image_uris") or p.get("image_uris") or {}).get("normal")
                if uri:
                    print(f"       {uri}")
    return 0


def cmd_rulings(args):
    card, err = lookup_one(args.name)
    if err:
        print(err, file=sys.stderr)
        return 1
    rulings = fetch_rulings(card)
    if args.json:
        json.dump({"name": card["name"],
                   "rulings": trim_card(card, rulings)["rulings"]},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    print(f"{card['name']} — {len(rulings)} ruling(s)" if rulings
          else f"{card['name']} — no rulings")
    for r in rulings:
        print(f"[{r.get('published_at')}] {r.get('comment')}")
    return 0


# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Magic cards through the Scryfall API.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="emit JSON on stdout instead of text")
    common.add_argument("--delay", type=float, default=DEFAULT_DELAY, metavar="SEC",
                        help=f"pause between calls (default {DEFAULT_DELAY})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("card", parents=[common],
                       help="oracle text of one or more cards")
    p.add_argument("names", nargs="*", help="names (EN or PT; 'A // B' accepted)")
    p.add_argument("-d", "--deck", metavar="FILE",
                   help="decklist in any format; - for stdin")
    p.add_argument("--formats", default="commander",
                   help="legalities to show, comma-separated (default: commander)")
    p.add_argument("--rulings", action="store_true", help="include rulings")
    p.set_defaults(fn=cmd_card)

    p = sub.add_parser("search", parents=[common],
                       help="search with Scryfall syntax")
    p.add_argument("query")
    p.add_argument("--order", metavar="FIELD",
                   help="name, cmc, released, usd, eur, edhrec, rarity, color, power, toughness...")
    p.add_argument("--dir", choices=("asc", "desc"))
    p.add_argument("--unique", default="cards", choices=("cards", "art", "prints"))
    p.add_argument("--limit", type=int, default=50, metavar="N",
                   help="maximum cards shown (default 50)")
    p.add_argument("--all", action="store_true", help="follow every page")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("printings", parents=[common],
                       help="every printing of a card")
    p.add_argument("name")
    p.add_argument("--no-digital", action="store_true", help="hide MTGO/Arena")
    p.add_argument("--no-promo", action="store_true", help="hide promos")
    p.add_argument("--image", action="store_true", help="image URL per face")
    p.set_defaults(fn=cmd_printings)

    p = sub.add_parser("rulings", parents=[common], help="rulings of a card")
    p.add_argument("name")
    p.set_defaults(fn=cmd_rulings)

    args = ap.parse_args(argv)
    DELAY[0] = args.delay
    try:
        return args.fn(args)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"network or API failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Card names are Unicode; Windows would otherwise use its legacy code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
