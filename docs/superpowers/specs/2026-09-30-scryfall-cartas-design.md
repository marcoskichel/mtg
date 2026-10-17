# scryfall-cartas — design

Skill under `skills/scryfall-cartas/` that looks up, searches and lists printings of Magic cards through the Scryfall API. Replaces the inline curl snippets in `AGENTS.md`.

## Goal

The model must reason from fetched card text, not memory. Today that means hand-writing curl + jq per question, with no help for pagination, double-faced cards, Portuguese names or Scryfall's silently-ignored search keywords. One script with four subcommands absorbs those traps.

## Layout

```
skills/scryfall-cartas/
  SKILL.md                     # Portuguese, same voice as ligamagic-*
  scripts/scryfall.py          # stdlib only
  references/api.md            # endpoint shapes + measured gotchas (dated)
  references/sintaxe-busca.md  # search syntax cheat sheet
  tests/test_scryfall.py       # unittest, mocked HTTP
```

## Subcommands

| Command | Endpoint | Output |
|---|---|---|
| `carta NOME... \| -d deck.txt \| -d -` | `POST /cards/collection` (75 ids/call) | per card: name, mana, type, P/T, oracle per face, color identity, legality in `--formatos` (default `commander`); `--regras` appends rulings |
| `busca "query"` | `GET /cards/search` | table name · mana · type · set; `--ordem`, `--limite N` (default 50), `--todas` follows `next_page`, `--unique prints` |
| `edicoes NOME` | card's `prints_search_uri` | set, set name, collector #, date, finishes, usd/eur, promo/digital flags; `--sem-digital`, `--sem-promo`, `--imagem` |
| `regras NOME` | card's `rulings_uri` | date + text |

Global: `--json` (trimmed Scryfall objects), `--delay` (default 0.1 s), retries on 429/5xx honoring `Retry-After`, `User-Agent: mtg-skills/0.1`.

## Name resolution (`carta`)

`/cards/collection` is exact-English-only. Fallback chain for each `not_found` entry, one step at a time:

1. Front face: `A // B` → `A`.
2. `GET /cards/named?fuzzy=` — handles typos and some Portuguese names.
3. `GET /cards/search?q=name:"X" lang:pt` → `name` (English) of first hit.

Renames go to the stderr report. Unresolved names list fuzzy suggestions when Scryfall gives them. Exit 1 when any name stays unresolved.

Deck parsing: same parser as `ligamagic-preco` (sections, Arena/Moxfield/MWS/Cockatrice), copied on purpose so the skill is self-contained.

## Measured gotchas (2026-09-30)

- Double-faced and split cards: top-level `oracle_text` and `mana_cost` are `null`; text lives in `card_faces[]`.
- `/cards/collection` with `"Delver of Secrets // Insectile Aberration"` → `not_found`; `"delver of secrets"` → found.
- Unknown search keyword → HTTP 200 with `warnings[]`; the expression is dropped and the query silently broadens. Script prints warnings to stderr in caps and exits 1.
- Search page = 175 cards; `has_more` + `next_page`.
- No `User-Agent` → HTTP 400.
- Prices are `usd`/`eur`/`tix`, never BRL — `ligamagic-preco` owns BRL.

## Not in v1

- Local cache. Scryfall allows 10 req/s and responses are fast; a cache would add state without solving a felt problem.
- Image download. `--imagem` prints URLs only.

## AGENTS.md

Keep the rule "card text comes from the API, never from memory". Replace the curl block with the `scryfall.py carta` invocation and a pointer to the skill.

## Testing

`tests/test_scryfall.py` with mocked `urlopen`: deck parser, DFC face formatting, fallback chain order, warnings → exit 1, pagination with `--todas`. One manual live run per subcommand before finishing.
