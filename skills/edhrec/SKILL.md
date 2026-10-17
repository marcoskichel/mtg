---
name: edhrec
description: Use when you need Commander popularity or context data for a card or commander — play rate (how many decks that could play a card actually do), salt, which commanders use a card, a commander's deck count, bracket split and themes, top commanders for a theme in some colors, or legal partner pairings — e.g. "how popular is Blood Artist", "what brackets is Edgar played at", "best aristocrats commanders in Orzhov", "who pairs with Tymna". Also the data source for score-card and commander-finder.
---

# EDHREC data

EDHREC has no public API. `json.edhrec.com/pages/<path>.json` is what the site
loads. It counts decks people uploaded: it measures **popularity, not power**.
A card in many decks is well supported, not necessarily strong; precon cards
are inflated because every precon list counts.

```bash
E=skills/edhrec/scripts/edhrec.py
python3 $E card "Blood Artist" "Sol Ring"            # play rate, salt, top commanders
python3 $E card -d decks/markov-gang.txt
python3 $E commander "Edgar Markov"
python3 $E commander "Kraum, Ludevic's Opus" "Tymna the Weaver"   # a pair
python3 $E theme aristocrats --colors wb
python3 $E partners "Tymna the Weaver"
```

`--json` on every subcommand gives `{path, fetched, data}` (`card` gives a list
of those, each with `name`); `data` is `null` when EDHREC has no page. `--ttl 0` fetches fresh (default cache 24h,
`~/.cache/mtg-skills/edhrec/`). Every output says when the data was fetched.

## What the numbers mean

- **play rate** = decks with the card ÷ decks that could play it (right colors).
  Sol Ring 83%, Blood Artist 11%. High = useful in many strategies.
- **salt**: how much players dislike facing the card (0–4).
- **bracket split** (commanders): how many of its decks sit in each bracket 1–5.
  Shows where people actually play it.
- **themes** (commanders only): EDHREC's tags with deck counts. Card pages
  carry no themes; a card's top commanders show where it lives.

## Read stderr

- `EDHREC BLOCKED` (exit 1): Cloudflare refused us after retries. The card may
  well have a page. Run again later with fewer cards; never tell the user the
  card has no EDHREC data.
- `no EDHREC page` on stdout: the page really doesn't exist (new card, never
  played, or a name EDHREC spells differently). Not fatal.
- `NOT FOUND` / `Names adjusted`: name resolution through Scryfall, same as
  `scryfall-cards`.

## Names

Names go through Scryfall first, then become EDHREC slugs: lowercase, no
accents, no apostrophes, commas or periods (`V.A.T.S.` → `vats`), `Æ` → `ae`. Double-faced and adventure cards
use the front face; split and aftermath cards use both halves (`fire-ice`).
Pairs join both slugs alphabetically.

## Theme names

`theme` takes EDHREC's tag slug (`aristocrats`, `plus-1-plus-1-counters`,
`lifegain`). A wrong slug answers "no EDHREC theme page" — look up the slug in
a commander's `themes` line or on edhrec.com/tags. `--colors` takes letters in
any order (`bw`, `wb`) or a name (`orzhov`, `esper`).

Pace: 0.5 s between uncached calls. Don't loop over hundreds of commanders
with `--ttl 0`.
