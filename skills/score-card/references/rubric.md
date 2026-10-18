# Scoring rubric

Grade every factor `low` / `med` / `high` with one line of reason. The reason
quotes or paraphrases the oracle text you just fetched, or names a number from
the data. A grade without a reason is not a grade.

## Factors

| Factor | Standalone: ask | In-deck: adjust |
|---|---|---|
| efficiency | Effect per mana compared with cards doing the same job | Less weight if the profile has cost reducers or a big-mana plan (avg mv ≥ 3.5, ramp ≥ 12); more on a low curve (avg mv ≤ 2.5) |
| speed | Impact the turn it lands: haste, ETB, flash, instant | More at brackets 4–5 and in aggro plans |
| card advantage | Draws or makes value repeatedly | More if role count `draw` + `card-advantage` < 8 |
| resilience | Survives spot removal and wipes; value when it dies | More if the plan depends on the board (tokens, voltron, aristocrats) |
| snowball | Gets worse for opponents every turn it stays | — |
| self-sufficiency | Works alone vs needs specific other cards | Less weight when the deck already has those pieces |
| interaction | Answers opponents' threats | More if `removal` < 8, `sweeper` < 2, or `protection` < 3 |
| usefulness | *Standalone only.* Strategies it fits; play rate from `edhrec.py card` | — |
| fit | *In-deck only.* Matches the profile's Plan and Rewards, the commander's text | — |
| fills gap | *In-deck only.* Covers a role in Lacks or a low role count; diminishing for the Nth copy of a role | — |

Role-count thresholds above are starting points for a 100-card deck; say when
you depart from them and why.

## Bracket emphasis

- **1–3**: fit, resilience, card advantage carry the verdict.
- **4**: speed, efficiency, interaction.
- **5**: speed, efficiency, combo potential; play rate matters less than
  cEDH results (`edhrec.py commander` bracket split, EDHTop16 in a later skill).

## Verdicts

| Verdict | Standalone | In-deck |
|---|---|---|
| `STAPLE` | Belongs in nearly any deck in its colors (play rate ≳ 30% and strong grades) | Auto-include |
| `STRONG` | Clearly good in its natural decks | Clearly worth a slot |
| `PLAYABLE` | Fine filler | Fine; first to cut for an upgrade |
| `NICHE` | Good only in specific strategies | Doesn't fit this deck's plan |
| `WEAK` | Outclassed | Outclassed or works against the plan |

## Flags

Print above the grades. A flag is never averaged away.

- `GAME CHANGER` — `game_changer` from Scryfall; bracket 3 allows up to 3.
- `INFINITE COMBO RISK` — your oracle read finds a two- or three-card infinite
  with commonly played cards. Name the partner cards.
- `OFF-IDENTITY` — outside the profile's colors.
- `BANNED` — `legalities.commander` is not `legal`.
- `PROFILE STALE` — no in-deck score; review the profile first.

## Data vs your read

Always print the `data:` line. When your read disagrees with it (STRONG at 2%
play rate, WEAK at 40%), add a `note:` with the reason: new card, precon
inflation, underplayed, popular for flavor. Don't move grades toward the data.

## Output

```
Blood Artist — in: Markov Gang (bracket 3)
  verdict: STRONG
  efficiency   high  2 mv, triggers on any creature death
  speed        med   no immediate impact
  resilience   low   1/1, dies to anything
  fit          high  deck makes vampire tokens; 4 sac outlets
  fills gap    med   deck already has 2 drain effects
  data: play rate 11.4% (595,488 / 5,217,553), salt 0.69, not a game changer
```

Standalone heading: `Blood Artist — standalone`. Use `usefulness` in place of
`fit` and `fills gap`.

## Worked examples (acceptance)

- Sol Ring standalone → `STAPLE`: efficiency high (1 mv, +2 mana), usefulness
  high (83% play rate, colorless). No flag: it is not on the Game Changers list
  (check `game_changer` every time; the list changes).
- Blood Artist standalone → `NICHE`: strong only where creatures die en masse;
  11% play rate.
- Blood Artist in an aristocrats profile → `STRONG`: fit high, fills a drain role.
- A 7+ mv sorcery bomb → efficiency `high` in a cost-reducer / big-mana profile,
  `low` in a low-curve aggro profile. Same card, different deck.
