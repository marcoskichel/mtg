#!/usr/bin/env python3
"""Show Magic cards in the browser and let the user pick from them.

Two subcommands an agent runs: show (look at a list of cards) and pick (choose
some of them, optionally with a note). Each call blocks until the user answers
in the browser, then prints one JSON object on stdout and exits 0 (answered),
130 (cancelled) or 124 (timed out).

Every call is a tab on one shared page. The page is hosted by a small local
server (the serve subcommand), started on demand by the first call and shut
down after it has been idle for a while. It binds 127.0.0.1 only; API calls
carry a token kept in ~/.cache/mtg-skills/card-picker/server.json.

Card text and images come from Scryfall through skills/scryfall-cards.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scryfall-cards" / "scripts"))
import scryfall  # noqa: E402

CACHE_DIR = Path.home() / ".cache" / "mtg-skills" / "card-picker"
STATE_FILE = CACHE_DIR / "server.json"
LOG_FILE = CACHE_DIR / "server.log"
PAGE = Path(__file__).resolve().parents[1] / "assets" / "picker.html"
DEFAULT_PORT = int(os.environ.get("CARD_PICKER_PORT", "8737"))

# A waiting call long-polls for WAIT_POLL seconds at a time; a request whose
# caller has not polled for CLIENT_GONE seconds belongs to a dead process.
WAIT_POLL = 20
CLIENT_GONE = 45
# The page polls every second; a poll this recent means a tab is open, so a
# new call shows up there instead of opening another tab.
BROWSER_FRESH = 4
IDLE_EXIT = 15 * 60
SYMBOLOGY_MAX_AGE = 30 * 24 * 3600
IMAGE_HOSTS = ("cards.scryfall.io", "svgs.scryfall.io")
SCRYFALL_API = "https://api.scryfall.com/"

EXIT_OK, EXIT_INPUT, EXIT_SERVER, EXIT_TIMEOUT, EXIT_CANCEL = 0, 2, 3, 124, 130
SECTION_ORDER = ("commander", "companion", "main", "side", "maybe")


def code_version():
    """Changes whenever this script or the page changes: a running server
    from an older version is replaced instead of serving a stale page."""
    h = hashlib.sha1()
    for p in (Path(__file__).resolve(), PAGE):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------- #
# input
# --------------------------------------------------------------------------- #

def parse_count(text):
    """'2' -> (2, 2); '1-3' -> (1, 3); 'any' -> (1, None = every card)."""
    text = text.strip().lower()
    if text == "any":
        return 1, None
    m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", text)
    if not m:
        raise argparse.ArgumentTypeError(f"--count wants N, N-M or any, got {text!r}")
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if lo < 1 or hi < lo:
        raise argparse.ArgumentTypeError(f"--count {text!r}: need 1 <= N <= M")
    return lo, hi


def parse_suggestions(text):
    """JSON list of names or {"name": ..., "reason": ...} -> [(name, reason)]."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"--suggestions is not valid JSON: {exc}") from None
    if not isinstance(data, list):
        raise ValueError("--suggestions must be a JSON list")
    out = []
    for item in data:
        if isinstance(item, str):
            out.append((item, ""))
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            out.append((item["name"], str(item.get("reason") or "")))
        else:
            raise ValueError(f"--suggestions item needs a name: {item!r}")
    return out


def read_text(path):
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def collect_entries(args):
    """[(name, reason)] from --deck, --cards and --suggestions, first one wins."""
    entries = []
    if args.deck:
        sections = scryfall.parse_input(read_text(args.deck))
        for key in SECTION_ORDER:
            entries += [(e.name, "") for e in sections[key]]
    entries += [(n, "") for n in args.cards or []]
    if args.suggestions:
        entries += parse_suggestions(read_text(args.suggestions))
    seen, out = set(), []
    for name, reason in entries:
        key = scryfall.fold(scryfall.front_face(name))
        if key and key not in seen:
            seen.add(key)
            out.append((name, reason))
    return out


# --------------------------------------------------------------------------- #
# cards
# --------------------------------------------------------------------------- #

def face_view(face):
    return {
        "name": face.get("name", ""),
        "cost": face.get("mana_cost") or "",
        "type": face.get("type_line", ""),
        "text": face.get("oracle_text") or "",
        "flavor": face.get("flavor_text"),
        "power": face.get("power"),
        "toughness": face.get("toughness"),
        "loyalty": face.get("loyalty"),
        "defense": face.get("defense"),
    }


def card_images(card):
    """Image URL per picture: one per face for transform/MDFC, else one."""
    faces = card.get("card_faces") or []
    if "image_uris" not in card and faces and all("image_uris" in f for f in faces):
        return [u for u in (f["image_uris"].get("normal") for f in faces) if u]
    url = (card.get("image_uris") or {}).get("normal")
    return [url] if url else []


def card_view(card, reason=""):
    """Scryfall card -> what the page renders. Image URLs stay server-side."""
    faces = card.get("card_faces")
    if faces:
        views = [face_view(f) for f in faces]
    else:
        views = [face_view(card)]
    return {
        "id": card["id"],
        "name": card["name"],
        "type": card.get("type_line", ""),
        "faces": views,
        "reason": reason,
        "printsUri": card.get("prints_search_uri") or "",
        **print_view(card),
    }


def print_view(card):
    """The parts of a card that change from one printing to the next."""
    faces = card.get("card_faces") or [{}]
    return {
        "id": card["id"],
        "set": (card.get("set") or "").upper(),
        "setName": card.get("set_name", ""),
        "cn": card.get("collector_number", ""),
        "rarity": card.get("rarity", "common"),
        "artist": card.get("artist") or faces[0].get("artist") or "",
        "images": len(card_images(card)),
    }


def resolve_cards(entries):
    """[(name, reason)] -> ([card view], {card id: [image url]}, Report)."""
    report = scryfall.Report()
    found, _ = scryfall.resolve_names([n for n, _ in entries], report)
    views, images, seen = [], {}, set()
    for name, reason in entries:
        card = found.get(scryfall.fold(scryfall.front_face(name)))
        if card is None or card["id"] in seen:
            continue
        seen.add(card["id"])
        views.append(card_view(card, reason))
        images[card["id"]] = card_images(card)
    return views, images, report


# --------------------------------------------------------------------------- #
# answers
# --------------------------------------------------------------------------- #

def build_answer(req, body):
    """What the page sent -> (JSON for the agent, exit code).

    The page sends indices; names come from the request's own cards, and the
    count and note rules are checked here, not trusted from the page. A
    printing the user chose must be one the server loaded for that card.
    """
    cards = req["cards"]
    status = body.get("status")
    if req["mode"] == "show":
        # Leaving a view is never a refusal: Esc and Done both close it.
        i = body.get("focused")
        name = cards[i]["name"] if type(i) is int and 0 <= i < len(cards) else None
        return {"status": "closed", "focused": name}, EXIT_OK
    if status == "cancelled":
        return {"status": "cancelled"}, EXIT_CANCEL
    if status != "picked":
        raise ValueError(f"unknown status {status!r}")
    picked = body.get("picked")
    # type() and not isinstance(): True would pass as index 1.
    if (not isinstance(picked, list)
            or not all(type(i) is int and 0 <= i < len(cards) for i in picked)
            or len(set(picked)) != len(picked)):
        raise ValueError("picked must be distinct card indices")
    lo, hi = req["min"], req["max"]
    if not lo <= len(picked) <= hi:
        raise ValueError(f"pick between {lo} and {hi} cards, got {len(picked)}")
    chosen = body.get("prints") or {}
    if not isinstance(chosen, dict):
        raise ValueError("prints must map card indices to printing ids")
    loaded = req.get("printings") or {}
    out = {"status": "picked", "picked": []}
    for i in picked:
        pv = cards[i]
        if str(i) in chosen:
            pv = next((p for p in loaded.get(str(i)) or [] if p["id"] == chosen[str(i)]), None)
            if pv is None:
                raise ValueError(f"unknown printing for card {i}")
        out["picked"].append({"name": cards[i]["name"], "set": pv["set"].lower(),
                              "collector_number": pv["cn"]})
    if req.get("prompt"):
        note = str(body.get("note") or "").strip() or None
        if note is None and not req.get("promptOptional"):
            raise ValueError("a note is required")
        if note:
            out["note"] = note
    return out, EXIT_OK


# --------------------------------------------------------------------------- #
# server
# --------------------------------------------------------------------------- #

class Hub:
    """Requests waiting for the user, shared by the HTTP threads."""

    def __init__(self, token, version):
        self.token = token
        self.version = version
        self.cond = threading.Condition()
        self.requests = {}
        self.images = {}
        self.browser_seen = float("-inf")
        self.idle_since = time.monotonic()
        # Set under cond together with the idle check, so no request can be
        # added between "nothing is waiting" and the server stopping.
        self.closing = False
        self.symbols = {}
        self.symbols_lock = threading.Lock()
        self.sets = {}
        self.sets_lock = threading.Lock()
        self.prints_lock = threading.Lock()

    def add(self, req, images):
        rid = secrets.token_hex(6)
        now = time.monotonic()
        with self.cond:
            if self.closing:
                raise RuntimeError("the server is shutting down")
            req.update(id=rid, created=time.time(), answer=None, seen=now)
            self.requests[rid] = req
            self.images.update(images)
            browser = now - self.browser_seen < BROWSER_FRESH
        return rid, browser

    def listing(self):
        with self.cond:
            self.browser_seen = time.monotonic()
            reqs = sorted(self.requests.values(), key=lambda r: r["created"])
            return [{k: v for k, v in r.items() if k not in ("cards", "printings", "answer", "seen")}
                    for r in reqs if r["answer"] is None]

    def get(self, rid):
        with self.cond:
            r = self.requests.get(rid)
            return None if r is None else {k: v for k, v in r.items() if k not in ("answer", "seen")}

    def answer(self, rid, body):
        """Raises KeyError when the caller is gone, ValueError on a bad answer."""
        with self.cond:
            req = self.requests.get(rid)
            if req is None or req["answer"] is not None:
                raise KeyError(rid)
            out, code = build_answer(req, body)
            req["answer"] = (out, code)
            self.cond.notify_all()
            return out, code

    def wait(self, rid, timeout):
        """('done', (json, code)) | ('pending', None) | ('gone', None)."""
        end = time.monotonic() + timeout
        with self.cond:
            while True:
                req = self.requests.get(rid)
                if req is None:
                    return "gone", None
                req["seen"] = time.monotonic()
                if req["answer"] is not None:
                    del self.requests[rid]
                    return "done", req["answer"]
                left = end - time.monotonic()
                if left <= 0:
                    return "pending", None
                self.cond.wait(left)

    def drop(self, rid):
        """Forget a request; returns its answer if the user answered first."""
        with self.cond:
            req = self.requests.pop(rid, None)
            self.cond.notify_all()
            return req and req["answer"]

    def close_if_idle(self):
        with self.cond:
            if self.requests:
                return False
            self.closing = True
            return True

    def prune(self):
        """Forget requests whose caller died; True when idle long enough to exit."""
        now = time.monotonic()
        with self.cond:
            for rid in [r for r, q in self.requests.items() if now - q["seen"] > CLIENT_GONE]:
                del self.requests[rid]
            if self.requests or now - self.browser_seen < BROWSER_FRESH:
                self.idle_since = now
            if now - self.idle_since > IDLE_EXIT:
                self.closing = True
            return self.closing

    def printings(self, rid, n):
        """Paper printings of card n of request rid, newest first; None if gone.

        Loaded from Scryfall on first ask and kept on the request, so the
        answer can check the user's choice against them.
        """
        with self.cond:
            req = self.requests.get(rid)
            if req is None or not 0 <= n < len(req["cards"]):
                return None
            if str(n) in req.setdefault("printings", {}):
                return req["printings"][str(n)]
            uri = req["cards"][n].get("printsUri") or ""
        # One Scryfall walk at a time: the API asks for spaced calls.
        with self.prints_lock:
            prints = load_printings(uri)
        views = [print_view(p) for p in prints]
        with self.cond:
            self.images.update({p["id"]: card_images(p) for p in prints})
            req["printings"][str(n)] = views
        return views

    def set_icon_url(self, code):
        with self.sets_lock:
            if not self.sets:
                self.sets = load_sets()
            return self.sets.get(code)

    def symbol_url(self, symbol):
        # The page asks for a handful of symbols at once; load the table once.
        # A failed load leaves it empty, so the next request tries again.
        with self.symbols_lock:
            if not self.symbols:
                self.symbols = load_symbology()
            return self.symbols.get(symbol)


def load_symbology():
    """{'{W/U}': svg url}, cached on disk for a month."""
    path = CACHE_DIR / "symbology.json"
    if path.exists() and time.time() - path.stat().st_mtime < SYMBOLOGY_MAX_AGE:
        return json.loads(path.read_text())
    resp = scryfall.api("/symbology")
    if scryfall.is_error(resp):
        return {}
    table = {s["symbol"]: s["svg_uri"] for s in resp.get("data") or [] if s.get("svg_uri")}
    write_private(path, json.dumps(table))
    return table


def load_sets():
    """{'dom': icon svg url}, cached on disk for a month."""
    path = CACHE_DIR / "sets.json"
    if path.exists() and time.time() - path.stat().st_mtime < SYMBOLOGY_MAX_AGE:
        return json.loads(path.read_text())
    resp = scryfall.api("/sets")
    if scryfall.is_error(resp):
        return {}
    table = {s["code"]: s["icon_svg_uri"] for s in resp.get("data") or [] if s.get("icon_svg_uri")}
    write_private(path, json.dumps(table))
    return table


def load_printings(uri):
    """Every paper printing behind a card's prints_search_uri."""
    if not uri.startswith(SCRYFALL_API):
        return []
    prints, resp = [], scryfall.api(uri)
    while not scryfall.is_error(resp):
        prints += [p for p in resp.get("data") or [] if "paper" in (p.get("games") or ["paper"])]
        if not resp.get("has_more") or not str(resp.get("next_page", "")).startswith(SCRYFALL_API):
            break
        resp = scryfall.api(resp["next_page"])
    return prints


def cached_fetch(url, path):
    """Bytes of url, kept at path. Only Scryfall's image hosts are fetched."""
    if path.exists():
        return path.read_bytes()
    if urllib.parse.urlsplit(url).hostname not in IMAGE_HOSTS:
        raise ValueError(f"refusing to fetch {url}")
    req = urllib.request.Request(url, headers={"User-Agent": scryfall.UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{secrets.token_hex(4)}")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data


def write_private(path, text):
    """Replace path atomically with a file only this user can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    tmp.replace(path)


def proof(token, nonce):
    return hmac.new(token.encode(), nonce.encode(), hashlib.sha256).hexdigest()


class Handler(BaseHTTPRequestHandler):
    hub = None  # set by make_server

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    # -- plumbing ------------------------------------------------------------

    def send(self, status, body=b"", ctype="application/json", cache=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=604800" if cache else "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def host_ok(self):
        # Blocks DNS rebinding: a remote page can resolve its own name to
        # 127.0.0.1, but it can't make the browser send this Host header.
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def token_ok(self):
        given = self.headers.get("X-Picker-Token") or ""
        return secrets.compare_digest(given.encode(), self.hub.token.encode())

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 <= n <= 5_000_000:
            raise ValueError("bad body length")
        body = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("body must be a JSON object")
        return body

    def route(self):
        path = urllib.parse.urlsplit(self.path).path
        return path, [p for p in path.split("/") if p]

    # -- verbs ---------------------------------------------------------------

    def do_GET(self):
        if not self.host_ok():
            return self.send(HTTPStatus.FORBIDDEN, {"error": "bad host"})
        path, parts = self.route()
        if path == "/":
            return self.send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        if len(parts) == 3 and parts[0] == "img":
            return self.image(parts[1], parts[2])
        if len(parts) == 2 and parts[0] == "sym":
            return self.symbol(urllib.parse.unquote(parts[1]))
        if len(parts) == 2 and parts[0] == "set":
            return self.set_icon(parts[1])
        if not path.startswith("/api/"):
            return self.send(HTTPStatus.NOT_FOUND, {"error": "not found"})
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        if path == "/api/ping":
            # Answered without the token: the caller sends a nonce and the
            # server proves it knows the token, so a process squatting the
            # port never sees the token or the cards.
            nonce = (qs.get("nonce") or [""])[0]
            if not 16 <= len(nonce) <= 64:
                return self.send(HTTPStatus.BAD_REQUEST, {"error": "nonce"})
            with self.hub.cond:
                pending = len(self.hub.requests)
            return self.send(HTTPStatus.OK, {"version": self.hub.version, "pending": pending,
                                             "proof": proof(self.hub.token, nonce)})
        if not self.token_ok():
            return self.send(HTTPStatus.UNAUTHORIZED, {"error": "bad token"})
        if path == "/api/requests":
            return self.send(HTTPStatus.OK, {"requests": self.hub.listing()})
        if len(parts) == 3 and parts[:2] == ["api", "requests"]:
            req = self.hub.get(parts[2])
            if req is None:
                return self.send(HTTPStatus.GONE, {"error": "gone"})
            return self.send(HTTPStatus.OK, req)
        if (len(parts) == 6 and parts[:2] == ["api", "requests"] and parts[3] == "cards"
                and parts[5] == "prints" and parts[4].isdigit()):
            try:
                prints = self.hub.printings(parts[2], int(parts[4]))
            except (OSError, ValueError, urllib.error.URLError) as exc:
                return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            if prints is None:
                return self.send(HTTPStatus.GONE, {"error": "gone"})
            return self.send(HTTPStatus.OK, {"printings": prints})
        if len(parts) == 4 and parts[:2] == ["api", "requests"] and parts[3] == "wait":
            try:
                timeout = max(0.0, min(float((qs.get("timeout") or [WAIT_POLL])[0]), 60))
            except ValueError:
                return self.send(HTTPStatus.BAD_REQUEST, {"error": "timeout"})
            state, ans = self.hub.wait(parts[2], timeout)
            if state == "gone":
                return self.send(HTTPStatus.GONE, {"error": "gone"})
            if state == "pending":
                return self.send(HTTPStatus.OK, {"pending": True})
            return self.send(HTTPStatus.OK, {"answer": ans[0], "code": ans[1]})
        return self.send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        if not self.host_ok():
            return self.send(HTTPStatus.FORBIDDEN, {"error": "bad host"})
        if not self.token_ok():
            return self.send(HTTPStatus.UNAUTHORIZED, {"error": "bad token"})
        path, parts = self.route()
        try:
            body = self.read_json()
        except ValueError as exc:
            return self.send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        if path == "/api/requests":
            images = body.pop("images", {})
            try:
                rid, browser = self.hub.add(body, images)
            except RuntimeError as exc:
                return self.send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            return self.send(HTTPStatus.OK, {"id": rid, "browser": browser})
        if len(parts) == 4 and parts[:2] == ["api", "requests"] and parts[3] == "answer":
            try:
                out, code = self.hub.answer(parts[2], body)
            except KeyError:
                return self.send(HTTPStatus.GONE, {"error": "the agent stopped waiting"})
            except ValueError as exc:
                return self.send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return self.send(HTTPStatus.OK, {"answer": out, "code": code})
        if path == "/api/shutdown":
            if not self.hub.close_if_idle():
                return self.send(HTTPStatus.CONFLICT, {"error": "requests pending"})
            self.send(HTTPStatus.OK, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        return self.send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_DELETE(self):
        if not self.host_ok() or not self.token_ok():
            return self.send(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
        _, parts = self.route()
        if len(parts) == 3 and parts[:2] == ["api", "requests"]:
            ans = self.hub.drop(parts[2])
            return self.send(HTTPStatus.OK, {"answer": ans[0], "code": ans[1]} if ans else {"ok": True})
        return self.send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    # -- images --------------------------------------------------------------

    def image(self, card_id, name):
        m = re.fullmatch(r"(\d)\.jpg", name)
        urls = self.hub.images.get(card_id) or []
        if not m or not re.fullmatch(r"[0-9a-f-]{36}", card_id) or int(m.group(1)) >= len(urls):
            return self.send(HTTPStatus.NOT_FOUND, {"error": "no such image"})
        n = int(m.group(1))
        try:
            data = cached_fetch(urls[n], CACHE_DIR / "cards" / f"{card_id}-{n}.jpg")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        return self.send(HTTPStatus.OK, data, "image/jpeg", cache=True)

    def set_icon(self, name):
        m = re.fullmatch(r"([0-9a-z]{2,8})\.svg", name)
        try:
            url = m and self.hub.set_icon_url(m.group(1))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        if not url:
            return self.send(HTTPStatus.NOT_FOUND, {"error": "no such set"})
        try:
            data = cached_fetch(url, CACHE_DIR / "sets" / f"{m.group(1)}.svg")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        return self.send(HTTPStatus.OK, data, "image/svg+xml", cache=True)

    def symbol(self, name):
        m = re.fullmatch(r"(.{1,12})\.svg", name)
        try:
            url = m and self.hub.symbol_url("{" + m.group(1) + "}")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        if not url:
            return self.send(HTTPStatus.NOT_FOUND, {"error": "no such symbol"})
        key = hashlib.sha1(m.group(1).encode()).hexdigest()[:16]
        try:
            data = cached_fetch(url, CACHE_DIR / "symbols" / f"{key}.svg")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return self.send(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        return self.send(HTTPStatus.OK, data, "image/svg+xml", cache=True)


def make_server(port, token, version):
    hub = Hub(token, version)
    handler = type("BoundHandler", (Handler,), {"hub": hub})
    # No SO_REUSEPORT: two racing servers must not both bind and split calls.
    server_cls = type("PickerServer", (ThreadingHTTPServer,),
                      {"daemon_threads": True, "allow_reuse_port": False})
    return server_cls(("127.0.0.1", port), handler), hub


def cmd_serve(args):
    token = secrets.token_urlsafe(24)
    version = code_version()
    try:
        server, hub = make_server(args.port, token, version)
    except OSError as exc:
        print(f"cannot bind 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return EXIT_SERVER
    write_private(STATE_FILE, json.dumps({
        "port": server.server_address[1], "token": token,
        "pid": os.getpid(), "version": version}))

    def janitor():
        while True:
            time.sleep(5)
            if hub.prune():
                server.shutdown()
                return

    threading.Thread(target=janitor, daemon=True).start()
    print(f"serving on http://127.0.0.1:{server.server_address[1]}/", file=sys.stderr)
    server.serve_forever()
    return EXIT_OK


# --------------------------------------------------------------------------- #
# client
# --------------------------------------------------------------------------- #

def call(state, method, path, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{state['port']}{path}", data=data, method=method,
        headers={"X-Picker-Token": state["token"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        with exc:
            raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"{}")
        except ValueError:
            return exc.code, {}


def read_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return None


def ping(state):
    """The server's status, or None unless it proves it holds state's token."""
    nonce = secrets.token_hex(16)
    try:
        url = f"http://127.0.0.1:{state['port']}/api/ping?nonce={nonce}"
        with urllib.request.urlopen(url, timeout=2) as resp:
            body = json.loads(resp.read())
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None
    if not isinstance(body, dict) or not hmac.compare_digest(
            str(body.get("proof", "")), proof(state["token"], nonce)):
        return None
    return body


def wait_until(check, seconds, step=0.2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = check()
        if found:
            return found
        time.sleep(step)
    return None


def ensure_server(port):
    """State of a live server running this code version, starting one if needed."""
    version = code_version()
    state = read_state()
    alive = state and ping(state)
    if alive and (alive["version"] == version or alive["pending"]):
        # An older server with someone waiting keeps serving: don't kill it.
        return state
    if alive:
        status, _ = call(state, "POST", "/api/shutdown")
        if status == 409:
            return state
        # serve_forever notices the shutdown within half a second; the port
        # is free once the old server stops answering.
        wait_until(lambda: not ping(state), 5)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "ab") as log:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(port)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)

    def started():
        fresh = read_state()
        info = fresh and ping(fresh)
        return fresh if info and info["version"] == version else None

    fresh = wait_until(started, 8)
    if fresh:
        return fresh
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
    except OSError:
        raise RuntimeError(f"the card-picker server did not start; see {LOG_FILE}") from None
    raise RuntimeError(
        f"127.0.0.1:{port} is held by a process that can't prove it is this card-picker "
        f"server (an older version exits after {IDLE_EXIT // 60} idle minutes); "
        "stop it or set CARD_PICKER_PORT")


def default_agent():
    if os.environ.get("CLAUDECODE"):
        return "Claude Code"
    if any(k.startswith("CODEX") for k in os.environ):
        return "Codex"
    return "Agent"


def build_request(args, mode, cards):
    if mode == "show":
        lo = hi = 0
        ask = args.title or (f"Take a look at {Path(args.deck).name}"
                             if args.deck and args.deck != "-" else "Take a look")
        label = args.label or "View"
    else:
        lo, hi = args.count
        hi = len(cards) if hi is None else min(hi, len(cards))
        want = ("any" if lo == 1 and hi == len(cards) > 1
                else f"{lo}" if lo == hi else f"{lo}–{hi}")
        ask = args.title or f"Pick {want} card{'s' if hi > 1 else ''}"
        label = args.label or (f"Pick {want}" + (" + note" if args.prompt else ""))
    return {
        "mode": mode, "min": lo, "max": hi, "ask": ask, "label": label,
        "agent": args.agent or default_agent(),
        "prompt": getattr(args, "prompt", None),
        "promptOptional": getattr(args, "prompt_optional", False),
        "cards": cards,
    }


def run_request(args, mode):
    try:
        entries = collect_entries(args)
    except (OSError, ValueError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return EXIT_INPUT
    if not entries:
        print("no cards given: use --cards, --deck or --suggestions", file=sys.stderr)
        return EXIT_INPUT
    try:
        cards, images, report = resolve_cards(entries)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"network or API failure: {exc}", file=sys.stderr)
        return EXIT_SERVER
    report.emit()
    if not cards:
        print("none of the cards were found on Scryfall", file=sys.stderr)
        return EXIT_INPUT
    if mode == "pick" and args.count[0] > len(cards):
        print(f"--count asks for {args.count[0]} but only {len(cards)} cards were found",
              file=sys.stderr)
        return EXIT_INPUT

    req = build_request(args, mode, cards)
    req["images"] = images
    try:
        for _ in range(3):
            state = ensure_server(args.port)
            status, resp = call(state, "POST", "/api/requests", req)
            if status != 503:  # 503: that server is shutting down, start another
                break
            time.sleep(1)
    except (OSError, urllib.error.URLError, RuntimeError) as exc:
        print(f"card-picker server failure: {exc}", file=sys.stderr)
        return EXIT_SERVER
    if status != 200:
        print(f"card-picker server refused the request: {resp}", file=sys.stderr)
        return EXIT_SERVER

    rid = resp["id"]
    url = f"http://127.0.0.1:{state['port']}/?t={state['token']}"
    print(f"Waiting for the user in the browser ({len(cards)} cards): {url}", file=sys.stderr)
    if not resp["browser"] and not args.no_open:
        webbrowser.open(url)

    # An agent stops a background call with SIGTERM: withdraw the tab then too.
    old_term = signal.signal(signal.SIGTERM, _interrupt)
    deadline = time.monotonic() + args.timeout
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return withdraw(state, rid, "timeout", EXIT_TIMEOUT)
            status, resp = call(state, "GET",
                                f"/api/requests/{rid}/wait?timeout={min(WAIT_POLL, left):.1f}",
                                timeout=WAIT_POLL + 10)
            if status == 200 and "answer" in resp:
                return emit(resp)
            if status != 200:
                print(f"card-picker server lost the request: {resp}", file=sys.stderr)
                return EXIT_SERVER
    except KeyboardInterrupt:
        try:
            return withdraw(state, rid, "cancelled", EXIT_CANCEL)
        except (OSError, urllib.error.URLError):
            print(json.dumps({"status": "cancelled"}))
            return EXIT_CANCEL
    except (OSError, urllib.error.URLError) as exc:
        print(f"card-picker server failure: {exc}", file=sys.stderr)
        return EXIT_SERVER
    finally:
        signal.signal(signal.SIGTERM, old_term)


def _interrupt(signum, frame):
    raise KeyboardInterrupt


def emit(resp):
    print(json.dumps(resp["answer"], ensure_ascii=False, indent=2))
    return resp["code"]


def withdraw(state, rid, status, code):
    """Take the tab down; an answer the user sent in the meantime still wins."""
    _, resp = call(state, "DELETE", f"/api/requests/{rid}")
    if "answer" in resp:
        return emit(resp)
    print(json.dumps({"status": status}))
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Show Magic cards in the browser and let the user pick.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    src = common.add_argument_group("cards (combine freely: deck first, then --cards, then --suggestions)")
    src.add_argument("--cards", nargs="+", metavar="NAME", help="card names")
    src.add_argument("-d", "--deck", metavar="FILE", help="decklist in any format; - for stdin")
    src.add_argument("--suggestions", metavar="FILE",
                     help='JSON list: ["Name", {"name": "...", "reason": "why"}]; - for stdin')
    common.add_argument("--title", help="what you ask the user, shown as the heading")
    common.add_argument("--label", help="short tab label")
    common.add_argument("--agent", help="who is asking (default: detected)")
    common.add_argument("--timeout", type=float, default=1800, metavar="SEC",
                        help="give up after SEC seconds (default 1800)")
    common.add_argument("--no-open", action="store_true",
                        help="don't open a browser tab; the URL is on stderr")
    common.add_argument("--port", type=int, default=DEFAULT_PORT, help=argparse.SUPPRESS)

    p = sub.add_parser("show", parents=[common], help="show cards; the user closes when done")
    p.set_defaults(fn=lambda a: run_request(a, "show"))

    p = sub.add_parser("pick", parents=[common], help="the user picks cards")
    p.add_argument("--count", type=parse_count, default=(1, 1), metavar="N|N-M|any",
                   help="how many to pick (default 1)")
    p.add_argument("--prompt", help="ask for a note after the pick")
    p.add_argument("--prompt-optional", action="store_true", help="the note may be skipped")
    p.set_defaults(fn=lambda a: run_request(a, "pick"))

    p = sub.add_parser("serve", help="run the shared server (started automatically)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
