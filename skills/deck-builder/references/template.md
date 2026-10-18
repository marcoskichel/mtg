# Targets

`build.py init` writes these to `<name>.build.json` under `targets`. Each is a
minimum count of cards in the deck carrying that role; a card can count for
more than one role (Deadly Dispute is draw and ramp). Everything left after
lands and roles is theme: the cards that carry the Plan.

| target | template | counts cards tagged |
|---|---|---|
| lands | 36 | type Land (front face) |
| ramp | 10 | `ramp` and its children (rocks, dorks, land ramp, rituals, Treasure) |
| draw | 10 | `draw`, `card-advantage` |
| removal | 8 | `removal` and children |
| sweeper | 3 | `sweeper` |
| protection | 3 | `protection` |

Tags are the oracle tags `card-finder roles` reads; `(no roles tagged)` cards
fall to theme.

## How init adjusts

When EDHREC has an average deck for the commander (`average-decks/<slug>`),
`init` counts the same roles in it and moves each target toward that count by
at most 3 (ramp 10 with an average of 14 becomes 13), and takes the land count
from it within 33–40. Without an average deck (new commander, partner pair
EDHREC hasn't built) the template stands. `init` prints where each number
came from.

Then the profile can move them further; say why when you change a target:

- **Low curve** (average mana value under ~2.5 or an aggro Plan): lands 33–34,
  ramp down 2.
- **Big spells or cost reducers in the Plan**: lands 37–38, ramp up 2.
- **Lacks names a role** ("Lacks: card draw"): that target up 2.
- **Go-wide or board-reliant Plan**: sweeper down to 1–2 (yours hit your board),
  protection up 1–2.
- **Bracket 4–5**: removal up 2. Counterspells count toward no role; in blue,
  plan 3–5 of them inside theme.

## Game changers

`gc_limit`: bracket 1–2 allow none (the pool drops them), bracket 3 allows 3,
brackets 4–5 have no limit. `status` counts them and exits 1 past the limit.
