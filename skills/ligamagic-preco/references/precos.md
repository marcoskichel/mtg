# `getEditions.php` — esquema e divergências

Extraído por request real em 29/08/2026. A Liga não publica documentação; tudo
aqui é reconferível repetindo a chamada. Os metadados gerais do site (IDs de
formato, seções, tipos de export, endpoint de busca de nomes) estão em
`../../ligamagic-deck/references/liga-metadata.md`.

## A chamada

```
POST https://www.ligamagic.com.br/ajax/cards/getEditions.php
Content-Type: application/x-www-form-urlencoded
Referer: https://www.ligamagic.com.br/

card_name=Lightning+Bolt&returnType=json&edicao_sel=&prefixo=
```

Sem autenticação, sem token. `card_name` aceita o nome em inglês **ou** em
português (`Raio` e `Lightning Bolt` devolvem o mesmo `card:"12534"`), mas exige
a grafia exata da Liga — ver "Falhas" abaixo.

## Resposta

```json
{"success":"1","card":"12534",
 "image":"//repositorio.sbrauble.com/images/cartas/nocard.jpg",
 "cardNamePT":null,"cardNameEN":null,"iCor":null,"iCustoManaConv":null,
 "iTipoCard":null,"sCusto":null,
 "itens":[
   {"key":480114,"value":"30th Anniversary Edition","image":"...","sigla":"30a",
    "precoMaior":"122.30","precoMedio":"120.70","precoMenor":"119.90",
    "foil_precoMaior":"0.00","foil_precoMedio":"0.00","foil_precoMenor":"0.00",
    "number":null,"iNumeroCartas":null}],
 "normal_precoMenor":"5.50","normal_precoMedio":"87.22","normal_precoMaior":"5499.99",
 "foil_precoMenor":"13.49","foil_precoMedio":"100.95","foil_precoMaior":"5499.99"}
```

Os seis agregados vêm **depois** de `itens` no JSON, não antes. `cardNamePT`,
`cardNameEN`, `iCor`, `iCustoManaConv`, `iTipoCard` e `sCusto` vieram `null` em
todas as cartas testadas — a resposta serve só para preço.

Cada item de `itens` é uma edição: `sigla` é o código do set na Liga (nem sempre
igual ao do Scryfall — `4e` para Fourth Edition, `rv` para Revised), `value` é o
nome, com entidades HTML (`Alian&ccedil;as`) e aspas escapadas com barra
(`Baldur\'s Gate`). Passe por unescape.

Valores em BRL, string com ponto decimal.

## `0.00` = sem estoque

Não é grátis: é ausência de anúncio ativo. Vale para os agregados e para cada
campo de cada edição, e os campos são **independentes** — existe linha com
`precoMenor` e `precoMaior` válidos e `precoMedio` em `0.00`:

```
rf30a  30th Anniversary Edition (Retro Frame)  menor=84.79  medio=0.00  maior=84.79
```

Carta inteiramente sem estoque devolve `success:"1"` com tudo zerado — testado com
`Fraternal Exaltation`: 1 edição, todos os doze campos em `0.00`.

## Falhas

Nome que a Liga não indexa devolve `{"error":"2"}`, sem `success` e sem `itens`:

```
card_name=Delver of Secrets // Insectile Aberration  ->  {"error":"2"}
card_name=Delver of Secrets                          ->  success:1, 8 edições
card_name=Valki, God of Lies // Tibalt, ...          ->  {"error":"2"}
card_name=Fire // Ice                                ->  success:1, 9 edições
```

Split e adventure mantêm o `//`; transformação e MDFC não. Resolva o nome pelo
`clubedaliga.com.br/api/cardsearch` antes.

**HTTP 429 com `Retry-After: 10`.** Cloudflare na frente do site. Umas dezenas de
consultas seguidas — mesmo espaçadas em 0.8s — começam a levar 429; sem delay
nenhum, chega em ~12. O cabeçalho vem preenchido, então honrá-lo basta. Ignorar
transforma metade do deck em "carta não encontrada".

## Agregados divergem das edições

Os seis campos do topo **não** são derivados de `itens`. Medido em 29/08/2026:

| Carta | agregado `normal_precoMenor` | menor `precoMenor` em `itens` | por quê |
|---|---|---|---|
| Lightning Bolt | 5.50 | 5.50 (`m11`) | batem |
| Sol Ring | 7.82 | 8.09 (`c19`) | agregado **abaixo** de qualquer edição listada |
| Force of Will | 315.00 (`ai`) | 94.90 (`wcd`) | agregado ignora World Championship Decks |

Ou seja: o agregado exclui impressões não sancionadas, mas também enxerga
anúncios que as linhas por edição não refletem. Para orçamento de deck, a linha
por edição é preferível — dá para nomear a edição e o número é rastreável até uma
carta comprável. O agregado serve como "a partir de" da página da carta.

`normal_precoMedio` é média dos anúncios, não mediana nem preço de mercado:
R$ 87,22 para Lightning Bolt, puxado por Alpha e Secret Lair.

## Siglas não sancionadas em torneio

Têm preço real na Liga e apareceriam como "edição mais barata", mas não são carta
legal:

| sigla | edição | motivo |
|---|---|---|
| `wcd` | World Championship Decks | borda dourada |
| `ced` | Collector's Edition | borda quadrada |
| `cedi` | International Collectors' Edition | borda quadrada |
| `30a` | 30th Anniversary Edition | proxy oficial |
| `rf30a` | 30th Anniversary Edition (Retro Frame) | proxy oficial |

Sets só de MTGO (`med`, `me2`, `me4`, `vma`) aparecem em `itens` mas sempre com
`0.00`, então se filtram sozinhos por falta de estoque.

## Não use `cards_stock`

A página `?view=cards/card&card=<Nome>` traz `var cards_stock` com os anúncios
individuais, mas o campo `precoCss` é ofuscado: classes CSS com nome aleatório por
page load, cada uma um `background-position` num sprite de dígitos. Anti-scraping
deliberado. Os agregados do `getEditions.php` são texto limpo.
