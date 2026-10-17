---
name: card-finder
description: Use when someone wants Magic cards that do something — "find me ramp in Golgari", "board wipes that spare my creatures", "cheap card draw for my Edgar deck", "what tutors are there for artifacts", "options for X effect", "replacements for this card" — anything that starts from a function or trait instead of a card name. Covers Scryfall oracle tags (otag:draw, otag:ramp, otag:removal, otag:wipe) and checks every result against its real oracle text.
---

# Finding cards by function

A search result is a **candidate**. It becomes an answer only after you read
its oracle text and confirm it does what was asked. Oracle tags are
community-maintained labels: they find the right neighbourhood fast, and they
also hold cards that only fit loosely. Acid Rain is a `sweeper` (it destroys
all Forests), and Abjure is a `sacrifice-outlet` (sacrificing is part of its
cost). The text decides.

```bash
F=skills/card-finder/scripts/finder.py
python3 $F tags board wipe             # which tag names this concept
python3 $F tag removal --depth 2       # its children, to pick the narrowest one
python3 $F find 'otag:sweeper-one-sided id<=wb f:commander mv<=5'
```

## Flow

1. **Pin the trait and the constraints.** The trait is what the card must do.
   The constraints come from the deck: color identity (`id<=`), format
   (`f:commander`), mana value, type, budget (`usd<=`). For a deck in
   `decks/`, read its commander and identity from the file before searching.
   Done when you can write both down in one line each.

2. **Choose the tag.** Run `tags <words>` for the concept, then `tag <slug>` on
   the best hit to see its children. Pick the narrowest tag that still covers
   the whole trait: "exile-based creature removal" is `otag:removal-exile`
   together with `otag:removal-creature`, not plain `otag:removal`. A parent tag
   matches every card under its children. When no tag fits, search the text
   (`o:"..."`, `o:/regex/`), with the syntax in
   `skills/scryfall-cards/references/search-syntax.md`. Done when every part of
   the trait maps to a tag or to a text term.

3. **Search.** `find "<query>"` checks each tag against the tag list before it
   calls Scryfall. Scryfall answers an unknown tag with 404 "no cards", the same
   reply as a real tag with no matches, so a typo looks like an empty result.
   `find` stops with `UNKNOWN TAG` and suggestions instead. Results come sorted
   by EDHREC popularity, with full oracle text and a `tagged:` line naming
   which tag in the query's tree each card carries.
   When the tag returns few results, the effect is niche, or the user wants
   recent sets, run a second search on the oracle text. Tags lag behind new
   releases, and tagging is never complete.

4. **Verify every candidate.** Read the printed text against every part of the
   trait and sort each card into one of three groups:
   - **fits**: the text does the whole job;
   - **fits with a catch**: it does the job with a condition that matters
     (only hits mana value 3 or less, also hits your own creatures, costs
     life);
   - **out**: the tag stretched, or it misses a constraint.
   For a double-faced card, read the face that does the job. Done when every
   card you're about to present has text you read in this session and a
   clause you can quote.

5. **Report.** For each verified card: name, cost, the clause that proves the
   fit (quoted), and the catch if there is one. Then the totals: how many came
   back, how many you read, how many were out and why in a few words. If you
   read only the first page out of hundreds, say so, and offer to tighten the
   query or read more.

Prices in BRL: `ligamagic-preco`. Adding the result to a deck: `moxfield-deck`.

## Read stderr

- `UNKNOWN TAG` (exit 2): the tag doesn't exist. Use a suggestion or run `tags`.
- `SCRYFALL WARNING` (exit 1): some other part of the query was ignored, so
  the search is broader than asked. Fix the query and run it again.
- `no cards for the query`: the tags are valid and nothing matches. Loosen a
  constraint.
- `could not load oracle tags`: the tag list didn't download, so tags were not
  checked. An empty result may be a typo.

## Tags

`otag:`, `oracletag:` and `function:` are the same keyword. Case, hyphens,
spaces and underscores don't matter, and aliases resolve: `otag:wipe`,
`otag:board-wipe` and `otag:"mass removal"` all hit `sweeper`. Combine tags with
the usual operators: `-otag:sweeper-one-sided`, `(otag:draw or otag:ramp)`.

The tag list comes from Scryfall's Oracle Tags bulk file, cached at
`~/.cache/mtg-skills/oracle-tags.jsonl.gz` and refreshed weekly (`--refresh`
forces it). The card counts it prints include every printing Scryfall
tracks, so they run a bit above what `find` returns.

Starting points (check them with `tag <slug>`, the list changes):

| concept | tag | narrower |
|---|---|---|
| card draw | `draw` | `repeatable-draw`, `cantrip`, `wheel`, `loot` |
| card advantage, any kind | `card-advantage` | `impulse`, `regrowth` |
| ramp | `ramp` | `land-ramp`, `mana-rock`, `mana-dork`, `ritual`, `cost-reducer` |
| removal | `removal` | `removal-creature`, `removal-exile`, `removal-artifact`, `removal-enchantment`, `edict` |
| board wipe | `sweeper` (`wipe`) | `sweeper-one-sided` |
| tutor | `tutor` | `tutor-creature`, `tutor-land`, `tutor-artifact` |
| counterspell | `counterspell` | `counterspell-soft`, `counterspell-free` |
| graveyard return | `recursion` | `reanimate`, `regrowth` |
| sacrifice outlet | `sacrifice-outlet` | |
| blink | `flicker` | |
| protection | `protection` | `gives-indestructible`, `gives-hexproof` |
| graveyard hate | `hate-graveyard` | |

Art tags (`art:`, `atag:`) search what the illustration shows. `find` doesn't
check them.
