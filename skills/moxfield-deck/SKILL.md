---
name: moxfield-deck
description: Use to create, update, pull, validate or sync a deck on Moxfield (moxfield.com) — "upload this deck to Moxfield", "import my list from Moxfield", "does the local deck match Moxfield?", "swap X for Y in the deck and update it there", a moxfield.com/decks/... link, Bulk Edit, Moxfield tags, checking a Commander deck is legal (100 cards, color identity, singleton, banned, game changers) before publishing. Applies even when the request doesn't mention Moxfield but involves maintaining a decklist that lives there.
compatibility: Python 3 (stdlib). Reading needs internet (api2.moxfield.com, api.scryfall.com). Writing needs Claude in Chrome with moxfield.com allowed in the extension permissions and a logged-in session.
metadata:
  author: kichelm
  version: "0.1"
---

# Deck on Moxfield

`$SKILLS` below is the folder that holds the installed MTG skills, one level up
from this file's folder (for example `~/.agents/skills`). Run commands from the
user's project folder, so files under `decks/` land there. On Windows, call
`python` (or `py`) when `python3` is missing.

Moxfield has no public API. Reading goes through the same JSON endpoint the site
uses (`api2.moxfield.com`), which answers `curl` with a browser User-Agent.
Writing only exists through the site, logged in — the script prepares the text
and Claude in Chrome pastes it into **Bulk Edit**.

That's why the source of truth is the **local file**, versioned in git. Moxfield
is the showcase: playtest, prices, sharing. Every change starts in the file, goes
through `validate`, goes to the site, and ends with `diff` confirming the site
matches the file.

## Flow

```bash
S=$SKILLS/moxfield-deck/scripts/moxfield.py

# 1. bring an existing deck (public or unlisted) into the repo
python3 $S pull https://moxfield.com/decks/<id> -o decks/markov-gang.txt

# 2. edit the file (or create it from scratch, format below)

# 3. validate: names on Scryfall, 100 cards, color identity, singleton,
#    banned, game changers. Exit 1 = some ERROR, don't proceed. Exit 0 with the
#    word `ok` = clean; exit 0 with only WARNING = passed, but read the warnings
#    and relay them.
python3 $S validate decks/markov-gang.txt

# 4. generate one board's block and paste it into Bulk Edit (see Browser section)
python3 $S export decks/markov-gang.txt --board mainboard --copy

# 5. confirm the site matches the file. Exit 0 = identical.
python3 $S diff decks/markov-gang.txt <id>
```

New deck: create the file, `validate`, create the empty deck on the site, paste
the `publicId` into `// Moxfield:`, paste the boards, `diff`.

Card swap requested by the user ("take out X, put in Y"): read the oracle text of
both on Scryfall before giving an opinion (skill `scryfall-cards`; rule in
`AGENTS.md`), edit the file, `validate`,
then the site. Don't edit on the site first — the file is what's versioned.

## Local file format

It's Moxfield's Bulk Edit syntax plus section headers, so what `pull` writes and
what `export` pastes are the same text:

```
// Moxfield: https://moxfield.com/decks/<publicId>
// Name: Markov Gang
// Format: commander
// Bracket: 3

// Commander
1 Olivia, Opulent Outlaw (OTJ) 229 *F*

// Mainboard
1 Edgar Markov (C17) 36 #alt-commander #vampire
1 Sol Ring (CMM) 410 #ramp
8 Swamp

// Sideboard
// Maybeboard
1 Bloodghast #vampire
```

- `qty name (SET) number *F* *A* #tag #!globalTag` — everything after the name is
  optional and order doesn't matter. Set and number pin the printing; without
  them Moxfield picks one. Tags with spaces don't exist: `#fast-ramp`.
- Accepted headers: `// Commander`, `// Mainboard`, `// Sideboard`,
  `// Maybeboard`, `// Companion`, with or without `//`, in Portuguese too
  (`Comandante`, `Reserva`, `Considerando`). With no header at all everything
  goes to Mainboard and the script warns — that's how the site's Export arrives.
- `// Key: value` at the top is free-form metadata; `Moxfield` and `Format` are
  the ones the script reads. The Portuguese keys older files use (`Nome`,
  `Formato`) still parse. A comment without `:` is ignored.
- The 100 total = Commander + Companion + Mainboard. Sideboard and Maybeboard
  don't count.

## Browser

Before opening the site: `tabs_context_mcp`. If `navigate` to moxfield.com
returns "This site is blocked by your site permissions", stop and ask the user
to allow `moxfield.com` in the Claude in Chrome extension — there's no
workaround. Headless Playwright won't do: the deck belongs to the user's account
and needs the logged-in session that only exists in their Chrome.

The step-by-step of the controls (New Deck, Bulk Edit per board, Save, Export)
and how to paste 100 lines without typing them one by one are in
`references/bulk-edit.md`. Read it before the first click. Find buttons by text
with `find`; don't guess coordinates.

After **Save**, run `diff`. Moxfield drops lines it doesn't recognize without
warning, so "saved" doesn't mean "got in".

## Traps

**Bulk Edit doesn't remove tags.** Deleting `#tag` from the line and saving leaves
the tag there. To remove it, use Table View (shift-click → Manage Tags). `diff`
shows `tags [...] -> [...]` until you do.

**Commander in the wrong box becomes 101 cards.** It has its own box in Bulk
Edit. `validate` already complains if the file has no `// Commander`.

**A private deck gives 404 on `pull` and `diff`.** api2 only serves public and
unlisted. For your own deck, keep it unlisted while working; nobody finds an
unlisted deck without the link. If it has to stay private, use Export → Text on
the site and add the section headers by hand.

**Cloudflare 403.** Happens if the User-Agent doesn't look like a browser, or in
bursts. The script already sends a Chrome UA; if it still gets 403, wait a minute.
Don't run `pull` in a loop over many decks.

**Double-faced names.** Moxfield stores `Delver of Secrets // Insectile Aberration`;
Scryfall `/cards/collection` doesn't find that name. The script tries the front
face on its own. If `validate` says it resolved as another name, check it — it may
be a typo fixed by fuzzy, it may be the wrong card.

**`validate` knows Commander, not the other formats in depth.** For a `Format:`
other than commander it checks only names and legality; deck size and singleton
are up to you.

**Game changers and bracket.** `validate` lists the deck's game changers
(Scryfall's `game_changer` field). Bracket 3 allows up to 3; the user's deck aims
for bracket 3–4 and doesn't want infinite combos — the script doesn't detect
that, you need to read the cards.

**BRL prices are the `ligamagic-preco` skill's job**; Moxfield's JSON carries
USD/EUR. To mirror the same file on LigaMagic, `ligamagic-deck` reads this
format (headers and tags included).

## Tests

```bash
python3 -m unittest discover -s $SKILLS/moxfield-deck/tests
```

The shape of the api2 JSON, measured calls and what changes between
public/unlisted/private are in `references/api.md` — read it when
`pull --json` is needed or something in the JSON doesn't match expectations.
