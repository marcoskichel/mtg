# Sintaxe de busca da Scryfall

Referência oficial: https://scryfall.com/docs/syntax. Palavras-chave são em
inglês; **palavra desconhecida é ignorada em silêncio** (ver `api.md`), então
`tipo:`, `cor:`, `custo:` não existem. Use as da tabela.

Termos separados por espaço são AND. `or` entre termos, `-` nega, parênteses
agrupam. Texto com espaço vai entre aspas.

## Cor e identidade

| quero | query |
|---|---|
| cartas vermelhas | `c:r` |
| exatamente azul e preto | `c=ub` |
| azul ou preto, mono | `c:u or c:b` com `c=1`... use `c<=ub c>=1` |
| incolor | `c:c` |
| multicolor | `c:m` |
| identidade de comandante Mardu | `id<=rwb` (cabe no deck) |
| identidade exatamente Rakdos | `id=br` |

Cores: `w u b r g c` (c = incolor, m = multi). Nomes de guilda e shard também
valem: `c:azorius`, `id:esper`.

## Tipo, texto, nome

| quero | query |
|---|---|
| criatura | `t:creature` |
| vampiro lendário | `t:legendary t:vampire` |
| texto oracle contém | `o:"draw a card"` |
| texto com o nome da carta | `o:~` (`~` = nome da própria carta) |
| texto por regex | `o:/^{T}:/` |
| nome contém | `name:bolt` ou só `bolt` |
| nome exato | `!"Lightning Bolt"` |
| palavra-chave | `kw:haste`, `kw:flying` |
| tipo de carta em lote | `t:instant or t:sorcery` |

## Custo e stats

| quero | query |
|---|---|
| valor de mana ≤ 3 | `mv<=3` (`cmc` ainda funciona) |
| custo exato | `m:{2}{R}` ou `mana:2R` |
| custo contém híbrido | `m:{r/g}` |
| poder ≥ 4 | `pow>=4`; resistência `tou`; lealdade `loy` |
| poder maior que resistência | `pow>tou` |
| sem custo de mana | `m:0` com `-t:land` |

## Formato, raridade, edição

| quero | query |
|---|---|
| legal em Commander | `f:commander` (banida: `banned:commander`) |
| legal em Pauper EDH | `f:paupercommander` |
| raridade | `r:common`, `r>=rare` |
| da edição | `s:m11` / `e:m11`; bloco `b:zendikar` |
| lançada depois de | `date>=2024-01-01` ou `year>=2024` |
| só primeira impressão | `is:firstprint`; reimpressão `is:reprint` |
| só em papel | `-is:digital` |
| promo / variante | `is:promo`, `-is:promo`, `unique:prints` |

Nomes de formato: `standard pioneer modern legacy vintage pauper commander
paupercommander brawl standardbrawl oathbreaker predh premodern oldschool
alchemy historic timeless penny`.

## Preço e popularidade

| quero | query |
|---|---|
| até 2 dólares | `usd<=2`; `eur`, `tix` |
| ordenar por popularidade em EDH | `--ordem edhrec` (menor = mais jogada) |
| ordenar | `--ordem name\|cmc\|released\|usd\|eur\|rarity\|color\|power\|toughness\|set`, `--dir desc` |

## Propriedades (`is:`)

`is:commander` (pode ser comandante), `is:partner`, `is:dfc`, `is:mdfc`,
`is:split`, `is:adventure`, `is:spell`, `is:permanent`, `is:vanilla`,
`is:historic`, `is:hybrid`, `is:phyrexian`, `is:funny` (Un-sets; exclua com
`-is:funny`), `is:reserved`, `is:fullart`, `is:foil`, `is:nonfoil`.

## Receitas

```bash
S=skills/scryfall-cartas/scripts/scryfall.py
# vampiros que cabem em Edgar Markov, até 3 de mana, ordenados por uso em EDH
python3 $S busca 'id<=rwb t:vampire mv<=3 f:commander' --ordem edhrec --limite 40
# remoção instantânea barata em preto, legal em Commander, sem Un-sets
python3 $S busca 'c:b t:instant o:destroy o:creature mv<=2 f:commander -is:funny'
# criaturas com "whenever another creature you control dies"
python3 $S busca 'o:"whenever another creature you control dies" t:creature'
# tudo da edição, inclusive variantes
python3 $S busca 's:dsc' --unique prints --todas
# comandantes possíveis com identidade exatamente Boros
python3 $S busca 'is:commander id=rw' --ordem edhrec
```
