# MTG workspace

Commander deck tooling. Each skill under `skills/` owns one job: `scryfall-cartas` reads cards (text, search, printings, rulings), `ligamagic-preco` prices them in BRL, `moxfield-deck` keeps a local decklist as source of truth and syncs it to moxfield.com.

## Card text comes from the API, never from memory

Before answering a rules question, researching cards, or assembling or editing a deck, fetch every card involved and read `oracle_text`, `type_line`, `mana_cost`, `power`/`toughness` and `legalities` from the response. Memory of a card is a hypothesis; the response is the fact. Reason only from text you just fetched.

```bash
python3 skills/scryfall-cartas/scripts/scryfall.py carta "Brash Taunter" "Edgar Markov"
python3 skills/scryfall-cartas/scripts/scryfall.py carta -d deck.txt
```

The script batches a decklist, handles double-faced cards and Portuguese names, and prints renames and misses to stderr. Read `skills/scryfall-cartas/SKILL.md` before searching with Scryfall syntax — an unknown keyword is silently dropped, not rejected.
