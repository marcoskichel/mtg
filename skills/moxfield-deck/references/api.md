# api2.moxfield.com — what was measured (2026-09-30)

The endpoint Moxfield's front end uses. Undocumented, no guarantees. Works with
plain `curl` as long as a browser `User-Agent` goes along; with no UA or a script
UA Cloudflare returns 403. The script also sends `Accept`, `Referer` and `Origin`.

| Call | Result |
|---|---|
| `GET /v3/decks/all/<publicId>` | public or unlisted deck: 200 with full JSON |
| same, private deck or wrong id | 404 |
| `GET /v2/decks/search?q=...&fmt=commander&pageSize=3&sortType=views&sortDirection=descending` | 200, `data[]` with `publicId`, `name`, `format`, `mainboardCount` |
| any POST/PUT without the session bearer | not tested — writing is done through the browser, see `bulk-edit.md` |

`publicId` is 22 base64url chars (`j-0aJlxuOUm9FnKRvJcfZw`) and appears in
`https://moxfield.com/decks/<publicId>`; suffixes `/primer`, `/export` etc. don't
change the id.

## JSON shape

Top-level keys that matter:

```
name, format, visibility ("public"|"unlisted"|"private"), publicId, publicUrl,
bracket (1-5 or null), autoBracket, colorIdentity ["W","R"], hubs[], version,
main {name}            # cover card, NOT the commander
authorTags {name: [tag, ...]}   # the deck's local tags, keyed by card NAME
boards {commanders, companions, mainboard, sideboard, maybeboard,
        signatureSpells, attractions, stickers, contraptions, planes, schemes, tokens}
tokens[]               # generated tokens, not part of the deck
```

Each board is `{count, cards: {<id>: entry}}`. Entry:

```
quantity, boardType, finish ("nonFoil"|"foil"|"etched"), isFoil, isAlter, isProxy,
card {id, uniqueCardId, scryfall_id, name, set, cn, set_name, layout, type_line,
      oracle_text, mana_cost, cmc, colors, color_identity, legalities{}, rarity,
      prices {usd, usd_foil, eur, eur_foil, ck, ct, scg, mp, tix_fb, ...}, card_faces[], ...}
```

Gotchas:

- **Tags don't live on the card entry.** They're in `authorTags`, by name. The same
  card in main and in maybeboard shares the tags. Global tags (`#!`) don't
  appear in the public JSON — they belong to the account, not the deck.
- `card.name` of a double-faced card comes in full: `Delver of Secrets // Insectile Aberration`.
  Scryfall `/cards/collection` doesn't find that name; the script falls back to the front face.
- `card.cn` can be `C15-56`, `MH1-7` (The List, set `plst`) or contain `★`. It's not an integer.
- `main.name` is the cover card chosen by the author. The commander is in
  `boards.commanders`.
- `prices` are from American/European stores. BRL is the `ligamagic-preco` skill's job.
- Decks with `format: "none"` exist (primers, loose lists). `validate` only applies
  the Commander rules when the format is `commander`.

No rate limit measured under normal use (a few calls per minute). Don't crawl.
