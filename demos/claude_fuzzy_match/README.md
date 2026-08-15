# Settling a misspelt name by asking

Puts one question to Claude under a name that answers to nothing, and watches it work
out what was meant without ever picking for you. The name is misspelt on purpose and
sits close to two different sorts of thing, so it cannot be settled by guessing. It
verifies nothing, and it talks to a real model on a credential of your own, so every run
costs whatever that credential is billed at, one question at a time.

## Setting up

One credential, for the model.

Create a **`.env` in this folder** (git-ignored) for the Anthropic credential:

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate it with `claude setup-token`, which uses your Claude subscription; an
`ANTHROPIC_API_KEY` in the same file works too and is billed per token.

A subscription token is not an api key: it goes in as a bearer token under the
`oauth-2025-04-20` beta, and that endpoint answers Claude Code, so it wants to be told
so in a system block of its own. This script sends `You are Claude Code, Anthropic's
official CLI for Claude.` as the first block and its own instructions as the second.
Fold the two together and the request is refused.

Then, from the repository root:

```bash
uv sync --all-extras
uv run poe build-artifact <documents>   # the questions here are written against it
```

The run prints the command it starts the wiki with and the knowledge base that wiki
read, so a run that answered from the wrong build is visible on its first line.

## Running it

```bash
uv run poe demo claude_fuzzy_match              # type the answers yourself
uv run poe demo claude_fuzzy_match --scripted   # answer with the built in choices
uv run poe demo claude_fuzzy_match --answer npc --answer "King Black Dragon"
uv run poe demo claude_fuzzy_match "who drops a dragon scimmitar?"
```
