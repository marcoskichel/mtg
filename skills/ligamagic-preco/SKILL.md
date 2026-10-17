---
name: ligamagic-preco
description: Use quando alguém perguntar quanto custa uma carta de Magic, o preço em real de um card, quanto sai um deck, cotação na LigaMagic, "vale a pena comprar", orçamento de decklist, preço foil, preço por edição, ou mandar uma lista de cartas querendo saber o valor — inclusive quando o pedido não cita a LigaMagic pelo nome.
---

# Preço de carta e de deck na LigaMagic

A Liga não tem API pública. O que existe é o `getEditions.php`, o mesmo endpoint
que a página da carta chama para montar a tabela de edições. Ele responde sem
autenticação e devolve texto limpo — ao contrário dos anúncios individuais das
lojas, que vêm com os dígitos ofuscados em sprite CSS de propósito.

Preço é em **BRL**, do marketplace da Liga (lojas parceiras), não de Cardmarket
nem TCGplayer. É preço de anúncio, não de venda concluída.

## Fluxo

```bash
# carta avulsa: agregado + tabela por edição, normal e foil
python3 scripts/ligapreco.py "Lightning Bolt"
python3 scripts/ligapreco.py "Raio" "Anel Solar"     # aceita português

# decklist inteira: custo total, edição mais barata por carta
python3 scripts/ligapreco.py -d deck.txt
cat lista.txt | python3 scripts/ligapreco.py -d -
```

A entrada do `-d` pode ser qualquer coisa: export do Arena com set code, Moxfield
com cabeçalho, MWS com `SB:`, XML do Cockatrice, nomes em português ou lista solta
colada pelo usuário. O parser detecta a forma sozinho.

| Flag | Quando usar |
|---|---|
| `--preco menor` \| `medio` \| `maior` | Padrão `menor`. `medio` é a média dos anúncios daquela edição |
| `--foil` | Precifica em foil em vez de normal |
| `--incluir-nao-sancionadas` | Deixa World Championship, Collector's Edition e 30th Anniversary entrarem como opção mais barata |
| `--ttl 6` | Preço mais fresco que as 24h padrão |
| `--delay 2` | Deck grande sem cache; ver "Ritmo" |
| `--json` | Saída para outro script consumir |
| `--top 20` | Quantas linhas mais caras listar no relatório |

Quando a pergunta é "vale a pena?" ou pede um substituto mais barato, leia o
texto oracle das cartas envolvidas na API da Scryfall antes de opinar (regra e
comandos em `AGENTS.md`). O preço diz o que a carta custa, não o que ela faz.

O total sai no stdout junto da tabela por seção; o relatório vai no **stderr** e é
a parte que precisa chegar ao usuário — é onde estão as cartas sem estoque, as não
resolvidas e as mais caras. Código de saída 1 quando alguma carta ficou sem preço
por nome não resolvido ou por falha de rede; nos dois casos o total está baixo.

## `0.00` significa sem estoque, não grátis

Esta é a armadilha central. A Liga devolve `"0.00"` em todo campo de preço que não
tem anúncio ativo. Somar isso como zero faz um deck de R$ 3.000 aparecer como
R$ 1.800 sem nenhum aviso — e o número parece plausível, que é o pior tipo de erro.

O script trata `0.00` como ausente em todos os níveis: escolhe a edição mais barata
**entre as que têm estoque**, deixa a carta fora do total quando nenhuma tem, e
marca o total como `TOTAL INCOMPLETO` listando o que ficou de fora. Quando ler o
relatório, diga ao usuário que o custo real é maior, não que a carta é barata.

Os campos são independentes: existe edição com `precoMenor` e `precoMaior` válidos
e `precoMedio` em `0.00`. Filtrar a linha inteira porque um campo zerou também
estaria errado.

## Nome tem que ser resolvido antes de pedir preço

`getEditions.php` só aceita a grafia exata da Liga. Nome que ela não reconhece
volta `{"error":"2"}` — não uma lista vazia, não um preço zero. Um deck do Moxfield
traz `Delver of Secrets // Insectile Aberration`, que na Liga é `Delver of Secrets`;
sem resolver, some do total calado.

Por isso o script passa cada nome pelo índice de busca da Liga antes, com fallback
para a face frontal. É a mesma regra da skill `ligamagic-deck` e o cache de nomes é
o mesmo arquivo, então rodar as duas no mesmo deck sai quase de graça na segunda.

`//` some em carta de transformação e fica em split (`Fire // Ice`) e adventure
(`Brazen Borrower // Petty Theft`) — não dá para decidir por regra sintática.

## Qual preço usar

O `getEditions.php` devolve **duas coisas que não batem**: os agregados no topo da
resposta e a linha de cada edição. Elas divergem nos dois sentidos:

- **Force of Will** — agregado `normal_precoMenor` = R$ 315,00, mas a edição mais
  barata na lista é World Championship Decks a R$ 94,90. O agregado ignora
  impressões não sancionadas; a lista não.
- **Sol Ring** — agregado R$ 7,82, mas a edição mais barata da lista é R$ 8,09. O
  agregado enxerga anúncios que as linhas por edição não refletem.

O script usa a **edição mais barata com estoque** e diz qual é, porque um total de
deck precisa ser rastreável até uma carta comprável. O agregado aparece no modo
carta avulsa, para comparação.

Consequência disso: sem `--incluir-nao-sancionadas`, o script pula World
Championship Decks (borda dourada), Collector's Edition e International Collectors'
Edition (borda quadrada) e 30th Anniversary Edition (proxy oficial). Elas têm preço
real na Liga mas não são carta legal em torneio — um Force of Will de R$ 94,90 num
orçamento de Legacy é uma resposta errada.

## Armadilhas

**`--preco medio` não é o preço de mercado.** É a média dos anúncios da edição. Para
Lightning Bolt o agregado médio é R$ 87,22, puxado por Alpha e Secret Lair. Serve
para comparar edições entre si, não para orçar deck. Para orçamento, `menor`.

**Maybeboard fica fora do total.** É lista de consideração, não deck. Sai numa seção
própria da tabela e não entra na soma.

**Linhas repetidas são somadas** dentro da mesma seção; a mesma carta em main e
sideboard consome **uma** consulta só, mas aparece nas duas linhas.

**Preço envelhece.** Cache de preços em `~/.cache/ligamagic/prices.json` com TTL de
24h por padrão (`--ttl`). O cache de nomes, em `~/.cache/ligamagic/cardnames.json`,
não tem TTL — nome não muda. Se o usuário está decidindo uma compra agora, use
`--ttl 1` ou `--ttl 0` e diga que os números foram buscados na hora.

**Ritmo.** Uma consulta por carta única, com pausa de 0.8s entre as não cacheadas.
Passado umas dezenas de consultas seguidas o Cloudflare da Liga devolve **429 com
`Retry-After: 10`** — o script honra o cabeçalho e tenta de novo (4 tentativas),
mas um deck de Commander sem cache leva minutos. Não rode vários decks em rajada com
`--no-cache`; o `robots.txt` pede `Crawl-delay: 360` para crawler.

**Falha de rede não é carta inexistente.** O relatório separa as duas: `NAO
RESOLVIDAS` é nome que a Liga não conhece, `FALHA DE REDE` é para rodar de novo com
`--delay` maior. Não diga ao usuário que a carta não existe quando foi 429.

## Metadados do site

Esquema completo da resposta do `getEditions.php`, divergências medidas e siglas
não sancionadas estão em `references/precos.md`. IDs de formato, seções, tipos de
export e os outros endpoints internos estão em
`../ligamagic-deck/references/liga-metadata.md`.
