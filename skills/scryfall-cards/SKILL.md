---
name: scryfall-cards
description: Use when you need a Magic card's oracle text, cost, type, legality or rulings, when evaluating or building a deck and you need to read the cards, when someone asks "what does card X do", "what sets was it printed in", or when the question involves Scryfall search syntax (c: t: o: mv: f:). Applies even when the request doesn't mention Scryfall or gives the card name in Portuguese.
---

# Magic cards through Scryfall

Memory of a card is a hypothesis; the API response is the fact. Before giving
an opinion on rules, synergy, substitutes or deck building, fetch the cards
involved and read the text that came back.

## Flow

```bash
S=skills/scryfall-cards/scripts/scryfall.py

# oracle text, one or many cards (EN or PT, "A // B" accepted)
python3 $S card "Brash Taunter" "Raio" "Delver of Secrets"
python3 $S card -d deck.txt            # whole decklist, batched
python3 $S card "Edgar Markov" --formats commander,modern --rulings

# search with Scryfall syntax
python3 $S search "c:r t:creature mv<=1 f:commander kw:haste" --order cmc
python3 $S search 'id<=wb o:"whenever a creature dies"' --all

# every printing, with USD/EUR price and image
python3 $S printings "Sol Ring" --no-digital --no-promo --image

# rulings
python3 $S rulings "Brash Taunter"
```

`search` shows 50 cards by default and reports the total on stderr; `--limit N`
or `--all` to see the rest. `--json` on any subcommand returns the Scryfall
objects already trimmed to the useful fields. `--help` on each subcommand
lists the flags.

Full search syntax in `references/search-syntax.md`. Response schema and
measured failures in `references/api.md`.

## Read stderr

stdout is the card; stderr is what changed along the way and must reach the
user:

- `SCRYFALL WARNING`. The search had an expression the API didn't understand
  and silently ignored. `tipo:creature` becomes nothing, the search gets
  broader and returns 1092 cards instead of 35, with HTTP 200. The script exits
  with code 1. Fix the query and run it again; never present the result as if
  it were what was asked.
- `Names adjusted`. The requested name became another one, through Portuguese
  translation, the front face of a double-faced card, or fuzzy matching on a
  typo. Confirm it is the card the user meant.
- `NOT FOUND`. A name nothing resolved. Ask the user, don't guess. When fuzzy
  returned a card that doesn't look like the request, the script rejects it
  and says which one it was.

Exit code 1 in any of these cases.

## Double-faced, split and adventure cards

`oracle_text`, `mana_cost` and `power` on the main object come back `null`; the
text is in `card_faces[]`. The script prints each face with `==`. When reasoning
about the card, use the face text: Delver of Secrets is a 1/1 on the front and
a 3/2 flyer on the back, not "null/null".

## Portuguese names

`/cards/collection` only accepts exact English. The script resolves whatever is
left with an exact search on the printed Portuguese name (`!"Raio" lang:pt`) and
only then tries fuzzy. In that order, because Scryfall's fuzzy returns any card
for a short name ("Raio" becomes Samurai of the Pale Curtain). The printing that
comes back in that case is the Portuguese one; `oracle_text` is still in English.

## What Scryfall doesn't give you

- **Price in BRL.** `prices` is `usd`, `eur`, `tix`. LigaMagic prices are the
  `ligamagic-preco` skill.
- **Downloaded image.** `--image` prints the URL; downloading is another call.

## Pacing and headers

Scryfall requires `User-Agent` and `Accept` (without them, HTTP 400) and asks for
at most 10 req/s. The script sends both, spaces calls 0.1 s apart and honors
`Retry-After` on 429. A Commander decklist takes 2 calls
(`/cards/collection` accepts 75 names); don't make one `named` call per card.
