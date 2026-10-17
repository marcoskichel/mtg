# Bulk Edit e import no Moxfield

## Sintaxe de linha

Vale no Bulk Edit, no "Paste in List" do deck novo e no `exportar` do script:

```
<qtd> <nome> (<SET>) <numero> *F* *A* #tag #!tagGlobal
1 Sol Ring (CMM) 410 *F* #ramp
1 Olivia, Opulent Outlaw
```

- Set e numero de colecionador sao opcionais; sem eles o Moxfield escolhe uma
  impressao padrao (a mais recente nao-promo).
- `*F*` foil, `*A*` alterada. `*E*` (etched) o script tambem le.
- `#tag` e tag do deck; `#!tag` e tag global da conta. Tag nao pode ter espaco —
  use `#ramp-rapido`.
- Nome com `//` funciona (`Fire // Ice`, `Delver of Secrets // Insectile Aberration`).
- Linha que o Moxfield nao reconhece e **descartada em silencio** ao salvar; a
  carta some sem aviso. Por isso o fluxo termina sempre com `diff`.
- **Bulk Edit adiciona tag mas nao remove.** Tirar `#tag` da linha e salvar deixa a
  tag como estava. Para remover: Table View, shift-click na carta, "Manage Tags".

Prefixos aceitos no import de texto (nao no Bulk Edit, que tem uma caixa por board):
`sideboard:` / `side:` / `sb:` manda a linha para o sideboard; `maybe:` /
`maybeboard:` / `consider:` / `considering:` para o maybeboard. Nao ha prefixo de
comandante no import — o comandante e escolhido depois, na pagina do deck.

## Caminho no site (deck proprio, logado)

Documentado a partir das referencias publicas; o Claude in Chrome ainda nao abriu o
site logado para conferir, entao localize os controles pelo texto (`find`) em vez
de confiar em posicao.

**Criar deck**

1. `https://moxfield.com/decks/personal` → botao **New Deck** (ou `/decks/new`).
2. Formulario: **Name**, **Format** (Commander / EDH), **Visibility**
   (Public / Unlisted / Private). Deixe Unlisted ate o deck estar validado — assim
   `baixar`/`diff` funcionam e ninguem ve lista pela metade.
3. Salvar o deck vazio e **copiar o `publicId` da URL** para a linha
   `// Moxfield:` do arquivo local.

**Atualizar lista (Bulk Edit)**

1. Na pagina do deck, menu **More** (ou o lapis de edicao) → **Bulk Edit**.
2. O modal tem uma aba/caixa por board: Commander(s), Mainboard, Sideboard,
   Maybeboard (e outros que nao interessam). Cada caixa mostra o conteudo atual
   do board nessa mesma sintaxe.
3. Para cada board que mudou: `exportar deck.txt --board <board> --copiar`,
   selecionar tudo na caixa (ctrl+a) e colar. Colar via `type` do `computer` com
   100 linhas e lento; melhor `javascript_tool` setando `textarea.value` e
   disparando `new Event("input", {bubbles: true})` para o React enxergar.
4. **Save**. Cartas rejeitadas somem sem aviso.
5. `diff deck.txt <id>` ate dar `igual`.

O comandante tem que ir na caixa Commander. Na caixa Mainboard ele vira a 101a carta
e o Moxfield marca o deck como ilegal — `validar` pega isso antes de voce colar.

**Metadados** (bracket, descricao/primer, hubs, capa) ficam em **Edit deck
details**, nao no Bulk Edit. `baixar` traz `bracket` e `visibilidade` no cabecalho
do arquivo so para registro; o script nao os altera.

## Export do site

Menu **Export** na pagina do deck: Text / Arena / MTGO / CSV. O texto do Moxfield usa
a mesma sintaxe de linha acima, com os boards separados por linha em branco e sem
cabecalho — `parse_deck` trata isso como tudo-mainboard e avisa. Para deck proprio
privado, exporte por ai e adicione os cabecalhos `// Commander` / `// Mainboard` na
mao, ou torne o deck unlisted e use `baixar`.
