# Bulk Edit and import on Moxfield

## Line syntax

Applies in Bulk Edit, in a new deck's "Paste in List", and in the script's `export`:

```
<qty> <name> (<SET>) <number> *F* *A* #tag #!globalTag
1 Sol Ring (CMM) 410 *F* #ramp
1 Olivia, Opulent Outlaw
```

- Set and collector number are optional; without them Moxfield picks a default
  printing (the most recent non-promo).
- `*F*` foil, `*A*` altered. `*E*` (etched) the script reads too.
- `#tag` is a deck tag; `#!tag` is an account-wide global tag. Tags can't have
  spaces — use `#fast-ramp`.
- Names with `//` work (`Fire // Ice`, `Delver of Secrets // Insectile Aberration`).
- A line Moxfield doesn't recognize is **silently dropped** on save; the card
  disappears without warning. That's why the flow always ends with `diff`.
- **Bulk Edit adds tags but doesn't remove them.** Removing `#tag` from the line
  and saving leaves the tag as it was. To remove: Table View, shift-click the
  card, "Manage Tags".

Prefixes accepted in text import (not in Bulk Edit, which has one box per board):
`sideboard:` / `side:` / `sb:` sends the line to the sideboard; `maybe:` /
`maybeboard:` / `consider:` / `considering:` to the maybeboard. There's no
commander prefix in import — the commander is chosen afterwards, on the deck page.

## Path on the site (own deck, logged in)

Documented from public references; Claude in Chrome hasn't opened the logged-in
site to confirm yet, so locate the controls by text (`find`) instead of trusting
position.

**Create deck**

1. `https://moxfield.com/decks/personal` → **New Deck** button (or `/decks/new`).
2. Form: **Name**, **Format** (Commander / EDH), **Visibility**
   (Public / Unlisted / Private). Leave it Unlisted until the deck is validated —
   that way `pull`/`diff` work and nobody sees a half-finished list.
3. Save the empty deck and **copy the `publicId` from the URL** into the
   `// Moxfield:` line of the local file.

**Update list (Bulk Edit)**

1. On the deck page, **More** menu (or the edit pencil) → **Bulk Edit**.
2. The modal has one tab/box per board: Commander(s), Mainboard, Sideboard,
   Maybeboard (and others that don't matter). Each box shows the board's current
   contents in this same syntax.
3. For each board that changed: `export deck.txt --board <board> --copy`,
   select everything in the box (ctrl+a) and paste. Pasting via `computer`'s
   `type` with 100 lines is slow; better to use `javascript_tool` setting
   `textarea.value` and dispatching `new Event("input", {bubbles: true})` so
   React sees it.
4. **Save**. Rejected cards disappear without warning.
5. `diff deck.txt <id>` until it says `identical`.

The commander has to go in the Commander box. In the Mainboard box it becomes the
101st card and Moxfield flags the deck as illegal — `validate` catches this before
you paste.

**Metadata** (bracket, description/primer, hubs, cover) lives in **Edit deck
details**, not in Bulk Edit. `pull` brings `bracket` and `visibility` into the
file header just for the record; the script doesn't change them.

## Export from the site

**Export** menu on the deck page: Text / Arena / MTGO / CSV. Moxfield's text uses
the same line syntax above, with boards separated by a blank line and no
header — `parse_deck` treats this as all-mainboard and warns. For your own
private deck, export from there and add the `// Commander` / `// Mainboard`
headers by hand, or make the deck unlisted and use `pull`.
