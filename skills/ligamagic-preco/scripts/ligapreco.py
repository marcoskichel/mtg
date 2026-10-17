#!/usr/bin/env python3
"""Preco de cartas de Magic em BRL pelos endpoints internos da LigaMagic.

Dois modos: carta avulsa (preco por edicao, normal e foil) e decklist inteira
(custo total, escolhendo a edicao mais barata com estoque para cada carta).

O nome e resolvido contra o indice da propria Liga antes de pedir preco, porque
'getEditions.php' exige o nome exato dela: um 'Delver of Secrets // Insectile
Aberration' vindo do Moxfield devolve {"error":"2"} e sumiria do total calado.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SEARCH_API = "https://www.clubedaliga.com.br/api/cardsearch"
PRICE_API = "https://www.ligamagic.com.br/ajax/cards/getEditions.php"
REFERER = "https://www.ligamagic.com.br/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

CACHE_DIR = (Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
             / "ligamagic")
# Compartilhado com a skill ligamagic-deck: nome nao envelhece, so cresce.
NAME_CACHE = CACHE_DIR / "cardnames.json"
# Separado: preco envelhece, entao tem TTL e carimbo de tempo por entrada.
PRICE_CACHE = CACHE_DIR / "prices.json"
DEFAULT_TTL_H = 24.0

# Edicoes com preco real mas que nao sao carta sancionada em torneio: borda
# dourada, borda quadrada ou proxy oficial. Entram na conta so com
# --incluir-nao-sancionadas, senao um Force of Will vira R$ 94,90 (World
# Championship Decks) num deck de Legacy.
NAO_SANCIONADAS = {
    "wcd",      # World Championship Decks (borda dourada)
    "ced",      # Collector's Edition (borda quadrada)
    "cedi",     # International Collectors' Edition
    "30a",      # 30th Anniversary Edition (proxy oficial)
    "rf30a",    # 30th Anniversary Edition (Retro Frame)
}

SECTION_HEADERS = {
    "deck": "main", "main": "main", "maindeck": "main", "main deck": "main",
    "mainboard": "main", "principal": "main",
    "sideboard": "side", "side": "side", "sb": "side", "reserva": "side",
    "maybeboard": "maybe", "maybe": "maybe", "considerando": "maybe",
    "commander": "commander", "comandante": "commander",
    "companion": "companion", "companheiro": "companion",
}
SECTIONS = ("main", "side", "maybe", "commander", "companion")
# Maybeboard fica fora do total: e lista de consideracao, nao deck.
TOTAL_SECTIONS = ("main", "side", "commander", "companion")

LINE_RE = re.compile(r"^\s*(?P<qty>\d+)\s*[xX]?\s+(?P<rest>\S.*?)\s*$")
SB_PREFIX_RE = re.compile(r"^\s*SB:\s*", re.I)
MWS_SET_RE = re.compile(r"^\[[^\]]*\]\s*")
ARENA_TAIL_RE = re.compile(r"\s*\([A-Za-z0-9]{2,6}\)\s+[0-9]+[a-z★]?\s*$")
FOIL_MARK_RE = re.compile(r"\s*\*[FEfe]\*\s*$")
VARIANT_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


# --------------------------------------------------------------------------- #
# normalizacao (mesmas regras do ligadeck.py, duplicadas de proposito para a
# skill ser autocontida)
# --------------------------------------------------------------------------- #

def fold(s):
    """Chave de comparacao: sem acento, sem caixa, espacos colapsados."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def clean_card_name(raw):
    """Tira ruido de export de outras ferramentas, preservando o nome real.

    O set code so sai quando vem seguido de numero de colecionador, senao
    sufixos legitimos como '(Art Card)' seriam destruidos.
    """
    name = raw.strip()
    name = MWS_SET_RE.sub("", name)
    prev = None
    while prev != name:
        prev = name
        name = FOIL_MARK_RE.sub("", name)
        name = ARENA_TAIL_RE.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


def brl(v):
    if v is None:
        return "     --"
    return f"R$ {v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------------------- #
# parsing da entrada
# --------------------------------------------------------------------------- #

class Entry:
    __slots__ = ("qty", "raw", "name", "section", "resolved", "status", "note",
                 "price", "edition", "sigla", "aggregate", "editions")

    def __init__(self, qty, raw, section="main"):
        self.qty = qty
        self.raw = raw
        self.name = clean_card_name(raw)
        self.section = section
        self.resolved = None
        self.status = "pendente"
        self.note = ""
        self.price = None        # preco unitario escolhido, None se sem estoque
        self.edition = None      # nome da edicao escolhida
        self.sigla = None
        self.aggregate = None    # dict de precos agregados da carta
        self.editions = []       # lista de edicoes cruas

    @property
    def out(self):
        return self.resolved or self.name

    @property
    def subtotal(self):
        return None if self.price is None else self.price * self.qty


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
    # Sem cabecalho e sem SB:, o unico sinal de secao e a linha em branco.
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
        # Linha "About"/"Name ..." do export do Arena.
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


def merge_duplicates(entries):
    """Junta linhas repetidas dentro da mesma secao, preservando a ordem."""
    order, byname = [], {}
    for e in entries:
        k = fold(e.out)
        if k in byname:
            byname[k].qty += e.qty
        else:
            byname[k] = e
            order.append(k)
    return [byname[k] for k in order]


# --------------------------------------------------------------------------- #
# rede
# --------------------------------------------------------------------------- #

class Throttle:
    """Uma pausa por consulta nao cacheada, compartilhada entre os dois clientes.

    O robots.txt da Liga pede Crawl-delay: 360 para crawler. Isto aqui nao e um
    crawler - sao os mesmos endpoints que o site chama por interacao - mas
    tambem nao pode virar rajada: passado de umas dezenas de consultas seguidas
    o Cloudflare da Liga comeca a devolver 429.
    """

    def __init__(self, delay, retries=4, backoff=8.0):
        self.delay = delay
        self.retries = retries
        self.backoff = backoff
        self.last = 0.0
        self.count = 0

    def wait(self):
        if self.delay and self.count:
            gap = self.delay - (time.monotonic() - self.last)
            if gap > 0:
                time.sleep(gap)
        self.count += 1
        self.last = time.monotonic()


RETRY_STATUS = {429, 500, 502, 503, 504}


def _send(req, timeout, retries, backoff):
    """Uma requisicao, com recuo em 429/5xx.

    A Liga fica atras de Cloudflare e devolve 429 com Retry-After: 10 depois de
    algumas dezenas de consultas seguidas. Sem recuo, um deck de 30 cartas
    unicas vira meia dezena de precos e um total silenciosamente baixo.
    """
    wait = backoff
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == retries:
                raise
            ra = exc.headers.get("Retry-After") if exc.headers else None
            try:
                pause = float(ra) if ra else wait
            except ValueError:
                pause = wait
            print(f"aviso: HTTP {exc.code} da Liga; aguardando {pause:.0f}s "
                  f"(tentativa {attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(pause)
            wait *= 2
    raise RuntimeError("inalcancavel")


def _post(url, fields, timeout, retries, backoff):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Referer": REFERER,
        "Accept": "application/json, text/javascript, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })
    return _send(req, timeout, retries, backoff)


def _get(url, params, timeout, retries, backoff):
    req = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": UA, "Referer": REFERER,
                 "Accept": "application/json"})
    return _send(req, timeout, retries, backoff)


# --------------------------------------------------------------------------- #
# resolucao de nome contra o indice da LigaMagic
# --------------------------------------------------------------------------- #

class NameResolver:
    """Traduz um nome qualquer para a grafia exata da Liga.

    Sem isso o preco vem vazio para toda carta de dupla face vinda do Scryfall
    e o total do deck sai baixo, calado. Cache sem TTL: nome nao envelhece.
    """

    def __init__(self, throttle, use_cache=True, timeout=20):
        self.throttle = throttle
        self.use_cache = use_cache
        self.timeout = timeout
        self.cache = {}
        self.dirty = False
        self.requests = 0
        self.hits = 0
        self.renames = {}
        self.missing = {}
        self.failed = {}
        if use_cache and NAME_CACHE.exists():
            try:
                self.cache = json.loads(NAME_CACHE.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.cache = {}

    def save(self):
        if not (self.use_cache and self.dirty):
            return
        try:
            NAME_CACHE.parent.mkdir(parents=True, exist_ok=True)
            NAME_CACHE.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=0),
                encoding="utf-8")
        except OSError as exc:
            print(f"aviso: nao gravei o cache de nomes ({exc})", file=sys.stderr)

    def _fetch(self, name):
        self.throttle.wait()
        self.requests += 1
        payload = _get(SEARCH_API, {"tcg": "1", "category": "cards",
                                    "maxQuantity": "12", "query": name},
                       self.timeout, self.throttle.retries,
                       self.throttle.backoff)
        if isinstance(payload, list):
            return []
        sugg = payload.get("suggestions") or []
        data = payload.get("data") or []
        out = []
        for i, s in enumerate(sugg):
            pt = ""
            if i < len(data):
                pt = html.unescape(data[i].get("sNomeIdiomaPrincipal") or "")
            out.append((html.unescape(s), pt))
        return out

    @staticmethod
    def _pick(query, candidates):
        """Exato vence; 'A // B' casa com o 'A' da Liga; 'A' casa com 'A // B'.

        Variantes entre parenteses so entram se nada mais casar - senao um
        'Lightning Bolt' pediria preco de '(Art Card)'.
        """
        qf = fold(query)
        front = fold(query.split("//")[0]) if "//" in query else None
        plain = [(en, pt) for en, pt in candidates
                 if not VARIANT_SUFFIX_RE.search(en)]
        for pool in (plain, candidates):
            for en, pt in pool:
                if fold(en) == qf or fold(pt) == qf:
                    return en, "exato"
            if front:
                for en, pt in pool:
                    if fold(en) == front or fold(pt) == front:
                        return en, "face frontal"
            for en, pt in pool:
                if "//" in en and fold(en.split("//")[0]) == qf:
                    return en, "nome composto"
                if pt and "//" in pt and fold(pt.split("//")[0]) == qf:
                    return en, "nome composto"
            for en, pt in pool:
                if pt and fold(pt) == qf:
                    return en, "traduzido do portugues"
        return None, ""

    def _lookup(self, name):
        cands = self._fetch(name)
        picked, why = self._pick(name, cands)
        if picked:
            return picked, why, cands
        if "//" in name:
            front = name.split("//")[0].strip()
            if front:
                cands2 = self._fetch(front)
                picked, why = self._pick(front, cands2)
                if picked:
                    return picked, "face frontal", cands2
                cands = cands or cands2
        return None, "", cands

    def resolve(self, entry):
        key = fold(entry.name)
        if not key:
            entry.status = "erro"
            entry.note = "linha sem nome de carta"
            return
        cached = self.cache.get(key) if self.use_cache else None
        if cached is not None:
            self.hits += 1
        else:
            try:
                name, why, cands = self._lookup(entry.name)
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                entry.resolved = entry.name
                entry.status = "falha de rede"
                entry.note = f"busca de nome falhou: {exc}"
                self.failed[entry.name] = entry.note
                return
            cached = {"n": name, "w": why,
                      "c": [] if name else [en for en, _ in cands[:6]]}
            self.cache[key] = cached
            self.dirty = True

        if cached.get("n"):
            entry.resolved = cached["n"]
            if fold(cached["n"]) == key:
                entry.status = "ok"
            else:
                entry.status = "renomeado"
                entry.note = cached.get("w") or ""
                self.renames[entry.name] = (cached["n"], entry.note)
        else:
            entry.resolved = entry.name
            entry.status = "nao encontrado"
            cands = cached.get("c") or []
            entry.note = ("sugestoes: " + ", ".join(cands[:4])) if cands \
                else "nenhuma sugestao na base da Liga"
            self.missing[entry.name] = entry.note


# --------------------------------------------------------------------------- #
# precos
# --------------------------------------------------------------------------- #

def _num(v):
    """'0.00' na Liga significa SEM ESTOQUE, nao gratis. Vira None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


class PriceClient:
    """getEditions.php + cache com TTL.

    Guarda tanto os agregados do topo quanto a linha de cada edicao, porque os
    dois divergem (ver references/precos.md) e a escolha de qual usar e do
    chamador.
    """

    def __init__(self, throttle, use_cache=True, ttl_hours=DEFAULT_TTL_H,
                 timeout=25):
        self.throttle = throttle
        self.use_cache = use_cache
        self.ttl = ttl_hours * 3600.0
        self.timeout = timeout
        self.cache = {}
        self.dirty = False
        self.requests = 0
        self.hits = 0
        if use_cache and PRICE_CACHE.exists():
            try:
                self.cache = json.loads(PRICE_CACHE.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.cache = {}

    def save(self):
        if not (self.use_cache and self.dirty):
            return
        try:
            PRICE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            PRICE_CACHE.write_text(
                json.dumps(self.cache, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8")
        except OSError as exc:
            print(f"aviso: nao gravei o cache de precos ({exc})", file=sys.stderr)

    def _fetch(self, name):
        self.throttle.wait()
        self.requests += 1
        payload = _post(PRICE_API, {"card_name": name, "returnType": "json",
                                    "edicao_sel": "", "prefixo": ""},
                        self.timeout, self.throttle.retries,
                        self.throttle.backoff)
        if not isinstance(payload, dict) or payload.get("success") != "1":
            # {"error":"2"} = a Liga nao reconheceu o nome.
            return None
        agg = {
            "normal": {"menor": _num(payload.get("normal_precoMenor")),
                       "medio": _num(payload.get("normal_precoMedio")),
                       "maior": _num(payload.get("normal_precoMaior"))},
            "foil": {"menor": _num(payload.get("foil_precoMenor")),
                     "medio": _num(payload.get("foil_precoMedio")),
                     "maior": _num(payload.get("foil_precoMaior"))},
        }
        eds = []
        for i in payload.get("itens") or []:
            eds.append({
                "sigla": (i.get("sigla") or "").lower(),
                "nome": html.unescape(i.get("value") or "").replace("\\'", "'"),
                "normal": {"menor": _num(i.get("precoMenor")),
                           "medio": _num(i.get("precoMedio")),
                           "maior": _num(i.get("precoMaior"))},
                "foil": {"menor": _num(i.get("foil_precoMenor")),
                         "medio": _num(i.get("foil_precoMedio")),
                         "maior": _num(i.get("foil_precoMaior"))},
            })
        return {"card": payload.get("card"), "agg": agg, "eds": eds}

    def get(self, name):
        """Devolve (dados, erro). dados=None quando a Liga nao tem a carta."""
        key = fold(name)
        if self.use_cache:
            hit = self.cache.get(key)
            if hit and (time.time() - hit.get("t", 0)) < self.ttl:
                self.hits += 1
                return hit.get("d"), None
        try:
            data = self._fetch(name)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            return None, f"consulta de preco falhou: {exc}"
        if self.use_cache:
            self.cache[key] = {"t": time.time(), "d": data}
            self.dirty = True
        return data, None


def choose(entry, data, campo, foil, incluir_nao_sancionadas):
    """Preenche entry com o preco escolhido. Fonte = edicao mais barata.

    Sem estoque fica com price=None de proposito: somar zero seria mentir sobre
    o custo do deck.
    """
    tipo = "foil" if foil else "normal"
    entry.aggregate = data["agg"]
    entry.editions = data["eds"]

    pool = [e for e in data["eds"] if e[tipo][campo] is not None]
    if not incluir_nao_sancionadas:
        elegiveis = [e for e in pool if e["sigla"] not in NAO_SANCIONADAS]
        if elegiveis:
            pool = elegiveis
    if pool:
        best = min(pool, key=lambda e: e[tipo][campo])
        entry.price = best[tipo][campo]
        entry.edition = best["nome"]
        entry.sigla = best["sigla"]
        entry.status = "precificado"
        return
    # Nenhuma edicao com estoque: cai para o agregado, que as vezes existe
    # quando as linhas por edicao estao zeradas.
    agg = data["agg"][tipo][campo]
    if agg is not None:
        entry.price = agg
        entry.edition = "(agregado da carta)"
        entry.status = "precificado"
    else:
        entry.status = "sem estoque"
        entry.note = f"nenhuma edicao com preco {tipo}/{campo}"


# --------------------------------------------------------------------------- #
# saida
# --------------------------------------------------------------------------- #

def print_card_detail(entry, campo, out=sys.stdout):
    title = entry.out
    if entry.status == "renomeado":
        title += f"   (pedido: {entry.name})"
    print(title, file=out)
    print("-" * max(40, len(title)), file=out)
    if entry.aggregate:
        a = entry.aggregate
        print(f"{'':22} {'menor':>12} {'medio':>12} {'maior':>12}", file=out)
        for tipo in ("normal", "foil"):
            row = a[tipo]
            print(f"  agregado {tipo:<12}"
                  f"{brl(row['menor']):>13}{brl(row['medio']):>13}"
                  f"{brl(row['maior']):>13}", file=out)
    if entry.editions:
        print(f"\n  edicoes ({len(entry.editions)}), por {campo} normal:", file=out)
        rows = sorted(entry.editions,
                      key=lambda e: (e["normal"][campo] is None,
                                     e["normal"][campo] or 0))
        for e in rows:
            flag = " *" if e["sigla"] in NAO_SANCIONADAS else "  "
            n, f = e["normal"][campo], e["foil"][campo]
            print(f"  {e['sigla']:<10}{e['nome'][:44]:<46}"
                  f"{brl(n):>12}{brl(f):>13}{flag}", file=out)
        if any(e["sigla"] in NAO_SANCIONADAS for e in entry.editions):
            print("  * nao sancionada em torneio (borda dourada/quadrada ou "
                  "proxy oficial)", file=out)
    if entry.status == "sem estoque":
        print("\n  SEM ESTOQUE na Liga.", file=out)
    elif entry.status == "nao encontrado":
        print(f"\n  NAO ENCONTRADA na base da Liga. {entry.note}", file=out)
    elif entry.status == "falha de rede":
        print(f"\n  SEM PRECO por falha de rede: {entry.note}", file=out)
    print(file=out)


def print_deck_table(entries, out=sys.stdout):
    print(f"{'qtd':>3}  {'carta':<40} {'edicao':<26} "
          f"{'unit':>12} {'subtotal':>13}", file=out)
    print("-" * 100, file=out)
    for e in entries:
        ed = (e.edition or "")[:26]
        if e.price is None:
            ed = {"sem estoque": "SEM ESTOQUE",
                  "nao encontrado": "NAO ENCONTRADA",
                  "falha de rede": "FALHA DE REDE"}.get(e.status, e.status)
        print(f"{e.qty:>3}  {e.out[:40]:<40} {ed:<26} "
              f"{brl(e.price):>12} {brl(e.subtotal):>13}", file=out)


def report(entries, total, campo, foil, names, prices, top, out=sys.stderr):
    missing = [e for e in entries if e.status == "nao encontrado"]
    failed = [e for e in entries if e.status == "falha de rede"]
    nostock = [e for e in entries if e.status == "sem estoque"]
    priced = [e for e in entries if e.price is not None]
    n_cards = sum(e.qty for e in entries)
    n_priced = sum(e.qty for e in priced)

    lines = [""]
    lines.append(f"Preco: {campo} / {'foil' if foil else 'normal'}, "
                 "edicao mais barata com estoque.")
    lines.append(f"TOTAL {brl(total)}  "
                 f"({n_priced} de {n_cards} cartas precificadas, "
                 f"{len(priced)} de {len(entries)} linhas)")
    if missing or nostock or failed:
        lines.append("  ^ TOTAL INCOMPLETO - as linhas abaixo nao entraram "
                     "na soma.")

    if nostock:
        lines.append(f"\nSem estoque na Liga ({len(nostock)}) - "
                     "custo real e MAIOR que o total acima:")
        for e in nostock:
            lines.append(f"  {e.qty}x {e.out}")
    if missing:
        lines.append(f"\nNAO RESOLVIDAS na base da Liga ({len(missing)}):")
        for e in missing:
            lines.append(f"  {e.qty}x {e.out}" + (f"\n      {e.note}" if e.note else ""))
    if failed:
        lines.append(f"\nFALHA DE REDE, sem preco ({len(failed)}) - "
                     "isto nao quer dizer que a carta nao existe. "
                     "Rode de novo com --delay maior:")
        for e in failed:
            lines.append(f"  {e.qty}x {e.out}" + (f"\n      {e.note}" if e.note else ""))
    if names.renames:
        lines.append(f"\nNomes ajustados para a grafia da Liga "
                     f"({len(names.renames)}):")
        for old, (new, why) in names.renames.items():
            lines.append(f"  {old}  ->  {new}" + (f"   [{why}]" if why else ""))

    if priced and top:
        _n = min(top, len(priced))
        lines.append(f"\n{_n} linha{'s' if _n != 1 else ''} mais cara{'s' if _n != 1 else ''}:")
        for e in sorted(priced, key=lambda x: -x.subtotal)[:top]:
            lines.append(f"  {brl(e.subtotal):>13}  {e.qty}x {e.out} "
                         f"({e.sigla or '-'}, {brl(e.price)} un.)")

    lines.append(f"\n{names.requests} busca(s) de nome + {prices.requests} "
                 f"consulta(s) de preco; {names.hits} nome(s) e {prices.hits} "
                 "preco(s) vieram do cache local.")
    print("\n".join(lines), file=out)


# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Preco de cartas de Magic em BRL pela LigaMagic.")
    ap.add_argument("cards", nargs="*",
                    help="nomes de carta (PT ou EN). Sem -d, e o modo avulso")
    ap.add_argument("-d", "--deck", metavar="ARQ",
                    help="decklist em qualquer formato; - para stdin")
    ap.add_argument("--preco", choices=("menor", "medio", "maior"),
                    default="menor", help="qual preco usar (padrao: menor)")
    ap.add_argument("--foil", action="store_true",
                    help="precificar em foil em vez de normal")
    ap.add_argument("--incluir-nao-sancionadas", action="store_true",
                    help="deixar WCD, Collector's Edition e 30th Anniversary "
                         "entrarem como edicao mais barata")
    ap.add_argument("--ttl", type=float, default=DEFAULT_TTL_H, metavar="HORAS",
                    help=f"validade do cache de precos (padrao: {DEFAULT_TTL_H:g}h)")
    ap.add_argument("--no-cache", action="store_true", help="ignorar os caches")
    ap.add_argument("--delay", type=float, default=0.8, metavar="SEG",
                    help="pausa entre consultas nao cacheadas (padrao: 0.8)")
    ap.add_argument("--retries", type=int, default=4,
                    help="tentativas extras em HTTP 429/5xx (padrao: 4)")
    ap.add_argument("--top", type=int, default=10,
                    help="quantas linhas mais caras listar no relatorio")
    ap.add_argument("--json", action="store_true",
                    help="emitir JSON no stdout em vez da tabela")
    args = ap.parse_args(argv)

    if not args.cards and not args.deck:
        ap.error("passe nomes de carta ou -d ARQUIVO")

    if args.deck:
        text = sys.stdin.read() if args.deck == "-" else \
            Path(args.deck).read_text(encoding="utf-8", errors="replace")
        sections = parse_input(text)
        if not any(sections.values()):
            print("nenhuma carta reconhecida na entrada", file=sys.stderr)
            return 2
    else:
        sections = {k: [] for k in SECTIONS}
        sections["main"] = [Entry(1, c) for c in args.cards]

    throttle = Throttle(args.delay, retries=max(0, args.retries))
    names = NameResolver(throttle, use_cache=not args.no_cache)
    prices = PriceClient(throttle, use_cache=not args.no_cache,
                         ttl_hours=args.ttl)

    for sec in SECTIONS:
        for e in sections[sec]:
            names.resolve(e)
        sections[sec] = merge_duplicates(sections[sec])
    names.save()

    entries = [e for sec in SECTIONS for e in sections[sec]]
    # Uma consulta por carta unica, mesmo que apareca em varias secoes.
    by_name = {}
    for e in entries:
        by_name.setdefault(fold(e.out), []).append(e)

    for key, group in by_name.items():
        head = group[0]
        if head.status in ("nao encontrado", "falha de rede"):
            for e in group:
                e.status = head.status
                e.note = head.note
            continue
        data, err = prices.get(head.out)
        if err:
            for e in group:
                e.status = "falha de rede"
                e.note = err
                names.failed.setdefault(e.out, err)
            continue
        if data is None:
            for e in group:
                e.status = "nao encontrado"
                e.note = "getEditions.php nao reconheceu o nome"
                names.missing.setdefault(e.out, e.note)
            continue
        for e in group:
            choose(e, data, args.preco, args.foil, args.incluir_nao_sancionadas)
    prices.save()

    total_entries = [e for sec in TOTAL_SECTIONS for e in sections[sec]]
    total = sum(e.subtotal for e in total_entries if e.subtotal is not None)

    if args.json:
        payload = {
            "preco": args.preco, "foil": args.foil, "total": round(total, 2),
            "moeda": "BRL",
            "completo": all(e.price is not None for e in total_entries),
            "cartas": [{
                "qtd": e.qty, "pedido": e.name, "liga": e.out,
                "secao": e.section, "status": e.status,
                "unitario": e.price, "subtotal": e.subtotal,
                "edicao": e.edition, "sigla": e.sigla,
                "agregado": e.aggregate,
            } for e in entries],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif args.deck:
        for sec in SECTIONS:
            if not sections[sec]:
                continue
            rotulo = {"main": "Main deck", "side": "Sideboard",
                      "maybe": "Maybeboard (fora do total)",
                      "commander": "Comandante",
                      "companion": "Companheiro"}[sec]
            sub = sum(e.subtotal for e in sections[sec]
                      if e.subtotal is not None)
            print(f"\n== {rotulo} == {brl(sub)}")
            print_deck_table(sections[sec])
    else:
        for e in entries:
            print_card_detail(e, args.preco)

    if args.deck or len(entries) > 1:
        report(total_entries or entries, total, args.preco, args.foil,
               names, prices, args.top)

    # Codigo 1 tambem para falha de rede: nos dois casos o total esta errado
    # por baixo, e sair 0 faria o chamador confiar num numero incompleto.
    return 1 if any(e.status in ("nao encontrado", "falha de rede")
                    for e in entries) else 0


if __name__ == "__main__":
    sys.exit(main())
