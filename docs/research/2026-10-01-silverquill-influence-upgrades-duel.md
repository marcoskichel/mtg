# TL;DR

- O precon é **Silverquill Influence**, do set *Secrets of Strixhaven Commander* (SOC), lançado em **2026-04-24** [Scryfall]. Shell: 37 terrenos, 26 encantamentos (22 deles Auras), apenas **4 artefatos de mana** e **3 remoções reais em instante/feitiço** (Anguished Unmaking, Fracture, Vanishing Verse) — [Scryfall], contagem conferida carta por carta contra a [lista oficial no EDHREC](https://edhrec.com/precon/silverquill-influence).
- Rode **Killian, Decisive Mentor** como comandante no multiplayer. É a conclusão explícita do [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/) ("I think Killian makes the better Commander for the deck") e a premissa de construção do [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade). O [CoolStuffInc](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck) é o único que relativiza ("If you decided to choose Scriv over Killian, the deck should still run well for you").
- O upgrade de maior retorno **não é mais payoff de Aura** — o shell já é ótimo nisso. Das cartas mais jogadas na [página do Killian no EDHREC](https://edhrec.com/commanders/killian-decisive-mentor) (10.925 decks), quase tudo já vem no precon; as duas grandes ausências são **Ethereal Armor (66%)** e **All That Glitters (63%)**. O resto do ganho está em **interação, remoção e rampa**.
- Os preços que circulam nos guias estão inflados. Pegando a impressão **mais barata** em vez da primeira listada: Light-Paws **$1.60** (NEO 25), Eye of Nidhogg **$0.54** (FIC 44), Mantle of the Ancients **$7.42** nonfoil (PIP 165), All That Glitters **$0.52** (CMM 622) [Scryfall].
- **Duel Commander hoje**: 20 pontos de vida, mulligan de Londres, **sem vitória por 21 de dano de comandante**, 100 cartas singleton — tudo verbatim nas [quickrules oficiais](https://www.duelcommander.org/rules/quickrules/). Banlist viva e atualizada em **2026-07-27** ([anúncio](https://www.duelcommander.org/announcements/2026/07/27/)).
- **Sol Ring é a única carta ilegal do precon** em Duel Commander — [banlist oficial](https://www.duelcommander.org/banlist/) + campo `duel: banned` [Scryfall]. Os 99 restantes e os seis comandantes alternativos voltaram `duel: legal`.
- **Goad em 1v1 força a criatura a atacar VOCÊ.** A ruling oficial do Killian (2026-03-20) diz: se não há outro jogador atacável, ela "must attack a planeswalker an opponent controls, a battle an opponent protects, **or the player that goaded it**" [Scryfall]. Deixa de ser escudo político e passa a ser "tira o bloqueador / força o ataque" — o que casa com Ghostly Prison, Nils e blocos de deathtouch.
- **Breena, the Demagogue é texto morto em 1v1** (precisa de "another of your opponents" para comparar vidas) [Scryfall]. Já a ficha Contract do Scriv fica **melhor**: o galho `+2/+0` é inalcançável em duelo, então o dono da criatura encantada **perde 2 de vida em todo ataque** — inferência de alta confiança a partir do templating, sem ruling oficial confirmando (as 2 rulings do Scriv tratam só de alvo ilegal) [Scryfall].

---

# 1. O precon como vem

Lista de referência: [EDHREC – Silverquill Influence](https://edhrec.com/precon/silverquill-influence). Censo conferido carta por carta via [Scryfall]; a matemática fecha em 100 (1 comandante + 25 criaturas + 4 artefatos + 3 instantes + 4 feitiços + 26 encantamentos + 37 terrenos), com 85 linhas únicas no mainboard.

| Categoria | Contagem | Observação |
|---|---|---|
| Terrenos | **37** (21 não-básicos + 8 Plains + 8 Swamp) | Maioria dos duais entra virado: Desolate Mire, Forum of Amity, Silverquill Campus, Sunlit Marsh, Temple of Silence, Umbral Expanse. Sem fixing premium além de Caves of Koilos e Fetid Heath. |
| Artefatos de mana | **4** (Sol Ring, Arcane Signet, Fellwar Stone, Talisman of Hierarchy) | Magro. |
| Encantamentos | **26**, dos quais **22 são Auras** | Os 4 não-Aura: Ghostly Prison, Land Tax, Forum Filibuster e Intermediate Chirography (que é *Enchantment — Class*). |
| Bestow | 1 (Eidolon of Countless Battles) | — |
| Payoffs de Aura | ~16 | Kor Spiritdancer, Sram, Pearl-Ear Imperial Advisor, Transcendent Envoy, Starfield Mystic, Herald of Amity, Hateful Eidolon, Eriette, Archon of Sun's Grace, Doomwake Giant, Ajani's Chosen, Armored Skyhunter etc. Redundância alta demais no eixo "saque ao conjurar encantamento". |
| Remoção pontual | **7, mas frágil** | Só 3 são instante/feitiço de verdade (Anguished Unmaking, Fracture, Vanishing Verse); as outras 4 são Auras de pseudo-remoção (Chains of Custody, Sheltered by Ghosts, Darksteel Mutation, Screams from Within) que se desfazem se a Aura sair — risco de 2-por-1. |
| Varredura | **1** (Winds of Rath, assimétrica) | — |
| Pacote de goad | **6** (Coercive / Ghoulish / Parasitic / Martial Impetus + Redemption Arc + gatilho de ETB do Killian) | Atenção: Coercive Impetus dá a carta **e você perde 1 de vida** [Scryfall] — detalhe que os guias omitem. |
| Seguro de Aura / recursão | 7 (Gift of Immortality, Shielded by Faith, Changing Loyalty, Screams from Within, Fallen Ideal, Ghoulish Impetus, Raffine's Guidance) | Força real do design: mitiga o 2-por-1 inerente a Auras. |

**Forças.** Densidade de Aura com recursão embutida; saque consistente (12 fontes de vantagem de carta, contando War Room e Land Tax); Winds of Rath como varredura que poupa justamente as suas criaturas encantadas; e um Killian que converte cada ataque encantado em carta.

**Fraquezas.** Rampa magra (4 artefatos), remoção dura quase inexistente, base de mana lenta (muitos duais virados num deck de 2 cores que quer curvar Auras nos turnos 2–4), e um pacote político (Mangara, Breena, Tomik, Combat Calligrapher, Nils, Keen Duelist, Secret Rendezvous) que o [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) descreve como tema que "doesn't gel with what the rest of the deck is doing".

**Qual comandante rodar.** Killian. O argumento mais limpo é o do [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/): "he doesn't have to put himself into harm's way to get his triggered ability" — o saque dispara independente de quem controla a criatura encantada. O [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) constrói tudo em torno dele e nota que Eriette era a opção Orzhov-Aura anterior, hoje mais fraca que Killian. Dado de uso real na [página do precon no EDHREC](https://edhrec.com/precon/silverquill-influence): Killian **6,4K** decks, **Eriette 551**, **Scriv 482**, Killian Ink Duelist 41, Breena 29, Shadrix 12 — ou seja, a comunidade prefere Eriette ao comandante secundário oficial, algo que nenhum guia comenta.

> Inconsistência interna do EDHREC que vale a ressalva: a página do precon marca Scriv com 482 decks, enquanto a [página do comandante](https://edhrec.com/commanders/scriv-the-obligator) reporta 2.161. Escopos/janelas diferentes; não trate nenhum dos dois como número absoluto.

---

# 2. Upgrades para multiplayer

## 2.1 Tabela consenso "Tira X / Põe Y"

Critério: corte com **≥2 guias verificados** concordando, ou troca que ataca uma fraqueza estrutural confirmada no §1. Ordenado por impacto.

| # | Tira | Põe | Por quê | ~USD (menor impressão) | Fontes |
|---|---|---|---|---|---|
| 1 | Raffine's Guidance | **Ethereal Armor** | Aura de 1 mana que escala com os 26 encantamentos; 66% de inclusão na página do Killian. Troca direta de uma Aura de 3 mana "extremely clunky". | $0.41 (DSK 7)* | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [EDHREC Killian](https://edhrec.com/commanders/killian-decisive-mentor) |
| 2 | Intermediate Chirography | **All That Glitters** | O corte mais consensual do precon (4 guias verificados). Entra o segundo pump escalável, 63% de inclusão. | **$0.52** (CMM 622) | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/) |
| 3 | Sentinel's Eyes | **Light-Paws, Emperor's Voice** | Busca e coloca uma Aura em jogo de graça a cada Aura conjurada — multiplicador direto de 22 Auras. Preço real é 7,8× menor que o anunciado nos guias. | **$1.60** (NEO 25) | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [EDHREC guide](https://edhrec.com/guides/silverquill-influence-precon-upgrade-guide), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) |
| 4 | Vanishing Verse | **Swords to Plowshares** | Ataca a fraqueza nº1: só 3 remoções reais. StP exila por 1 mana sem a restrição monocolorida do Verse. 58% na página do Scriv. | não reconferido | [EDHREC Scriv](https://edhrec.com/commanders/scriv-the-obligator), [Scryfall] |
| 5 | Ajani's Chosen | **Ondu Spiritdancer** | Copia a próxima Aura conjurada por turno. Dobra tudo que o deck já faz, em vez de um payoff de 4 manas desajeitado. | **$11.25** (CMM 723) | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Yahoo/GameDaily](https://tech.yahoo.com/gaming/articles/secrets-strixhaven-silverquill-influence-commander-234019760.html) |
| 6 | Shadrix Silverquill | **Mantle of the Ancients** | O MTGGoldfish chama de "single best aura, mass recursion and wincon". Sai o 5-drop político que 3 guias cortam. Nonfoil existe em 5 das 7 impressões — o "foil-only $20" que circula é falso. | **$7.42** (PIP 165) | [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) |
| 7 | Firemane Commando | **Retether** | "Poor man's Replenish": devolve todas as Auras do cemitério ao campo e re-dispara Killian. Caro mas é o melhor botão de recuperação do arquétipo. | **$14.39** (WOC 72) — é o piso | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) |
| 8 | Tomik, Wielder of Law | **Eye of Nidhogg** | Aura lendária de 2026 ({2}{B}, Final Fantasy Commander, 2025-06-13): transforma o alvo em Dragon 4/2 voador com deathtouch, goadeado, e volta pra mão quando morre. Dissuasor fraco sai, payoff de goad recorrente entra. | **$0.54** (FIC 44) | [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Yahoo/GameDaily](https://tech.yahoo.com/gaming/articles/secrets-strixhaven-silverquill-influence-commander-234019760.html), [Scryfall] |
| 9 | Breena, the Demagogue | **Hallowed Haunting** | "Way too much conditions for two counters and a card draw". Entra motor de fichas que escala com encantamento. | **$8.34** (SPG 64) — é o piso | [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/) |
| 10 | Keen Duelist | **Mesa Enchantress** | Redundância de saque confiável no lugar de um 3-drop que 3 guias cortam. | $1.04 (DSC 68)* | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/) |
| 11 | Combat Calligrapher | **Kaya's Ghostform** | Efeito estreito (só protege contra Inklings) e a ficha pode bloquear os seus próprios atacantes goadeados. Entra seguro de 1 mana pro alvo encantado. | $2.24 (PLST WAR-94)* | [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [CoolStuffInc review](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) |
| 12 | Chains of Custody | **Dimensional Exile** | Nova em 2026 (TMNT, 2026-03-06): O-Ring que encanta um **terreno básico** em vez da criatura — não dá 2-por-1 quando a criatura morre, ao contrário das 4 Auras-remoção do precon. | ~$0.21–0.30 (não reconferido) | [Scryfall] |
| 13 | Secret Rendezvous | **Phyrexian Arena** | Saque simétrico (3 pra você, 3 pro oponente) vira saque assimétrico recorrente. Corte com 3 guias. | $1.30 (FDC 123)* | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) |
| 14 | Armored Skyhunter | **Sigil of the Empty Throne** | O "once per attack" é lento demais: "the secret to Auras is that they want to cast multiple auras per turn and snowball fast, and this 'once per attack' thing doesn't cut it". | não reconferido | [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade), [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) |
| 15 | Nils, Discipline Enforcer | **Minimus Containment** | Aura-remoção flexível (vira qualquer permanente não-terreno em Treasure), pega artefatos e encantamentos que Darksteel Mutation não alcança. | não reconferido | [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) |
| 16 | Screams from Within | **Glasswing Grace** | MDFC WB: Aura quando você precisa, terreno quando não. Reduz as mortas sem mexer na contagem de terrenos. | $0.34 (MH3 254)* | [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) |
| 17 | Fallen Ideal | **Spirit Link** | Aura barata em criatura do oponente: ganha vida e dispara Killian quando ela ataca outro. | $0.33 (PLST 10E-45)* | [EDHREC guide](https://edhrec.com/guides/silverquill-influence-precon-upgrade-guide), [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) |
| 18 | Forum Filibuster | **Sphere of Safety** | Pillowfort que escala com 26 encantamentos. 56% na página do Scriv. **É branca**, não verde [Scryfall]. | não reconferido | [EDHREC Scriv](https://edhrec.com/commanders/scriv-the-obligator), [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) |
| 19 | Sage's Reverie | **Umbra Mystic** | Dá "umbra armor" às suas Auras — resolve diretamente a fragilidade estrutural de 2-por-1 das 4 Auras-remoção. | não reconferido | [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/), [Scryfall] |
| 20 | 1 Swamp | **Scoured Barrens** ou **Brightclimb Pathway // Grimclimb Pathway** | Básico sai por dual com upside; o Pathway entra **desvirado** escolhendo a cor. | ~$0.20 / ~$4.56–4.70 (não reconferido) | [Scryfall] |
| 21 | Study Hall | **Rogue's Passage** | Terreno de valor marginal sai por um que fecha jogo com a criatura voltron. | não reconferido | [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) |

\* Preço de **uma impressão representativa**, não necessariamente a mais barata — só os 8 valores em negrito passaram por uma varredura de mínimo entre todas as impressões.

### Dois cortes que eu não faria sem pensar

- **Eldrazi Conscription** e **Ghostly Prison** aparecem como cortes em [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/), [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) e [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) — 8 manas lento e tax defensivo que briga com o plano agressivo. O [CoolStuffInc review](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck) defende os dois: Conscription porque "Giving a Creature +10/+10, Trample, and Annihilator 2 should close out the game in short order", e Ghostly Prison como "a good way to lock players out of swinging out on you completely". É divergência **editorial**, não de fato. Em mesa de 4 com Sphere of Safety entrando, eu mantenho Ghostly Prison e corto Conscription.

## 2.2 Upgrades premium opcionais

Não entram na lista de 21 por preço ou por serem luxo, mas todos conferidos W/B-legais e `commander: legal` [Scryfall]:

| Carta | Função | ~USD |
|---|---|---|
| **Sigarda's Aid** | Auras em velocidade de flash — ataca em combate, protege em resposta à remoção | **$18.38** (CMR 384) |
| **Greater Auramancy** | Blinda suas criaturas encantadas; a melhor proteção do arquétipo | não reconferido |
| **Starfield of Nyx** | Recursão de encantamento por turno + anima tudo com 5+ | não reconferido |
| **Open the Vaults** | Reanimação em massa de artefatos/encantamentos | não reconferido |
| **Three Dreams** | Busca 3 Auras diferentes | não reconferido |
| **Sun Titan** | Recursão de permanentes CMC≤3. Curiosidade: **está impresso em SOC 178, mas não neste precon** [Scryfall] | não reconferido |
| **Danitha Capashen, Paragon** | Reduz custo de Aura/Equipamento, corpo relevante | não reconferido |
| **Weathered Wayfarer** | Tutor de terreno, casa com o Land Tax que já vem no deck | não reconferido |

**Não inclua Ephemerate** mesmo com 55% de inclusão na [página do Scriv](https://edhrec.com/commanders/scriv-the-obligator): piscar sua própria criatura encantada manda **todas** as Auras pro cemitério. Legal, mas anti-sinérgico aqui.

## 2.3 Cartas novas de 2025–2026 que encaixam

Datas de lançamento conferidas via Scryfall /sets [Scryfall]:

| Carta | Set / data | Veredito |
|---|---|---|
| **Eye of Nidhogg** {2}{B} | Final Fantasy Commander, 2025-06-13 | **Entra.** Goad + corpo 4/2 voador deathtouch + auto-recursão, $0.54. |
| **Dimensional Exile** {1}{W} | Teenage Mutant Ninja Turtles, 2026-03-06 | **Entra.** Única remoção-Aura do pool que não dá 2-por-1 (encanta terreno básico). |
| **Tempest Technique** {3}{W} | Tarkir: Dragonstorm Commander, 2025-04-11 | Storm escalando com encantamentos. Opinião: baixa prioridade. |
| **Hardlight Containment** {W} | Edge of Eternities, 2025-08-01 | Precisa de âncora em artefato. Opinião: nicho. |
| **Chorale of the Void** {3}{B} | Edge of Eternities, 2025-08-01 | Cláusula de sacrifício (Void). Opinião: condicional demais. |
| **Spiral into Solitude**, **Evershrike's Gift** | Lorwyn Eclipsed, 2026-01-23 | Opinião: marginais. |
| Twinblade Geist, Lunarch Mantle, Gryff's Boon | Innistrad Remastered, 2025-01-24 | **Não são novas** — reimpressões de Shadows over Innistrad (2016) [Scryfall]. Ótimas como filler barato ($0.14–0.34), mas não venda como novidade. |

## 2.4 Mana base

Mantenha **37 terrenos**. O problema é qualidade, não quantidade: seis duais entram virados num deck que quer curvar Aura no turno 2.

- **Tier barato:** troque Umbral Expanse e Desolate Mire por **Scoured Barrens** (~$0.20) e **Brightclimb Pathway // Grimclimb Pathway** (~$4.56–4.70) — o Pathway entra desvirado escolhendo a cor, estritamente melhor que um dual virado [Scryfall].
- **Tier premium:** **Godless Shrine** (~$8.54–9.54), **Silent Clearing** (~$7.25–12.79), **Marsh Flats** (~$32–34). Entram no lugar de Forum of Amity, Silverquill Campus e Temple of Silence — o scry/surveil deles não paga o turno perdido [Scryfall].
- **Não adicione Vault of Champions** se você pretende levar o deck pra 1v1: "This land enters tapped unless you have two or more opponents" [Scryfall]. No multiplayer é um dual WB razoável.
- Preços de terreno não passaram pela varredura de mínimo entre impressões; trate como ordem de grandeza.

---

# 3. Duel Commander: o formato hoje

**Regras** (verbatim nas [quickrules oficiais](https://www.duelcommander.org/rules/quickrules/), 2026-10-01):

| Regra | Valor |
|---|---|
| Vida inicial | **20** — "Start with 20 life points (instead of 40 in multiplayer Commander)" |
| Mão inicial / mulligan | 7 cartas, **mulligan de Londres** — "Apply the London mulligan if you want to mulligan" |
| Dano de comandante | **Não existe** — "In Duel Commander, there is NO victory by dealing 21 combat damage with your Commander" |
| Deck | "100-Card Singleton Deck", identidade de cor padrão |
| Terrenos (orientação oficial) | "For beginners: **38-40 lands** is a safe average" |

> O site canônico `duelcommander.com` redireciona (301) para `https://www.duelcommander.org/`.
> **Primeiro jogador não saca carta extra no turno 1**: sustentado apenas pelo [guia da Draftsim](https://draftsim.com/duel-commander-mtg/) — a página oficial de quickrules **não trata** do assunto. Quase certamente correto como regra de Magic, mas não é claim verificado na fonte oficial.
> Circula numa fonte de fã (`mtgdc.info`) a afirmação de que o Duel Commander "foi substituído por AeonShift em 2026-03-03". **É falso**: a [banlist oficial](https://www.duelcommander.org/banlist/) está viva e foi atualizada em [2026-07-27](https://www.duelcommander.org/announcements/2026/07/27/) pelo "Duel Commander Committee".

**Banlist** — última atualização **2026-07-27**, com 6 seções: Banned as Companion (1 — Lutri), Banned as Commander only (27, incluindo Edgar Markov, Raffine, Urza, Rograkh, Vial Smasher, Derevi), Banned in Deck (80 — toda a Power 9, todos os Mox, Sol Ring, Mana Crypt, Mana Vault, Grim Monolith, Ancient Tomb, Gaea's Cradle, The One Ring, Jeweled Lotus, Fierce Guardianship, Ragavan, Nadu), Recently Unbanned (3), Banned for Offensive Content (7) e Structurally Banned Cards ([banlist](https://www.duelcommander.org/banlist/)).

**Troca de comandante entre partidas.** A substância é corroborada por duas fontes independentes (a [página de regras abrangentes oficial](https://www.duelcommander.org/rules/duelcommander_comprehensiverules/) e um espelho de fã): um comandante conjurado por partida, troca permitida entre partidas de um match, desde que a identidade de cor não mude e só se usem comandantes da lista registrada. **Não cito número de regra** — os dois espelhos divergem na numeração e o documento integral não foi lido na fonte. Isso importa muito pro §5.

**Meta.** A seção de Duel Commander no mtgtop8 é [`f=EDH`](https://mtgtop8.com/format?f=EDH). O único top-8 completo verificado é o [Czech DC Masters 2026](https://www.mtgtop8.com/event?e=91395&f=EDH) (Praga, 75 jogadores, 27/09/26): Glarb, Calamity's Augur (1º), Nick Fury, Agent of S.H.I.E.L.D. (2º), Atraxa, Grand Unifier + Celes, Rune Knight (3–4), Atraxa / Ellie, Brick Master & Vengeful Hunter / Phelia, Exuberant Shepherd / Raph & Mikey, Troublemakers (5–8). **Duas cadeiras de Atraxa, zero Orzhov.** Os guias de meta do Cardsrealm reforçam: o de [controle](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame) (2026-02-12) chama Esper "the best control lists in the format" e Atraxa 4c "probably the best control list in the format", sem mencionar Orzhov puro; o de [aggro](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-aggro-metagame) (2026-05-02) lista Phelia, Slimefoot, shells Rakdos e tempo Satya/Aragorn — nenhum comandante de Aura-voltron. Esse guia também destaca dois pontos estruturais: comandante disponível desde o turno 1 ("a lot more consistent") e **ausência de sideboard**, o que obriga mais interação no maindeck.

**Legalidade de Killian e Scriv.** Ambos `commander: legal, duel: legal` [Scryfall] e ausentes da lista de 27 comandantes banidos ([banlist](https://www.duelcommander.org/banlist/)). O mesmo vale para Killian, Ink Duelist, Breena, Shadrix Silverquill e Eriette.

**Onde Aura-voltron W/B se encaixa.** A metade negativa é sólida: o arquétipo **não aparece** no único top-8 verificado nem em nenhum dos dois guias de meta. A metade positiva ("mas é um arquétipo registrado, só fora do topo") dependia inteiramente de snippets do mtgdecks.net, domínio que retornou 403 em toda tentativa direta — então o honesto é: **não há evidência em nenhuma direção sobre volume de decks registrados**. Trate o deck como escolha rogue com teto desconhecido, não como tier estabelecido.

---

# 4. Cartas do precon banidas ou fracas em 1v1

## 4.1 Banidas

| Carta | Status | Fonte |
|---|---|---|
| **Sol Ring** | **Banida em deck** no Duel Commander | [banlist oficial](https://www.duelcommander.org/banlist/) (seção "Banned in Deck", 80 cartas) + `duel: banned` [Scryfall] |

É só essa. Os outros 99 e os seis comandantes alternativos passaram por checagem individual de `--formatos commander,duel` e voltaram **todos** `duel: legal` — incluindo Land Tax, Animate Dead, Eldrazi Conscription, Fabled Passage, Path of Ancestry [Scryfall]. O precon é **99% legal direto da caixa**; tirar Sol Ring é questão de legalidade, não de poder.

## 4.2 Cartas só-multiplayer

### Goad em 1v1: a regra

Ruling oficial publicada em 2026-03-20 para Killian, Decisive Mentor — texto idêntico também nas rulings de Coercive Impetus [Scryfall]:

> "If the creature doesn't meet any of the above exceptions and can attack, it must attack a player other than the controller of the spell or ability that goaded it if able. If the creature can't attack any of those players but could otherwise attack, it must attack a planeswalker an opponent controls, a battle an opponent protects, **or the player that goaded it**."

Aplicando a 2 jogadores: "um jogador diferente de quem goadeou" seria o próprio controlador da criatura, e criatura não ataca o próprio controlador. O galho é impossível, cai na cláusula final — **a criatura é obrigada a atacar você**. O texto-lembrete do próprio Killian ("attacks a player other than you if able") confirma.

Consequência prática: goad **não redireciona** nada em duelo. Ele faz duas coisas: (a) tira a criatura da defesa — ela não pode ficar de bloqueadora; (b) força o oponente a atacar você quando ele não queria. Isso **não é ruim**: converte os 4 Impetus + o ETB do Killian de ferramenta política em ferramenta de tempo, que casa com Ghostly Prison, Nils, Sphere of Safety e blocos de deathtouch. Mas a metade "escudo" do comandante morre.

A [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/) chega à mesma conclusão por outro caminho: "The issue with goad is that it becomes irrelevant when the game becomes a 1v1." O [CoolStuffInc](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck) também: "When you end up in a 1v1, Goad can no longer save you from the board of big meanies you've created."

Carta por carta do pacote de goad em duelo [Scryfall]:

| Carta | 1v1 |
|---|---|
| **Parasitic Impetus** | **Melhor keep específico de duelo do deck.** "Whenever enchanted creature attacks, its controller loses 2 life and you gain 2 life" — incondicional, sem cláusula de número de jogadores. Swing de 4 pontos garantido por ataque, num formato de 20 de vida. |
| **Coercive Impetus** | Funciona: você saca sempre que a criatura encantada atacar, mas **perde 1 de vida** no gatilho. Teto menor que Parasitic. |
| **Ghoulish Impetus** | Funciona (goad + recursão). |
| **Martial Impetus** | **Morto na prática.** O pump é "each other creature that's **attacking one of your opponents** gets +1/+1" — "your" é você, dono da Aura. Em 1v1, a criatura goadeada ataca **você**, logo ninguém está atacando um oponente seu, e a cláusula nunca se aplica. Corte. |
| **Redemption Arc** | Funciona como goad simples. |

### A ficha Contract do Scriv em 1v1

Oracle [Scryfall]: Scriv cria "a white Aura enchantment token named Contract attached to target creature **an opponent controls**", e a ficha diz "Whenever enchanted creature attacks, it gets +2/+0 until end of turn if it's attacking **one of your opponents**. Otherwise, **its controller** loses 2 life."

A habilidade é controlada por **você**, então a ficha é sua, e "your opponents" dentro dela se refere aos **seus** oponentes. Em 1v1 a criatura encantada pertence ao seu único oponente e só pode atacar **você** — e você não é oponente de si mesmo. O galho `if` é **inalcançável**; o `otherwise` dispara sempre: **o oponente perde 2 de vida em cada ataque com aquela criatura**.

Ressalva obrigatória: as duas rulings publicadas do Scriv tratam apenas do caso de alvo ilegal na criação da ficha [Scryfall]. Isso é **inferência de regras a partir do templating**, de alta confiança, mas **sem ruling oficial confirmando**. Confirme com o juiz antes de um evento. (Um dos relatórios de pesquisa afirmava o oposto — que a ficha sempre dá +2/+0 de graça pro oponente. Está invertido e foi descartado.)

### Breena e Secret Rendezvous

- **Breena, the Demagogue**: "Whenever a player attacks one of your opponents, **if that opponent has more life than another of your opponents**…" [Scryfall]. Com um oponente só, não existe "another of your opponents" — condição matematicamente insatisfazível. Vira um 1/3 voador vanilla. Corte.
- **Secret Rendezvous**: "You and target opponent each draw three cards" [Scryfall]. Em 1v1 é **neutro em cartas** (3 pra cada), não desvantagem — mas zero vantagem com custo de mana e tempo. Corte.

### Cartas "políticas" que você NÃO deve cortar por reflexo

Conferido no oracle [Scryfall]: **Mangara, the Diplomat** (ambos os gatilhos referenciam só "você" e "um oponente"), **Ghostly Prison** (tax puro, sem diluição), **Nils, Discipline Enforcer**, **Combat Calligrapher**, **Tomik**, **Shadrix Silverquill** e **Keen Duelist** funcionam identicamente ou melhor em 1v1. Se você cortar algum deles, corte por nível de poder, não por contagem de jogadores. E **Kor Spiritdancer, Sram, Sage's Reverie, Songbirds' Blessing, Transcendent Envoy, Starfield Mystic** não têm nenhum texto dependente de número de jogadores — são keeps.

---

# 5. Adaptação para Duel Commander

## 5.1 Comandante

**Registre Killian, Decisive Mentor como comandante principal, com Scriv, the Obligator como alternativa legal pra trocar entre partidas** (a troca entre jogos do match é permitida, identidade de cor travada — corroborado pela [página oficial de regras abrangentes](https://www.duelcommander.org/rules/duelcommander_comprehensiverules/) e por um espelho independente; sem número de regra, por divergência entre as fontes).

Por quê Killian: o segundo gatilho ("sempre que uma ou mais criaturas encantadas por uma Aura que você controla atacarem, saque um card") é **completamente agnóstico a número de jogadores** [Scryfall] — é o motor real. A metade de goad perde o upside político (§4.2) mas continua tapando bloqueador e forçando ataque.

Quando trocar pro Scriv no jogo 2/3: contra oponente pobre em criaturas, onde tap+goad do Killian tem poucos alvos relevantes, mas a ficha Contract ainda cobra 2 de vida de qualquer coisa que atacar (§4.2) — inevitabilidade lenta num formato de 20 de vida. Note que isso depende da leitura de templating não confirmada por ruling.

**Breena está fora de cogitação** como comandante (§4.2). Não há fonte verificada defendendo Eriette, Killian Ink Duelist ou Shadrix como comandante de duelo.

## 5.2 Cortes (18)

| Carta | Motivo |
|---|---|
| **Sol Ring** | **Banida** ([banlist](https://www.duelcommander.org/banlist/), [Scryfall]) — não é escolha, é legalidade |
| **Breena, the Demagogue** | Gatilho insatisfazível com 1 oponente [Scryfall] |
| **Secret Rendezvous** | Saque neutro e simétrico, zero vantagem [Scryfall] |
| **Martial Impetus** | Pump nunca se aplica em 1v1 [Scryfall] |
| **Promise of Loyalty** | Sacrifício simétrico: num shell voltron você também perde corpos. Opinião, não regra |
| **Eldrazi Conscription** | 8 manas num formato de 20 de vida e curva baixa. Opinião — e contestada pelo [CoolStuffInc](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck) |
| **Intermediate Chirography** | Corte mais consensual do precon (4 guias verificados) |
| **Raffine's Guidance** | "Extremely clunky" ([CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/)) |
| **Sentinel's Eyes** | Baixo impacto (3 guias) |
| **Ajani's Chosen** | Payoff lento de 4 manas (3 guias) |
| **Armored Skyhunter** | "Once per attack" é lento demais ([MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade)) |
| **Firemane Commando** | Corpo e saque lentos (3 guias) |
| **Forum Filibuster** | Cortado pelo [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) |
| **Doomwake Giant** | Cortado pela [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/); 5 manas num formato rápido |
| **Shadrix Silverquill** | 5-drop fora do plano (3 guias) |
| **Fallen Ideal** | Cortado por [Wargamer](https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide) e [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) |
| **Screams from Within** | Cortado por [Draftsim](https://draftsim.com/silverquill-influence-upgrade-guide/) e [Card Kingdom](https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/) |
| **Combat Calligrapher** | Efeito estreito; ficha bloqueia seus próprios atacantes goadeados (3 fontes) |

**Mantenha Parasitic Impetus, Ghostly Prison, Nils, Winds of Rath, Mangara, Gift of Immortality, Kor Spiritdancer, Sram, Transcendent Envoy, Starfield Mystic, Flickering Ward, Land Tax, Animate Dead.**

## 5.3 Adições — tier orçamento (18)

Todas conferidas identidade W/B-ou-incolor **e** `duel: legal` [Scryfall]:

| Carta | Função |
|---|---|
| **Swords to Plowshares** | Exílio por 1 mana. Tapa a fraqueza nº1 (3 remoções reais) |
| **Path to Exile** | Segunda remoção de 1 mana |
| **Fatal Push** | Remoção instantânea de 1 mana pra curva baixa do formato |
| **Vindicate** | Destrói qualquer permanente — pega planeswalker, encantamento, terreno |
| **Orzhov Signet** | Substituto direto do Sol Ring banido |
| **Mind Stone** | Rampa incolor que vira carta no late |
| **Ethereal Armor** | Pump de 1 mana escalando com encantamentos |
| **All That Glitters** | Pump de 2 manas, mesma função |
| **Hyena Umbra** | Aura de 1 mana com Umbra Armor embutido — resiliência contra remoção |
| **Cartouche of Solidarity** | Aura de 1 mana que também deixa uma ficha 1/1 de backup |
| **Gryff's Boon** | Evasão de 1 mana com recursão do cemitério |
| **Light-Paws, Emperor's Voice** | Tutor-em-jogo de Aura ($1.60) |
| **Sphere of Safety** | Pillowfort que escala com encantamentos; **mais forte em duelo**, já que há só um atacante pra taxar e o oponente solitário raramente contorna o custo (leitura de jogo, não claim de fonte) |
| **Thalia, Guardian of Thraben** | Taxa toda interação não-criatura do único oponente |
| **Drannith Magistrate** | Trava o recast do comandante adversário — em 1v1 bloqueia exatamente um, sem diluição |
| **Dimensional Exile** | Remoção-Aura que não dá 2-por-1 (encanta terreno básico) |
| **Eye of Nidhogg** | Goad + Dragon 4/2 deathtouch; em duelo força o ataque e come um bloqueador ($0.54) |
| **Umbra Mystic** | Umbra armor em todas as suas Auras |

**Sobre preços:** só **Light-Paws ($1.60)** e **Eye of Nidhogg ($0.54)** passaram por varredura de mínimo. As cotações de $1.49 / $1.70 / $0.85 para Swords / Path / Fatal Push que circulam vieram do mtgdecks.net, domínio que retornou 403 — **não publicáveis**. As demais são commons/uncommons antigos, provavelmente abaixo de $3, mas **sem confirmação** — refaça uma cotação fresca (ex.: via LigaMagic) antes de comprar.

## 5.4 Adições — tier sem orçamento

Aqui tem uma particularidade do formato: a banlist do Duel Commander ataca justamente os outliers de mana rápido (Sol Ring, Mana Crypt, Mana Vault, Black Lotus, Ancestral Recall, Time Walk, Timetwister, Gaea's Cradle, Serra's Sanctum, Tolarian Academy, Ancient Tomb, Force of Will, Mana Drain, Vampiric Tutor, Imperial Seal — [banlist](https://www.duelcommander.org/banlist/)). **Não existe caminho de "versão premium" para os slots de rampa.** O dinheiro vai pra qualidade e stax:

| Carta | Função |
|---|---|
| **Opposition Agent** | Rouba o tutor do único oponente inteiro, sem diluição. Confirmado `duel: legal` apesar da reputação [Scryfall] |
| **Containment Priest** | Responde reanimator/flicker |
| **Archon of Emeria** | Um feitiço por turno + terrenos adversários virados |
| **Thalia, Heretic Cathar** | Taxa o tempo do oponente |
| **Greater Auramancy** | Blinda suas criaturas encantadas |
| **Sigarda's Aid** | Auras em flash ($18.38) |
| **Mantle of the Ancients** | Recursão em massa + win-con ($7.42) |
| **Godless Shrine / Silent Clearing / Marsh Flats** | Duais desvirados substituindo os duais virados (~$8.5 / ~$7.3 / ~$32, não reconferidos) |

## 5.5 Contagem de terrenos

**Mantenha 37** (ou no mínimo 36). A orientação oficial do próprio comitê do formato é "For beginners: **38-40 lands** is a safe average" ([quickrules](https://www.duelcommander.org/rules/quickrules/)), o que empurra na direção de **não** cortar. A recomendação de "33–36" que circula vinha de dados de Commander geral (não-DC) aplicados por analogia, e de uma paráfrase incorreta da própria página oficial — descartada. Com Sol Ring saindo e só Orzhov Signet + Mind Stone entrando, cortar terreno seria duplamente errado.

## 5.6 Plano de jogo em 1v1

1. **Turnos 1–2: ameaça barata e evasiva.** O objetivo não é o comandante — **não existe vitória por 21 de dano de comandante no formato** ([quickrules](https://www.duelcommander.org/rules/quickrules/)). São 20 pontos de vida comuns, e uma criatura de 1–2 manas com Ethereal Armor + All That Glitters chega lá rápido.
2. **Turnos 2–4: empilhe Auras de 1 mana.** A tese do [MTGGoldfish](https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade) vale ainda mais em 1v1: o arquétipo quer "cast multiple auras per turn and snowball fast". Cada ataque encantado é uma carta via Killian, e cada Aura é +1/+1 duplo (Armor + Glitters).
3. **Resolva o 2-por-1 antes de over-committar.** Hyena Umbra, Umbra Mystic, Greater Auramancy, Kaya's Ghostform e Gift of Immortality existem exatamente pra isso. Sem eles, uma Swords to Plowshares ganha o jogo do oponente.
4. **Use goad como tempo, não como política.** Goadear a melhor bloqueadora dele antes do seu combate limpa o caminho; no turno dele ela é obrigada a atacar você (§4.2) — e aí Ghostly Prison / Nils / Sphere of Safety cobram o pedágio, ou ela morre num bloqueio. **Parasitic Impetus** numa criatura dele é 4 pontos de swing por ataque num formato de 20.
5. **Maindeck precisa ser 100% vivo.** Não há sideboard ([guia de aggro do Cardsrealm](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-aggro-metagame)); a única alavanca entre partidas é a troca de comandante. Nada de tech situacional de multiplayer.
6. **Expectativa realista:** o meta verificado é Esper/Atraxa controle e aggro de swarm/tempo ([Czech DC Masters 2026](https://www.mtgtop8.com/event?e=91395&f=EDH), [guia de controle](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame)). Aura-voltron Orzhov não aparece em nenhuma dessas fontes. Isso é um deck de casa/local bem construído, não um registro competitivo testado.

---

# 6. Pontos em aberto / contradições não resolvidas

1. **A ficha Contract do Scriv em 1v1 não tem ruling oficial.** A leitura (oponente perde 2 de vida por ataque) vem do templating: a ficha é controlada por você, logo "your opponents" são os seus. As duas rulings publicadas do Scriv só tratam de alvo ilegal [Scryfall]. Um dos relatórios de pesquisa chegou à conclusão **oposta** e foi descartado. Confirme com juiz antes de competir.
2. **Eldrazi Conscription e Ghostly Prison: divergência editorial não resolvível com dados.** 3 guias verificados cortam, 1 defende explicitamente ([CoolStuffInc](https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck)). Depende da velocidade da sua mesa.
3. **Scriv tem 482 ou 2.161 decks no EDHREC?** A [página do precon](https://edhrec.com/precon/silverquill-influence) diz 482, a [do comandante](https://edhrec.com/commanders/scriv-the-obligator) diz 2.161. Escopos diferentes, inconsistência não explicada pela fonte.
4. **Volume real de Aura-voltron W/B em Duel Commander: desconhecido.** O mtgdecks.net (única fonte de listas registradas) retornou 403 em todas as tentativas. Sabemos que o arquétipo **não** aparece no único top-8 verificado nem nos dois guias de meta; não sabemos se é jogado em volume fora do topo.
5. **O guia do TCGplayer é inverificável.** A página retorna só header (renderizada por JS). Nenhuma atribuição exclusiva ao TCGplayer foi usada aqui — as cartas que ele sugeria aparecem em guias verificados de qualquer forma.
6. **Preços cotados, com exceção de 10 valores em negrito, não passaram por varredura de mínimo entre impressões.** Os números que circulam nos guias superestimam em até 8× (Light-Paws: $12.55 anunciado vs **$1.60** real). Para um orçamento em BRL, refaça a cotação do zero.
7. **Numeração das regras abrangentes do Duel Commander é inconsistente entre espelhos.** A substância da troca de comandante entre partidas está duplamente corroborada; o número da regra, não. Nenhum numeral foi publicado neste relatório por isso.
8. **"Primeiro jogador não saca no turno 1"** repousa apenas na [Draftsim](https://draftsim.com/duel-commander-mtg/) — a página oficial não aborda o tema.
9. **Nenhuma estatística de duração média de partida em DC foi encontrada.** A caracterização "formato rápido e denso em interação" é qualitativa, extraída dos guias do Cardsrealm, não medida.
10. **Descartado como erro:** Utter End e Mortify **não estão** no precon (os únicos instantes são Anguished Unmaking, Fracture, Inkshield e Vanishing Verse); **Omen of the Forge é vermelha** [THB 145], fora da identidade W/B; o guia do blog.edhlab.gg lista cartas (Embercleave, Expressive Iteration, Awakening of Vronos, Inkling Summoning, Luxurious Locomotion) que **não existem** nesta lista de 100 — fonte inteira excluída.

---

# Fontes

- https://edhrec.com/precon/silverquill-influence
- https://edhrec.com/commanders/killian-decisive-mentor
- https://edhrec.com/commanders/scriv-the-obligator
- https://edhrec.com/guides/silverquill-influence-precon-upgrade-guide
- https://draftsim.com/silverquill-influence-upgrade-guide/
- https://draftsim.com/mtg-goad/
- https://draftsim.com/duel-commander-mtg/
- https://www.wargamer.com/magic-the-gathering/silverquill-influence-precon-upgrade-guide
- https://www.mtggoldfish.com/articles/silverquill-influence-precon-upgrade
- https://blog.cardkingdom.com/secrets-of-strixhaven-silverquill-influence-commander-deck-upgrade-guide/
- https://cardgamebase.com/silverquill-influence-upgrade-guide/
- https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026
- https://www.coolstuffinc.com/a/cashinds-seo-04102026-a-look-at-the-silverquill-influence-commander-deck
- https://mtg.cardsrealm.com/en-us/articles/upgrading-commander-precon-silverquill-influence-killian-decisive-mentor
- https://tech.yahoo.com/gaming/articles/secrets-strixhaven-silverquill-influence-commander-234019760.html
- https://www.thegamer.com/magic-the-gathering-secrets-of-strixhaven-silverquill-influence-commander-deck-list-upgrades/
- https://www.duelcommander.org/banlist/
- https://www.duelcommander.org/rules/quickrules/
- https://www.duelcommander.org/rules/duelcommander_comprehensiverules/
- https://www.duelcommander.org/announcements/2026/07/27/
- https://mtgtop8.com/format?f=EDH
- https://www.mtgtop8.com/event?e=91395&f=EDH
- https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-aggro-metagame
- https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame
- https://scryfall.com (texto de oracle, rulings, identidade de cor, legalidade `commander`/`duel`, datas de set e preços — citado inline como [Scryfall])

*Citado mas inverificável, sem claim exclusivo dependendo dele:* https://www.tcgplayer.com/content/article/Silverquill-Influence-MTG-Commander-Precon-Deck-Upgrade-Guide/98bf17d1-6f54-451f-8db4-db166c052340/ (corpo do artigo não carrega sem JS).