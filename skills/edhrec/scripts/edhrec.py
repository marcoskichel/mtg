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
