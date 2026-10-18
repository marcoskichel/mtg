# Scryfall search syntax

Official reference: https://scryfall.com/docs/syntax. Keywords are in
English; **an unknown keyword is silently ignored** (see `api.md`), so
`tipo:`, `cor:`, `custo:` don't exist. Use the ones in the tables.
Everything here was checked against the live API on 2026-10-17.

Space-separated terms are AND. `or` between terms, `-` negates (`not:x` is
`-is:x`), parentheses group. Text with spaces goes in quotes.

## Color and identity

`c:` is the colors in the mana cost. `id:` is the color identity, which is what
Commander deck building checks. For a deck, use `id`.

| want | query |
|---|---|
| fits in a W/U deck (includes mono and colorless) | `id<=wu`, same as `commander:wu` |
| identity exactly W/U | `id=wu` |
| at least red and green, maybe more | `c>=rg` (`c:rg` is the same) |
| exactly white and black | `c=wb` |
| exactly two colors, any | `c=2` |
| colorless | `c:c`; colorless identity `id:c` |
| multicolor | `c:m` |
| has hybrid mana | `is:hybrid`, or one symbol `m:{w/b}` |

Colors are `w u b r g`. Every group nickname works with both keywords: guilds
(`azorius`, `orzhov`...), shards (`esper`, `bant`...), wedges (`mardu`,
`abzan`...), colleges (`quandrix`, `silverquill`...), and the four-color names
`chaos`, `aggression`, `altruism`, `growth`, `artifice`.

`c:wb t:creature` gives 436 cards, `c=wb` 239 and `id=wb` 273. The last two
differ because identity also counts mana symbols in the rules text and
hybrid costs.

## Commanders and Commander format

| want | query |
|---|---|
| commanders with identity exactly W/U | `is:commander id=wu f:commander` |
| commanders whose identity fits W/U | `is:commander id<=wu f:commander` |
| any partner mechanic | `is:partner` |
| "Partner with" pairs | `is:commander o:"partner with"` |
| Friends forever, Doctor's companion | `is:partner o:"friends forever"`, `is:partner o:"doctor's companion"` |
| Backgrounds / commanders that take one | `t:background`, `o:"choose a background"` |
| companions | `is:companion` |
| legal in Commander / banned | `f:commander` / `banned:commander` |
| Game Changers (brackets) | `is:gamechanger`; exclude with `-is:gamechanger` |
| popularity on EDHREC | `edhrec<=500` (1 = most played, basics excluded) |
| Duel Commander | `f:duel`, commanders `is:duelcommander` |
| Brawl, Oathbreaker, pre-2020 EDH | `is:brawler`, `is:oathbreaker`, `f:predh` |

- `is:commander` covers legendary creatures, cards that say "can be your
  commander", and Backgrounds. The 30 Backgrounds only work beside a commander
  that says "choose a background", so drop them with `-t:background` when
  you need a commander that stands alone.
- Keep `f:commander` next to `is:commander`. Without it, `is:commander id=wu`
  returns 10 cards that can't be played in Commander.
- `is:partner` matches every flavor: Partner, Partner with, Friends forever,
  Doctor's companion and Backgrounds. Read the text to see who pairs with whom.

## Type, text, name

| want | query |
|---|---|
| creature | `t:creature` (partial words work: `t:legend`) |
| legendary vampire | `t:legendary t:vampire` |
| oracle text contains | `o:"draw a card"` |
| text including reminder text | `fo:"enters tapped"` |
| text with the card's own name | `o:"~ enters tapped"` (`~` = the card's own name) |
| text by regex | `o:/^{T}: Add/` (works on `o:`, `t:`, `name:`, `ft:`) |
| keyword ability | `kw:lifelink`, `kw:flying` |
| cards that mention a type but aren't one | `o:vampire -t:vampire` |
| name contains | `name:bolt` or just `bolt` |
| exact name | `!"Lightning Bolt"` |
| several card types | `t:instant or t:sorcery` |
| cast as spell / permanent | `is:spell`, `is:permanent` |
| modal spells, vanilla creatures, manlands | `is:modal`, `is:vanilla`, `is:manland` |
| double-faced, split, adventure | `is:dfc`, `is:mdfc`, `is:split`, `is:adventure` |
| outlaws, party | `is:outlaw`, `is:party` |
| oracle tag (what the card does) | `otag:ramp`. Use the `card-finder` skill, which checks tag names |

## Cost and stats

| want | query |
|---|---|
| mana value ≤ 3 | `mv<=3` (`cmc` still works); even/odd `manavalue:odd` |
| exact cost | `m:{2}{R}` or `mana:2R` |
| cost contains hybrid | `m:{r/g}` |
| devotion | `devotion:{b}{b}{b}` |
| produces mana | `produces:wb` (W and B, maybe more), `produces=wb` (exactly) |
| power ≥ 4 | `pow>=4`; toughness `tou`; loyalty `loy`; power+toughness `pt` |
| power greater than toughness | `pow>tou` |
| no mana cost | `m:0` with `-t:land` |

## Lands

`t:land id<=wb produces=wb` finds the W/B dual lands (36 cards). Named cycles:
`is:shockland`, `is:fetchland`, `is:dual`, `is:triome` (`is:tricycleland`),
`is:checkland`, `is:fastland`, `is:slowland`, `is:painland`, `is:filterland`,
`is:bounceland`, `is:gainland`, `is:scryland`, `is:surveilland`,
`is:pathway`, `is:bondland`, `is:canopyland`, `is:shadowland` (snarls),
`is:tangoland` (battle lands), `is:bikeland`, `is:storageland`,
`is:creatureland`. Combine them with `id<=` for the deck's colors.

## Format, rarity, set, release

| want | query |
|---|---|
| legal in Commander | `f:commander` (banned: `banned:commander`) |
| legal in Pauper EDH | `f:paupercommander` |
| rarity | `r:common`, `r>=rare`; ever printed at rare `in:rare` |
| from set | `s:m11` / `e:m11`; block `b:zendikar`; set family `g:fin` |
| printed in a product type | `st:commander`, `st:masters` |
| released after | `date>=2024-01-01`, `year>=2024`, `date>ori` |
| not released yet | `date>now` |
| new in a set | `e:c16 not:reprint` |
| paper only | `game:paper` (or `-is:digital`); Arena `game:arena` |
| no Universes Beyond | `not:universesbeyond` |
| Reserved List | `is:reserved` |
| in a cube list | `cube:vintage` |
| art, artist, flavor | `art:dragon`, `a:magali`, `ft:kjeldoran`; lore in any field `lore:jhoira` |
| promo / variant | `is:promo`, `-is:promo`, `is:fullart`, `unique:prints` |
| silly cards | `is:funny`; exclude with `-is:funny` |

Format names: `standard future pioneer modern legacy vintage pauper commander
paupercommander duel brawl standardbrawl oathbreaker predh premodern oldschool
alchemy historic timeless gladiator penny tlr`.

**Printing keywords match if any printing matches.** `usd`, `game:`, `s:`,
`r:`, `date`/`year`, `is:promo`, `is:fullart` and `is:universesbeyond` describe
a printing, and a card passes when one of its printings does.
`not:universesbeyond` keeps every card with at least one non-UB printing,
which is the right filter for "no Universes Beyond": it drops Cid, Timeless
Artificer and keeps Sol Ring. `is:universesbeyond` flags Sol Ring, Brago and
Grand Arbiter Augustin IV, because each has a Secret Lair or UB-set reprint.
It doesn't mean "a UB character".

`date>now` matches about 770 printings from sets that haven't released yet,
and many already show `commander: legal`. When a result's `released_at` is in
the future, say so: the card isn't in stores yet.

## Price and popularity

| want | query |
|---|---|
| up to 2 dollars | `usd<2`; `eur`, `tix` |
| show the cheapest printing | `cheapest:usd` |
| sort by EDH popularity | `--order edhrec` (lower = more played) |
| sort | `--order name\|cmc\|released\|usd\|eur\|rarity\|color\|power\|toughness\|set`, `--dir desc` |

`usd<2` keeps a card if **any** printing is under $2. The printing it shows is
one that matches, not always the cheapest. Kodama's Reach comes back at $1.88
when its cheapest printing is $1.55. Sol Ring fails `usd<1` because its
cheapest printing is $1.25. Prices are Scryfall's daily USD estimate. BRL
prices come from `ligamagic-preco`.

## Display keywords

`order:usd`, `direction:desc`, `unique:prints` and `prefer:oldest` can go
inside the query. A keyword in the query wins over the `--order` flag:
`find 'is:gamechanger order:usd direction:desc'` sorts by price even though
`find` defaults to `--order edhrec`.

## Advanced search form → syntax

The form at scryfall.com/advanced only builds a query string. Each field maps
to a keyword:

| form field | keyword |
|---|---|
| Card Name | `name:` |
| Text | `o:` |
| Type Line (IS / NOT) | `t:` / `-t:` |
| Colors (exactly / including / at most) | `c=` / `c>=` / `c<=` |
| Commander | `id<=` (`commander:`) |
| Mana Cost | `m:` |
| Stats | `mv`, `pow`, `tou`, `loy`, `pt` with `= < > <= >= !=` |
| Games | `game:paper`, `game:arena`, `game:mtgo` |
| Formats (Legal / Banned / Restricted) | `f:` / `banned:` / `restricted:` |
| Sets, Blocks | `s:`, `b:` |
| Rarity | `r:` |
| Criteria | `is:` (see the lists above) |
| Prices | `usd`, `eur`, `tix` |
| Artist | `a:` |
| Flavor Text | `ft:` |
| Lore Finder | `lore:` |
| Language | `lang:` (`lang:any` for every language) |

## Recipes

```bash
S=$SKILLS/scryfall-cards/scripts/scryfall.py
# vampires that fit Edgar Markov, up to 3 mana, sorted by EDH usage
python3 $S search 'id<=rwb t:vampire mv<=3 f:commander' --order edhrec --limit 40
# commanders with identity exactly Orzhov, paper only, no Backgrounds
python3 $S search 'is:commander id=wb f:commander game:paper -t:background' --order edhrec
# partner commanders that fit a Mardu deck
python3 $S search 'is:partner id<=rwb f:commander' --order edhrec
# Game Changers a Mardu deck could play (bracket check)
python3 $S search 'is:gamechanger id<=rwb'
# W/B dual lands, cheapest printing under $5
python3 $S search 't:land id<=wb produces=wb f:commander usd<5 cheapest:usd'
# cheap black instant removal, legal in Commander, no Un-sets
python3 $S search 'c:b t:instant o:destroy o:creature mv<=2 f:commander -is:funny'
# cards that care about vampires without being one
python3 $S search 'o:vampire -t:vampire id<=rwb f:commander'
# creatures with "whenever another creature you control dies"
python3 $S search 'o:"whenever another creature you control dies" t:creature'
# what's new: cards first printed this year that fit the deck
python3 $S search 'year>=2026 not:reprint id<=wb f:commander' --order edhrec
# the whole set, variants included
python3 $S search 's:dsc' --unique prints --all
```
