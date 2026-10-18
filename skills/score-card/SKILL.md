---
name: score-card
description: Use when someone asks how good a Magic card is, whether it belongs in a deck, which of several cards is better, or wants a candidate list ranked — "is Blood Artist good", "should I play X in my Edgar deck", "rate these cards", "score this pool for my aristocrats deck", "is this a staple". Grades per factor with reasons, standalone or against a deck profile built from a deck file, a commander, or a strategy; shows the ranked cards in the card-picker page.
---

# Scoring cards

A card has no fixed power. Standalone, it's raw power plus how many strategies
it fits. In a deck, the deck sets the weights: mana value matters less in a
deck full of cost reducers than in a low-curve aggro deck. Scripts gather
facts; you grade with `references/rubric.md`. Every grade cites text you
fetched in this session or a number from the data.

```bash
S=skills/scryfall-cards/scripts/scryfall.py
F=skills/card-finder/scripts/finder.py
E=skills/edhrec/scripts/edhrec.py
P=skills/score-card/scripts/deckprofile.py
K=skills/card-picker/scripts/picker.py
```

## Pick the context

| User gave | Do |
|---|---|
| Only cards | Standalone |
| A deck file in `decks/` | `$P show decks/x.txt` |
| A Moxfield link | `moxfield-deck`: `pull <url> -o decks/x.txt`, then as above |
| A commander, no list | `$P new --commander "<name>" --bracket N -o decks/<slug>.profile.md` |
| A strategy, no commander | `$P new --strategy "<words>" --colors wb --bracket N -o decks/<slug>.profile.md` |

No bracket given and none in the deck file: ask. It changes the weights.

## The profile

`deckprofile.py show` prints measured facts (curve, average mana value, colored
sources, role counts, game changers) and the strategy from
`<deck>.profile.md`, then a status:

- `fresh` — score.
- `drift (+X −Y)` — score, but read the changed cards first; if one shifts the
  plan, update the strategy and `stamp`.
- `STALE` (exit 1) — do not score in-deck. Read the current deck, rewrite Plan /
  Rewards / Lacks / Avoid, run `$P stamp <profile>`, then `show` again.
- `NO PROFILE` (exit 1) — `$P new --deck <file>`, read the deck's cards
  (`$S card -d <file>`), write the strategy, `stamp`.

Writing the strategy: Plan is how the deck wins; Rewards is what it wants more
of; Lacks comes from the role counts and the plan; Avoid holds house rules
(e.g. no infinite combos for the Markov Gang deck). Keep it short; it is read
on every score.

## One card

1. Profile (in-deck only), as above.
2. `$S card "<name>"` — oracle text, type, cost, legality.
3. `$F roles "<name>"` — ramp, draw, removal...
4. `$E card "<name>"` — play rate, salt, top commanders, themes.
5. Grade each factor with the rubric, print the output block from
   `references/rubric.md`, flags first.
6. Scoring several cards at once ("rate these", "which is better")? After the
   blocks, show them side by side: `$K show --suggestions <file>` with the
   verdict and the deciding grade as each `reason`, run in the background.

## A pool (dozens to hundreds of cards)

1. Write the pool one card per line as `1 <name>` (`scryfall.py card -d` skips
   lines without a quantity), then batch: `$S card -d pool.txt`,
   `$F roles -d pool.txt`, `$E card -d pool.txt`.
2. Drop off-identity and banned cards, and cards with no role and nothing in
   their text that touches the profile's Plan or Rewards. List what you dropped
   and why, in one line each.
3. One line per survivor: `verdict  name — fit tag`.
4. Full rubric block only for cards near the cut line, borderline
   `PLAYABLE`/`STRONG`, or when asked.
5. Put the survivors in front of the user with `card-picker`, best verdict
   first, at most about 15. Each `reason` is the verdict, the fit tag and any
   flag: `"STRONG — free sac outlet, 1 mana"`,
   `"WEAK — INFINITE COMBO RISK with Gravecrawler; Avoid forbids infinites"`.
   - Filling slots: `$K pick --suggestions <file> --count <open slots or N-M>
     --title "<the question>"`. Picked cards go to the deck through
     `moxfield-deck`; a `note` overrides your ranking.
   - Only ranking: `$K show --suggestions <file> --title "<the question>"`.

   Run it in the background (it blocks until the user answers) and say in one
   line that the picker is open. The dropped list and the one-line grades stay
   in chat. A chat-only ranking is the fallback when the user asks for text or
   the picker exits 3.

## Traps

- **EDHREC counts popularity, not power.** Precon cards are inflated; new cards
  are deflated. When your read and the data disagree, say so in a `note:`.
- **`EDHREC BLOCKED` is not "no data".** Run again later; don't grade
  usefulness as low because the request failed.
- **`(no roles tagged)` is not "does nothing".** Tags lag new sets. Read the text.
- **Bracket 3 allows 3 game changers.** Adding a 4th pushes the deck to bracket 4;
  say so when scoring one into a deck already at 3.
- **Don't edit the deck.** Scoring recommends; changes go through `moxfield-deck`.
