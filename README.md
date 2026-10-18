# MTG Commander skills

A set of skills that teach an AI coding agent ([Claude Code](https://claude.com/claude-code))
to help you build and tune Magic: The Gathering Commander decks.

You talk to the agent in plain language ("find me cheap ramp for my Edgar Markov
deck", "how much does this list cost?", "build me an aristocrats deck") and it
uses these skills to look things up on real card databases. It does not answer
from memory: every card it suggests is checked against its official text on
[Scryfall](https://scryfall.com) first. When you need to choose between cards,
it opens a page in your browser with the card images so you can click the ones
you want.

## What each skill does

| Skill | What it does | Example request |
| --- | --- | --- |
| `scryfall-cards` | Reads card text, cost, type, legality, printings and rulings from Scryfall. Understands Portuguese card names. | "What does Brash Taunter do?" |
| `card-finder` | Finds cards by what they do (ramp, removal, card draw...), checks each one against its real text, and lists the roles cards play in a deck. | "Board wipes that spare my creatures in Orzhov" |
| `edhrec` | Reads Commander popularity data from [EDHREC](https://edhrec.com): how often a card is played, salt score, power bracket, themes, partner pairings. | "How popular is Blood Artist?" |
| `score-card` | Grades a card on its own or for a specific deck, with a reason for each grade, and ranks a list of candidates. | "Should I play Zulaport Cutthroat in my deck?" |
| `card-picker` | Opens a browser page with card images and the agent's reason for each one. You pick, and your choice goes back to the agent. | "Show me the options and let me pick" |
| `deck-builder` | Builds a full 100-card Commander deck in rounds: the agent gathers candidates per role and you pick in `card-picker`. | "Build me an Edgar Markov deck" |
| `moxfield-deck` | Keeps your decklist in a local file, checks it is legal, and syncs it with [Moxfield](https://moxfield.com). | "Upload this deck to Moxfield" |
| `ligamagic-preco` | Prices cards and whole decks in Brazilian reais (BRL) using [LigaMagic](https://www.ligamagic.com.br). Its instructions are in Portuguese. | "Quanto custa esse deck?" |

The skills call each other. For example, `deck-builder` uses `card-finder` to
find candidates, `score-card` to rank them and `card-picker` to let you choose.

## Installation

You need four things: a terminal, Git, Python and Claude Code. If you already
have one of them, skip its step.

> **Windows users:** use [WSL](https://learn.microsoft.com/windows/wsl/install)
> (Windows Subsystem for Linux) and follow the Linux steps inside it. The repo
> uses a symbolic link that plain Windows Git does not create by default.

### 1. Open a terminal

- **macOS:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Linux:** open your distribution's Terminal app.
- **Windows:** open the Ubuntu (WSL) app.

Every command below is typed into this window, followed by Enter.

### 2. Install Git

Check if you already have it:

```bash
git --version
```

If you see a version number, move on. Otherwise:

- **macOS:** run `xcode-select --install` and accept the prompt.
- **Ubuntu / Debian / WSL:** `sudo apt update && sudo apt install git`
- **Other systems:** see [git-scm.com/downloads](https://git-scm.com/downloads).

### 3. Install Python 3.10 or newer

Check:

```bash
python3 --version
```

If it prints `Python 3.10` or higher, move on. Otherwise:

- **macOS:** download the installer from [python.org/downloads](https://www.python.org/downloads/).
- **Ubuntu / Debian / WSL:** `sudo apt install python3`

The skills only use Python's standard library, so there is nothing else to
install with `pip`.

### 4. Install Claude Code

Claude Code is the AI agent that runs the skills. You need a Claude account
(Pro, Max, Team or Enterprise plan) or an Anthropic API key.

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Then check it worked:

```bash
claude --version
```

If the command is not found, close the terminal, open a new one and try again.
More options are in the [Claude Code setup guide](https://docs.claude.com/en/docs/claude-code/setup).

### 5. Download this repository

```bash
git clone https://github.com/marcoskichel/mtg.git
cd mtg
```

### 6. Start Claude Code inside the folder

```bash
claude
```

The first time, it asks you to log in and to trust the folder. Say yes.

That's it: the skills are already installed. Claude Code loads them from the
`.claude/skills` folder of this repository whenever you start it from here.
Always start `claude` from inside the `mtg` folder, because the skills run
their scripts from there.

### 7. Try it

Type a request, for example:

```text
What does Sol Ring do, and is it legal in Commander?
```

Claude should run the `scryfall-cards` skill and answer with the card's
real text. Then try something bigger:

```text
Find me 5 cheap ramp cards for a Golgari deck and let me pick
```

A browser tab opens with the cards. Click the ones you want and confirm.

### Optional: write decks to Moxfield

Reading a Moxfield deck works out of the box. To create or update decks on
your Moxfield account, Claude needs to control your browser:

1. Install the [Claude in Chrome](https://claude.com/chrome) extension.
2. In the extension settings, allow `moxfield.com`.
3. Log in to Moxfield in Chrome.

## Your decks

Put decklists in the `decks/` folder as plain text, one card per line
(`1 Sol Ring`). Exports from Moxfield, Arena and most deck sites work. The
folder is ignored by Git, so your decks stay on your computer.

## Updating

From inside the `mtg` folder:

```bash
git pull
```

## Using another agent

Each folder under `skills/` is a standard Agent Skill: a `SKILL.md` file with
instructions plus Python scripts. Agents that read `AGENTS.md` and support
skills can use them too, but they are only tested with Claude Code.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License and legal

Code under the [MIT License](LICENSE).

This project is unofficial Fan Content permitted under the
[Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
Not approved or endorsed by Wizards. Portions of the materials used are
property of Wizards of the Coast. ©Wizards of the Coast LLC.

Card data comes from Scryfall, EDHREC, Moxfield and LigaMagic. This project is
not affiliated with any of them. Please use it at a personal pace and respect
each site's terms.
