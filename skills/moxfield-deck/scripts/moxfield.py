#!/usr/bin/env python3
"""Deck local <-> Moxfield.

Subcomandos:
  baixar   <id|url> [-o deck.txt] [--json]     deck publico do Moxfield -> arquivo local
  validar  <deck.txt> [--formato commander]    checa estrutura, nomes e legalidade (Scryfall)
  diff     <deck.txt> <id|url>                 local vs Moxfield, por board
  exportar <deck.txt> [--board X] [--copiar]   blocos para colar no Bulk Edit

So biblioteca padrao. Leitura usa o api2.moxfield.com (mesmo endpoint do site);
nao existe escrita por API — isso e feito no navegador, ver SKILL.md.
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

MOX_API = "https://api2.moxfield.com/v3/decks/all/"
SCRY_COLLECTION = "https://api.scryfall.com/cards/collection"
SCRY_NAMED = "https://api.scryfall.com/cards/named"
UA_BROWSER = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
UA_SCRY = "mtg-skills/0.1 (moxfield-deck)"
SCRY_DELAY = 0.1

# Boards do Moxfield que importam para deck de Commander. Os outros
# (attractions, stickers, planes...) ficam de fora de proposito.
BOARDS = ("commanders", "companions", "mainboard", "sideboard", "maybeboard")
BOARD_TITLE = {
    "commanders": "Commander", "companions": "Companion", "mainboard": "Mainboard",
    "sideboard": "Sideboard", "maybeboard": "Maybeboard",
}
SECTION_HEADERS = {
    "commander": "commanders", "commanders": "commanders", "comandante": "commanders",
    "companion": "companions", "companheiro": "companions",
    "main": "mainboard", "mainboard": "mainboard", "deck": "mainboard",
    "maindeck": "mainboard", "main deck": "mainboard", "principal": "mainboard",
    "sideboard": "sideboard", "side": "sideboard", "sb": "sideboard", "reserva": "sideboard",
    "maybeboard": "maybeboard", "maybe": "maybeboard", "considering": "maybeboard",
    "considerando": "maybeboard",
}
# Conta como "deck" para o total de 100: commander + companion + main.
# Sideboard no Moxfield e lista auxiliar; maybeboard e consideracao.
DECK_BOARDS = ("commanders", "companions", "mainboard")

LINE_RE = re.compile(r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<rest>\S.*?)\s*$")
SET_RE = re.compile(r"\(([A-Za-z0-9]{2,6})\)")
TAG_RE = re.compile(r"#(!?)([^\s#]+)")
MARK_RE = re.compile(r"\*([FAfaEe])\*")
# Numero de colecionador: "123", "123a", "★", "A-123", e os da The List "C15-56",
# "MH1-7", "2X2-391". Precisa ter digito e nao pode parecer palavra de nome.
CN_RE = re.compile(r"^(?=.*[0-9★])[A-Za-z0-9★†]{1,6}(-[A-Za-z0-9★]{1,6})?$")
PUBLIC_ID_RE = re.compile(r"[A-Za-z0-9_-]{20,24}")
BASIC_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes")


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


# --------------------------------------------------------------------------- #
# formato local
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
    """`1 Nome (SET) 123 *F* *A* #tag #!global` — ordem dos sufixos livre."""
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
        # So trata "(XXX)" como set quando esta no fim do nome; "(Art Card)"
        # e parte de nome legitimo e nao casa o regex de 2-6 alfanumericos.
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
    """Arquivo local -> {board: [Card]}, metadados de comentario `// Chave: valor`."""
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
                meta[k.strip().lower()] = v.strip()
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
        meta.setdefault("_aviso", "arquivo sem cabecalho de secao; tudo foi para Mainboard")
    return boards, meta


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
# rede
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
            raise SystemExit("rede: %s" % e.reason)


def public_id(ref):
    """Aceita id puro ou qualquer URL moxfield.com/decks/<id>[/...]."""
    ref = ref.strip()
    m = re.search(r"/decks/(" + PUBLIC_ID_RE.pattern + ")", ref)
    if m:
        return m.group(1)
    if PUBLIC_ID_RE.fullmatch(ref):
        return ref
    raise SystemExit("nao parece id nem URL de deck do Moxfield: %r" % ref)


def fetch_deck(ref):
    pid = public_id(ref)
    status, data = _get_json(MOX_API + pid, {
        "User-Agent": UA_BROWSER, "Accept": "application/json",
        "Referer": "https://moxfield.com/", "Origin": "https://moxfield.com",
    })
    if status == 404:
        raise SystemExit("404: deck %s nao existe ou e privado/unlisted. Deck seu privado: "
                         "abra no navegador e use Export, ou deixe-o unlisted." % pid)
    if status == 403:
        raise SystemExit("403 do Cloudflare no api2.moxfield.com. Tente de novo em um minuto; "
                         "se persistir, exporte pelo navegador.")
    if status != 200:
        raise SystemExit("HTTP %s em %s: %s" % (status, pid, str(data)[:200]))
    return data


def deck_from_moxfield(data):
    """JSON do api2 -> ({board: [Card]}, meta). Tags vem de `authorTags`,
    indexadas por nome de carta (nao por board)."""
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
        "nome": data.get("name") or "",
        "formato": data.get("format") or "",
        "visibilidade": data.get("visibility") or "",
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

    def resolve(self, names):
        """-> {nome_pedido: card_json | None}. Lote de 75; fallback face frontal, depois fuzzy."""
        out = {}
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
        # segunda rodada: face frontal pelo lote, depois fuzzy um a um
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
# validar
# --------------------------------------------------------------------------- #

def validate(boards, fmt="commander", scry=None, out=sys.stderr):
    problems, warnings = [], []
    all_cards = [c for b in BOARDS for c in boards[b]]
    deck_cards = [c for b in DECK_BOARDS for c in boards[b]]
    total = sum(c.qty for c in deck_cards)
    cmds = boards["commanders"]

    if fmt == "commander":
        if not cmds:
            problems.append("sem comandante: ponha-o sob `// Commander`, senao o Moxfield "
                            "joga tudo no mainboard e o deck fica com 101")
        if len(cmds) > 2:
            problems.append("%d comandantes; maximo 2 (partner/background)" % len(cmds))
        if total != 100:
            problems.append("deck tem %d cartas (commander + companion + main); precisa de 100" % total)

    # repetidos entre boards do deck (main vs commander e o classico)
    seen = {}
    for c in deck_cards:
        seen.setdefault(c.key, []).append(c)
    dupes = {k: v for k, v in seen.items() if sum(x.qty for x in v) > 1}

    if scry is None:
        for k, v in dupes.items():
            if not any(v[0].name.startswith(bt) for bt in BASIC_TYPES):
                warnings.append("repetida (%dx): %s — ok so se for basica ou "
                                "'any number'" % (sum(x.qty for x in v), v[0].name))
        _report(problems, warnings, out)
        return not problems

    names = [c.name for c in all_cards]
    resolved = scry.resolve(names)
    unresolved = [c for c in all_cards if resolved.get(c.name) is None]
    for c in unresolved:
        problems.append("nome nao encontrado na Scryfall (linha %d, %s): %s"
                        % (c.line, BOARD_TITLE[c.board], c.name))
    renamed = [(c, resolved[c.name]["name"]) for c in all_cards
               if resolved.get(c.name) and fold(resolved[c.name]["name"]) != c.key
               and fold(resolved[c.name]["name"].split(" // ")[0]) != c.key]
    for c, real in renamed:
        warnings.append("linha %d: '%s' resolveu como '%s' — confira e corrija o arquivo"
                        % (c.line, c.name, real))

    for k, v in dupes.items():
        sc = resolved.get(v[0].name)
        if sc and not any_number_allowed(sc):
            problems.append("repetida (%dx) sem permissao: %s" % (sum(x.qty for x in v), v[0].name))

    if fmt == "commander" and cmds:
        ci = set()
        for c in cmds:
            sc = resolved.get(c.name)
            if not sc:
                continue
            if not can_be_commander(sc):
                problems.append("nao pode ser comandante: %s (%s)" % (c.name, sc.get("type_line")))
            ci |= card_colors(sc)
        if len(cmds) == 2:
            texts = [(resolved.get(c.name) or {}).get("oracle_text") or "" for c in cmds]
            tls = [(resolved.get(c.name) or {}).get("type_line") or "" for c in cmds]
            partner = all("Partner" in t for t in texts)
            background = any("Background" in t for t in tls) and any("Choose a Background" in t for t in texts)
            if not (partner or background):
                problems.append("dois comandantes sem Partner nem Background: %s + %s"
                                % (cmds[0].name, cmds[1].name))
        for c in deck_cards:
            sc = resolved.get(c.name)
            if sc and not card_colors(sc) <= ci:
                problems.append("fora da identidade de cor %s: %s (%s)"
                                % ("".join(sorted(ci)) or "incolor", c.name,
                                   "".join(sorted(card_colors(sc)))))

    gc = []
    for c in deck_cards:
        sc = resolved.get(c.name)
        if not sc:
            continue
        leg = (sc.get("legalities") or {}).get(fmt)
        if leg in ("banned", "not_legal"):
            problems.append("%s em %s: %s" % (leg, fmt, c.name))
        elif leg == "restricted":
            warnings.append("restricted em %s: %s" % (fmt, c.name))
        if sc.get("game_changer"):
            gc.append(c.name)
    if fmt == "commander" and gc:
        warnings.append("game changers (%d): %s — bracket 3 permite ate 3; 4+ e bracket 4"
                        % (len(gc), ", ".join(sorted(gc))))

    _report(problems, warnings, out)
    return not problems


def _report(problems, warnings, out):
    for p in problems:
        print("ERRO  " + p, file=out)
    for w in warnings:
        print("AVISO " + w, file=out)
    if not problems and not warnings:
        print("ok", file=out)


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #

def diff_boards(local, remote):
    """-> lista de (board, simbolo, texto). '+' so no local, '-' so no remoto, '~' qty/tags."""
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


def cmd_baixar(a):
    data = fetch_deck(a.deck)
    if a.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
        return 0
    boards, meta = deck_from_moxfield(data)
    text = render_deck(boards, meta)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(text)
        print("gravado em %s" % a.output, file=sys.stderr)
    else:
        sys.stdout.write(text)
    counts = ", ".join("%s %d" % (BOARD_TITLE[b], sum(c.qty for c in boards[b]))
                       for b in BOARDS if boards[b])
    print("%s | %s | %s | bracket %s | %s" % (meta["nome"], meta["formato"], meta["visibilidade"],
                                            meta.get("bracket", "-"), counts), file=sys.stderr)
    return 0


def cmd_validar(a):
    boards, meta = parse_deck(_read(a.deck))
    if "_aviso" in meta:
        print("AVISO " + meta["_aviso"], file=sys.stderr)
    fmt = a.formato or meta.get("formato") or "commander"
    ok = validate(boards, fmt, None if a.sem_rede else Scryfall(a.delay))
    return 0 if ok else 1


def cmd_diff(a):
    local, _ = parse_deck(_read(a.deck))
    remote, meta = deck_from_moxfield(fetch_deck(a.moxfield))
    rows = diff_boards(local, remote)
    if not rows:
        print("igual: %s == %s" % (a.deck, meta["moxfield"]), file=sys.stderr)
        return 0
    cur = None
    for b, sym, txt in rows:
        if b != cur:
            print("== " + BOARD_TITLE[b])
            cur = b
        print("%s %s" % (sym, txt))
    print("\n+ so no arquivo local, - so no Moxfield, ~ quantidade/tags diferentes",
          file=sys.stderr)
    return 1


def cmd_exportar(a):
    boards, _ = parse_deck(_read(a.deck))
    wanted = [a.board] if a.board else [b for b in BOARDS if boards[b]]
    chunks = []
    for b in wanted:
        body = "\n".join(c.render(not a.sem_tags, not a.sem_edicao)
                         for c in merge(boards[b]))
        chunks.append((b, body))
    if a.board:
        text = chunks[0][1] + "\n"
    else:
        text = "\n\n".join("== %s ==\n%s" % (BOARD_TITLE[b], body) for b, body in chunks) + "\n"
    if a.copiar:
        tool = next((t for t in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"])
                     if shutil.which(t[0])), None)
        if not tool:
            raise SystemExit("nenhum wl-copy/xclip/pbcopy no PATH")
        subprocess.run(tool, input=text.encode(), check=True)
        print("copiado para a area de transferencia: %s" % ", ".join(BOARD_TITLE[b] for b, _ in chunks),
              file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("baixar", help="deck publico do Moxfield -> arquivo local")
    s.add_argument("deck", help="id publico ou URL")
    s.add_argument("-o", "--output")
    s.add_argument("--json", action="store_true", help="JSON cru do api2")
    s.set_defaults(fn=cmd_baixar)

    s = sub.add_parser("validar", help="estrutura, nomes (Scryfall) e legalidade")
    s.add_argument("deck", help="arquivo local ou - para stdin")
    s.add_argument("--formato", help="padrao: '// Formato:' do arquivo, senao commander")
    s.add_argument("--sem-rede", action="store_true", help="so checagens estruturais")
    s.add_argument("--delay", type=float, default=SCRY_DELAY)
    s.set_defaults(fn=cmd_validar)

    s = sub.add_parser("diff", help="arquivo local vs deck no Moxfield")
    s.add_argument("deck")
    s.add_argument("moxfield", help="id publico ou URL")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("exportar", help="blocos para o Bulk Edit")
    s.add_argument("deck")
    s.add_argument("--board", choices=BOARDS)
    s.add_argument("--sem-tags", action="store_true")
    s.add_argument("--sem-edicao", action="store_true", help="so quantidade e nome")
    s.add_argument("--copiar", action="store_true", help="manda para a area de transferencia")
    s.set_defaults(fn=cmd_exportar)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
