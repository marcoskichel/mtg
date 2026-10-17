# Scryfall search syntax

Official reference: https://scryfall.com/docs/syntax. Keywords are in
English; **an unknown keyword is silently ignored** (see `api.md`), so
`tipo:`, `cor:`, `custo:` don't exist. Use the ones in the tables.

Space-separated terms are AND. `or` between terms, `-` negates, parentheses
group. Text with spaces goes in quotes.

## Color and identity

| want | query |
|---|---|
| red cards | `c:r` |
| exactly blue and black | `c=ub` |
| blue or black, mono | `c:u or c:b` with `c=1`... use `c<=ub c>=1` |
| colorless | `c:c` |
| multicolor | `c:m` |
| Mardu commander identity | `id<=rwb` (fits the deck) |
| identity exactly Rakdos | `id=br` |

Colors: `w u b r g c` (c = colorless, m = multi). Guild and shard names also
work: `c:azorius`, `id:esper`.

## Type, text, name

| want | query |
|---|---|
| creature | `t:creature` |
| legendary vampire | `t:legendary t:vampire` |
| oracle text contains | `o:"draw a card"` |
| text with the card's own name | `o:~` (`~` = the card's own name) |
| text by regex | `o:/^{T}:/` |
| name contains | `name:bolt` or just `bolt` |
| exact name | `!"Lightning Bolt"` |
| keyword | `kw:haste`, `kw:flying` |
| several card types | `t:instant or t:sorcery` |

## Cost and stats

| want | query |
|---|---|
| mana value ≤ 3 | `mv<=3` (`cmc` still works) |
| exact cost | `m:{2}{R}` or `mana:2R` |
| cost contains hybrid | `m:{r/g}` |
| power ≥ 4 | `pow>=4`; toughness `tou`; loyalty `loy` |
| power greater than toughness | `pow>tou` |
| no mana cost | `m:0` with `-t:land` |

## Format, rarity, set

| want | query |
|---|---|
| legal in Commander | `f:commander` (banned: `banned:commander`) |
| legal in Pauper EDH | `f:paupercommander` |
| rarity | `r:common`, `r>=rare` |
| from set | `s:m11` / `e:m11`; block `b:zendikar` |
| released after | `date>=2024-01-01` or `year>=2024` |
| first printing only | `is:firstprint`; reprint `is:reprint` |
| paper only | `-is:digital` |
| promo / variant | `is:promo`, `-is:promo`, `unique:prints` |

Format names: `standard pioneer modern legacy vintage pauper commander
paupercommander brawl standardbrawl oathbreaker predh premodern oldschool
alchemy historic timeless penny`.

## Price and popularity

| want | query |
|---|---|
| up to 2 dollars | `usd<=2`; `eur`, `tix` |
| sort by EDH popularity | `--order edhrec` (lower = more played) |
| sort | `--order name\|cmc\|released\|usd\|eur\|rarity\|color\|power\|toughness\|set`, `--dir desc` |

## Properties (`is:`)

`is:commander` (can be a commander), `is:partner`, `is:dfc`, `is:mdfc`,
`is:split`, `is:adventure`, `is:spell`, `is:permanent`, `is:vanilla`,
`is:historic`, `is:hybrid`, `is:phyrexian`, `is:funny` (Un-sets; exclude with
`-is:funny`), `is:reserved`, `is:fullart`, `is:foil`, `is:nonfoil`.

## Recipes

```bash
S=skills/scryfall-cards/scripts/scryfall.py
# vampires that fit Edgar Markov, up to 3 mana, sorted by EDH usage
python3 $S search 'id<=rwb t:vampire mv<=3 f:commander' --order edhrec --limit 40
# cheap black instant removal, legal in Commander, no Un-sets
python3 $S search 'c:b t:instant o:destroy o:creature mv<=2 f:commander -is:funny'
# creatures with "whenever another creature you control dies"
python3 $S search 'o:"whenever another creature you control dies" t:creature'
# the whole set, variants included
python3 $S search 's:dsc' --unique prints --all
# possible commanders with identity exactly Boros
python3 $S search 'is:commander id=rw' --order edhrec
```
