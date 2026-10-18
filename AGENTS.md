# MTG workspace

Commander deck tooling. Each skill under `skills/` owns one job: `scryfall-cards` reads cards (text, search, printings, rulings), `card-finder` finds cards by what they do (Scryfall oracle tags, every result checked against its text), `ligamagic-preco` prices them in BRL, `moxfield-deck` keeps a local decklist as source of truth and syncs it to moxfield.com, `card-picker` puts cards in front of the user in the browser so they pick and the answer returns as JSON.

## Card text comes from the API, never from memory

Before answering a rules question, researching cards, or assembling or editing a deck, fetch every card involved and read `oracle_text`, `type_line`, `mana_cost`, `power`/`toughness` and `legalities` from the response. Memory of a card is a hypothesis; the response is the fact. Reason only from text you just fetched.

```bash
python3 skills/scryfall-cards/scripts/scryfall.py card "Brash Taunter" "Edgar Markov"
python3 skills/scryfall-cards/scripts/scryfall.py card -d deck.txt
```

The script batches a decklist, handles double-faced cards and Portuguese names, and prints renames and misses to stderr. Read `skills/scryfall-cards/SKILL.md` before searching with Scryfall syntax — an unknown keyword is silently dropped, not rejected.
