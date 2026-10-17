#!/usr/bin/env python3
"""Consulta de cartas de Magic na API da Scryfall.

Quatro subcomandos: carta (texto oracle de uma ou muitas cartas, inclusive
decklist inteira), busca (sintaxe de busca da Scryfall), edicoes (todas as
impressoes de uma carta) e regras (rulings).

Saida pensada para ser lida por um modelo: texto compacto no stdout, relatorio
de nomes nao resolvidos e avisos no stderr, --json quando outro script consome.
"""

import argparse
import difflib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://api.scryfall.com"
# Scryfall exige User-Agent e Accept; sem eles responde 400.
UA = "mtg-skills/0.1"
# Scryfall pede no maximo 10 req/s. 0.1s entre chamadas respeita isso.
DEFAULT_DELAY = 0.1
COLLECTION_BATCH = 75
PAGE_SIZE = 175
# "Lightnig Bolt" x "Lightning Bolt" = 0.96; "Raio" x "Samurai of the Pale
# Curtain" = 0.26. 0.75 separa erro de grafia de chute da API.
FUZZY_MIN_RATIO = 0.75

SECTION_HEADERS = {
    "deck": "main", "main": "main", "maindeck": "main", "main deck": "main",
    "mainboard": "main", "principal": "main",
    "sideboard": "side", "side": "side", "sb": "side", "reserva": "side",
    "maybeboard": "maybe", "maybe": "maybe", "considerando": "maybe",
    "commander": "commander", "comandante": "commander",
    "companion": "companion", "companheiro": "companion",
}
SECTIONS = ("commander", "companion", "main", "side", "maybe")
SECTION_LABELS = {"commander": "Comandante", "companion": "Companheiro",
                  "main": "Main deck", "side": "Sideboard", "maybe": "Maybeboard"}

LINE_RE = re.compile(r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<rest>\S.*?)\s*$")
SB_PREFIX_RE = re.compile(r"^\s*SB:\s*", re.I)
MWS_SET_RE = re.compile(r"^\[[^\]]*\]\s*")
ARENA_TAIL_RE = re.compile(r"\s*\([A-Za-z0-9]{2,6}\)\s+[0-9]+[a-z★]?\s*$")
FOIL_MARK_RE = re.compile(r"\s*\*[FEfe]\*\s*$")

# Campos que valem a pena quando --json: o objeto cru da Scryfall tem ~60.
CARD_FIELDS = (
    "name", "layout", "lang", "printed_name", "mana_cost", "cmc", "type_line",
    "oracle_text", "power", "toughness", "loyalty", "defense", "colors",
    "color_identity", "keywords", "legalities", "set", "set_name",
    "collector_number", "rarity", "released_at", "prices", "finishes", "promo",
    "digital", "image_uris", "scryfall_uri", "rulings_uri", "prints_search_uri",
)
FACE_FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "power",
               "toughness", "loyalty", "defense", "colors", "image_uris")


# --------------------------------------------------------------------------- #
# nomes
# --------------------------------------------------------------------------- #

def fold(s):
    """Chave de comparacao: sem acento, sem caixa, espacos colapsados."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def front_face(name):
    """'A // B' -> 'A'. /cards/collection so reconhece a face da frente."""
    return name.split("//")[0].strip() if "//" in name else name.strip()


def clean_card_name(raw):
    """Tira ruido de export de outras ferramentas, preservando o nome real."""
    name = raw.strip()
    name = MWS_SET_RE.sub("", name)
    prev = None
    while prev != name:
        prev = name
        name = FOIL_MARK_RE.sub("", name)
        name = ARENA_TAIL_RE.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


# --------------------------------------------------------------------------- #
# parsing de decklist (mesmas regras da skill ligamagic-preco, duplicadas de
# proposito para a skill ser autocontida)
# --------------------------------------------------------------------------- #

class Entry:
    __slots__ = ("qty", "raw", "name", "section", "card", "status", "note")

    def __init__(self, qty, raw, section="main"):
        self.qty = qty
        self.raw = raw
        self.name = clean_card_name(raw)
        self.section = section
        self.card = None
        self.status = "pendente"
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
# rede
# --------------------------------------------------------------------------- #

_last_call = [0.0]
DELAY = [DEFAULT_DELAY]
RETRY_STATUS = {429, 500, 502, 503, 504}


def _http(method, url, body=None, retries=3):
    """Uma chamada a API, com ritmo e recuo em 429/5xx.

    Erros 4xx que a Scryfall explica (404 not_found, ambiguous) voltam como o
    JSON de erro, nao como excecao: o chamador decide o que dizer ao usuario.
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
                print(f"aviso: HTTP {exc.code} da Scryfall; aguardando {pause:.0f}s",
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
    raise RuntimeError("inalcancavel")


def api(path, **params):
    url = path if path.startswith("http") else API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return _http("GET", url)


def is_error(obj):
    return isinstance(obj, dict) and obj.get("object") == "error"


# --------------------------------------------------------------------------- #
# resolucao de nome
# --------------------------------------------------------------------------- #

def _index_cards(cards):
    """Chaves pelas quais uma carta devolvida pode casar com o nome pedido."""
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


def resolve_names(names, report):
    """Nome pedido -> objeto carta, via /cards/collection + fallbacks.

    Scryfall so casa o nome exato em ingles na colecao; 'A // B' precisa ir
    como 'A'. O que sobrar tenta fuzzy (erros de grafia, alguns nomes em
    portugues) e depois busca por nome impresso em portugues.
    """
    wanted = {}
    for n in names:
        wanted.setdefault(fold(front_face(n)), front_face(n))
    found = {}
    keys = list(wanted)
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
        # Nome impresso em portugues, casamento exato ('!'): 'name:' e
        # substring e devolveria 67 cartas para "Raio".
        pt = api("/cards/search", q=f'!"{query}" lang:pt', unique="cards")
        if not is_error(pt) and pt.get("data"):
            card = pt["data"][0]
            # A impressao em portugues tem oracle em ingles e o nome canonico
            # em 'name'; 'printed_name' e o que o usuario escreveu.
            found[k] = card
            report.renames[query] = (card["name"], "nome em português")
            continue
        card = api("/cards/named", fuzzy=query)
        if is_error(card):
            report.missing[query] = card.get("details") or ""
            continue
        # fuzzy com nome curto ou em portugues devolve qualquer coisa ("Raio"
        # -> Samurai of the Pale Curtain). So aceita se parecer com o pedido.
        if looks_like(query, card):
            found[k] = card
            report.renames[query] = (card["name"], "fuzzy")
        else:
            report.missing[query] = (f"fuzzy sugeriu \"{card['name']}\", rejeitado "
                                     "por não parecer com o nome pedido")
    return found, wanted


def looks_like(query, card):
    """Gate do fuzzy: substring ou similaridade alta com algum nome da carta."""
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

    def emit(self, out=None):
        out = out or sys.stderr
        if self.warnings:
            for w in self.warnings:
                print(f"AVISO DA SCRYFALL: {w}", file=out)
            print("  ^ expressao ignorada = a busca ficou MAIS AMPLA do que o "
                  "pedido. Corrija a query antes de usar o resultado.", file=out)
        if self.renames:
            print(f"Nomes ajustados ({len(self.renames)}):", file=out)
            for old, (new, why) in self.renames.items():
                print(f"  {old}  ->  {new}   [{why}]", file=out)
        if self.missing:
            print(f"NÃO ENCONTRADA na Scryfall ({len(self.missing)}):", file=out)
            for name, hint in self.missing.items():
                print(f"  {name}" + (f"\n      {hint}" if hint else ""), file=out)

    @property
    def failed(self):
        return bool(self.missing or self.warnings)


# --------------------------------------------------------------------------- #
# formatacao
# --------------------------------------------------------------------------- #

def faces_of(card):
    """Faces com texto proprio; carta normal e uma face so."""
    if card.get("oracle_text") is None and card.get("card_faces"):
        return card["card_faces"]
    return [card]


def _pt(face):
    if face.get("power") is not None:
        return f"{face['power']}/{face['toughness']}"
    if face.get("loyalty") is not None:
        return f"lealdade {face['loyalty']}"
    if face.get("defense") is not None:
        return f"defesa {face['defense']}"
    return ""


def format_card(card, formats, rulings=None):
    lines = []
    name = card.get("name", "?")
    ci = "".join(card.get("color_identity") or []) or "incolor"
    head = f"{name}  [{card.get('set', '').upper()} {card.get('collector_number', '')}]  identidade: {ci}"
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
    if formats:
        leg = card.get("legalities") or {}
        parts = [f"{f}: {leg.get(f, '?').replace('_', ' ')}" for f in formats]
        lines.append("  legalidade: " + ", ".join(parts))
    if rulings is not None:
        if rulings:
            lines.append("  rulings:")
            for r in rulings:
                lines.append(f"    [{r.get('published_at')}] {r.get('comment')}")
        else:
            lines.append("  rulings: sem rulings")
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
    """Uma carta por nome aproximado, para edicoes/regras. (carta, erro)."""
    card = api("/cards/named", fuzzy=query)
    if is_error(card):
        if card.get("type") == "ambiguous":
            return None, f"nome ambíguo: {card.get('details')}"
        return None, card.get("details") or "não encontrada"
    return card, None


# --------------------------------------------------------------------------- #
# subcomandos
# --------------------------------------------------------------------------- #

def cmd_carta(args):
    if args.deck:
        text = sys.stdin.read() if args.deck == "-" else \
            Path(args.deck).read_text(encoding="utf-8", errors="replace")
        sections = parse_input(text)
        if not any(sections.values()):
            print("nenhuma carta reconhecida na entrada", file=sys.stderr)
            return 2
    elif args.nomes:
        sections = {k: [] for k in SECTIONS}
        sections["main"] = [Entry(1, n) for n in args.nomes]
    else:
        print("passe nomes de carta ou -d ARQUIVO (- para stdin)", file=sys.stderr)
        return 2

    entries = [e for s in SECTIONS for e in sections[s]]
    report = Report()
    found, _ = resolve_names([e.name for e in entries], report)
    formats = [f.strip() for f in args.formatos.split(",") if f.strip()]

    rulings = {}
    for e in entries:
        e.card = found.get(fold(front_face(e.name)))
        if e.card and args.regras:
            key = e.card.get("rulings_uri")
            if key not in rulings:
                rulings[key] = fetch_rulings(e.card)

    if args.json:
        payload = {"cartas": [], "nao_encontradas": list(report.missing)}
        for e in entries:
            if not e.card:
                continue
            item = trim_card(e.card, rulings.get(e.card.get("rulings_uri")) if args.regras else None)
            item["pedido"] = e.name
            item["qtd"] = e.qty
            item["secao"] = e.section
            payload["cartas"].append(item)
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
                                  rulings.get(e.card.get("rulings_uri")) if args.regras else None))
    report.emit()
    return 1 if report.failed else 0


def cmd_busca(args):
    report = Report()
    params = {"q": args.query, "unique": args.unique}
    if args.ordem:
        params["order"] = args.ordem
    if args.dir:
        params["dir"] = args.dir
    cards, total = [], 0
    resp = api("/cards/search", **params)
    while True:
        if is_error(resp):
            if resp.get("code") == "not_found":
                print(f"nenhuma carta para a query: {args.query}", file=sys.stderr)
                if resp.get("details"):
                    print(f"  {resp['details']}", file=sys.stderr)
                return 1
            print(f"erro da Scryfall: {resp.get('details')}", file=sys.stderr)
            return 1
        for w in resp.get("warnings") or []:
            if w not in report.warnings:
                report.warnings.append(w)
        total = resp.get("total_cards", 0)
        cards.extend(resp.get("data") or [])
        if not resp.get("has_more") or (not args.todas and len(cards) >= args.limite):
            break
        resp = api(resp["next_page"])
    if not args.todas:
        cards = cards[:args.limite]

    if args.json:
        json.dump({"total": total, "mostradas": len(cards),
                   "cartas": [trim_card(c) for c in cards]},
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
    print(f"{total} carta(s) no total, {len(cards)} mostrada(s)"
          + ("" if args.todas or len(cards) >= total else
             f". Use --limite N ou --todas para ver mais"), file=sys.stderr)
    report.emit()
    return 1 if report.failed else 0


def cmd_edicoes(args):
    card, err = lookup_one(args.nome)
    if err:
        print(err, file=sys.stderr)
        return 1
    prints = []
    resp = api(card["prints_search_uri"])
    while True:
        if is_error(resp):
            print(f"erro da Scryfall: {resp.get('details')}", file=sys.stderr)
            return 1
        prints.extend(resp.get("data") or [])
        if not resp.get("has_more"):
            break
        resp = api(resp["next_page"])
    if args.sem_digital:
        prints = [p for p in prints if not p.get("digital")]
    if args.sem_promo:
        prints = [p for p in prints if not p.get("promo")]

    if args.json:
        json.dump({"nome": card["name"], "edicoes": [trim_card(p) for p in prints]},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    print(f"{card['name']} — {len(prints)} impressão(ões)")
    print(f"{'set':<6} {'edição':<34} {'nº':>7} {'data':<10} {'acab.':<16} "
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
        if args.imagem:
            for face in faces_of(p):
                uri = (face.get("image_uris") or p.get("image_uris") or {}).get("normal")
                if uri:
                    print(f"       {uri}")
    return 0


def cmd_regras(args):
    card, err = lookup_one(args.nome)
    if err:
        print(err, file=sys.stderr)
        return 1
    rulings = fetch_rulings(card)
    if args.json:
        json.dump({"nome": card["name"],
                   "rulings": trim_card(card, rulings)["rulings"]},
                  sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    print(f"{card['name']} — {len(rulings)} ruling(s)" if rulings
          else f"{card['name']} — sem rulings")
    for r in rulings:
        print(f"[{r.get('published_at')}] {r.get('comment')}")
    return 0


# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Cartas de Magic pela API da Scryfall.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="emitir JSON no stdout em vez de texto")
    common.add_argument("--delay", type=float, default=DEFAULT_DELAY, metavar="SEG",
                        help=f"pausa entre chamadas (padrão {DEFAULT_DELAY})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("carta", parents=[common],
                       help="texto oracle de uma ou mais cartas")
    p.add_argument("nomes", nargs="*", help="nomes (EN ou PT; 'A // B' aceito)")
    p.add_argument("-d", "--deck", metavar="ARQ",
                   help="decklist em qualquer formato; - para stdin")
    p.add_argument("--formatos", default="commander",
                   help="legalidades a mostrar, separadas por vírgula (padrão: commander)")
    p.add_argument("--regras", action="store_true", help="incluir rulings")
    p.set_defaults(fn=cmd_carta)

    p = sub.add_parser("busca", parents=[common],
                       help="busca com a sintaxe da Scryfall")
    p.add_argument("query")
    p.add_argument("--ordem", metavar="CAMPO",
                   help="name, cmc, released, usd, eur, edhrec, rarity, color, power, toughness...")
    p.add_argument("--dir", choices=("asc", "desc"))
    p.add_argument("--unique", default="cards", choices=("cards", "art", "prints"))
    p.add_argument("--limite", type=int, default=50, metavar="N",
                   help="máximo de cartas mostradas (padrão 50)")
    p.add_argument("--todas", action="store_true", help="seguir todas as páginas")
    p.set_defaults(fn=cmd_busca)

    p = sub.add_parser("edicoes", parents=[common],
                       help="todas as impressões de uma carta")
    p.add_argument("nome")
    p.add_argument("--sem-digital", action="store_true", help="ocultar MTGO/Arena")
    p.add_argument("--sem-promo", action="store_true")
    p.add_argument("--imagem", action="store_true", help="URL da imagem por face")
    p.set_defaults(fn=cmd_edicoes)

    p = sub.add_parser("regras", parents=[common], help="rulings de uma carta")
    p.add_argument("nome")
    p.set_defaults(fn=cmd_regras)

    args = ap.parse_args(argv)
    DELAY[0] = args.delay
    try:
        return args.fn(args)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"falha de rede ou da API: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
