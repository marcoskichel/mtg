# MTG Commander skills

A set of skills that teach an AI coding agent, such as [Codex](https://developers.openai.com/codex)
or [Claude Code](https://claude.com/claude-code), to help you build and tune
Magic: The Gathering Commander decks.

You talk to the agent in plain language ("find me cheap ramp for my Edgar Markov
deck", "how much does this list cost?", "build me an aristocrats deck") and it
uses these skills to look things up on real card databases. It does not answer
from memory: every card it suggests is checked against its official text on
[Scryfall](https://scryfall.com) first. When you need to choose between cards,
it opens a page in your browser with the card images so you can click the ones
you want.

Works on Windows, macOS and Linux.

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
Install all of them together.

## Installation

You need a terminal, Python, Node.js and an AI agent (Codex or Claude Code).
If you already have one of them, skip its step.

### 1. Open a terminal

- **Windows:** press the Windows key, type `PowerShell`, press Enter.
- **macOS:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Linux:** open your distribution's Terminal app.

Every command below is typed into this window, followed by Enter.

### 2. Install Python 3.10 or newer

The skills are small Python scripts. Check if you already have Python:

```bash
python3 --version
```

On Windows, type `python --version` instead. If it prints `Python 3.10` or
higher, move on. Otherwise:

- **Windows:** run `winget install Python.Python.3.13`, or download the
  installer from [python.org/downloads](https://www.python.org/downloads/)
  and tick **"Add python.exe to PATH"** on the first screen.
- **macOS:** download the installer from [python.org/downloads](https://www.python.org/downloads/).
- **Ubuntu / Debian:** `sudo apt install python3`

Close the terminal and open a new one after installing, then check again.
Nothing else needs to be installed with `pip`: the scripts use only Python's
standard library.

### 3. Install Node.js

Node.js gives you the `npx` command, which installs the skills. Check:

```bash
npx --version
```

If you see a version number, move on. Otherwise:

- **Windows:** run `winget install OpenJS.NodeJS.LTS`, or download the LTS
  installer from [nodejs.org](https://nodejs.org).
- **macOS:** download the LTS installer from [nodejs.org](https://nodejs.org).
- **Ubuntu / Debian:** `sudo apt install nodejs npm`

Close and reopen the terminal after installing.

### 4. Install an AI agent

Pick one. Both work with these skills.

**Codex** (needs a ChatGPT account or an OpenAI API key):

```bash
npm install -g @openai/codex
```

**Claude Code** (needs a Claude Pro, Max, Team or Enterprise plan, or an
Anthropic API key):

```bash
# macOS / Linux
curl -fsSL https://claude.ai/install.sh | bash
```

```powershell
# Windows (PowerShell)
irm https://claude.ai/install.ps1 | iex
```

Check it worked with `codex --version` or `claude --version`. If the command
is not found, close the terminal, open a new one and try again.

### 5. Install the skills

```bash
npx skills add marcoskichel/mtg --skill '*' -g
```

- `--skill '*'` installs all eight skills. They depend on each other.
- `-g` installs them for your user, so they work in any folder.

The installer asks which agents to install to. Use the arrow keys and the
space bar to select Codex, Claude Code or both, then press Enter.

### 6. Make a folder for your decks and start the agent

```bash
mkdir mtg-decks
cd mtg-decks
codex      # or: claude
```

The first time, the agent asks you to log in and to trust the folder. Say yes.
Always start the agent from this folder: the skills save your decks in a
`decks/` folder inside it.

### 7. Try it

Type a request, for example:

```text
What does Sol Ring do, and is it legal in Commander?
```

The agent should use the `scryfall-cards` skill and answer with the card's
real text. Then try something bigger:

```text
Find me 5 cheap ramp cards for a Golgari deck and let me pick
```

A browser tab opens with the cards. Click the ones you want and confirm.

### Optional: write decks to Moxfield (Claude Code only)

Reading a Moxfield deck works with any agent. To create or update decks on
your Moxfield account, Claude Code needs to control your browser:

1. Install the [Claude in Chrome](https://claude.com/chrome) extension.
2. In the extension settings, allow `moxfield.com`.
3. Log in to Moxfield in Chrome.

## Your decks

The agent keeps decklists in the `decks/` folder as plain text, one card per
line (`1 Sol Ring`). You can also drop your own lists there: exports from
Moxfield, Arena and most deck sites work.

## Updating and removing

```bash
npx skills update -g     # get the latest version
npx skills remove -g     # pick skills to uninstall
```

## Troubleshooting

- **`python3` not found on Windows:** that's normal. The agent falls back to
  `python` or `py`. If neither works, reinstall Python and tick "Add python.exe
  to PATH".
- **The agent doesn't use the skills:** check they are installed with
  `npx skills list -g`, then restart the agent.
- **The picker page doesn't open:** open the address the agent prints in your
  browser yourself.

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
