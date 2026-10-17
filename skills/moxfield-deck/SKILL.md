---
name: moxfield-deck
description: Use para criar, atualizar, baixar, validar ou sincronizar um deck no Moxfield (moxfield.com) — "sobe esse deck pro Moxfield", "importa minha lista do Moxfield", "o deck local bate com o do Moxfield?", "troca X por Y no deck e atualiza lá", link moxfield.com/decks/..., Bulk Edit, tags do Moxfield, checar se o deck de Commander é legal (100 cartas, identidade de cor, singleton, banidas, game changers) antes de publicar. Vale mesmo quando o pedido não cita o Moxfield mas envolve manter uma decklist que vive lá.
compatibility: Python 3 (stdlib). Leitura precisa de internet (api2.moxfield.com, api.scryfall.com). Escrita precisa do Claude in Chrome com moxfield.com liberado nas permissões da extensão e sessão logada.
metadata:
  author: kichelm
  version: "0.1"
---

# Deck no Moxfield

O Moxfield nao tem API publica. Leitura sai pelo mesmo endpoint JSON que o site
usa (`api2.moxfield.com`), que responde a `curl` com User-Agent de navegador.
Escrita so existe pelo site, logado — o script prepara o texto e o Claude in
Chrome cola no **Bulk Edit**.

Por isso a fonte da verdade e o **arquivo local**, versionado em git. O Moxfield e
a vitrine: playtest, preco, compartilhar. Toda mudanca comeca no arquivo, passa
por `validar`, vai para o site, e termina com `diff` confirmando que o site ficou
igual ao arquivo.

## Fluxo

```bash
S=skills/moxfield-deck/scripts/moxfield.py

# 1. trazer um deck existente (publico ou unlisted) para o repo
python3 $S baixar https://moxfield.com/decks/<id> -o decks/markov-gang.txt

# 2. editar o arquivo (ou criar do zero, formato abaixo)

# 3. validar: nomes na Scryfall, 100 cartas, identidade de cor, singleton,
#    banidas, game changers. Exit 1 = algum ERRO, nao siga. Exit 0 com a palavra
#    `ok` = limpo; exit 0 com so AVISO = passou, mas leia os avisos e repasse-os.
python3 $S validar decks/markov-gang.txt

# 4. gerar o bloco de um board e colar no Bulk Edit (ver secao Navegador)
python3 $S exportar decks/markov-gang.txt --board mainboard --copiar

# 5. conferir que o site ficou igual ao arquivo. Exit 0 = igual.
python3 $S diff decks/markov-gang.txt <id>
```

Deck novo: crie o arquivo, `validar`, crie o deck vazio no site, cole o
`publicId` em `// Moxfield:`, cole os boards, `diff`.

Troca de carta pedida pelo usuario ("tira X, poe Y"): leia o oracle das duas na
Scryfall antes de opinar (skill `scryfall-cartas`; regra do `AGENTS.md`), edite o
arquivo, `validar`,
depois o site. Nao edite no site primeiro — o arquivo e que e versionado.

## Formato do arquivo local

E a sintaxe do Bulk Edit do Moxfield mais cabecalhos de secao, entao o que
`baixar` grava e o que `exportar` cola sao o mesmo texto:

```
// Moxfield: https://moxfield.com/decks/<publicId>
// Nome: Markov Gang
// Formato: commander
// Bracket: 3

// Commander
1 Olivia, Opulent Outlaw (OTJ) 229 *F*

// Mainboard
1 Edgar Markov (C17) 36 #cmd-alternativo #vampiro
1 Sol Ring (CMM) 410 #ramp
8 Swamp

// Sideboard
// Maybeboard
1 Bloodghast #vampiro
```

- `qtd nome (SET) numero *F* *A* #tag #!tagGlobal` — tudo depois do nome e
  opcional e a ordem nao importa. Set e numero fixam a impressao; sem eles o
  Moxfield escolhe. Tag com espaco nao existe: `#ramp-rapido`.
- Cabecalhos aceitos: `// Commander`, `// Mainboard`, `// Sideboard`,
  `// Maybeboard`, `// Companion`, com ou sem `//`, em portugues tambem
  (`Comandante`, `Reserva`, `Considerando`). Sem nenhum cabecalho tudo vai para
  Mainboard e o script avisa — e assim que o Export do site chega.
- `// Chave: valor` no topo e metadado livre; `Moxfield` e `Formato` sao os que o
  script le. Comentario que nao tem `:` e ignorado.
- Total de 100 = Commander + Companion + Mainboard. Sideboard e Maybeboard nao
  contam.

## Navegador

Antes de abrir o site: `tabs_context_mcp`. Se `navigate` para moxfield.com
devolver "This site is blocked by your site permissions", pare e peca ao usuario
para liberar `moxfield.com` na extensao Claude in Chrome — nao ha contorno.
Playwright headless nao serve: o deck e da conta do usuario e precisa da sessao
logada que so existe no Chrome dele.

Passo a passo dos controles (New Deck, Bulk Edit por board, Save, Export) e a
forma de colar 100 linhas sem digitar uma a uma estao em
`references/bulk-edit.md`. Leia antes do primeiro clique. Ache botoes por texto
com `find`; nao chute coordenadas.

Depois de **Save**, rode `diff`. O Moxfield descarta linha que nao reconhece sem
avisar, entao "salvou" nao quer dizer "entrou".

## Armadilhas

**Bulk Edit nao remove tag.** Apagar `#tag` da linha e salvar deixa a tag la. Para
tirar, e na Table View (shift-click → Manage Tags). O `diff` mostra `tags [...] ->
[...]` ate voce fazer isso.

**Comandante na caixa errada vira 101 cartas.** Ele tem caixa propria no Bulk
Edit. `validar` ja reclama se o arquivo nao tem `// Commander`.

**Deck privado da 404 em `baixar` e `diff`.** O api2 so entrega public e unlisted.
Para deck seu, deixe-o unlisted enquanto trabalha; ninguem acha unlisted sem o
link. Se tiver que ficar privado, use Export → Text no site e acrescente os
cabecalhos de secao na mao.

**403 do Cloudflare.** Acontece se o User-Agent nao parecer navegador ou em
rajada. O script ja manda UA de Chrome; se mesmo assim der 403, espere um minuto.
Nao rode `baixar` em loop sobre muitos decks.

**Nome dupla-face.** O Moxfield grava `Delver of Secrets // Insectile Aberration`;
a Scryfall `/cards/collection` nao acha esse nome. O script tenta a face frontal
sozinho. Se `validar` disser que resolveu como outro nome, confira — pode ser typo
corrigido pelo fuzzy, pode ser carta errada.

**`validar` conhece Commander, nao os outros formatos a fundo.** Para `Formato:`
diferente de commander ele checa so nomes e legalidade; tamanho de deck e
singleton ficam por sua conta.

**Game changers e bracket.** `validar` lista os game changers do deck (campo
`game_changer` da Scryfall). Bracket 3 aceita ate 3; o deck do usuario mira
bracket 3–4 e nao quer combo infinito — isso o script nao detecta, voce precisa
ler as cartas.

**Preco em BRL e assunto da `ligamagic-preco`**; o JSON do Moxfield traz USD/EUR.
Para espelhar o mesmo arquivo na LigaMagic, `ligamagic-deck` le este formato
(cabecalhos e tags inclusos).

## Testes

```bash
python3 -m unittest discover -s skills/moxfield-deck/tests
```

Forma do JSON do api2, chamadas medidas e o que muda entre public/unlisted/private
estao em `references/api.md` — leia quando `baixar --json` for necessario ou algo
no JSON nao bater com o esperado.
