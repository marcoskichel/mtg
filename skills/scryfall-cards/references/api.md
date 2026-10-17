# Scryfall API: endpoints used and measured failures

Measured with real requests on 2026-09-30. Official docs at
https://scryfall.com/docs/api. Everything here can be rechecked by repeating the call.

Base `https://api.scryfall.com`. Required headers: `User-Agent` (any value;
empty gives HTTP 400) and `Accept: application/json`. Limit requested by
Scryfall: 10 req/s. `Cache-Control: public, max-age=172800` on card responses
(48 h).

## `GET /cards/named?exact=` | `?fuzzy=`

One card. `exact` requires the full English name (`Fire // Ice` or just `Fire`
work; the API resolves the face). `fuzzy` accepts typos, but:

- ambiguous name → `{"object":"error","code":"not_found","type":"ambiguous"}`
  (`bolt`);
- short or Portuguese name → **some arbitrary card**, HTTP 200. `Raio` returned
  Samurai of the Pale Curtain; `anel solar` returned Sol Ring by luck. The
  script only accepts fuzzy when the result looks like the request
  (`looks_like`).

## `POST /cards/collection`

Up to 75 identifiers per call, `{"identifiers":[{"name":"Sol Ring"},
{"set":"m11","collector_number":"149"}]}`. Response `data[]` with the cards and
`not_found[]` with the identifiers that failed.

- English only, exact name (case-insensitive): `Raio` → `not_found`.
- **A double-faced card has to go by its front face.** `"Delver of Secrets //
  Insectile Aberration"` → `not_found`; `"delver of secrets"` → found, with the
  full `name` `Delver of Secrets // Insectile Aberration`.
- The order of `data[]` is not guaranteed to match the identifiers; the script
  matches by name, front face and face name.

## `GET /cards/search?q=`

175 cards per page; `total_cards`, `has_more`, `next_page` (ready-made URL).
Parameters: `unique=cards|art|prints`, `order=name|cmc|released|usd|eur|edhrec|
rarity|color|power|toughness|set|tix|artist|review|penny`, `dir=asc|desc`,
`include_extras`, `include_multilingual`, `include_variations`.

- **An unknown keyword is not an error.** `c:r tipo:creature o:haste` →
  HTTP 200, `warnings: ["Invalid expression “tipo:creature” was ignored. Unknown
  keyword “tipo”."]`, and the search runs as `c:r o:haste`: 1092 cards instead of
  35. Every consumer has to read `warnings[]`.
- Query with no results → HTTP 404 `code:"not_found"` with `details` explaining.
- `name:"Raio" lang:pt` is a substring match (67 cards); `!"Raio" lang:pt` is exact (1).
  `include_multilingual` is not needed when `lang:` is in the query.
- `!"Delver of Secrets" lang:pt` finds the card even with no Portuguese printing
  in that case (`printed_name: null`).

## `prints_search_uri` and `rulings_uri`

Each card carries both URLs ready-made. `prints_search_uri` is a
`/cards/search?q=oracleid:...&unique=prints&order=released` and paginates like
any search; it includes `digital` (MTGO/Arena) and `promo` printings. Lightning
Bolt: 70 printings in 1 page.

`rulings_uri` returns `data[]` of `{source, published_at, comment}`.

## Card object, fields that matter

| field | note |
|---|---|
| `name` | `A // B` for double-faced, split, adventure cards |
| `layout` | `normal`, `transform`, `modal_dfc`, `split`, `adventure`, `flip`, `meld`... |
| `oracle_text`, `mana_cost`, `power`, `toughness` | **`null` when there are `card_faces`** |
| `card_faces[]` | `name, mana_cost, type_line, oracle_text, power, toughness, image_uris` per face |
| `cmc` | mana value; on a double-faced card it's the front's (split sums) |
| `color_identity` | for Commander |
| `legalities` | `legal`, `not_legal`, `restricted`, `banned` per format (`commander`, `modern`, `pauper`, `paupercommander`, `brawl`, `predh`...) |
| `prices` | `usd`, `usd_foil`, `usd_etched`, `eur`, `eur_foil`, `tix`. Strings, `null` with no price. No BRL. |
| `image_uris` | `small, normal, large, png, art_crop, border_crop`; on a double-faced card it sits inside each face |
| `set`, `set_name`, `collector_number`, `released_at`, `finishes`, `promo`, `digital` | per printing |
| `printed_name`, `lang` | only on a non-English printing |

Scryfall sets use their own codes: `plst` (The List), `sld` (Secret Lair),
`p*` is usually promo. They don't match LigaMagic's set codes.
