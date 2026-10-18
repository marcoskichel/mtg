---
name: card-picker
description: Use when the user should see Magic cards and choose among them instead of reading a list in chat — suggesting cards to add, offering cuts or swaps, "which of these do you want", "show me the deck", "let me pick". Opens a browser page with card images, oracle text and your reason per card; the user picks with keyboard or mouse and the answer comes back as JSON.
---

# Letting the user pick cards

The user decides; your job is a short list worth deciding on. Every card on
the page carries your **reason**, and a reason holds only if it rests on
oracle text you read in this session (fetch it with `scryfall-cards`, find
candidates with `card-finder`). The page shows the real card next to your
reason, so a reason the text doesn't back is visible to the user.

```bash
P=skills/card-picker/scripts/picker.py
python3 $P pick --suggestions picks.json --count 1-3 --title "Ramp for Edgar" \
  --prompt "Anything to change?" --prompt-optional
python3 $P pick --cards "Sol Ring" "Arcane Signet" --count 1 --title "Which rock?"
python3 $P show --deck decks/saruman.txt
```

## Flow

1. **Build the list.** Pick candidates the usual way and verify each against
   its oracle text. Write a JSON list for `--suggestions`, with each reason in one
   or two sentences naming the clause that makes the card fit:
   `[{"name": "Fellwar Stone", "reason": "{T}: mana of a color an opponent's land could make — fixes in 3+ colors."}]`.
   Done when every card has a reason you can trace to its text. Plain
   `--cards` or `--deck` fits when there's nothing to explain (showing a deck,
   picking cuts from it).

2. **Ask.** Set `--title` to the question as the user would say it, and set
   `--count` to how many the answer needs: `N` exact, `N-M` a range, `any` = at least one.
   Add `--prompt` when you need the why (`--prompt-optional` when it's a
   nice-to-have). Run the command **in the background** (Claude Code:
   `run_in_background: true`) because it blocks until the user answers, for
   up to `--timeout` seconds (default 1800), which is far longer than a foreground
   shell call is allowed. Tell the user in one line that the picker is open. Done when
   stderr shows `Waiting for the user in the browser`. Names Scryfall
   couldn't resolve are listed above that line: fix them and run again,
   because they're missing from the page.

3. **Act on the answer.** Read stdout when the command finishes:

   | exit | stdout | do |
   |---|---|---|
   | 0 | `{"status": "picked", "picked": [{"name", "set", "collector_number"}], "note"?}` | carry out the pick; the `note` overrides your plan where they conflict |
   | 0 | `{"status": "closed", "focused": "Name"}` | `show` ended (Done or Esc); `focused` is the card the user ended on |
   | 130 | `{"status": "cancelled"}` | the user declined to pick: ask in chat what they want instead |
   | 124 | `{"status": "timeout"}` | ask in chat |
   | 2 | (stderr) | bad input or no card found: fix and rerun |
   | 3 | (stderr) | server failure; stderr names the log |

   Done when the picked cards are applied (deck edit via `moxfield-deck`,
   price via `ligamagic-preco`) or the user has redirected you.

## How it runs

The first call starts a local server on `127.0.0.1:8737` (env
`CARD_PICKER_PORT`), and every later call reuses it. Each waiting call is a tab on
the same page, so parallel agents share one browser tab, and a new tab opens only
when none is connected (`--no-open` prints the URL instead). The server
exits after 15 idle minutes, and a call that finds a server running older code replaces it
once nothing is waiting on it. Log, token and cached images live in `~/.cache/mtg-skills/card-picker/`.
Tests: `python3 -m unittest discover -s skills/card-picker/tests`.
