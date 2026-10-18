---
name: card-finder
description: Use when someone wants Magic cards that do something — "find me ramp in Golgari", "board wipes that spare my creatures", "cheap card draw for my Edgar deck", "what tutors are there for artifacts", "options for X effect", "replacements for this card", "which commanders are W/U" — anything that starts from a function or trait, colors or format filter instead of a card name. Covers Scryfall oracle tags (otag:draw, otag:ramp, otag:removal, otag:wipe) and checks every result against its real oracle text, then shows the verified cards in the card-picker page for the user to see or pick from.
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
   Write them as Scryfall keywords from
   `skills/scryfall-cards/references/search-syntax.md`. It covers commanders
   and partners, land cycles, Game Changers, price and release date, plus the
   traps: `id=wu` is "exactly W/U" but `id<=wu` and `commander:wu` are "fits
   in W/U", and `usd<2` passes if any printing is under $2. A bare color with
   no deck ("ramp in black") means what that color's deck can play:
   `id<=b`, colorless cards included. `c:b` would add multicolor cards it
   can't cast, and `c:b id<=b` drops Sol Ring and Cabal Coffers. Say which
   reading you used in the totals. Done when you can write both down in one
   line each.

2. **Choose the tag.** Run `tags <words>` for the concept, then `tag <slug>` on
   the best hit to see its children. Pick the narrowest tag that still covers
   the whole trait: "exile-based creature removal" is `otag:removal-exile`
   together with `otag:removal-creature`, not plain `otag:removal`. A parent tag
   matches every card under its children, so a broad request ("ramp") takes
   the parent, while "mana that stays" points at children like `mana-rock`
   or `land-ramp` instead of `ritual`. When no tag fits, search the text
   (`o:"..."`, `o:/regex/`). Done when every part of
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
   - **out**: the tag stretched, or it misses a constraint. Typical stretches:
     the trait is a side effect of a card built for something else (Revel in
     Riches makes Treasure but is a win condition), the output is restricted
     (Master of Dark Rites' mana only casts certain spells), or the effect is
     one-shot where the user wants lasting (a ritual is not a mana rock).
   For a double-faced card, read the face that does the job. Done when every
   card you're about to present has text you read in this session and a
   clause you can quote.

5. **Report.** When the user asks for the best or a top N, the ranking is
   `score-card`'s job: hand it the verified cards and follow its pool flow
   (standalone, or against the deck's profile when there is a deck). It
   grades each card and opens the picker with its verdicts, so skip the rest
   of this step. Otherwise put the verified cards in front of the user with
   `card-picker`, not as a list in chat. Write them to a JSON file, best first, at most about
   15; each `reason` quotes the clause that proves the fit and names the catch
   if there is one:
   `[{"name": "Fellwar Stone", "reason": "\"{T}: Add one mana of any color that a land an opponent controls could produce.\" Catch: depends on opponents' lands."}]`.
   Then choose the call by what the user needs:
   - **They will choose** (cards to add, a replacement, "which of these"):
     `picker.py pick --suggestions <file> --count <N|N-M|any> --title "<their question>"`.
     Act on the answer as `card-picker`'s SKILL.md says; an added card goes
     through `moxfield-deck`.
   - **They only want to see** what exists ("what tutors are there"):
     `picker.py show --suggestions <file> --title "<their question>"`.

   Run either in the background (it blocks until the user answers) and say in
   one line that the picker is open. In chat, give only the totals: how many
   came back, how many you read, how many were out and why in a few words,
   and how many verified cards didn't fit on the page. If you read only the
   first page out of hundreds, say so, and offer to tighten the query or read
   more. Fall back to a chat list (name, cost, quoted clause, catch) when the
   user asks for text or the picker exits 3. Done when the picker is open
   with every verified card it can hold, or the chat list is out.

```bash
P=skills/card-picker/scripts/picker.py
python3 $P pick --suggestions ramp.json --count 1-3 --title "Ramp for Edgar"
python3 $P show --suggestions tutors.json --title "Black tutors under 3 mana"
```

Prices in BRL: `ligamagic-preco`. Adding the result to a deck: `moxfield-deck`.

## Roles of a card or deck

`roles` says which of a fixed set of functions each card carries, from the
cached tag file, with no searches:

```bash
python3 $F roles "Blood Artist" "Sol Ring"
python3 $F roles -d decks/markov-gang.txt        # + counts per role (deck boards, by quantity)
```

Roles: `ramp, mana-rock, cost-reducer, draw, card-advantage, removal, sweeper,
counterspell, protection, tutor, sacrifice-outlet, recursion`. A parent counts
its children (`removal` includes `removal-creature`). `(no roles tagged)` means
nobody tagged it, not that the card does nothing — read its text. score-card
uses these counts to see what a deck lacks.

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
