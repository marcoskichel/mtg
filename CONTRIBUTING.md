# Contributing

Thanks for helping. Bug reports, new skills and fixes are all welcome.

## Reporting a bug or idea

Open an [issue](https://github.com/marcoskichel/mtg/issues) with:

- what you asked the agent,
- what it did,
- what you expected instead.

If a script failed, paste the command and its full error output.

## Setting up

Follow the [installation steps](README.md#installation), then work from the
repository root. Nothing else to install: the scripts use only Python's
standard library.

## Project layout

```text
skills/<name>/
  SKILL.md       instructions the agent reads (YAML frontmatter + body)
  scripts/       Python scripts the skill runs
  tests/         unittest tests for those scripts
  references/    longer docs the agent reads on demand (optional)
  assets/        static files, such as HTML pages (optional)
.claude/skills   symlink to skills/, so Claude Code finds them
AGENTS.md        rules every agent follows in this repo
```

## Running the tests

Each skill with scripts has its own tests. Run one skill's tests:

```bash
cd skills/scryfall-cards
python3 -m unittest discover -s tests
```

Run all of them from the repository root:

```bash
for d in skills/*/tests; do (cd "${d%/tests}" && python3 -m unittest discover -s tests) || exit 1; done
```

Tests must not hit the network. Mock HTTP calls the way the existing tests do.

## Rules for code

- **Standard library only.** No `pip` dependencies, so a fresh Python install
  is enough to run everything.
- **Card text comes from the API, never from memory.** Skills fetch every card
  they reason about (see [AGENTS.md](AGENTS.md)).
- **Paths start at the repository root** in `SKILL.md` examples, for example
  `python3 skills/card-picker/scripts/picker.py`.
- **Be gentle with the data sources.** Keep request rates low and cache what
  you can. Scryfall asks for 50–100 ms between requests.
- **One job per skill.** If a skill needs another skill's data, call that
  skill's script instead of copying its logic.

## Writing or changing a skill

- The `description` in the frontmatter decides when the agent uses the skill.
  Write it as the requests a user would actually type.
- Keep `SKILL.md` short and move long reference material into `references/`.
- Test the skill by hand in Claude Code with a few real requests, and say in
  the pull request what you tried.

## Pull requests

1. Fork the repo and create a branch: `feat/<short-name>` or `fix/<short-name>`.
2. Make your change and run the tests.
3. Use [Conventional Commits](https://www.conventionalcommits.org) for the
   title, lowercase, no period: `feat(card-finder): add tribal search`.
4. Open the pull request against `main` and describe what changed and why.

Pull requests are squash-merged.

## License

By contributing, you agree your contribution is licensed under the
[MIT License](LICENSE).
