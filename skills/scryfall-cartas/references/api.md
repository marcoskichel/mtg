# API da Scryfall: endpoints usados e falhas medidas

Medido por request real em 30/09/2026. Documentação oficial em
https://scryfall.com/docs/api. Tudo aqui é reconferível repetindo a chamada.

Base `https://api.scryfall.com`. Cabeçalhos obrigatórios: `User-Agent` (qualquer
valor; vazio dá HTTP 400) e `Accept: application/json`. Limite pedido pela
Scryfall: 10 req/s. `Cache-Control: public, max-age=172800` nas respostas de
carta (48 h).

## `GET /cards/named?exact=` | `?fuzzy=`

Uma carta. `exact` exige o nome completo em inglês (`Fire // Ice` ou só `Fire`
funcionam; a API resolve a face). `fuzzy` aceita erro de grafia, mas:

- nome ambíguo → `{"object":"error","code":"not_found","type":"ambiguous"}`
  (`bolt`);
- nome curto ou em português → **uma carta qualquer**, HTTP 200. `Raio` devolveu
  Samurai of the Pale Curtain; `anel solar` devolveu Sol Ring por sorte. O
  script só aceita fuzzy quando o resultado parece com o pedido
  (`looks_like`).

## `POST /cards/collection`

Até 75 identificadores por chamada, `{"identifiers":[{"name":"Sol Ring"},
{"set":"m11","collector_number":"149"}]}`. Resposta `data[]` com as cartas e
`not_found[]` com os identificadores que falharam.

- Só inglês, nome exato (sem caixa): `Raio` → `not_found`.
- **Carta de duas faces precisa ir pela face da frente.** `"Delver of Secrets //
  Insectile Aberration"` → `not_found`; `"delver of secrets"` → encontrada, com
  `name` completo `Delver of Secrets // Insectile Aberration`.
- A ordem de `data[]` não é garantida igual à dos identificadores; o script casa
  por nome, face frontal e nome de face.

## `GET /cards/search?q=`

175 cartas por página; `total_cards`, `has_more`, `next_page` (URL pronta).
Parâmetros: `unique=cards|art|prints`, `order=name|cmc|released|usd|eur|edhrec|
rarity|color|power|toughness|set|tix|artist|review|penny`, `dir=asc|desc`,
`include_extras`, `include_multilingual`, `include_variations`.

- **Palavra-chave desconhecida não é erro.** `c:r tipo:creature o:haste` →
  HTTP 200, `warnings: ["Invalid expression “tipo:creature” was ignored. Unknown
  keyword “tipo”."]`, e a busca roda como `c:r o:haste`: 1092 cartas em vez de
  35. Qualquer consumidor tem que ler `warnings[]`.
- Query sem resultado → HTTP 404 `code:"not_found"` com `details` explicando.
- `name:"Raio" lang:pt` é substring (67 cartas); `!"Raio" lang:pt` é exato (1).
  Não precisa de `include_multilingual` quando `lang:` está na query.
- `!"Delver of Secrets" lang:pt` acha a carta mesmo sem impressão em português
  nesse caso (`printed_name: null`).

## `prints_search_uri` e `rulings_uri`

Cada carta traz as duas URLs prontas. `prints_search_uri` é um
`/cards/search?q=oracleid:...&unique=prints&order=released` e pagina como
qualquer busca; inclui impressões `digital` (MTGO/Arena) e `promo`. Lightning
Bolt: 70 impressões em 1 página.

`rulings_uri` devolve `data[]` de `{source, published_at, comment}`.

## Objeto carta, campos que importam

| campo | nota |
|---|---|
| `name` | `A // B` para carta dupla, split, adventure |
| `layout` | `normal`, `transform`, `modal_dfc`, `split`, `adventure`, `flip`, `meld`... |
| `oracle_text`, `mana_cost`, `power`, `toughness` | **`null` quando há `card_faces`** |
| `card_faces[]` | `name, mana_cost, type_line, oracle_text, power, toughness, image_uris` por face |
| `cmc` | valor de mana; em carta dupla é o da frente (split soma) |
| `color_identity` | para Commander |
| `legalities` | `legal`, `not_legal`, `restricted`, `banned` por formato (`commander`, `modern`, `pauper`, `paupercommander`, `brawl`, `predh`...) |
| `prices` | `usd`, `usd_foil`, `usd_etched`, `eur`, `eur_foil`, `tix`. Strings, `null` sem preço. Sem BRL. |
| `image_uris` | `small, normal, large, png, art_crop, border_crop`; em carta dupla fica dentro de cada face |
| `set`, `set_name`, `collector_number`, `released_at`, `finishes`, `promo`, `digital` | por impressão |
| `printed_name`, `lang` | só em impressão não inglesa |

Sets de Scryfall usam código próprio: `plst` (The List), `sld` (Secret Lair),
`p*` costuma ser promo. Não coincidem com as siglas da LigaMagic.
