---
name: deck-builder
description: Use when the user wants a Commander deck built or filled out — "build me an Edgar Markov deck", "make a deck around aristocrats in Orzhov", "finish this list", "fill my deck to 100", or a commander, strategy, deck file or Moxfield link to build from. Builds in rounds: a candidate pool, then the user picks per role in card-picker, until the deck is a legal 100.
---

# Building a deck in rounds

The user decides every card; your job is to put the right shortlist in front
of them, one role at a time, and keep count. The build lives in files in
`decks/`: `<name>.txt` holds the locked cards (Commander + Mainboard) and the
candidate pool (Maybeboard), `<name>.build.json` holds targets, rejected cards
and rounds, `<name>.profile.md` holds the strategy. A build stops and resumes
at any step: `status` says where it is.

```bash
B=skills/deck-builder/scripts/build.py
P=skills/score-card/scripts/deckprofile.py
K=skills/card-picker/scripts/picker.py
```

## Flow

1. **Start the deck.** Get to a deck file with a `// Commander` section.
   - Commander given: write `decks/<slug>.txt` with `// Name:`,
     `// Format: commander` and `// Commander` holding it (two lines for a pair).
   - Deck file: use it; its Mainboard is already locked in.
   - Moxfield link: `moxfield-deck` pull into `decks/`.
   - Strategy only: `edhrec.py theme <theme> --colors <c>`, read the top
     commanders' text, and offer 5–8 in `$K pick --count 1` with a reason each.
   Done when the file exists with its commander.

2. **Setup.** Ask for the bracket (1–5) unless the file has `// Bracket:`, and
   ask once for an optional budget: whole deck and/or per card, in BRL. Then
   `$B init <deck> --bracket N [--budget X] [--budget-card Y]`, and
   `$P new --deck <deck>`. Read the commander's text and the average deck's
   themes (`edhrec.py commander <name>`), write the profile's Plan, Rewards,
   Lacks and Avoid (house rules such as "no infinite combos" go in Avoid),
   show it with the targets `init` printed, and apply the user's changes:
   strategy in the profile then `$P stamp`, targets by editing
   `targets` in `<name>.build.json`. Done when the user has confirmed both.

3. **Pool.** Search for what the Plan needs beyond EDHREC's lists with
   `card-finder` (one `find --json` per theme or role the profile names),
   collect the names in a file, then `$B pool <deck> --extra <file>`. It adds
   EDHREC's cards for this commander, the average deck and your searches,
   minus off-identity, banned, over-budget and (bracket 1–2) game changer
   cards, and reports each drop. Done when the Maybeboard holds the pool and
   you've told the user its size and the drops in one or two lines.

4. **Rounds.** In order: `no-brainers`, `ramp`, `draw`, `removal`, `sweeper`,
   `protection`, `theme`, `lands`. For each:
   1. `$B round <deck> <role> --out <file>` writes the shortlist, best
      EDHREC inclusion first, and prints how many the role still needs.
      Skip a role whose need is 0.
   2. Read every shortlisted card's text (`scryfall-cards`), grade it in-deck
      with `score-card`'s rubric against the profile, and rewrite each
      `reason` to lead with the verdict and the clause that earns it; keep the
      script's numbers after it. Drop the cards the Avoid rules forbid, and
      order the file best first.
   3. `$K pick --suggestions <file> --count <N-M> --title "<role> for <deck>"`
      in the background, with `N-M` around the need (no-brainers: as many as
      fit). Act on the answer per `card-picker`: picked JSON goes to
      `$B apply <deck> --answer <answer file> --offered <file>`; a `note`
      changes your next shortlist; cancel or timeout means ask in chat.
   Picked cards move to the Mainboard with the printing the user chose; the
   rest of a role round leaves the pool, while no-brainers that weren't
   picked stay for their role round. Done when every role's need is 0 or the
   user has said it's enough.

5. **Fill or cut.** `$B status <deck>`. Under 100: run `theme` again, or
   `lands` for basics, until the deck is 100 (basics: add the count to the
   Mainboard directly, split by the colors the curve needs). Over 100: grade
   the Mainboard in-deck, write the weakest as suggestions (verdict as each
   reason), `$K pick --suggestions <file> --count <excess>`, and apply the
   answer with `$B apply <deck> --answer <answer file> --offered <file> --cut`. Done when `status` says 100/100, no `OVER BRACKET`.

6. **Finish.** `moxfield.py validate <deck>`, then the total with
   `ligamagic-preco -d <deck>` against the budget, then `$P show <deck>` for
   the final role counts. Report those three in a few lines and offer the
   Moxfield upload; upload only when the user says so (`moxfield-deck`).
   Done when validate passes and the user has the total.

Targets, the template and how `init` adjusts them: `references/template.md`.

## Traps

- **Inclusion is popularity.** "In 82% of Edgar decks" says players run it,
  not that it fits this Plan. The verdict comes from the text and the rubric.
- **Rejections stick.** A card left unpicked in a role round won't come back;
  if the user asks for one back, remove it from `rejected` in the build file
  and rerun `pool`.
- **Game changers.** `status` exits 1 with `OVER BRACKET` past the bracket's
  limit (3 at bracket 3); cut one before finishing.
- **The profile tracks the list.** `apply` restamps `<name>.profile.md` after
  every round, so it never reads stale; when picks change the plan (a note
  says "more tokens"), rewrite Plan/Rewards and stamp again.
