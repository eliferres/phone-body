# Contributing

Welcome things:

- New body adapters (a Discord body, an SMS body) that keep the contract: own
  credentials, a path to the brain, nothing else.
- A rules-enforcement layer inside `handle()`, with tests: the biggest honest
  gap in the skeleton.
- Fixes to anything the README or `docs/architecture.md` claims that turns out
  not to be true.

Ground rules: the skeleton stays stdlib-only, the brain stays plain Markdown in
the [agent-memory-vault](https://github.com/eliferres/agent-memory-vault) format,
and every change keeps `python3 -m unittest discover -s tests` green. No
credentials, hostnames or personal paths in any file, including examples.
Architectural proposals belong in an issue before a PR; the pattern here is
deliberately small, and most feature ideas are better as forks.
