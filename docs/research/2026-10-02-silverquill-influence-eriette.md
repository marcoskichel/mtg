# TL;DR

- **Eriette não é um Killian mais forte: é um deck diferente.** X = número de **Auras que você controla**, ponto — não importa em quem estão, não precisa atacar, não precisa de combate. Killian era goad/tap em ETB de encantamento; Eriette é dreno automático no seu end step + "nenhuma criatura encantada por Aura sua pode atacar você" [Scryfall].
- **O precon já tem 22 Auras e 30 encantamentos** (contagem verificada carta por carta), contra 31 encantamentos / 34 terrenos da lista média da EDHREC — ou seja, o deck **não está 8 encantamentos atrás**; o déficit real é **Auras especificamente, 3 terrenos a menos e 2 remoções reais a mais** ([EDHREC average](https://edhrec.com/average-decks/eriette-of-the-charmed-apple)).
- **554 decks** já fizeram exatamente essa troca (Killian stock: 6.400; Scriv: 485) e a EDHREC publica os cortes/adições com percentual exato — Intermediate Chirography sai de 86,5%, Ethereal Armor entra em 50,4% ([precon/Eriette](https://edhrec.com/precon/silverquill-influence/eriette-of-the-charmed-apple)).
- **O combo mecânico exclusivo da Eriette é Aura em criatura do oponente**: ela trava o ataque *e* conta para o X. **Scriv, the Obligator**, que você já tem, faz isso de graça e repetidamente (token de Aura "Contract" em ETB **e** em cada ataque) [Scryfall]. Soul Link ($0,25), Stab Wound ($0,12), Vampiric Link ($2,52), Pacifism ($0,05), Vow of Duty ($0,09) custam quase nada [Scryfall].
- **Pacote de upgrade inteiro abaixo de US$ 15** se você ficar nos tier-1: Ethereal Armor $0,36 + Mesa Enchantress $0,53 + All That Glitters $0,50 + Danitha $0,35 + Light-Paws $1,66 + Swords to Plowshares $1,01 + Kaya's Ghostform $2,15 + Shattered Sanctum $1,44 [Scryfall]. Os caros (Ondu Spiritdancer $11, Retether $14,35, Greater Auramancy $21,49) são opcionais.
- **Fraqueza estrutural confirmada por três fontes independentes: falta de recursão de encantamento.** Hall of Heliod's Generosity / Retether / Lurrus são a correção ([CoolStuffInc](https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026), [CardsRealm](https://mtg.cardsrealm.com/en-us/articles/commander-deck-tech-eriette-of-the-charmed-apple), [Draftsim](https://draftsim.com/eriette-edh-deck/)).
- **Para bracket 2-3 sem infinitos: não monte Sanguine Bond + Exquisite Blood** (nem as outras 6 duplas rotuladas "infinite" pela própria EDHREC). Rode **no máximo um** amplificador de dreno. Atenção ao teto de Game Changers: Teferi's Protection, Opposition Agent, Drannith Magistrate, Smothering Tithe, Enlightened Tutor, Serra's Sanctum e Farewell **são Game Changers** ([lista](https://commanderbrackets.com/game-changers)) — 3 é o limite no bracket 3.
- **Duel Commander: Eriette provavelmente é melhor que Killian, mas isso é raciocínio, não dado.** Zero resultado de torneio encontrado para ela; o top 8 do Czech DC Masters 2026 (75 jogadores, 27/09/2026) é Glarb/Nick Fury/Atraxa/Celes/Ellie/Phelia/Raph & Mikey ([mtgtop8](https://www.mtgtop8.com/event?e=91395&f=EDH)). Sol Ring e Serra's Sanctum são banidos ([banlist](https://www.duelcommander.org/banlist/)).

# 1. O que muda com Eriette no comando

## Oracle

**Eriette of the Charmed Apple** — {1}{W}{B}, Legendary Creature — Human Warlock, 2/4. "Each creature that's enchanted by an Aura you control can't attack you or planeswalkers you control. At the beginning of your end step, each opponent loses X life and you gain X life, where X is the number of Auras you control." Commander: legal. Duel: legal. Impressão mais barata: **SOC #307, $0,39** (24/04/2026) [Scryfall].

Três consequências que a maioria dos jogadores subestima:

1. **X conta Auras, não criaturas encantadas.** Aura em criatura sua, em criatura do oponente, em terreno seu (Dimensional Exile) e **Aura Curse** (que encanta jogador) — todas contam. Scryfall confirma `type_line: "Enchantment — Aura Curse"` para Trespasser's Curse, Cruel Reality, Curse of Disturbance, Nurgle's Rot [Scryfall]. Curse não pede board state e não morre junto com criatura.
2. **A cláusula estática é a melhor remoção barata do deck.** Qualquer Aura sem restrição de dono, colocada na criatura do oponente, vira um Pacifism parcial (não ataca você nem seus planeswalkers) *e* +1 de dreno.
3. **Ela é a identidade de cor exata do Killian (WB)**, então promovê-la **não invalida nenhuma carta do 99** [Scryfall]. Ela já ocupa um slot do 99 no precon — promovê-la **libera exatamente 1 vaga**.

## Aritmética do dreno

Ninguém publicou uma curva turno-a-turno — procurei e não existe fonte com esse cálculo (ver §6). O que segue é **aritmética direta do oracle**, não estimativa de curva:

| Auras que você controla (X) | Vida perdida por oponente / end step | Total em pod de 4 | Sua vida ganha |
|---|---|---|---|
| 2 | 2 | 6 | +2 |
| 4 | 4 | 12 | +4 |
| 6 | 6 | 18 | +6 |
| 8 | 8 | 24 | +8 |
| 10 | 10 | 30 | +10 |
| 22 (todas as Auras do precon) | 22 | 66 | +22 |

Duas propriedades importam mais que a velocidade: o dreno é **incondicional** (sem passo de combate, sem alvo, sem permissão) e **monotônico** (nada no deck remove Auras do seu lado, então X só sobe). A partir de X≈6 é um relógio real; até lá é vantagem de vida.

## O que a engine do Killian dava e você perde

Killian, Decisive Mentor tem dois gatilhos [Scryfall]: **goad** em cada encantamento que entra, e **saque** sempre que criaturas encantadas por Auras suas atacam. As rulings oficiais de 20/03/2026 na própria carta tratam da criatura goadeada. Goad é política de multiplayer: redireciona ataques para terceiros, cria aliados temporários, e as cartas construídas em volta disso (Combat Calligrapher, Breena, Firemane Commando, Secret Rendezvous, Shadrix) deixam de pagar aluguel. Você perde:

- a camada política ativa (goad como ferramenta de negociação);
- um plano de vitória por combate redirecionado;
- a sinergia "ataque com criatura encantada" (Firemane Commando, Combat Calligrapher).

## O que Eriette dá em troca

- Relógio de vida que **não depende do oponente** nem do combate.
- Remoção pseudo-gratuita: cada Aura barata em criatura inimiga é meia-remoção + 1 dreno.
- Ganho de vida constante, que liga Vito/Cliffhaven Vampire/Archon of Sun's Grace.
- Resistência a board wipe de criatura: o dreno continua enquanto as Auras estiverem em permanentes que sobrevivam (ou em jogadores, no caso de Curses).

## Killian e Scriv como cartas no 99

**Killian, Decisive Mentor — mantém.** As rulings de 20/03/2026 estabelecem: "If, during a player's declare attackers step, a creature that player controls that's been goaded is tapped, is affected by a spell or ability that says it can't attack, or hasn't been under that player's control continuously since the turn began (and doesn't have haste), then it doesn't attack" [Scryfall, rulings de Killian, Decisive Mentor e Coercive Impetus, idênticas]. Em multiplayer isso significa redirecionamento; em 1v1, travamento total (§5).

**Scriv, the Obligator — mantém, e é a descoberta mais útil deste levantamento.** Oracle verificado: 2/3 flying deathtouch, "Whenever Scriv enters or attacks, create a white Aura enchantment token named Contract attached to target creature an opponent controls" [Scryfall]. É a única carta **nativa WB do próprio precon** que coloca Aura em criatura do oponente de graça, em ETB **e em cada ataque** — ou seja, +1 de X por combate, e a criatura encantada deixa de poder atacar você. Caveat: nenhuma ruling nomeia o token "Contract" especificamente; o raciocínio (controlador do token = criador = você, logo conta para X) é a aplicação direta da regra de tokens, não uma ruling citável (§6).

**Killian, Ink Duelist — mantém.** 76-79% de inclusão nas páginas Eriette da EDHREC ([auras](https://edhrec.com/commanders/eriette-of-the-charmed-apple/auras), [pillow-fort](https://edhrec.com/commanders/eriette-of-the-charmed-apple/pillow-fort)) — redutor de custo de Aura, exatamente o que um plano de 26+ Auras quer.

# 2. Como a comunidade constrói Eriette

**Números EDHREC (02/10/2026):** 19.107 decks, rank #86 ([página principal](https://edhrec.com/commanders/eriette-of-the-charmed-apple)). Temas: **Auras 3.2K**, **Enchantress 1.2K**, **Lifegain 562**, **Control 380**. Na página do precon Silverquill Influence, Eriette é a comandante alternativa mais popular: **554 decks**, contra Killian Decisive Mentor 6.400 (stock), Scriv 485, Killian Ink Duelist 41, Breena 29, Shadrix 12 ([precon index](https://edhrec.com/precon/silverquill-influence)).

**Núcleo consensual** (inclusão na página principal): Mesa Enchantress 85%, Sram, Senior Edificer 85%, Kor Spiritdancer 81%, All That Glitters 76%, Ethereal Armor 75%; payoffs Archon of Sun's Grace 55% (10,5K decks), Sigil of the Empty Throne 44% (8,5K), Angelic Destiny 40% (7,6K); proteção Kaya's Ghostform 69%, Gift of Immortality ~51-52%, Greater Auramancy 36-44% ([mesma página](https://edhrec.com/commanders/eriette-of-the-charmed-apple)). Nichos de alta sinergia (16-18x de lift): **Clawing Torment, Dead Man's Chest, Demotion**.

**Página Auras (3.260 decks):** Mesa 87%, Sram 85%, Kor 82%, Killian Ink Duelist 79%, All That Glitters 77% — e um padrão de **reconstrução pós-wipe**: Retether 59%, Winds of Rath 53% ([/auras](https://edhrec.com/commanders/eriette-of-the-charmed-apple/auras)).

**Página Pillow-fort (308 decks):** Mesa 89, Sram 89, Kor 85, **Darksteel Mutation 77**, **Killian Ink Duelist 76**, **Sage's Reverie 75**, **Ghoulish Impetus 68**, Ethereal Armor 68, **Parasitic Impetus 67**, All That Glitters 66, Sphere of Safety 60, Ghostly Prison 56, Timely Ward 54 ([/pillow-fort](https://edhrec.com/commanders/eriette-of-the-charmed-apple/pillow-fort)). **Seis dessas dez já estão no seu 99** — sinal forte de que são keeps, não cortes.

**Sub-build Curses:** a build "Optimized Curses" roda **10 Curses** — Curse of Conformity, Curse of Death's Hold, Curse of Disturbance, Curse of Exhaustion, Curse of Fool's Wisdom, Curse of Misfortunes, Curse of Silence, Cruel Reality, Overwhelming Splendor, Trespasser's Curse ([optimized/curses](https://edhrec.com/average-decks/eriette-of-the-charmed-apple/optimized/curses)).

## Primers publicados e fraquezas declaradas

| Fonte | Arquétipo declarado | Tese central | Fraqueza declarada |
|---|---|---|---|
| [Draftsim](https://draftsim.com/eriette-edh-deck/) | Group-hug óptico + Voltron/pillowfort real | **"I had more success buffing my opponents' creatures and slowly draining the table"**; "By putting your auras on your opponents' creatures, they'll be forced to only attack each other instead of you". Proteção: Spectral Steel, Hyena Umbra. Taxas: Ghostly Prison, **Koskun Falls**, Norn's Annex. Recursão: Hall of Heliod's Generosity, Umbra Mystic, Open the Vaults | não declara |
| [CardsRealm](https://mtg.cardsrealm.com/en-us/articles/commander-deck-tech-eriette-of-the-charmed-apple) (23/04/2025) | **Midrange control** — "let the opponents spend resources first, and pressure them at the right moment" | Auras em 3 baldes: Control (Despondency, Ghoulish Impetus), Power (All That Glitters, Ethereal Armor, Mantle of the Ancients, Sage's Reverie), Protection (Flickering Ward, Benevolent Blessing, Fungal Fortitude). Alt-wincon: Test of Endurance | **risco explícito de empate técnico** quando vários jogadores ganham vida e o dreno estagna |
| [CoolStuffInc](https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026) (Paige Smith, 14/05/2026 — sobre o precon, **não** trata Eriette como comandante alternativa) | — | "If you look at the Oracle text on each of Spirit Link, Soul Link, and Vampiric Link… if you put one of these Auras onto an opponent's Creature, **you'll** gain the life". Rejeita Silverquill, the Disputant porque "the precon itself only contains four Instants and three Sorceries" | **"If I had to point to one main pain point for this deck, I'd say it's getting your Enchantments back after they hit the graveyard"** — Hall of Heliod's Generosity, Sun Titan, Treasury Thrull, Lurrus, Starfield of Nyx |
| [Sci-Fi Bloggers](https://scifibloggers.com/a-charming-deck-tech-with-eriette/) (18/09/2023 — **escrito para MTGO Historic Brawl**, não Commander em papel) | Aggro/Combo/Control, dreno sobre combate | "it's actually (usually) better not to attack… destroy your opponent purely with drain effects"; nota que se o oponente roubar sua criatura encantada por Aura **sua**, ela ainda não pode te atacar | **morre para agressão rápida no começo** |

Convergência independente: **recursão de encantamento é o ponto fraco**, e as três fontes chegam lá por caminhos diferentes.

**Nota de evidência:** [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) é um guia de upgrade **Killian-first que nunca menciona Eriette**. Seus 10 swaps coincidem com a EDHREC em 6 — mas só do **lado dos cortes**. Suas adições (Eye of Nidhogg, Ondu Spiritdancer, Retether, Vampiric Link, Nurgle's Rot, Visions of Brutality) são fonte única e não validadas para Eriette; a única delas que a lógica da Eriette ativamente quer é Eye of Nidhogg (goad + não pode te atacar).

# 3. Conversão do precon para Eriette (multiplayer)

Baseline verificado: **22 Auras, 30 encantamentos totais, 37 terrenos**, carta por carta via Scryfall [Scryfall].

## Mantém e por quê (ficam melhores sob Eriette)

| Carta | Por que melhora |
|---|---|
| **Scriv, the Obligator** | Token de Aura "Contract" em criatura do oponente, em ETB **e em cada ataque** — único gerador nativo WB de Aura-no-inimigo; +X e trava o atacante [Scryfall] |
| **Darksteel Mutation** | "Enchant creature" sem restrição de dono [Scryfall]; 77% nas listas pillow-fort. Vira a melhor criatura do oponente em 0/1 indestrutível *e* conta para X |
| **Ghoulish / Parasitic / Martial / Coercive Impetus** | Todas `id:B`, encantam qualquer criatura + goad [Scryfall]. Agora são 2-por-1: redirecionam o atacante **e** somam +1 ao dreno. Ghoulish 68% / Parasitic 67% nas listas pillow-fort |
| **Chains of Custody**, **Sheltered by Ghosts** | "enchant creature you control" + exila permanente não-terreno no ETB [Scryfall]: contagem de Aura e remoção na mesma carta |
| **Screams from Within** | Aura de -1/-1 recorrente; mata o alvo pequeno e volta [Scryfall] |
| **Sage's Reverie**, **Eidolon of Countless Battles**, **Hateful Eidolon**, **Herald of Amity** | Escalam com "Auras you control" — exatamente a métrica da sua comandante agora [Scryfall]. Sage's Reverie 75% nas listas pillow-fort |
| **Pearl-Ear, Imperial Advisor** | Affinity for Auras + saque; aceleração pura para um plano de 26+ Auras [Scryfall] |
| **Killian, Ink Duelist** | 76-79% de inclusão; redutor de custo de Aura |
| **Killian, Decisive Mentor** | Goad continua funcional e não depende de ser comandante (§1, §5) |
| **Winds of Rath** | "destroy all creatures that aren't enchanted" vira wrath unilateral quando seu board está coberto de Auras [Scryfall]; 53% na página Auras |
| **Kor Spiritdancer**, **Sram, Senior Edificer**, **Starfield Mystic**, **Transcendent Envoy** | 81-89% de inclusão; motor de card advantage e redução de custo, indiferentes à troca de comandante |
| **Archon of Sun's Grace** | 55% / 10,5K decks — payoff de ETB de encantamento |
| **Angelic Destiny**, **Eldrazi Conscription** | Alvo de "voltron reverso": na melhor criatura do oponente, trava sob a estática da Eriette e ainda conta para X ([Draftsim](https://draftsim.com/eriette-edh-deck/)). Angelic Destiny 40% |
| **Gift of Immortality**, **Animate Dead**, **Replenish**, **Shielded by Faith**, **Redemption Arc** | Proteção/recursão que a comandante nova precisa ainda mais; Gift ~51-52% |
| **Vanishing Verse**, **Anguished Unmaking**, **Fracture**, **Doomwake Giant**, **Mangara, the Diplomat**, **Flickering Ward**, **Spirit Mantle**, **Songbirds' Blessing** | Neutros — nenhuma referência a goad/política; avaliação não muda [Scryfall] |

## Corta e por quê

| Carta | Taxa de corte (554 decks Eriette) | Motivo |
|---|---|---|
| Intermediate Chirography | **86,5%** | Class lenta, zero sinergia com Aura; o investimento de mana só se pagava com o payoff do Killian |
| Keen Duelist | **79,1%** | Perda de vida simétrica e reveal de carta não tocam Auras nem o dreno |
| Combat Calligrapher | **77,3%** | Gatilho é "qualquer jogador atacando um oponente" — payoff da era goad, não de Aura |
| Secret Rendezvous | **76,4%** | Política pura: dá cartas ao oponente sem retorno em Aura/dreno |
| Tomik, Wielder of Law | **74,9%** | 2/4 voador sem interação com Aura |
| Firemane Commando | **71,8%** | Saque exige **você** atacando com 2+ criaturas — briga com o plano defensivo |
| Shadrix Silverquill | **68,6%** | Nenhum dos 3 modos toca Auras ou dreno |
| Nils, Discipline Enforcer | **63,0%** | Redundante com a própria cláusula "can't attack you" da Eriette |
| Terramorphic Expanse | **38,1%** (mais cortado entre terrenos) | Entra tapado; troque por dual |
| Breena, the Demagogue | sem % publicada | Exige oponente atacando **outro** oponente com vida estritamente maior — morto sem goad como engine central; **completamente morto em 1v1** [Scryfall] |
| Ajani's Chosen | sem % publicada | Corpo 3/3 por 4 substituível por payoff de Aura de maior impacto |
| Raffine's Guidance | sem % publicada | Taxa fraca de +1/+1 por 3 mana ([CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/)) |
| Sentinel's Eyes | sem % publicada | Filler de +1/+1 e vigilance; perde para Aura com remoção ou saque embutido |
| Fallen Ideal | sem % publicada | Corte do [CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/); exige sacrificar criaturas que você quer encantadas |
| Sol Ring | — | **Só em Duel Commander** (banido, §5). Em multiplayer, mantenha |

## Tira X / Põe Y — 24 trocas, ordenadas por impacto

Preços = nonfoil mais barato no Scryfall em **02/10/2026** [Scryfall]. "GC" = Game Changer — nenhuma carta desta tabela é Game Changer.

| # | Tira | Põe | US$ | Por quê / fonte |
|---|---|---|---|---|
| 1 | Intermediate Chirography | **Ethereal Armor** | 0,36 | Adição #1 (50,4%) e 75% na página principal; escala com cada encantamento ([precon/Eriette](https://edhrec.com/precon/silverquill-influence/eriette-of-the-charmed-apple)) |
| 2 | Keen Duelist | **Mesa Enchantress** | 0,53 | Adição #2 (49,1%); 85-89% em toda página Eriette. Saca em **qualquer** encantamento, não só Aura |
| 3 | Combat Calligrapher | **All That Glitters** | 0,50 | Adição #3 (47,8%); conta artefatos também (sinergia com os 4 rocks do precon) |
| 4 | Secret Rendezvous | **Swords to Plowshares** | 1,01 | 30,9% de adoção na página do precon; o precon tem só 3 remoções "reais". Preço de impressão FRC lançada hoje — vai subir |
| 5 | Tomik, Wielder of Law | **Danitha Capashen, Paragon** | 0,35 | 33,6% de adoção; desconta {1} em cada Aura — aceleração direta do X |
| 6 | Firemane Commando | **Light-Paws, Emperor's Voice** | 1,66 | 30,9%; tutora Aura de custo igual/menor direto no campo ao conjurar Aura |
| 7 | Fallen Ideal | **Kaya's Ghostform** | 2,15 | 31,9% de adoção no precon; **69%** na página principal — a proteção de comandante mais jogada do arquétipo |
| 8 | Terramorphic Expanse | **Shattered Sanctum** | 1,44 | Terreno mais adicionado (23,6%). Preço é de promo PSOS 260p |
| 9 | Sentinel's Eyes | **Pacifism** | 0,05 | Pseudo-remoção de 2 mana que é simultaneamente +1 de dreno quando colada no inimigo [Scryfall] |
| 10 | Ajani's Chosen | **Vow of Duty** | 0,09 | Dá literalmente "can't attack you or planeswalkers you control" — espelha a estática da Eriette e soma ao X [Scryfall] |
| 11 | vaga liberada pela promoção da Eriette | **Soul Link** | 0,25 | "Enchant creature" sem restrição de dono; na criatura do oponente **você** ganha a vida ([CoolStuffInc](https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026)) |
| 12 | −1 Plains (37 → 36) | **Stab Wound** | 0,12 | -2/-2 + dreno de upkeep, sem restrição de dono [Scryfall]; 100% numa sub-build pequena de Exhibition Control |
| 13 | −1 Swamp (36 → 35) | **Vampiric Link** | 2,52 | Mesma tecnologia de Soul Link por 1 mana ([CoolStuffInc](https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026)) |
| 14 | Nils, Discipline Enforcer | **Visions of Brutality** | 0,26 | Não pode bloquear + controlador perde vida quando ela causa dano; dreno extra em cima do end step ([CardGameBase](https://cardgamebase.com/silverquill-influence-upgrade-guide/) — Killian-tuned) |
| 15 | Breena, the Demagogue | **Lurrus of the Dream-Den** | 2,10 | Recompra qualquer permanente MV≤2 por turno — cobre a fraqueza de recursão com a maioria das Auras baratas [Scryfall] |
| 16 | Raffine's Guidance | **Nurgle's Rot** | 6,06 | Aura que **obriga** encantar criatura do oponente, volta pra mão quando morre e deixa um 1/3 [Scryfall]; também é Aura Curse-adjacente no plano |
| 17 | Shadrix Silverquill | **Ondu Spiritdancer** | 11,03 | Copia cada encantamento que entra (1x/turno) = **+1 de X imediato**, o único "doubler" real do X no turno [Scryfall]. Fonte única Killian-tuned |
| 18 | −1 terreno (35 → 34) ou corte livre | **Hall of Heliod's Generosity** | não verificado | Recursão de encantamento — fraqueza #1 apontada por três fontes independentes |
| 19 | corte livre (tier 2) | **Retether** | 14,35 | Replenish de orçamento; com 26+ Auras no deck é um blowout de uma carta. 59% na página Auras |
| 20 | corte livre (tier 2) | **Eye of Nidhogg** | 0,45 | Transforma qualquer criatura em 4/2 flying deathtouch goadeada e volta pra mão; único add do CardGameBase que a lógica da Eriette ativamente quer |
| 21 | corte livre (tier 2) | **Cliffhaven Vampire** | 0,61 | 2/4 voador, {2}{W}{B}: "whenever you gain life, each opponent loses 1" — multiplica o próprio ganho de vida da Eriette [Scryfall]. **Veja a caixa de infinitos antes** |
| 22 | corte livre (tier 2) | **Vito, Thorn of the Dusk Rose** | 9,15 | 1/3, {2}{B}; dobra cada ponto de vida ganho pela Eriette [Scryfall]. **Rode só um entre Vito e Cliffhaven — veja a caixa de infinitos** |
| 23 | corte livre (tier 2) | **With Great Power . . .** | 0,60 | {3}{W}, +2/+2 por Aura/Equipment anexado **e redireciona todo dano a você para a criatura encantada** — defesa real para um deck cuja comandante é ímã de remoção [Scryfall] |
| 24 | corte livre (tier 2) | **Greater Auramancy** | 21,49 | "Other enchantments you control have shroud. **Enchanted creatures you control have shroud**" [Scryfall] — protege Eriette no momento em que ela carrega uma Aura sua. **Contrapartida: shroud bloqueia seu próprio targeting**, você não anexa mais Auras nela depois |

**Opcionais não tabelados, por falta de preço verificado:** Sphere of Safety (60% pillow-fort), Ghostly Prison (56%), Timely Ward (54%, concede indestrutível — resposta direta ao problema de wrath), Dead Man's Chest ("Enchant creature an opponent controls", 16-18x de lift), Demotion, Clawing Torment, Idyllic Tutor ($12,49 — ver §6: a citação de que ele está na lista média da EDHREC é falsa; a recomendação se sustenta pelo mérito, a fonte não).

**Umbra Mystic ($6,00): não recomendo nesta build.** O oracle real é "**Auras attached to permanents you control** have umbra armor" [Scryfall] — ou seja, **zero proteção** para as Auras que você colou nas criaturas dos oponentes, que é metade do plano.

## Cartas novas 2025-2026 (busca Scryfall `id<=wb (t:aura or o:aura) year>=2025`, 88 resultados)

| Carta | Set / data | Veredito |
|---|---|---|
| **Eye of Nidhogg** | FIC, 13/06/2025 | **Sim** — $0,45, goad + deathtouch + volta pra mão (troca #20) |
| **With Great Power . . .** | SPM | **Sim** — $0,60, redirecionamento de dano (troca #23). Nome exato tem espaços entre os pontos |
| Chorale of the Void | EOE | Não — {3}{B}, se sacrifica sem condição satisfeita; nichado |
| Hardlight Containment | EOE | Não — {W} mas precisa encantar **artefato seu**; alvo desconfortável aqui |
| Lightwheel Enhancements | DFT | Não — depende do mecanismo Speed |
| Roadside Assistance | DFT | Filler aceitável, perde para as opções acima |
| Tempest Technique | TDC | Não — Storm count é baixo em Commander singleton |
| Evershrike's Gift (ECL), Uneasy Alliance (TMT), Path to Redemption (TLA), Swampsnare Trap (TLA) | 2025-26 | Legais e aceitáveis, nenhuma supera as escolhas acima |
| **Selenia, the Cursed Heart** / **Grakk the Pacifist** | MBC, **09/11/2026** | **Watch-list.** Scryfall retorna `commander: not legal` e sem preço [Scryfall]. Tematicamente perfeitas (Selenia dobra lifegain e deixa Aura Curse ao morrer; Grakk saca ao mirar criatura do oponente com Aura), mas não são compráveis nem legais hoje |

## Contagens-alvo

| Métrica | Precon hoje | Média EDHREC Eriette | Alvo recomendado |
|---|---|---|---|
| **Auras** | 22 [Scryfall] | — (a média publica 31 **encantamentos**, não Auras) | **26-28** |
| Encantamentos totais | **30** [Scryfall] | 31 ([average](https://edhrec.com/average-decks/eriette-of-the-charmed-apple)) | ~31 — você já está em paridade, o déficit é só de Auras |
| Corpos de enchantress/saque | 4 (Kor Spiritdancer, Sram, Pearl-Ear, Starfield Mystic) | — | **6** (+ Mesa Enchantress, Light-Paws) |
| Remoção instantânea real | 3 + Fracture/Vanishing Verse | **5** (Swords to Plowshares, Path to Exile, Anguished Unmaking, Generous Gift, Not Dead After All) | **5-6** |
| Ramp | 4 rocks (Sol Ring, Arcane Signet, Fellwar Stone, Talisman) | mesmos + Orzhov Signet | **5** |
| Criaturas | — | 18 | 16-18 |
| Terrenos | **37** [Scryfall] | **34** (11 Plains, 9 Swamp, 14 utilitários) | **34-35** (a curva baixa ao cortar as cartas de goad) |
| Instants / Sorceries / Artefatos | — | 5 / 5 / 6 | manter nessa faixa |

# 4. Como o deck fecha o jogo

## Amplificadores de dreno (todos WB, commander + duel legal)

| Carta | Efeito | Infinito com… |
|---|---|---|
| **Vito, Thorn of the Dusk Rose** (1/3, {2}{B}) | "Whenever you gain life, target opponent loses that much" [Scryfall] | Exquisite Blood, Bloodthirsty Conqueror |
| **Cliffhaven Vampire** (2/4 flying, {2}{W}{B}) | "Whenever you gain life, each opponent loses 1" [Scryfall] | Exquisite Blood |
| **Marauding Blight-Priest** | igual ao acima, corpo menor [Scryfall] | Exquisite Blood |
| **Sanguine Bond** | "Whenever you gain life, target opponent loses that much" [Scryfall] | Exquisite Blood, Bloodthirsty Conqueror, Beacon of Immortality |
| **Wound Reflection** | No end step de cada jogador, cada oponente perde vida igual à que perdeu naquele turno [Scryfall] | **nenhum loop** — dobra o dano do turno, não cria ciclo. O amplificador mais seguro da lista para bracket 2-3 |
| Enduring Tenacity, Bloodthirsty Conqueror, Exquisite Blood, Aetherflux Reservoir | ver caixa abaixo | sim |

**Regra prática para bracket 2-3:** escolha **um** entre Vito / Cliffhaven Vampire / Sanguine Bond, e **nunca** coloque no deck Exquisite Blood, Bloodthirsty Conqueror, Enduring Tenacity, Marauding Blight-Priest (como segunda peça) ou Aetherflux Reservoir junto. Wound Reflection é a opção que não forma loop nenhum.

## Multiplicadores de Aura (sobem o X, não a vida)

**Ondu Spiritdancer** (copia encantamento que entra, 1x/turno) e **Light-Paws, Emperor's Voice** (Aura extra ao conjurar Aura) são os únicos que aumentam X **no mesmo turno** [Scryfall]. **Mantle of the Ancients**, **Retether** e **Replenish** (já no 99) reconstroem X depois de um wrath [Scryfall].

## Fechamentos sem combo

- **"Voltron reverso" é o plano real, e vem do próprio autor de primer.** [Draftsim](https://draftsim.com/eriette-edh-deck/): "I had more success buffing my opponents' creatures and slowly draining the table" e "By putting your auras on your opponents' creatures, they'll be forced to only attack each other instead of you". Mecanicamente funciona porque X = Auras **que você controla**, independente de onde estejam: um Angelic Destiny ou Eldrazi Conscription na maior criatura do oponente (a) a trava sob a estática da Eriette e (b) ainda conta para o dreno. Resposta direta à pergunta "faz sentido voltronizar uma 2/4 pillowfort?": **não**. Voltronize a criatura **deles**. Encantar as suas próprias é o plano B, para quando a Eriette for removida — no melhor jogo do autor, as Auras foram para um **Kor Spiritdancer**.
- **Payoffs de ETB de encantamento:** Archon of Sun's Grace 55% / 10,5K decks, Sigil of the Empty Throne 44% / 8,5K ([página principal](https://edhrec.com/commanders/eriette-of-the-charmed-apple)). Starfield of Nyx e Approach of the Second Sun **não aparecem** na tabela de inclusão dessa página — leia como adoção baixa, não como ausência comprovada.
- **Test of Endurance** como wincon alternativo para jogos travados ([CardsRealm](https://mtg.cardsrealm.com/en-us/articles/commander-deck-tech-eriette-of-the-charmed-apple)).
- **Dimensional Exile** ({1}{W}, "Enchant basic land you control. When this Aura enters, exile target creature an opponent controls until this Aura leaves the battlefield") [Scryfall]: remoção limpa **e** +1 de X, e a criatura não volta por board wipe ou chump block — só se o próprio Aura-no-terreno sair.

## ⛔ EVITE — só bracket 4+: linhas infinitas

**Todas as linhas abaixo são rotuladas "infinite" ou "near-infinite" pela própria EDHREC**, não por inferência minha ([combos da Eriette](https://edhrec.com/combos/eriette-of-the-charmed-apple)). Nenhuma delas exige a Eriette no campo — são combos genéricos de lifegain Orzhov. Seu objetivo declarado é bracket 2-3 sem infinitos, então **nenhuma destas entra**:

| Linha | Rótulo EDHREC | Decks |
|---|---|---|
| Sanguine Bond + Exquisite Blood | infinite lifegain / lifeloss | 148.269 (2,88%) |
| Sanguine Bond + Bloodthirsty Conqueror | infinite | 76.500 |
| **Sanguine Bond + Beacon of Immortality** | "**Target opponent loses the game**" | 17.249 |
| Exquisite Blood + Enduring Tenacity | infinite | 74.128 |
| Exquisite Blood + Marauding Blight-Priest | infinite | 59.764 |
| Exquisite Blood + Aetherflux Reservoir | infinite damage | 55.652 |
| Enduring Tenacity + Revival // Revenge | near-infinite | 9.323 |

Notas de bracket: as regras oficiais, conforme resumidas pela [EDHREC](https://edhrec.com/articles/commander-philosophy-2-card-combos-in-lower-brackets), proíbem combos infinitos de 2 cartas montáveis com confiabilidade antes do turno 8 no **bracket 2** e antes de ~turno 6 no **bracket 3**; brackets 4-5 são livres. Sanguine Bond + Exquisite Blood é *tecnicamente* legal no bracket 3 como linha de late game — mas é exatamente o que você disse que não quer. **Nenhuma das cartas acima é Game Changer** (Sanguine Bond, Exquisite Blood, Aetherflux Reservoir e Sol Ring estão fora da lista, confirmado em duas fontes: [commanderbrackets](https://commanderbrackets.com/game-changers), [krakenthemeta](https://krakenthemeta.com/blog/mtg-commander-brackets/)). Legal ≠ alinhado ao seu objetivo.

## O que derrota Eriette, e como protegê-la

- **Wraths de encantamento.** O 2-por-1 clássico contra deck de Aura: a criatura morre e a Aura vai com ela. Farewell (modo exilar encantamentos) e Austere Command (modo destruir encantamentos) são as respostas nominais. **Caveat de honestidade:** a tese de que Austere Command é *especificamente* devastadora contra shells de Eriette não tem fonte — o artigo que a sustentava é sobre **Eriette, the Beguiler** ({1}{W}{U}{B}, OTJ 202, identidade WUB — **carta diferente**) e não menciona Austere Command. O ponto estratégico pode estar certo; a citação não existe (§6).
- **Pressão de Game Changer nas próprias respostas.** **Teferi's Protection** e **Farewell** estão na lista oficial de Game Changers (duas fontes independentes: [commanderbrackets](https://commanderbrackets.com/game-changers), [krakenthemeta](https://krakenthemeta.com/blog/mtg-commander-brackets/)) — e **Smothering Tithe, Enlightened Tutor, Serra's Sanctum, Opposition Agent e Drannith Magistrate também**. O bracket 3 permite **3**. Smothering Tithe (22%), Enlightened Tutor (20%) e Serra's Sanctum (13%) aparecem na página Auras da EDHREC como aceleradores comuns — se você pegar os três mais Teferi's Protection, estourou o teto antes de qualquer outra escolha. **Nenhum é necessário** para a build que recomendo acima.
- **Proteção on-color verificada, sem custo de Game Changer:** Kaya's Ghostform (69%), Gift of Immortality (~51-52%, já no 99), Swiftfoot Boots, Lightning Greaves, Greater Auramancy (36-44%, com a contrapartida de shroud bloquear seu próprio targeting), Timely Ward (54% pillow-fort, concede indestrutível) [Scryfall + páginas EDHREC].
- **Sterling Grove está fora de cor** (identidade GW) [Scryfall] — não é opção.
- **Flawless Maneuver** é legal em Commander mas **banida em Duel Commander** [Scryfall] — só serve na config multiplayer.
- **Taxas de ataque** que combinam com o plano: Sphere of Safety (60%, escala com contagem de encantamentos), Ghostly Prison (56%), e — do primer da Draftsim — **Koskun Falls** e Norn's Annex.

# 5. Eriette em Duel Commander

## Regras em 1v1

O oracle dela **não tem dependência de multiplayer**: nenhum "each other player", nenhuma referência ao número de oponentes. "Each opponent loses X" = o único oponente perde X. A cláusula estática é um Pacifism pessoal em qualquer coisa que você encantar [Scryfall].

## Goad + Eriette: a interação, com a citação

As rulings de **20/03/2026** em Killian, Decisive Mentor e Coercive Impetus (texto idêntico nas duas, o que confirma que o mecanismo é geral e não específico de carta) dizem [Scryfall]:

> "If, during a player's declare attackers step, a creature that player controls that's been goaded is tapped, is affected by a spell or ability that says it can't attack, or hasn't been under that player's control continuously since the turn began (and doesn't have haste), then it doesn't attack."

> "If the creature doesn't meet any of the above exceptions and can attack, it must attack a player other than the controller of the spell or ability that goaded it if able. If the creature can't attack any of those players but could otherwise attack, it must attack a planeswalker an opponent controls, a battle an opponent protects, or the player that goaded it."

**A cadeia correta em 1v1** (atenção: a estática da Eriette **não** é um "can't attack" genérico — é "can't attack **you** or planeswalkers you control", então a primeira ruling não se aplica literalmente): goad é um **requisito**, a Eriette é uma **restrição**, e restrições vencem requisitos. O alvo "um jogador diferente do goader" não existe em 1v1; os fallbacks "você" e "seus planeswalkers" estão travados pela Eriette. Resultado: **a criatura não tem ataque legal e simplesmente não ataca.** Mesmo resultado que os pesquisadores concluíram, base mais limpa.

Consequência prática: em 1v1, **cada Impetus** (Ghoulish, Martial, Parasitic, Coercive) e o próprio gatilho do Killian deixam de ser "redirecionamento" e passam a ser **Pacifism integral**, mantendo o buff de stats e o +1 de dreno. Isso é melhor em 1v1 do que em multiplayer, não pior.

**Edge case que nenhum pesquisador marcou:** o fallback de goad inclui explicitamente "**a battle an opponent protects**", e a Eriette **não** impede ataque a battle. Irrelevante hoje (o 99 não tem battle), relevante se você adicionar uma.

## Presença em torneio: não encontrada

| Evidência | Resultado |
|---|---|
| [Czech DC Masters 2026](https://www.mtgtop8.com/event?e=91395&f=EDH), Praga, 75 jogadores, 27/09/2026, formato Duel Commander (re-verificado) | Top 8: Glarb Calamity's Augur; Nick Fury, Agent of S.H.I.E.L.D.; Atraxa, Grand Unifier; Celes, Rune Knight; Ellie; Phelia, Exuberant Shepherd; Raph & Mikey. **Sem Eriette** |
| [Cardsrealm, guia do metagame de controle DC](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame) (fev/2026) | Controle roda **6-10 criaturas** + "a little over 20 counters and a lot of global and spot removals"; shells mais fortes **Esper (WUB)**, depois Azorius e Dimir, em torno de Tivit, Elminster, Atraxa; Hidetsugu/Kairi como combo-control. **Pillowfort, stax, dreno e lifegain não aparecem em nenhum lugar do artigo** |
| [commanderspellbook](https://commanderspellbook.com) | Busca por "Eriette of the Charmed Apple": "No Combos Found — Your search didn't match any combos". Ela não é peça de combo |
| mtgdecks.net (página DC dedicada à Eriette) | **HTTP 403 nesta passada — UNVERIFIABLE.** Um pesquisador relatou 6 decklists, todas com "Event: Social media" e "Event Level: Not available" (nov/out 2024), ou seja, listas casuais submetidas pela comunidade, não resultados de torneio. **Não consegui confirmar** |
| mtgtop8, busca por comandante no formato EDH | O campo de busca não filtra por comandante nesse formato; **"zero resultados" é ausência de evidência, não ausência provada** |

**Veredito honesto: nenhum resultado competitivo documentado em Duel Commander até 02/10/2026**, e isso é "não encontrei", não "não existe".

## Legalidade dos adds em DC

Confirmados **commander: legal, duel: legal** [Scryfall]: Swords to Plowshares, Path to Exile, Fatal Push, Vindicate, Orzhov Signet, Mind Stone, Pacifism, Faith's Fetters, Prison Term, Reprobation, Minimus Containment, Dimensional Exile, Spirit Link, Soul Link, Vampiric Link, Hyena Umbra, Ethereal Armor, All That Glitters, Sphere of Safety, Ghostly Prison, Authority of the Consuls, Blind Obedience, Opposition Agent, Drannith Magistrate, Archon of Emeria, Thalia Guardian of Thraben, Vito, Sanguine Bond, Exquisite Blood.

**Banidas** ([banlist oficial](https://www.duelcommander.org/banlist/), fetch de 02/10/2026, mais flag do Scryfall):

- **Sol Ring** — está no 99 do precon; **tem que sair** em qualquer build 1v1.
- **Serra's Sanctum** — não adicione, por mais perfeita que pareça num deck WB de encantamento. (Também é **Game Changer** e custa $536+ [Scryfall].)
- **Flawless Maneuver** — não adicione.

Categorias completas da banlist: Banned as Companion (1: Lutri), Banned as Commander Only (27, inclui Edgar Markov, Raffine, Urza Lord High Artificer, Rograkh), Fully Banned in Deck (80, inclui Sol Ring, Mana Crypt, Ancient Tomb, todos os Moxen, Serra's Sanctum, Gaea's Cradle, Library of Alexandria), Banned for Offensive Content (7).

## Lista de trocas específica para DC

Partindo da build multiplayer da §3:

| Tira | Põe | Motivo |
|---|---|---|
| **Sol Ring** | Orzhov Signet ou Mind Stone | Banido [banlist] |
| **Breena, the Demagogue** | Path to Exile | O gatilho exige oponente atacando **outro** oponente — impossível com um oponente só [Scryfall] |
| **Combat Calligrapher** | Vindicate | Gatilho político, morto em 1v1 |
| **Secret Rendezvous** | Fatal Push | Dar carta ao único oponente em 1v1 é pior ainda |
| **Forum Filibuster / Mangara, the Diplomat** (se mantidos) | **Opposition Agent** | O meta é Esper/Azorius/Dimir + Atraxa 4c com vantagem de tutor ([Cardsrealm](https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame)); "you control your opponents while they're searching their libraries" taxa exatamente isso. Corpo 3/2 com flash também bloqueia. **É Game Changer** — irrelevante em DC (não há bracket), relevante se você reusar a lista em multiplayer |
| corte livre | **Drannith Magistrate** | "Opponents can't cast spells from anywhere other than their hands" contra recursão grindy e contra o shell combo-control Hidetsugu/Kairi. **Também Game Changer** |
| — | **não adicione Thalia, Guardian of Thraben** | Ela taxa **seus próprios 26-31 encantamentos** em {1}. A recomendação original de um dos pesquisadores se autocontradiz no meio da frase. Anti-sinergia clara |

**Mantém e vale mais em 1v1:** Killian, Decisive Mentor e os quatro Impetus — viram travamento total em vez de redirecionamento (ver regra acima). **Dimensional Exile** continua sendo remoção limpa + X.

## Teto honesto contra o meta 2026

As duas metades da Eriette se separam violentamente contra esse campo:

- **Metade Pacifism frequentemente morta.** Contra controle puro com 6-10 criaturas, não há o que travar, e o truque goad-como-Pacifism não tem alvo.
- **Metade dreno sempre viva.** X = total de Auras **suas**: mesmo num matchup em que você nunca toca uma criatura do oponente, o relógio tiquetaqueia com Ethereal Armor, Spirit Link, Hyena Umbra, até Dimensional Exile no seu próprio terreno. Essa é a parte que não depende do que o oponente faz.

## Eriette vs Killian para Duel Commander — recomendação

**Eriette, com a ressalva de que não é um deck conhecido no formato.** O argumento é mecânico, não estatístico: contra um campo denso em counterspell e remoção, o plano do Killian precisa que um atacante encantado conecte todo turno (removível, counterável, bloqueável), enquanto o dreno da Eriette não precisa de nada passar. Somando as rulings de goad — que em 1v1 convertem o próprio Killian e os quatro Impetus em travamento integral — **Killian rende mais como peça do 99 sob Eriette do que como comandante**. O contra-argumento é real: metade da carta dela fica sem função contra controle com 6-10 criaturas, e o primer de Brawl registra que o arquétipo **morre para agressão rápida** ([Sci-Fi Bloggers](https://scifibloggers.com/a-charming-deck-tech-with-eriette/)).

Teto realista: **deck de mesa casual/local forte, não um contender de top 8**. Nenhum dos dois tem resultado documentado, e nada no meta publicado sugere que o arquétipo esteja escondido esperando descoberta.

# 6. Pontos em aberto / contradições não resolvidas

1. **Texto do Killian, Decisive Mentor — resolvido.** Dois relatórios descreveram cada um só metade da carta. Oracle completo [Scryfall, 01/10/2026]: "Whenever an enchantment you control enters, tap up to one target creature and goad it. Whenever one or more creatures that are enchanted by an Aura you control attack, draw a card." Ou seja, **tem goad e tem saque**, e o saque dispara com criatura encantada atacando independente de quem a controla. Como carta do 99 sob Eriette, o saque continua ligado às Auras que você colar nas criaturas dos oponentes quando elas atacarem outros jogadores.
2. **Curva de dreno turno-a-turno: não existe fonte.** Qualquer "T5 = X=2, T7-8 = X=4-5, 12-15 por rodada em pod de 4" que você leu é modelagem de pesquisador, não cálculo citado — o artigo da norerolls.co.uk que foi apontado como fonte **não contém exemplo numérico**. A §1 só traz aritmética direta do oracle.
3. **Austere Command como ameaça específica a shells de Eriette: sem fonte.** O artigo citado é sobre **Eriette, the Beguiler** (WUB, OTJ 202 — carta diferente) e não menciona Austere Command, Farewell nem wrath de encantamento em nenhum momento. A única linha de mass removal lá é Winds of Rath como **ferramenta**. O argumento estratégico pode estar correto; não há citação.
4. **Idyllic Tutor NÃO está na lista média da EDHREC**, ao contrário do que um relatório afirmou. A recomendação se defende pelo mérito; a citação é falsa. Mesma situação com **Lurrus** ("está na base de criaturas da lista média") — a lista média só expõe contagens por tipo (18 criaturas), não os nomes.
5. **Conflação de percentuais.** "Swords to Plowshares aparece em 30,9% dos decks de Eriette" é **errado**: 30,9% é a taxa de **adição na conversão do precon**, não a inclusão geral. Mesmo risco em Danitha 33,6%, Light-Paws 30,9%, Kaya's Ghostform 31,9%. Os números são reais; a legenda deles mudou.
6. **Umbra Mystic foi lida errado na pesquisa original.** O oracle é "**Auras attached to permanents you control** have umbra armor" — não "todas as suas Auras". Auras que você colocou em criaturas dos oponentes não ganham nada. Isso muda o valor da carta o suficiente para tirá-la da tabela principal.
7. **Role tokens: a conclusão sobrevive, a evidência não.** "WB não tem ferramenta nativa de Role em criatura do oponente" continua valendo, mas a justificativa dada (Charming Scoundrel's "Cursed Role" podendo mirar qualquer criatura) é duplamente errada: o Role dele é **Wicked** e o texto é "attached to **target creature you control**". O único Role-granter irrestrito é **Twisted Fealty** (vermelho, fora de cor). Além disso, a conclusão foi incompleta: **Nurgle's Rot** e **Dead Man's Chest** leem "Enchant creature an opponent controls" — WB tem Auras **obrigatoriamente** no inimigo, só não via Role token.
8. **Scriv's Contract token: nenhuma ruling nomeia o token.** Que ele conte para o X da Eriette segue da regra geral de controle de token (controlador = criador), e é o mesmo princípio da ruling de 01/09/2023 da Eriette sobre Role tokens, mas não existe ruling citando "Contract". Confiança alta, citação direta ausente.
9. **Presença em Duel Commander é "não encontrei", não "não existe".** A busca por comandante do mtgtop8 não funciona no formato EDH; a mtgdecks.net (única fonte positiva de listas casuais DC) retorna 403 agora. O que foi verificado diretamente: top 8 do Czech DC Masters 2026 (sem Eriette), roundup de meta da Cardsrealm (sem o arquétipo), commanderspellbook (zero combos).
10. **Percentuais da EDHREC variam entre páginas — e isso não é drift.** Kaya's Ghostform é 69% na página do comandante e 66% na página pillow-fort (202/308); os dois números estão certos no contexto deles. Já o número agregado "2.198 decks / rank #84" que circulou é **cache velho** — o valor ao vivo é **19.107 / #86**.
11. **Swiftfoot Boots 32-35% e Lightning Greaves 15%** não foram reproduzidos em nenhuma das páginas verificadas. As cartas são boas; os percentuais são não verificados.
12. **O primer da Sci-Fi Bloggers é de MTGO Historic Brawl**, não Commander em papel. As observações mecânicas (dreno sobre combate, Aura sua em criatura roubada ainda travando o ataque) valem; as inclusões específicas (Necropotence, Phyrexian Arena, Halvar, Vito) precisam ser filtradas por singleton e orçamento.
13. **Preços são snapshots de 02/10/2026 e vão se mover.** Swords to Plowshares a $1,01 é a impressão **FRC lançada hoje**; Shattered Sanctum a $1,44 é promo PSOS 260p. Tudo acima de $5 (Ondu Spiritdancer, Retether, Greater Auramancy, Idyllic Tutor, Nurgle's Rot, Umbra Mystic, Vito) é onde a pressão de orçamento está num pacote que é, de resto, sub-US$1 por carta.
14. **Nomes a corrigir antes de qualquer export de decklist:** "With Great Power…" → **`With Great Power . . .`** (pontos espaçados); "Victor Valgavoth's Seneschal" → **`Victor, Valgavoth's Seneschal`** (vírgula).
15. **Primers não acessíveis nesta passada:** o deck guide da TCGplayer e os dois primers do Moxfield (u2YFouwSaUCtQL_FzOxXtA, R9A2GibMGUOszAI7e5sSWw) retornaram JS-gated/403, assim como as três listas "Duel Commander" de Eriette no Moxfield (Cloudflare 403). Callouts atribuídos a eles (Boromir Warden of the Tower, Call of the Ring) são **[Estimado]**, não leitura de fonte primária.
16. **Não foi encontrada nenhuma thread de r/EDH discutindo especificamente trocar Eriette no Silverquill Influence** — esse ângulo é coberto só pela página de comparação da própria EDHREC e pelo artigo da CoolStuffInc (que não trata dela como comandante alternativa).

# Fontes

- https://edhrec.com/precon/silverquill-influence
- https://edhrec.com/precon/silverquill-influence/eriette-of-the-charmed-apple
- https://edhrec.com/commanders/eriette-of-the-charmed-apple
- https://edhrec.com/commanders/eriette-of-the-charmed-apple/auras
- https://edhrec.com/commanders/eriette-of-the-charmed-apple/pillow-fort
- https://edhrec.com/commanders/eriette-of-the-charmed-apple/exhibition/control
- https://edhrec.com/average-decks/eriette-of-the-charmed-apple
- https://edhrec.com/average-decks/eriette-of-the-charmed-apple/optimized/curses
- https://edhrec.com/combos/eriette-of-the-charmed-apple
- https://edhrec.com/articles/commander-philosophy-2-card-combos-in-lower-brackets
- https://commanderbrackets.com/game-changers
- https://krakenthemeta.com/blog/mtg-commander-brackets/
- https://www.coolstuffinc.com/a/silverquill-influence-precon-upgrade-05142026
- https://cardgamebase.com/silverquill-influence-upgrade-guide/
- https://draftsim.com/eriette-edh-deck/
- https://mtg.cardsrealm.com/en-us/articles/commander-deck-tech-eriette-of-the-charmed-apple
- https://mtg.cardsrealm.com/en-us/articles/duel-commander-guide-control-metagame
- https://scifibloggers.com/a-charming-deck-tech-with-eriette/
- https://www.duelcommander.org/banlist/
- https://www.mtgtop8.com/event?e=91395&f=EDH
- https://mtgtop8.com/format?f=EDH
- https://commanderspellbook.com
- Texto de oracle, rulings, legalidade e preços: Scryfall, consultado em 02/10/2026 via `/home/kichelm/mtg/skills/scryfall-cartas/scripts/scryfall.py` (`carta`, `busca`, `edicoes`, `regras`) — marcado [Scryfall] no corpo do relatório
- Fontes consultadas e **não** utilizáveis nesta passada: https://mtgdecks.net/Duel-Commander/eriette-of-the-charmed-apple (HTTP 403); TCGplayer Eriette deck guide (JS-gated); Moxfield primers u2YFouwSaUCtQL_FzOxXtA e R9A2GibMGUOszAI7e5sSWw (403); https://norerolls.co.uk/2026/08/24/magic-monday-my-eriette-of-the-charmed-apple-deck/ (acessado, sem o conteúdo numérico que lhe foi atribuído); https://www.coolstuffinc.com/a/abesargent-05072024-budget-commander-77-controlling-with-auras-with-eriette (trata de **Eriette, the Beguiler**, carta diferente)