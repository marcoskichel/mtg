---
name: scryfall-cartas
description: Use quando precisar do texto oracle, custo, tipo, legalidade ou rulings de uma carta de Magic, quando for avaliar ou montar um deck e precisar ler as cartas, quando alguém perguntar "o que faz a carta X", "quais cartas existem que...", "em que edições saiu", ou quando a pergunta envolver sintaxe de busca da Scryfall (c: t: o: mv: f:). Inclusive quando o pedido não cita a Scryfall e vem com nome em português.
---

# Cartas de Magic pela Scryfall

Memória de carta é hipótese; a resposta da API é o fato. Antes de opinar sobre
regra, sinergia, substituto ou montagem de deck, busque as cartas envolvidas e
leia o texto que voltou.

## Fluxo

```bash
S=skills/scryfall-cartas/scripts/scryfall.py

# texto oracle, uma ou várias cartas (EN ou PT, "A // B" aceito)
python3 $S carta "Brash Taunter" "Raio" "Delver of Secrets"
python3 $S carta -d deck.txt            # decklist inteira, em lote
python3 $S carta "Edgar Markov" --formatos commander,modern --regras

# busca com a sintaxe da Scryfall
python3 $S busca "c:r t:creature mv<=1 f:commander kw:haste" --ordem cmc
python3 $S busca 'id<=wb o:"whenever a creature dies"' --todas

# todas as impressões, com preço em USD/EUR e imagem
python3 $S edicoes "Sol Ring" --sem-digital --sem-promo --imagem

# rulings
python3 $S regras "Brash Taunter"
```

`busca` mostra 50 cartas por padrão e diz o total no stderr; `--limite N` ou
`--todas` para ver o resto. `--json` em qualquer subcomando devolve os objetos
da Scryfall já enxugados para os campos úteis. `--help` em cada subcomando
lista as flags.

Sintaxe de busca completa em `references/sintaxe-busca.md`. Esquema das
respostas e falhas medidas em `references/api.md`.

## Leia o stderr

O stdout é a carta; o stderr é o que mudou no caminho e precisa chegar ao
usuário:

- `AVISO DA SCRYFALL`. A busca tinha uma expressão que a API não entendeu e
  ignorou em silêncio. `tipo:creature` vira nada, a busca fica mais ampla e
  devolve 1092 cartas em vez de 35, com HTTP 200. O script sai com código 1.
  Corrija a query e rode de novo; nunca apresente o resultado como se fosse o
  pedido.
- `Nomes ajustados`. O nome pedido virou outro, por tradução do português, face
  frontal de carta dupla ou fuzzy por erro de grafia. Confirme que é a carta
  que o usuário quis.
- `NÃO ENCONTRADA`. Nome que nada resolveu. Pergunte ao usuário, não chute.
  Quando o fuzzy devolveu uma carta que não parece com o pedido, o script
  rejeita e diz qual foi.

Código de saída 1 em qualquer desses casos.

## Carta dupla, split e adventure

`oracle_text`, `mana_cost` e `power` do objeto principal vêm `null`; o texto
está em `card_faces[]`. O script imprime cada face com `==`. Ao raciocinar
sobre a carta, use o texto da face: Delver of Secrets é 1/1 na frente e 3/2
voadora atrás, não "null/null".

## Nome em português

`/cards/collection` só aceita inglês exato. O script resolve o que sobrar por
busca exata no nome impresso em português (`!"Raio" lang:pt`) e só depois
tenta fuzzy. Nessa ordem, porque o fuzzy da Scryfall devolve qualquer carta
para nome curto ("Raio" vira Samurai of the Pale Curtain). A impressão que volta
nesse caso é a em português; o `oracle_text` continua em inglês.

## O que a Scryfall não dá

- **Preço em real.** `prices` é `usd`, `eur`, `tix`. Preço na LigaMagic é a
  skill `ligamagic-preco`.
- **Imagem baixada.** `--imagem` imprime a URL; baixar é outra chamada.

## Ritmo e cabeçalhos

Scryfall exige `User-Agent` e `Accept` (sem eles, HTTP 400) e pede no máximo
10 req/s. O script manda os dois, espaça 0,1 s entre chamadas e honra
`Retry-After` em 429. Uma decklist de Commander vai em 2 chamadas
(`/cards/collection` aceita 75 nomes); não faça uma chamada `named` por carta.
