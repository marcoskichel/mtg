#!/usr/bin/env python3
"""Local deck <-> Moxfield.

Subcommands:
  pull     <id|url> [-o deck.txt] [--json]     public Moxfield deck -> local file
  validate <deck.txt> [--format commander]     checks structure, names and legality (Scryfall)
  diff     <deck.txt> <id|url>                 local vs Moxfield, per board
  export   <deck.txt> [--board X] [--copy]     blocks to paste into Bulk Edit

Standard library only. Reading uses api2.moxfield.com (the same endpoint as the
site); there is no write API — writing is done in the browser, see SKILL.md.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scryfall-cards" / "scripts"))
import scryfall  # noqa: E402

MOX_API = "https://api2.moxfield.com/v3/decks/all/"
SCRY_COLLECTION = "https://api.scryfall.com/cards/collection"
SCRY_NAMED = "https://api.scryfall.com/cards/named"
SCRY_SEARCH = "https://api.scryfall.com/cards/search"
UA_BROWSER = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
UA_SCRY = "mtg-skills/0.1 (moxfield-deck)"
SCRY_DELAY = 0.1

# Moxfield boards that matter for a Commander deck. The others
# (attractions, stickers, planes...) are left out on purpose.
BOARDS = ("commanders", "companions", "mainboard", "sideboard", "maybeboard")
BOARD_TITLE = {
    "commanders": "Commander", "companions": "Companion", "mainboard": "Mainboard",
    "sideboard": "Sideboard", "maybeboard": "Maybeboard",
}
# English headers plus Portuguese aliases; existing deck files use both.
SECTION_HEADERS = {
    "commander": "commanders", "commanders": "commanders", "comandante": "commanders",
    "companion": "companions", "companheiro": "companions",
    "main": "mainboard", "mainboard": "mainboard", "deck": "mainboard",
    "maindeck": "mainboard", "main deck": "mainboard", "principal": "mainboard",
    "sideboard": "sideboard", "side": "sideboard", "sb": "sideboard", "reserva": "sideboard",
    "maybeboard": "maybeboard", "maybe": "maybeboard", "considering": "maybeboard",
    "considerando": "maybeboard",
}
# Formats with a commander, a 100-card singleton deck and color identity.
COMMANDER_FORMATS = ("commander", "paupercommander")
# Counts as "deck" toward the 100 total: commander + companion + main.
# Sideboard on Moxfield is an auxiliary list; maybeboard is under consideration.
DECK_BOARDS = ("commanders", "companions", "mainboard")

LINE_RE = re.compile(r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<rest>\S.*?)\s*$")
SET_RE = re.compile(r"\(([A-Za-z0-9]{2,6})\)")
TAG_RE = re.compile(r"#(!?)([^\s#]+)")
MARK_RE = re.compile(r"\*([FAfaEe])\*")
# Collector number: "123", "123a", "★", "A-123", and The List ones "C15-56",
# "MH1-7", "2X2-391". Must contain a digit and must not look like a name word.
CN_RE = re.compile(r"^(?=.*[0-9★])[A-Za-z0-9★†]{1,6}(-[A-Za-z0-9★]{1,6})?$")
PUBLIC_ID_RE = re.compile(r"[A-Za-z0-9_-]{20,24}")
BASIC_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes")
# Metadata keys are canonical in English; the Portuguese ones older deck files
# use (`// Nome:`, `// Formato:`) still parse as aliases.
META_ALIASES = {"nome": "name", "formato": "format", "visibilidade": "visibility"}


canonical_format = scryfall.canonical_format


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


# --------------------------------------------------------------------------- #
# local format
# --------------------------------------------------------------------------- #

class Card:
    __slots__ = ("qty", "name", "set", "cn", "foil", "alter", "tags", "gtags", "board", "line")

    def __init__(self, qty, name, board, set_=None, cn=None, foil=False, alter=False,
                 tags=None, gtags=None, line=0):
        self.qty = qty
        self.name = name
        self.board = board
        self.set = set_.lower() if set_ else None
        self.cn = cn
        self.foil = foil
        self.alter = alter
        self.tags = list(tags or [])
        self.gtags = list(gtags or [])
        self.line = line

    @property
    def key(self):
        return fold(self.name)

    @property
    def front(self):
        return self.name.split(" // ")[0].strip()

    def render(self, with_tags=True, with_printing=True):
        parts = [str(self.qty), self.name]
        if with_printing and self.set:
            parts.append("(%s)" % self.set.upper())
            if self.cn:
                parts.append(str(self.cn))
        if with_printing and self.foil:
            parts.append("*F*")
        if with_printing and self.alter:
            parts.append("*A*")
        if with_tags:
            parts += ["#" + t for t in self.tags] + ["#!" + t for t in self.gtags]
        return " ".join(parts)


def parse_line(body, board, lineno=0):
    """`1 Name (SET) 123 *F* *A* #tag #!global` — suffixes in any order."""
    m = LINE_RE.match(body)
    if not m:
        return None
    qty = int(m.group("qty"))
    rest = m.group("rest")

    tags, gtags = [], []
    for g, t in TAG_RE.findall(rest):
        (gtags if g else tags).append(t)
    rest = TAG_RE.sub("", rest)

    foil = alter = False
    for mk in MARK_RE.findall(rest):
        if mk.upper() == "A":
            alter = True
        else:
            foil = True
    rest = MARK_RE.sub("", rest)

    set_ = cn = None
    sm = SET_RE.search(rest)
    if sm:
        tail = rest[sm.end():].strip()
        head = rest[:sm.start()].strip()
        # Only treat "(XXX)" as a set when it sits at the end of the name; "(Art Card)"
        # is part of a legitimate name and doesn't match the 2-6 alphanumeric regex.
        tok = tail.split()
        if not tok or CN_RE.match(tok[0]):
            set_ = sm.group(1)
            if tok:
                cn = tok[0]
                tail = " ".join(tok[1:])
            rest = (head + " " + tail).strip()
    name = re.sub(r"\s+", " ", rest).strip()
    if not name:
        return None
    return Card(qty, name, board, set_, cn, foil, alter, tags, gtags, lineno)


def parse_deck(text):
    """Local file -> {board: [Card]}, metadata from `// Key: value` comments."""
    boards = {b: [] for b in BOARDS}
    meta = {}
    current = "mainboard"
    seen_header = False
    for n, raw in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("//"):
            body = s[2:].strip()
            key = body.rstrip(":").lower()
            if key in SECTION_HEADERS:
                current = SECTION_HEADERS[key]
                seen_header = True
            elif ":" in body:
                k, v = body.split(":", 1)
                k = k.strip().lower()
                meta[META_ALIASES.get(k, k)] = v.strip()
            continue
        key = s.rstrip(":").lower()
        if key in SECTION_HEADERS:
            current = SECTION_HEADERS[key]
            seen_header = True
            continue
        card = parse_line(s, current, n)
        if card:
            boards[current].append(card)
    if not seen_header and not boards["commanders"]:
        meta.setdefault("_warning", "file has no section header; everything went to Mainboard")
    return boards, meta


def read_card_list(path, boards=DECK_BOARDS):
    """[(qty, name)] from a deck file (Bulk Edit syntax, headers, tags) or a loose list.

    Lines without a quantity count as 1; repeated names merge, keeping the first
    spelling. Default boards are the ones that count toward the deck.
    """
    text = sys.stdin.read() if str(path) == "-" else _read(path)
    fixed = []
    for ln in text.splitlines():
        s = ln.strip()
        if s and not s.startswith("//") and not LINE_RE.match(s) \
                and s.rstrip(":").lower() not in SECTION_HEADERS:
            s = "1 " + s
        fixed.append(s)
    parsed, _ = parse_deck("\n".join(fixed))
    out, idx = [], {}
    for b in boards:
        for c in parsed[b]:
            if c.key in idx:
                out[idx[c.key]][0] += c.qty
            else:
                idx[c.key] = len(out)
                out.append([c.qty, c.name])
    return [tuple(x) for x in out]

def merge(cards):
    out, idx = [], {}
    for c in cards:
        k = (c.key, c.set, c.cn, c.foil)
        if k in idx:
            idx[k].qty += c.qty
            for t in c.tags:
                if t not in idx[k].tags:
                    idx[k].tags.append(t)
        else:
            idx[k] = c
            out.append(c)
    return out


def render_deck(boards, meta=None, with_tags=True, with_printing=True):
    lines = []
    for k, v in (meta or {}).items():
        if not k.startswith("_"):
            lines.append("// %s: %s" % (k.capitalize(), v))
    if lines:
        lines.append("")
    for b in BOARDS:
        cards = boards.get(b) or []
        if not cards and b not in ("commanders", "mainboard"):
            continue
        lines.append("// " + BOARD_TITLE[b])
        for c in sorted(cards, key=lambda c: (c.key, c.set or "")):
            lines.append(c.render(with_tags, with_printing))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# network
# --------------------------------------------------------------------------- #

def _get_json(url, headers, retries=3):
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (429, 502, 503) and attempt < retries - 1:
                wait = float(e.headers.get("Retry-After") or 2 * (attempt + 1))
                time.sleep(wait)
                continue
            try:
                return e.code, json.loads(body)
            except ValueError:
                return e.code, {"_raw": body[:300]}
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise SystemExit("network: %s" % e.reason)


def public_id(ref):
    """Accepts a bare id or any moxfield.com/decks/<id>[/...] URL."""
    ref = ref.strip()
    m = re.search(r"/decks/(" + PUBLIC_ID_RE.pattern + ")", ref)
    if m:
        return m.group(1)
    if PUBLIC_ID_RE.fullmatch(ref):
        return ref
    raise SystemExit("does not look like a Moxfield deck id or URL: %r" % ref)


def fetch_deck(ref):
    pid = public_id(ref)
    status, data = _get_json(MOX_API + pid, {
        "User-Agent": UA_BROWSER, "Accept": "application/json",
        "Referer": "https://moxfield.com/", "Origin": "https://moxfield.com",
    })
    if status == 404:
        raise SystemExit("404: deck %s does not exist or is private/unlisted. Your own private deck: "
                         "open it in the browser and use Export, or make it unlisted." % pid)
    if status == 403:
        raise SystemExit("403 from Cloudflare on api2.moxfield.com. Try again in a minute; "
                         "if it persists, export from the browser.")
    if status != 200:
        raise SystemExit("HTTP %s on %s: %s" % (status, pid, str(data)[:200]))
    return data


def deck_from_moxfield(data):
    """api2 JSON -> ({board: [Card]}, meta). Tags come from `authorTags`,
    keyed by card name (not by board)."""
    tags_by_name = data.get("authorTags") or {}
    boards = {b: [] for b in BOARDS}
    for b in BOARDS:
        entries = ((data.get("boards") or {}).get(b) or {}).get("cards") or {}
        for e in entries.values():
            card = e.get("card") or {}
            name = card.get("name")
            if not name:
                continue
            boards[b].append(Card(
                e.get("quantity") or 1, name, b,
                card.get("set"), card.get("cn"),
                bool(e.get("isFoil")) or e.get("finish") in ("foil", "etched"),
                bool(e.get("isAlter")),
                tags=tags_by_name.get(name) or [],
            ))
    meta = {
        "moxfield": data.get("publicUrl") or "",
        "name": data.get("name") or "",
        "format": canonical_format(data.get("format")) if data.get("format") else "",
        "visibility": data.get("visibility") or "",
    }
    if data.get("bracket"):
        meta["bracket"] = str(data["bracket"])
    return boards, meta


# --------------------------------------------------------------------------- #
# scryfall
# --------------------------------------------------------------------------- #

class Scryfall:
    def __init__(self, delay=SCRY_DELAY):
        self.delay = delay
        self.cache = {}

    def _post(self, identifiers):
        req = urllib.request.Request(
            SCRY_COLLECTION, data=json.dumps({"identifiers": identifiers}).encode(),
            headers={"User-Agent": UA_SCRY, "Content-Type": "application/json",
                     "Accept": "application/json"}, method="POST")
        time.sleep(self.delay)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def _named_fuzzy(self, name):
        url = SCRY_NAMED + "?" + urllib.parse.urlencode({"fuzzy": name})
        status, data = _get_json(url, {"User-Agent": UA_SCRY, "Accept": "application/json"})
        return data if status == 200 else None

    def pdh_commander(self, card):
        """Can the card lead a Pauper Commander deck? None when Scryfall didn't answer."""
        # oracleid needs no quoting; a name with '"' in it would break !"..."
        what = "oracleid:" + card["oracle_id"] if card.get("oracle_id") else '!"%s"' % card["name"]
        url = SCRY_SEARCH + "?" + urllib.parse.urlencode({"q": what + " is:paupercommander"})
        time.sleep(self.delay)
        status, data = _get_json(url, {"User-Agent": UA_SCRY, "Accept": "application/json"})
        if status == 200:
            return bool(data.get("data"))
        return False if status == 404 else None

    def resolve(self, names):
        """-> {requested_name: card_json | None}. Custom cards first, then batches
        of 75; front-face fallback, then fuzzy."""
        out = {}
        custom = scryfall.load_custom_cards()
        for n in dict.fromkeys(names):
            hit = custom.get(scryfall.fold(scryfall.front_face(n)))
            if hit and n not in self.cache:
                self.cache[n] = hit
        pending = [n for n in dict.fromkeys(names) if n not in self.cache]
        for i in range(0, len(pending), 75):
            chunk = pending[i:i + 75]
            data = self._post([{"name": n} for n in chunk])
            found = {fold(c["name"]): c for c in data.get("data", [])}
            for n in chunk:
                hit = found.get(fold(n))
                if hit is None and " // " in n:
                    hit = found.get(fold(n.split(" // ")[0]))
                self.cache[n] = hit
        # second round: front face in a batch, then fuzzy one by one
        retry = [n for n in pending if self.cache[n] is None and " // " in n]
        if retry:
            data = self._post([{"name": n.split(" // ")[0]} for n in retry])
            found = {fold(c["name"]): c for c in data.get("data", [])}
            for n in retry:
                self.cache[n] = found.get(fold(n.split(" // ")[0])) or \
                    next((c for c in found.values() if fold(c["name"]).startswith(fold(n.split(" // ")[0]))), None)
        for n in pending:
            if self.cache[n] is None:
                time.sleep(self.delay)
                self.cache[n] = self._named_fuzzy(n)
        for n in names:
            out[n] = self.cache.get(n)
        return out


def card_colors(sc):
    return set(sc.get("color_identity") or [])


def can_be_commander(sc):
    tl = sc.get("type_line") or ""
    text = sc.get("oracle_text") or " ".join(f.get("oracle_text") or "" for f in sc.get("card_faces") or [])
    front = (sc.get("card_faces") or [{}])[0]
    tl_front = front.get("type_line") or tl
    return ("Legendary" in tl_front and "Creature" in tl_front) or "can be your commander" in text


def any_number_allowed(sc):
    tl = sc.get("type_line") or ""
    text = sc.get("oracle_text") or ""
    return "Basic" in tl or "A deck can have any number of cards named" in text


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #

def validate(boards, fmt="commander", scry=None, out=sys.stderr):
    problems, warnings = [], []
    all_cards = [c for b in BOARDS for c in boards[b]]
    deck_cards = [c for b in DECK_BOARDS for c in boards[b]]
    total = sum(c.qty for c in deck_cards)
    cmds = boards["commanders"]

    if fmt in COMMANDER_FORMATS:
        if not cmds:
            problems.append("no commander: put it under `// Commander`, otherwise Moxfield "
                            "dumps everything into the mainboard and the deck ends up with 101")
        if len(cmds) > 2:
            problems.append("%d commanders; maximum 2 (partner/background)" % len(cmds))
        if total != 100:
            problems.append("deck has %d cards (commander + companion + main); needs 100" % total)

    # duplicates across deck boards (main vs commander is the classic one)
    seen = {}
    for c in deck_cards:
        seen.setdefault(c.key, []).append(c)
    dupes = {k: v for k, v in seen.items() if sum(x.qty for x in v) > 1}

    if scry is None:
        for k, v in dupes.items():
            if not any(v[0].name.startswith(bt) for bt in BASIC_TYPES):
                warnings.append("duplicate (%dx): %s — fine only if basic or "
                                "'any number'" % (sum(x.qty for x in v), v[0].name))
        _report(problems, warnings, out)
        return not problems

    names = [c.name for c in all_cards]
    resolved = scry.resolve(names)
    unresolved = [c for c in all_cards if resolved.get(c.name) is None]
    for c in unresolved:
        problems.append("name not found on Scryfall (line %d, %s): %s"
                        % (c.line, BOARD_TITLE[c.board], c.name))
    custom = sorted({resolved[c.name]["name"] for c in all_cards
                     if scryfall.is_custom(resolved.get(c.name))})
    if custom:
        warnings.append("custom cards, legality and commander eligibility not checked: "
                        + ", ".join(custom))
    renamed = [(c, resolved[c.name]["name"]) for c in all_cards
               if resolved.get(c.name) and fold(resolved[c.name]["name"]) != c.key
               and fold(resolved[c.name]["name"].split(" // ")[0]) != c.key]
    for c, real in renamed:
        warnings.append("line %d: '%s' resolved as '%s' — check it and fix the file"
                        % (c.line, c.name, real))

    for k, v in dupes.items():
        sc = resolved.get(v[0].name)
        if sc and not any_number_allowed(sc):
            problems.append("duplicate (%dx) not allowed: %s" % (sum(x.qty for x in v), v[0].name))

    if fmt in COMMANDER_FORMATS and cmds:
        ci = set()
        for c in cmds:
            sc = resolved.get(c.name)
            if not sc:
                continue
            if scryfall.is_custom(sc):
                pass
            elif fmt == "paupercommander":
                ok = scry.pdh_commander(sc)
                if ok is None:
                    warnings.append("could not ask Scryfall whether %s can lead a Pauper "
                                    "Commander deck; run validate again" % c.name)
                elif not ok:
                    problems.append("cannot lead a Pauper Commander deck (needs a creature "
                                    "printed at uncommon): %s" % c.name)
            elif not can_be_commander(sc):
                problems.append("cannot be a commander: %s (%s)" % (c.name, sc.get("type_line")))
            ci |= card_colors(sc)
        if len(cmds) == 2:
            texts = [(resolved.get(c.name) or {}).get("oracle_text") or "" for c in cmds]
            tls = [(resolved.get(c.name) or {}).get("type_line") or "" for c in cmds]
            partner = all("Partner" in t for t in texts)
            background = any("Background" in t for t in tls) and any("Choose a Background" in t for t in texts)
            if not (partner or background):
                problems.append("two commanders without Partner or Background: %s + %s"
                                % (cmds[0].name, cmds[1].name))
        for c in deck_cards:
            sc = resolved.get(c.name)
            if sc and not card_colors(sc) <= ci:
                problems.append("outside color identity %s: %s (%s)"
                                % ("".join(sorted(ci)) or "colorless", c.name,
                                   "".join(sorted(card_colors(sc)))))

    gc = []
    for c in deck_cards:
        sc = resolved.get(c.name)
        if not sc or scryfall.is_custom(sc):
            continue
        leg = (sc.get("legalities") or {}).get(fmt)
        # A Pauper Commander commander is usually an uncommon: not legal in the 99,
        # but a banned one is still banned.
        if fmt == "paupercommander" and c.board == "commanders" and leg == "not_legal":
            continue
        if leg in ("banned", "not_legal"):
            problems.append("%s in %s: %s" % (leg, fmt, c.name))
        elif leg == "restricted":
            warnings.append("restricted in %s: %s" % (fmt, c.name))
        if sc.get("game_changer"):
            gc.append(c.name)
    if fmt == "commander" and gc:
        warnings.append("game changers (%d): %s — bracket 3 allows up to 3; 4+ is bracket 4"
                        % (len(gc), ", ".join(sorted(gc))))

    _report(problems, warnings, out)
    return not problems


def _report(problems, warnings, out):
    for p in problems:
        print("ERROR   " + p, file=out)
    for w in warnings:
        print("WARNING " + w, file=out)
    if not problems and not warnings:
        print("ok", file=out)


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #

def diff_boards(local, remote):
    """-> list of (board, symbol, text). '+' local only, '-' remote only, '~' qty/tags."""
    rows = []
    for b in BOARDS:
        li = {c.key: c for c in merge(local.get(b) or [])}
        ri = {c.key: c for c in merge(remote.get(b) or [])}
        for k in sorted(set(li) | set(ri)):
            lc, rc = li.get(k), ri.get(k)
            if lc and not rc:
                rows.append((b, "+", lc.render(with_printing=False)))
            elif rc and not lc:
                rows.append((b, "-", rc.render(with_printing=False)))
            else:
                bits = []
                if lc.qty != rc.qty:
                    bits.append("qty %d -> %d" % (rc.qty, lc.qty))
                if sorted(lc.tags) != sorted(rc.tags):
                    bits.append("tags %s -> %s" % (sorted(rc.tags), sorted(lc.tags)))
                if bits:
                    rows.append((b, "~", "%s (%s)" % (lc.name, "; ".join(bits))))
    return rows


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def cmd_pull(a):
    data = fetch_deck(a.deck)
    if a.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
        return 0
    boards, meta = deck_from_moxfield(data)
    text = render_deck(boards, meta)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(text)
        print("written to %s" % a.output, file=sys.stderr)
    else:
        sys.stdout.write(text)
    counts = ", ".join("%s %d" % (BOARD_TITLE[b], sum(c.qty for c in boards[b]))
                       for b in BOARDS if boards[b])
    print("%s | %s | %s | bracket %s | %s" % (meta["name"], meta["format"], meta["visibility"],
                                            meta.get("bracket", "-"), counts), file=sys.stderr)
    return 0


def cmd_validate(a):
    boards, meta = parse_deck(_read(a.deck))
    if "_warning" in meta:
        print("WARNING " + meta["_warning"], file=sys.stderr)
    fmt = canonical_format(a.format or meta.get("format"))
    ok = validate(boards, fmt, None if a.offline else Scryfall(a.delay))
    return 0 if ok else 1


def cmd_diff(a):
    local, _ = parse_deck(_read(a.deck))
    remote, meta = deck_from_moxfield(fetch_deck(a.moxfield))
    rows = diff_boards(local, remote)
    if not rows:
        print("identical: %s == %s" % (a.deck, meta["moxfield"]), file=sys.stderr)
        return 0
    cur = None
    for b, sym, txt in rows:
        if b != cur:
            print("== " + BOARD_TITLE[b])
            cur = b
        print("%s %s" % (sym, txt))
    print("\n+ local file only, - Moxfield only, ~ quantity/tags differ",
          file=sys.stderr)
    return 1


def cmd_export(a):
    boards, _ = parse_deck(_read(a.deck))
    wanted = [a.board] if a.board else [b for b in BOARDS if boards[b]]
    chunks = []
    for b in wanted:
        body = "\n".join(c.render(not a.no_tags, not a.no_printing)
                         for c in merge(boards[b]))
        chunks.append((b, body))
    if a.board:
        text = chunks[0][1] + "\n"
    else:
        text = "\n\n".join("== %s ==\n%s" % (BOARD_TITLE[b], body) for b, body in chunks) + "\n"
    if a.copy:
        tool = next((t for t in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"])
                     if shutil.which(t[0])), None)
        if not tool:
            raise SystemExit("no wl-copy/xclip/pbcopy on PATH")
        subprocess.run(tool, input=text.encode(), check=True)
        print("copied to clipboard: %s" % ", ".join(BOARD_TITLE[b] for b, _ in chunks),
              file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pull", help="public Moxfield deck -> local file")
    s.add_argument("deck", help="public id or URL")
    s.add_argument("-o", "--output")
    s.add_argument("--json", action="store_true", help="raw api2 JSON")
    s.set_defaults(fn=cmd_pull)

    s = sub.add_parser("validate", help="structure, names (Scryfall) and legality")
    s.add_argument("deck", help="local file or - for stdin")
    s.add_argument("--format", help="default: the file's '// Format:', otherwise commander")
    s.add_argument("--offline", action="store_true", help="structural checks only")
    s.add_argument("--delay", type=float, default=SCRY_DELAY)
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("diff", help="local file vs deck on Moxfield")
    s.add_argument("deck")
    s.add_argument("moxfield", help="public id or URL")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("export", help="blocks for Bulk Edit")
    s.add_argument("deck")
    s.add_argument("--board", choices=BOARDS)
    s.add_argument("--no-tags", action="store_true", help="omit tags")
    s.add_argument("--no-printing", action="store_true", help="quantity and name only")
    s.add_argument("--copy", action="store_true", help="send to the clipboard")
    s.set_defaults(fn=cmd_export)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    # Card names are Unicode; Windows would otherwise use its legacy code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
