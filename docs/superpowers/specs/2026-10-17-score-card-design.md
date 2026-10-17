# score-card — design

Date: 2026-10-17. Status: approved in brainstorm, pending spec review.

## Goal

Grade a Magic card for Commander in one of two contexts:

- **Standalone**: raw power plus usefulness — how many strategies the card fits.
- **In-deck**: how good the card is *for a given deck*. The deck sets the
  weights: in a big-spells deck with cost reducers, mana value matters less
  than in a low-curve aggro deck.

The deck context can come from anything: a strategy with no list yet, a
commander name, a deck file in `decks/`, a Moxfield link, or a partial list
that grows while building.

score-card is the foundation for two later skills, each with its own spec:

```
score-card  ◄── commander-finder (ranks commanders against a theme + bracket brief)
     ▲
     └──────── deck-builder (strategy → big candidate pool → no-brainers → build around)
TUI (deferred until a designer defines look and feel) renders output of both
```

## Decisions

| Topic | Decision |
|---|---|
| Output | Per-factor grade `low`/`med`/`high` with a one-line reason, plus a verdict and a `data:` line. No single number. |
| Who grades | The agent, following `references/rubric.md`. Scripts gather facts and check freshness; they never grade. |
| Deck context | A **profile**: measured facts (recomputed every run, never stored) + a strategy section the agent writes (stored, fingerprinted). |
| Freshness | Strategy section carries a hash of the deck list. Fresh → score; drift ≤5 cards → score with warning; >5 cards or commander/bracket changed → `STALE`, stop until reviewed. |
| Data sources | Scryfall (text, legality, game changer), Scryfall Oracle Tags bulk file (roles), EDHREC (play rate, salt, homes, themes, bracket split). |
| Code placement | Each new fact goes to the skill that owns its source. One new data skill (`edhrec`), one new command in `card-finder` (`roles`), one small script in `score-card` (`deckprofile.py`). |

## Components

### 1. `skills/edhrec/` — new skill, one job: read EDHREC

EDHREC has no public API. `json.edhrec.com/pages/<path>.json` is what the site
itself loads; it answers `curl` with a browser User-Agent. Verified
2026-10-17.

```bash
E=skills/edhrec/scripts/edhrec.py
python3 $E card "Blood Artist" "Sol Ring"            # play rate, salt, top commanders, themes
python3 $E card -d pool.txt                           # batch; any decklist format
python3 $E commander "Edgar Markov"                   # decks, rank, salt, bracket_counts, themes, top cards
python3 $E commander "Kraum, Ludevic's Opus" "Tymna the Weaver"   # pair page
python3 $E theme aristocrats --colors wb              # commanders for theme + colors
python3 $E partners "Tymna the Weaver"                # legal pairings with deck counts
```

All subcommands take `--json` and `--ttl HOURS`.

Paths (verified):

| Subcommand | Path |
|---|---|
| `card` | `cards/<slug>` |
| `commander` | `commanders/<slug>` (pair: both slugs, alphabetical, joined by `-`) |
| `theme` | `tags/<theme>` or `tags/<theme>/<colorname>` (e.g. `orzhov`) |
| `partners` | `partners/<slug>` |

`commanders/<colorname>/<theme>` returns 403 — not a valid path.

**Slug rule**: lowercase; strip accents; drop apostrophes and commas; any other
run of non-alphanumerics becomes `-`. Transform/modal double-faced cards use
the **front face** (`delver-of-secrets`); split cards keep **both halves**
(`fire-ice`). Names come from Scryfall first so the slug is built from the
canonical English name.

**Fields used** (`container.json_dict.card` unless noted):

- `num_decks`, `potential_decks` → **play rate** = `num_decks / potential_decks`,
  printed with both raw numbers. Missing `potential_decks` → play rate `n/a`.
- `salt`, `rank`
- top-level `bracket_counts` (commander pages) — `{"1": n, …, "5": n}`
- top-level `tag_counts` (commander pages) — theme tags with counts (same data as `panels.taglinks`)
- `cardlists[]` — top commanders (card pages), pairings (partner pages),
  top/new commanders (theme pages)

Measured examples: Sol Ring 8.59M / 10.31M = 83%; Blood Artist 595k / 5.22M =
11.4%; Zulaport Cutthroat 444k / 5.22M = 8.5%. Kraum/Tymna bracket split:
5 → 4120, 4 → 255, 3 → 140.

**Not found vs blocked.** A missing page answers **403 with a non-JSON body**,
not 404. A Cloudflare block can also be 403. Rule: 403 whose body is a
Cloudflare challenge page (`cf-` markers / "Just a moment") or any 429 →
**blocked**: back off and retry ×4 (honor `Retry-After`), then report
`EDHREC BLOCKED`. Other 403 → **not found**. The two are separate report lines;
never tell the user a card has no EDHREC page when the request was blocked.

**Cache**: `~/.cache/mtg-skills/edhrec/<path>.json`, default TTL 24h (server
sends `max-age=1620`, so this is safe). Output prints the fetch date. 0.5 s
pause between uncached calls.

`-d` uses `scryfall.parse_input` (imported the way `card-finder` does), so any
decklist format works.

### 2. `card-finder`: new `roles` subcommand

The Oracle Tags bulk file that `card-finder` already caches
(`~/.cache/mtg-skills/oracle-tags.jsonl.gz`, 4,578 tags) maps each tag to
`oracle_id`s, and `finder.py` already resolves descendants (`TagIndex.cards`).
So roles are computed **offline**, with no per-role Scryfall searches.

```bash
F=skills/card-finder/scripts/finder.py
python3 $F roles "Blood Artist" "Sol Ring"
python3 $F roles -d decks/markov-gang.txt [--json]
```

- Resolves names with `scryfall.resolve_names` (batch, Portuguese, DFC) to get
  each card's `oracle_id`.
- For each role in a fixed list, checks membership in `TagIndex.cards(tag)`.
- Prints `<name>: ramp, mana-rock` per card; deck mode also prints counts per
  role.

Role list (one constant in `finder.py`; slugs checked against the tag index at
load, an unknown slug is an error in tests):

`ramp, mana-rock, cost-reducer, draw, card-advantage, removal, sweeper,
counterspell, protection, tutor, sacrifice-outlet, recursion`

Tags are community labels and lag new sets: a card with no role is reported as
`(no roles tagged)`, not as "does nothing". `card-finder`'s rule applies — the
oracle text decides.

### 3. `skills/score-card/` — the skill

```
skills/score-card/
  SKILL.md               how to score: flow, modes, pools, freshness, traps
  references/rubric.md   factors, bracket weights, verdicts, flags, worked examples
  scripts/deckprofile.py     deck profile: facts, fingerprint, staleness
  tests/test_profile.py
```

#### `deckprofile.py`

Imports `moxfield.parse_deck` (deck files), `scryfall` (card data) and
`finder` (roles) through `sys.path`, as `card-finder` does today.

```bash
P=skills/score-card/scripts/deckprofile.py
python3 $P show decks/markov-gang.txt            # or a .profile.md path
python3 $P new --deck decks/markov-gang.txt
python3 $P new --commander "Edgar Markov" --bracket 3 -o decks/edgar.profile.md
python3 $P new --strategy "aristocrats, drain on death" --colors wb --bracket 3 -o decks/orzhov-aristocrats.profile.md
python3 $P stamp decks/markov-gang.profile.md
```

`show` prints:

1. **Measured facts** (computed now, never stored): commander(s), color
   identity, bracket, deck size, curve by mana value, average mana value of
   non-lands, colored sources per color, role counts (from `finder roles`),
   game changers (count and names).
2. **Strategy section** read from the profile file.
3. **Freshness**: `fresh` / `drift (+X −Y): <names>` / `STALE (<reason>)`.

`STALE` → exit 1. Missing profile file → print facts, then
`NO PROFILE — run: deckprofile.py new --deck <path>` and exit 1.

`new` writes the header and an empty strategy skeleton for the agent to fill.
`stamp` recomputes the hash against the current deck and rewrites **only the
header**; run it after reviewing or rewriting the strategy.

Moxfield link as context: `moxfield.py pull <url> -o decks/<name>.txt` first,
then use the file. `deckprofile.py` does not fetch Moxfield itself.

#### Profile file format

`decks/<name>.profile.md`, next to the deck file, versioned in git:

```
// profile-of: decks/markov-gang.txt
// commanders: Olivia, Opulent Outlaw + Edgar Markov
// colors: wbr
// bracket: 3
// deck-hash: 3f9a1c2e
// cards-at-write: 87
// reviewed: 2026-10-17

## Plan
Go wide with vampire tokens from Edgar's eminence; Olivia turns combat damage
into treasure...

## Rewards
Casting vampires, creatures dying, attacking with many creatures.

## Lacks
Card draw (3 sources), protection for the board.

## Avoid
Infinite combos (house rule).
```

Strategy-only profiles omit `profile-of`, `deck-hash` and `cards-at-write`;
they are fresh until edited.

**Fingerprint**: SHA-256 (first 8 hex) of the sorted `name` list across
Commander + Companion + Mainboard, names case-folded, quantity included.
Order, printing, tags and whitespace don't change it. Sideboard and
Maybeboard don't count.

**Staleness rule**:

| Change since `deck-hash` | Status |
|---|---|
| none | `fresh` |
| ≤5 cards added+removed, same commanders and bracket | `drift`, exit 0, list the cards |
| >5 cards, or commanders changed, or bracket changed | `STALE`, exit 1 |

To compute the drift list, `stamp` also stores the sorted name list in a
sibling `decks/<name>.profile.lock` (one name per line). Threshold `5` is a
constant; tune later.

#### Rubric (`references/rubric.md`)

Factors (each `low`/`med`/`high` + reason quoting the oracle text or data):

| Factor | Standalone | In-deck adjustment |
|---|---|---|
| efficiency | effect per mana vs similar cards | less weight with cost reducers / big-mana plan; more on a low curve |
| speed | impact the turn it lands | more at brackets 4–5 and in aggro |
| card advantage | draws or generates value over time | more if profile lacks draw |
| resilience | survives removal / wipes | more if deck depends on board |
| snowball | gets worse for opponents each turn unanswered | — |
| self-sufficiency | works alone vs needs pieces | less weight if the deck has the pieces |
| interaction | answers threats | more if profile lacks removal/protection |
| usefulness | *standalone only*: strategies it fits; play rate + oracle read | — |
| fit | *in-deck only*: matches plan, commander, themes | — |
| fills gap | *in-deck only*: covers a role the profile lacks; diminishing for the Nth of a role | — |

Bracket emphasis: 1–3 fit, resilience, card advantage. 4 speed, efficiency,
interaction. 5 speed, efficiency, combo potential.

Verdicts: `STAPLE` (nearly any deck in its colors; play rate ≳30% and strong
grades), `STRONG`, `PLAYABLE`, `NICHE` (standalone: narrow; in-deck: doesn't fit
this deck), `WEAK`.

Flags, printed above the grades, never averaged away: `GAME CHANGER`,
`INFINITE COMBO RISK` (agent's oracle read), `OFF-IDENTITY`, `BANNED`,
`PROFILE STALE`.

**Data vs read**: the `data:` line always prints. When the read disagrees with
the data (STRONG with 2% play rate), add a `note:` explaining why (new card,
underplayed, precon inflation). Don't bend grades to match data.

Output shape:

```
Blood Artist — in: Markov Gang (bracket 3)
  verdict: STRONG
  efficiency   high  2 mv, triggers on any creature death
  speed        med   no immediate impact
  resilience   low   1/1, dies to anything
  fit          high  deck makes vampire tokens; 4 sac outlets
  fills gap    med   deck already has 2 drain effects
  data: play rate 11.4% (595k/5.22M), salt 0.69, not a game changer
```

### SKILL.md flow

**Single card**

1. In-deck: `deckprofile.py show <deck>`. `STALE` or `NO PROFILE` → read the deck,
   write or review the strategy, `stamp`, run again.
2. `scryfall.py card <name>` — oracle text, legality.
3. `finder.py roles <name>`.
4. `edhrec.py card <name>`.
5. Grade with the rubric; print the output shape.

**Pool (150–300 cards)**

1. Batch the same three calls with `-d pool.txt`.
2. Drop off-identity, banned, and cards with no role and no theme relevance to
   the profile; list what was dropped and why.
3. One-line quick grade for every survivor: verdict + fit tag.
4. Full write-up only near the cut line, for borderline `PLAYABLE`/`STRONG`, or
   on request.

## Errors

stdout is the answer; stderr is what changed or failed. Exit 1 whenever the
answer is incomplete.

| Case | Behavior |
|---|---|
| Card name unresolved | `NOT FOUND` (existing scryfall logic), exit 1 |
| EDHREC page missing | `edhrec: not found` for that card; still scored; data line says `no EDHREC data` |
| EDHREC blocked | retry ×4, then `EDHREC BLOCKED`, exit 1 |
| Oracle tags unavailable | `could not load oracle tags` (existing finder logic); roles omitted, exit 1 |
| Profile stale | `PROFILE STALE` + diff, exit 1 |
| Profile drift | warning + cards, exit 0 |
| Deck file without `// Commander` | profile from colors + strategy, warning |
| Network failure | `NETWORK FAILURE`, exit 1; never reported as "doesn't exist" |

## Testing

`unittest`, `urlopen` mocked, like the existing suites.

- **edhrec**: slug rule (accents, apostrophes, commas, DFC front face, split
  both halves, pair alphabetical); 403 not-found vs challenge vs 429; play-rate
  math incl. missing `potential_decks`; cache TTL; `-d` batch.
- **finder roles**: every role slug exists in a fixture tag index; descendant
  tags count (`removal` via `removal-creature`); DFC resolves to the right
  `oracle_id`; untagged card prints `(no roles tagged)`.
- **profile.py**: hash ignores order/printing/tags/whitespace; fresh / drift /
  stale thresholds; commander and bracket change → stale; `new` from deck,
  commander, strategy; `stamp` rewrites only the header; facts on a fixture
  deck (curve, sources, role counts).

**Live smoke run** before finishing: each new subcommand once;
`deckprofile.py show decks/saruman.txt`; one full in-deck and one standalone score;
a 30-card pool.

**Rubric acceptance** (by hand, recorded in the PR):

- Sol Ring standalone → `STAPLE`.
- Blood Artist standalone → `NICHE`; in an aristocrats profile → `STRONG`.
- A big sorcery (e.g. a 7+ mv bomb) → efficiency `high` in a cost-reducer /
  big-mana profile, `low` in a low-curve aggro profile.

## Out of scope

commander-finder, deck-builder, TUI and card rendering, budget/price (stays in
`ligamagic-preco`), Commander Spellbook combo lookup (candidate for a later
`INFINITE COMBO RISK` data source).

## Delivery

One worktree (`feat/score-card`), one PR, one commit per component: `edhrec`,
`card-finder roles`, `score-card`. `AGENTS.md` lists the new skills.
