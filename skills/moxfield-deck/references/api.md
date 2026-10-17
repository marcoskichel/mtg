# api2.moxfield.com — o que foi medido (2026-09-30)

Endpoint que o front do Moxfield usa. Nao documentado, sem garantia. Funciona com
`curl` puro desde que vá `User-Agent` de navegador; sem UA ou com UA de script o
Cloudflare devolve 403. O script manda tambem `Accept`, `Referer` e `Origin`.

| Chamada | Resultado |
|---|---|
| `GET /v3/decks/all/<publicId>` | deck publico ou unlisted: 200 com JSON completo |
| mesmo, deck privado ou id errado | 404 |
| `GET /v2/decks/search?q=...&fmt=commander&pageSize=3&sortType=views&sortDirection=descending` | 200, `data[]` com `publicId`, `name`, `format`, `mainboardCount` |
| qualquer POST/PUT sem bearer da sessao | nao testado — escrita e feita pelo navegador, ver `bulk-edit.md` |

`publicId` tem 22 chars base64url (`j-0aJlxuOUm9FnKRvJcfZw`) e aparece em
`https://moxfield.com/decks/<publicId>`; sufixos `/primer`, `/export` etc. nao
mudam o id.

## Forma do JSON

Chaves de topo que importam:

```
name, format, visibility ("public"|"unlisted"|"private"), publicId, publicUrl,
bracket (1-5 ou null), autoBracket, colorIdentity ["W","R"], hubs[], version,
main {name}            # carta de capa, NAO o comandante
authorTags {nome: [tag, ...]}   # tags locais do deck, indexadas por NOME da carta
boards {commanders, companions, mainboard, sideboard, maybeboard,
        signatureSpells, attractions, stickers, contraptions, planes, schemes, tokens}
tokens[]               # tokens gerados, nao fazem parte do deck
```

Cada board e `{count, cards: {<id>: entrada}}`. Entrada:

```
quantity, boardType, finish ("nonFoil"|"foil"|"etched"), isFoil, isAlter, isProxy,
card {id, uniqueCardId, scryfall_id, name, set, cn, set_name, layout, type_line,
      oracle_text, mana_cost, cmc, colors, color_identity, legalities{}, rarity,
      prices {usd, usd_foil, eur, eur_foil, ck, ct, scg, mp, tix_fb, ...}, card_faces[], ...}
```

Pontos que pegam:

- **Tags nao ficam na entrada da carta.** Estao em `authorTags`, por nome. A mesma
  carta no main e no maybeboard compartilha as tags. Tags globais (`#!`) nao
  aparecem no JSON publico — sao da conta, nao do deck.
- `card.name` de carta dupla vem completo: `Delver of Secrets // Insectile Aberration`.
  A Scryfall `/cards/collection` nao acha esse nome; o script cai para a face frontal.
- `card.cn` pode ser `C15-56`, `MH1-7` (The List, set `plst`) ou ter `★`. Nao e inteiro.
- `main.name` e a carta de capa escolhida pelo autor. O comandante esta em
  `boards.commanders`.
- `prices` sao de lojas americanas/europeias. BRL e assunto da `ligamagic-preco`.
- Deck `format: "none"` existe (primers, listas soltas). `validar` so faz as regras de
  Commander quando o formato e `commander`.

Sem rate limit medido em uso normal (poucas chamadas por minuto). Nao faca varredura.
